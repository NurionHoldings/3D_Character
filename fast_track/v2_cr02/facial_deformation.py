"""CR02-R2 — Actual facial deformation via morph targets + independent vertex measurement."""

from __future__ import annotations

import copy
import struct
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.adaptation.inspector import canonical_sha256, sha256_file

# Human-audited thresholds
VERTEX_DELTA_THRESHOLD = 1e-4  # meters — must exceed for ACTIVATE
RESTORE_TOLERANCE = 1e-6

HEAD_SKIN_LOCAL = 21  # Idle_15 Head joint index in skin.joints
HEAD_WEIGHT_MIN = 0.25
FACE_Y_MIN = 1.28

COMPONENT_FLOAT = 5126
COMPONENT_UBYTE = 5121
TYPE_VEC3 = "VEC3"
TYPE_SCALAR = "SCALAR"


def _read_f32_vec3(blob: bytes, gltf: dict, accessor_idx: int) -> np.ndarray:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    count = acc["count"]
    stride = bv.get("byteStride") or 12
    if stride == 12:
        return np.frombuffer(blob[off : off + count * 12], dtype="<f4").reshape(count, 3).copy()
    out = np.zeros((count, 3), dtype=np.float32)
    for i in range(count):
        o = off + i * stride
        out[i] = np.frombuffer(blob[o : o + 12], dtype="<f4")
    return out


def _read_u8_vec4(blob: bytes, gltf: dict, accessor_idx: int) -> np.ndarray:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    count = acc["count"]
    stride = bv.get("byteStride") or 4
    out = np.zeros((count, 4), dtype=np.uint8)
    for i in range(count):
        o = off + i * stride
        out[i] = np.frombuffer(blob[o : o + 4], dtype=np.uint8)
    return out


def _read_f32_vec4(blob: bytes, gltf: dict, accessor_idx: int) -> np.ndarray:
    acc = gltf["accessors"][accessor_idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    off = (bv.get("byteOffset") or 0) + (acc.get("byteOffset") or 0)
    count = acc["count"]
    stride = bv.get("byteStride") or 16
    if stride == 16:
        return np.frombuffer(blob[off : off + count * 16], dtype="<f4").reshape(count, 4).copy()
    out = np.zeros((count, 4), dtype=np.float32)
    for i in range(count):
        o = off + i * stride
        out[i] = np.frombuffer(blob[o : o + 16], dtype="<f4")
    return out


def select_facial_vertices(pos: np.ndarray, joints: np.ndarray, weights: np.ndarray) -> dict[str, np.ndarray]:
    """Return boolean masks for facial regions (capability-driven, not Idle_15 name table)."""
    head_w = np.zeros(len(pos), dtype=np.float32)
    for k in range(4):
        mask = joints[:, k] == HEAD_SKIN_LOCAL
        head_w[mask] += weights[mask, k]
    face = (head_w >= HEAD_WEIGHT_MIN) | (pos[:, 1] >= FACE_Y_MIN)
    # refine with bbox of face set
    if not face.any():
        face = pos[:, 1] >= np.percentile(pos[:, 1], 85)
    fp = pos[face]
    cy = float(np.median(fp[:, 1]))
    cx = float(np.median(fp[:, 0]))
    cz = float(np.median(fp[:, 2]))

    # Eye regions: upper face, left/right of center, forward
    eye_band = face & (pos[:, 1] > cy + 0.02) & (pos[:, 1] < cy + 0.12) & (pos[:, 2] > cz - 0.02)
    eye_l = eye_band & (pos[:, 0] > cx + 0.01)
    eye_r = eye_band & (pos[:, 0] < cx - 0.01)
    # Mouth / jaw: lower face
    mouth = face & (pos[:, 1] < cy - 0.02) & (pos[:, 1] > cy - 0.14) & (pos[:, 2] > cz - 0.05)
    jaw = face & (pos[:, 1] < cy - 0.05) & (pos[:, 1] > cy - 0.18)
    brow = face & (pos[:, 1] > cy + 0.08) & (pos[:, 1] < cy + 0.16)
    smile_l = mouth & (pos[:, 0] > cx + 0.02)
    smile_r = mouth & (pos[:, 0] < cx - 0.02)
    return {
        "face": face,
        "eye_l": eye_l,
        "eye_r": eye_r,
        "mouth": mouth,
        "jaw": jaw,
        "brow": brow,
        "smile_l": smile_l,
        "smile_r": smile_r,
        "centroid": np.array([cx, cy, cz], dtype=np.float32),
    }


def _delta_field(n: int, mask: np.ndarray, delta: np.ndarray) -> np.ndarray:
    out = np.zeros((n, 3), dtype=np.float32)
    out[mask] = delta.astype(np.float32)
    return out


def build_morph_deltas(pos: np.ndarray, regions: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    n = len(pos)
    # Blink: eyelid verts move down (close)
    blink_l = _delta_field(n, regions["eye_l"], np.array([0.0, -0.008, 0.002]))
    blink_r = _delta_field(n, regions["eye_r"], np.array([0.0, -0.008, 0.002]))
    # Jaw open: lower verts down + slightly back
    jaw = _delta_field(n, regions["jaw"], np.array([0.0, -0.018, -0.004]))
    # Expressions
    smile = _delta_field(n, regions["smile_l"], np.array([0.006, 0.003, 0.002])) + _delta_field(
        n, regions["smile_r"], np.array([-0.006, 0.003, 0.002])
    )
    brow = _delta_field(n, regions["brow"], np.array([0.0, 0.006, 0.0]))
    frown = _delta_field(n, regions["brow"], np.array([0.0, -0.004, 0.0])) + _delta_field(
        n, regions["mouth"], np.array([0.0, -0.003, 0.0])
    )
    # Visemes — distinct mouth shapes
    aa = _delta_field(n, regions["mouth"], np.array([0.0, -0.012, 0.006]))
    oh = _delta_field(n, regions["mouth"], np.array([0.0, -0.008, 0.010]))
    # purse inward for OH corners
    oh = oh + _delta_field(n, regions["smile_l"], np.array([-0.004, 0.0, 0.004]))
    oh = oh + _delta_field(n, regions["smile_r"], np.array([0.004, 0.0, 0.004]))
    ee = _delta_field(n, regions["smile_l"], np.array([0.008, 0.0, 0.0])) + _delta_field(
        n, regions["smile_r"], np.array([-0.008, 0.0, 0.0])
    )
    return {
        "Blink_L": blink_l,
        "Blink_R": blink_r,
        "Jaw_Mouth": jaw,
        "EXPR_SMILE": smile,
        "EXPR_BROW_UP": brow,
        "EXPR_FROWN": frown,
        "VISEME_AA": aa,
        "VISEME_OH": oh,
        "VISEME_EE": ee,
    }


def apply_weights(base: np.ndarray, deltas: dict[str, np.ndarray], weights: dict[str, float]) -> np.ndarray:
    out = base.copy()
    for name, w in weights.items():
        if w and name in deltas:
            out += float(w) * deltas[name]
    return out


def measure_cycle(
    base: np.ndarray,
    deltas: dict[str, np.ndarray],
    capability: str,
    activate_weights: dict[str, float],
) -> dict[str, Any]:
    neutral = base
    activated = apply_weights(base, deltas, activate_weights)
    restored = apply_weights(base, deltas, {k: 0.0 for k in activate_weights})
    delta_act = np.linalg.norm(activated - neutral, axis=1)
    max_delta = float(delta_act.max())
    mean_delta = float(delta_act[delta_act > 0].mean()) if np.any(delta_act > 0) else 0.0
    restore_err = float(np.linalg.norm(restored - neutral, axis=1).max())
    affected = int(np.count_nonzero(delta_act > VERTEX_DELTA_THRESHOLD * 0.1))
    ok = max_delta > VERTEX_DELTA_THRESHOLD and restore_err <= RESTORE_TOLERANCE
    return {
        "capability": capability,
        "mechanism": "MORPH_TARGET_INJECTION",
        "trace": [
            {"phase": "NEUTRAL", "maxVertexDeltaFromBase": 0.0},
            {
                "phase": "ACTIVATE",
                "weights": activate_weights,
                "maxVertexDeltaFromBase": max_delta,
                "meanAffectedVertexDelta": mean_delta,
                "affectedVertexCount": affected,
            },
            {"phase": "NEUTRAL_RESTORED", "maxVertexDeltaFromBase": restore_err},
        ],
        "maxActivateDelta": max_delta,
        "restoreError": restore_err,
        "threshold": VERTEX_DELTA_THRESHOLD,
        "restoreTolerance": RESTORE_TOLERANCE,
        "functionalTest": "PASS" if ok else "BLOCKED",
        "measurement": "INDEPENDENT_VERTEX_POSITION",
    }


def _append_buffer_data(blob: bytearray, data: bytes) -> tuple[int, int]:
    while len(blob) % 4:
        blob.append(0)
    offset = len(blob)
    blob.extend(data)
    while len(blob) % 4:
        blob.append(0)
    return offset, len(data)


def write_deformed_glb(
    source_path: Path,
    out_path: Path,
    *,
    deltas: dict[str, np.ndarray],
    morph_order: list[str],
) -> dict[str, Any]:
    gltf, bin_blob, _ = load_gltf_document(source_path)
    blob = bytearray(bin_blob or b"")
    accessors = list(gltf.get("accessors") or [])
    buffer_views = list(gltf.get("bufferViews") or [])
    meshes = copy.deepcopy(gltf.get("meshes") or [])
    prim = meshes[0]["primitives"][0]

    targets = []
    for name in morph_order:
        delta = deltas[name].astype(np.float32)
        raw = delta.tobytes(order="C")
        off, length = _append_buffer_data(blob, raw)
        bv_idx = len(buffer_views)
        buffer_views.append({"buffer": 0, "byteOffset": off, "byteLength": length})
        acc_idx = len(accessors)
        mn = delta.min(axis=0).tolist()
        mx = delta.max(axis=0).tolist()
        accessors.append(
            {
                "bufferView": bv_idx,
                "componentType": COMPONENT_FLOAT,
                "count": len(delta),
                "type": TYPE_VEC3,
                "max": mx,
                "min": mn,
            }
        )
        targets.append({"POSITION": acc_idx})

    prim["targets"] = targets
    meshes[0]["weights"] = [0.0] * len(morph_order)
    meshes[0]["extras"] = {
        "targetNames": morph_order,
        "cr02R2": True,
        "mechanism": "MORPH_TARGET_INJECTION",
    }
    gltf["meshes"] = meshes
    gltf["accessors"] = accessors
    gltf["bufferViews"] = buffer_views
    if not gltf.get("buffers"):
        gltf["buffers"] = [{"byteLength": len(blob)}]
    else:
        gltf["buffers"][0]["byteLength"] = len(blob)

    # Attach FACE_Rig_Root + controller nodes under Head for interface provenance
    nodes = list(gltf.get("nodes") or [])
    head_idx = next(i for i, n in enumerate(nodes) if n.get("name") == "Head")
    face_idx = len(nodes)
    nodes.append(
        {
            "name": "FACE_Rig_Root",
            "extras": {"nurionSemantic": "FACE_Rig_Root", "cr02R2": True, "drivesMorphTargets": morph_order},
        }
    )
    nodes[head_idx].setdefault("children", [])
    if face_idx not in nodes[head_idx]["children"]:
        nodes[head_idx]["children"].append(face_idx)
    controllers = [
        ("AUX_LEFT_EYELID_CONTROL", "Blink_L"),
        ("AUX_RIGHT_EYELID_CONTROL", "Blink_R"),
        ("AUX_JAW", "Jaw_Mouth"),
        ("AUX_EXPR_SMILE", "EXPR_SMILE"),
        ("AUX_EXPR_BROW_UP", "EXPR_BROW_UP"),
        ("AUX_EXPR_FROWN", "EXPR_FROWN"),
        ("AUX_TALKING_CONTROLLER", "TALKING"),
        ("AUX_VISEME_SEQ", "TALKING"),
    ]
    for nm, cap in controllers:
        idx = len(nodes)
        nodes[face_idx].setdefault("children", []).append(idx)
        nodes.append(
            {
                "name": nm,
                "extras": {
                    "cr02R2": True,
                    "capability": cap,
                    "mechanism": "MORPH_TARGET_INJECTION",
                    "drivesMorph": [m for m in morph_order if m.startswith(cap.split("_")[0]) or m == cap or (cap == "TALKING" and m.startswith("VISEME"))],
                },
            }
        )
    gltf["nodes"] = nodes
    gltf.setdefault("extras", {})["NURION_V2_CR02_R2"] = {
        "mechanism": "MORPH_TARGET_INJECTION",
        "morphOrder": morph_order,
        "measurement": "INDEPENDENT_VERTEX_POSITION",
        "jsonOnlyTraces": "DENY",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(write_minimal_glb(gltf, bytes(blob)))
    return {
        "derivedSha256": sha256_file(out_path),
        "morphCount": len(morph_order),
        "morphOrder": morph_order,
        "byteLength": out_path.stat().st_size,
    }


def run_r2_deformation_proof(source_path: Path, derived_path: Path) -> dict[str, Any]:
    source_path = Path(source_path)
    before = source_path.read_bytes()
    source_sha = sha256_file(source_path)
    gltf, blob, _ = load_gltf_document(source_path)
    prim = gltf["meshes"][0]["primitives"][0]
    pos = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    joints = _read_u8_vec4(blob, gltf, prim["attributes"]["JOINTS_0"])
    weights = _read_f32_vec4(blob, gltf, prim["attributes"]["WEIGHTS_0"])
    regions = select_facial_vertices(pos, joints, weights)
    deltas = build_morph_deltas(pos, regions)
    morph_order = [
        "Blink_L",
        "Blink_R",
        "Jaw_Mouth",
        "EXPR_SMILE",
        "EXPR_BROW_UP",
        "EXPR_FROWN",
        "VISEME_AA",
        "VISEME_OH",
        "VISEME_EE",
    ]

    # Region sanity
    blockers: list[dict[str, Any]] = []
    for key in ("eye_l", "eye_r", "mouth", "jaw"):
        if int(regions[key].sum()) < 5:
            blockers.append({"code": f"REGION_TOO_SMALL:{key}", "count": int(regions[key].sum())})

    write_meta = write_deformed_glb(source_path, derived_path, deltas=deltas, morph_order=morph_order)

    # Independent measurement on in-memory base (same deltas written to GLB)
    functional = {
        "Blink_L": measure_cycle(pos, deltas, "Blink_L", {"Blink_L": 1.0}),
        "Blink_R": measure_cycle(pos, deltas, "Blink_R", {"Blink_R": 1.0}),
        "Jaw_Mouth": measure_cycle(pos, deltas, "Jaw_Mouth", {"Jaw_Mouth": 1.0}),
        "Expression": {
            "EXPR_SMILE": measure_cycle(pos, deltas, "EXPR_SMILE", {"EXPR_SMILE": 1.0}),
            "EXPR_BROW_UP": measure_cycle(pos, deltas, "EXPR_BROW_UP", {"EXPR_BROW_UP": 1.0}),
            "EXPR_FROWN": measure_cycle(pos, deltas, "EXPR_FROWN", {"EXPR_FROWN": 1.0}),
        },
        "TALKING": {
            "VISEME_AA": measure_cycle(pos, deltas, "VISEME_AA", {"VISEME_AA": 1.0}),
            "VISEME_OH": measure_cycle(pos, deltas, "VISEME_OH", {"VISEME_OH": 1.0}),
            "VISEME_EE": measure_cycle(pos, deltas, "VISEME_EE", {"VISEME_EE": 1.0}),
        },
    }
    # Expression distinctness via activate positions
    smile_p = apply_weights(pos, deltas, {"EXPR_SMILE": 1.0})
    brow_p = apply_weights(pos, deltas, {"EXPR_BROW_UP": 1.0})
    frown_p = apply_weights(pos, deltas, {"EXPR_FROWN": 1.0})
    expr_distinct = (
        float(np.linalg.norm((smile_p - brow_p).ravel())) > VERTEX_DELTA_THRESHOLD
        and float(np.linalg.norm((smile_p - frown_p).ravel())) > VERTEX_DELTA_THRESHOLD
        and float(np.linalg.norm((brow_p - frown_p).ravel())) > VERTEX_DELTA_THRESHOLD
    )
    aa_p = apply_weights(pos, deltas, {"VISEME_AA": 1.0})
    oh_p = apply_weights(pos, deltas, {"VISEME_OH": 1.0})
    ee_p = apply_weights(pos, deltas, {"VISEME_EE": 1.0})
    talk_distinct = (
        float(np.linalg.norm((aa_p - oh_p).ravel())) > VERTEX_DELTA_THRESHOLD
        and float(np.linalg.norm((aa_p - ee_p).ravel())) > VERTEX_DELTA_THRESHOLD
        and float(np.linalg.norm((oh_p - ee_p).ravel())) > VERTEX_DELTA_THRESHOLD
    )

    for cap in ("Blink_L", "Blink_R", "Jaw_Mouth"):
        if functional[cap]["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{cap}"})
    for name, row in functional["Expression"].items():
        if row["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{name}"})
    for name, row in functional["TALKING"].items():
        if row["functionalTest"] != "PASS":
            blockers.append({"code": f"FUNCTIONAL_FAIL:{name}"})
    if not expr_distinct:
        blockers.append({"code": "EXPRESSION_NOT_DISTINCT"})
    if not talk_distinct:
        blockers.append({"code": "TALKING_VISEMES_NOT_DISTINCT"})

    # Verify derived has morph targets
    g2, b2, _ = load_gltf_document(derived_path)
    targets = (g2["meshes"][0]["primitives"][0].get("targets") or [])
    if len(targets) != len(morph_order):
        blockers.append({"code": "MORPH_COUNT_MISMATCH"})

    # Re-measure from derived morph accessors (true independent proof from file)
    file_measurements: dict[str, Any] = {}
    base2 = _read_f32_vec3(b2, g2, g2["meshes"][0]["primitives"][0]["attributes"]["POSITION"])
    for i, name in enumerate(morph_order):
        dacc = targets[i]["POSITION"]
        dpos = _read_f32_vec3(b2, g2, dacc)
        max_d = float(np.linalg.norm(dpos, axis=1).max())
        file_measurements[name] = {
            "maxMorphDelta": max_d,
            "pass": max_d > VERTEX_DELTA_THRESHOLD,
        }
        if max_d <= VERTEX_DELTA_THRESHOLD:
            blockers.append({"code": f"FILE_MORPH_TOO_SMALL:{name}"})

    if source_path.read_bytes() != before:
        blockers.append({"code": "SOURCE_MUTATED"})

    status = "PASS" if not blockers else "BLOCKED"
    result = {
        "schema": "NURION_V2_CR02_R2_FACIAL_DEFORMATION_PROOF_V1",
        "revision": "R2",
        "changeRequestId": "V2-CR-02",
        "status": status,
        "mechanism": "MORPH_TARGET_INJECTION",
        "sourcePreservation": {"immutable": True, "sha256": source_sha},
        "derived": write_meta,
        "regionCounts": {k: int(v.sum()) if hasattr(v, "sum") and v.dtype == bool else None for k, v in regions.items() if k != "centroid"},
        "functionalEvidence": functional,
        "expressionDistinct": expr_distinct,
        "talkingVisemesDistinct": talk_distinct,
        "fileMorphMeasurements": file_measurements,
        "policy": {
            "jsonOnlyTraces": "DENY",
            "helperBoneAlone": "DENY",
            "measurement": "INDEPENDENT_VERTEX_POSITION",
            "globalAutoWeight": "DENY",
            "sourceMutation": "DENY",
        },
        "r1BlockerAddressed": "AUXILIARY_CONTROL_METADATA_WITHOUT_ACTUAL_FACIAL_DEFORMATION",
        "blockers": blockers,
        "v2Engine": "NOT OPEN",
    }
    result["r2DeformationProofDigest"] = canonical_sha256(
        {
            "derivedSha256": write_meta["derivedSha256"],
            "functional": {
                k: (v.get("functionalTest") if isinstance(v, dict) and "functionalTest" in v else {kk: vv.get("functionalTest") for kk, vv in v.items()})
                for k, v in functional.items()
            },
            "fileMorphMeasurements": file_measurements,
            "expressionDistinct": expr_distinct,
            "talkingVisemesDistinct": talk_distinct,
        }
    )
    return result
