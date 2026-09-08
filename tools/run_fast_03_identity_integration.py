#!/usr/bin/env python3
"""FAST-03 Identity Integration — 03A separation, 03B Path-A proof, 03C gate (STOP)."""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import importlib.util
import json
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(r"d:\NURION Character Landmarker")
FAST02 = ROOT / "tools" / "fast_02_semantic_partition_audit.py"
IDENTITY_SKIN = (
    ROOT
    / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
    / "candidate_a_makehuman_hm08/derived_v1_basis_nd/NURION_DerivedHead_v1_basis_skin.obj"
)

REGIONS = (
    "BODY",
    "CLOTHING_ACCESSORY",
    "HAIR",
    "HEAD_SKIN",
    "FACE_IDENTITY_REGION",
    "NECK_TRANSITION",
)

# Path-A feasibility thresholds (proof gate — evidence-tuned, conservative)
MIN_FACE_VERTS = 180
MAX_DISP_EDGE_RATIO = 2.75
MAX_LANDMARK_ERROR_HEAD_FRAC = 0.18
MIN_IDENTITY_COVERAGE = 0.62


def load_fast02():
    spec = importlib.util.spec_from_file_location("fast_02", FAST02)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def parse_obj_verts(path: Path) -> np.ndarray:
    verts: list[list[float]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            p = line.split()
            verts.append([float(p[1]), float(p[2]), float(p[3])])
    return np.asarray(verts, np.float64)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_bone_role(name: str) -> str:
    lower = name.lower()
    if any(x in lower for x in ("head", "skull")) and "end" not in lower and "front" not in lower:
        return "head"
    if "neck" in lower:
        return "neck"
    return "body"


def dominant_role(weights: np.ndarray, joints: np.ndarray, roles: dict[int, str]) -> str:
    order = np.argsort(-weights)
    for idx in order:
        if weights[idx] <= 0:
            break
        role = roles.get(int(joints[idx]), "body")
        if role in ("head",):
            return "head"
        if role == "neck":
            return "neck"
    return "body"


def build_mesh_data(f2, glb_path: Path) -> dict[str, Any]:
    gltf, bin_blob = f2.load_glb(glb_path)
    nodes = gltf["nodes"]
    skins = gltf["skins"]
    skin = skins[0]
    joint_nodes = skin["joints"]
    joint_names = [nodes[j].get("name", f"j{j}") for j in joint_nodes]
    roles = {i: classify_bone_role(n) for i, n in enumerate(joint_names)}

    head_ji = next(i for i, n in enumerate(joint_names) if roles[i] == "head")
    neck_ji = next(i for i, n in enumerate(joint_names) if roles[i] == "neck")
    headfront_ji = next(
        (i for i, n in enumerate(joint_names) if "headfront" in n.lower()),
        head_ji,
    )

    mesh = gltf["meshes"][0]
    prim = mesh["primitives"][0]
    attrs = prim["attributes"]
    pos_acc = attrs["POSITION"]
    pos = f2.read_accessor(gltf, bin_blob, pos_acc).astype(np.float64)
    joints = f2.read_accessor(gltf, bin_blob, attrs["JOINTS_0"]).astype(np.int32)
    weights_raw = f2.read_accessor(gltf, bin_blob, attrs["WEIGHTS_0"]).astype(np.float64)
    row_sum = weights_raw.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    weights = weights_raw / row_sum

    if "indices" in prim:
        indices = f2.read_accessor(gltf, bin_blob, prim["indices"]).astype(np.int64)
    else:
        indices = np.arange(len(pos), dtype=np.int64)

    ibm = f2.read_accessor(gltf, bin_blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
    head_world = np.linalg.inv(ibm[head_ji])
    head_local = (head_world @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]

    headfront_world = np.linalg.inv(ibm[headfront_ji])
    hf_local = (head_world @ np.c_[pos, np.ones(len(pos))].T).T[:, :3]
    # face forward in head space: Head -> headfront bind direction
    hf_bind = np.linalg.inv(ibm[headfront_ji]) @ np.array([0, 0, 0, 1.0])
    hf_in_head = (head_world @ hf_bind)[:3]
    face_forward = hf_in_head / (np.linalg.norm(hf_in_head) + 1e-12)

    head_w = np.array([float(weights[i, joints[i] == head_ji].sum()) for i in range(len(pos))])
    neck_w = np.array([float(weights[i, joints[i] == neck_ji].sum()) for i in range(len(pos))])

    head_mask = np.array([dominant_role(weights[i], joints[i], roles) == "head" for i in range(len(pos))])
    neck_mask = np.array([dominant_role(weights[i], joints[i], roles) == "neck" for i in range(len(pos))])
    body_mask = ~(head_mask | neck_mask)

    seam_mask = (head_w >= 0.05) & (neck_w >= 0.05)
    neck_transition = seam_mask.copy()

    if head_mask.any():
        head_y = head_local[head_mask, 1]
        hair_y_cut = float(np.quantile(head_y, 0.72))
    else:
        hair_y_cut = 0.0

    hair_mask = head_mask & (head_local[:, 1] >= hair_y_cut)

    # face: head skin, not hair, forward-facing, above lower face cutoff
    forward_score = head_local @ face_forward
    if head_mask.any():
        face_z_cut = float(np.quantile(forward_score[head_mask & ~hair_mask], 0.35))
        face_y_low = float(np.quantile(head_local[seam_mask, 1], 0.55)) if seam_mask.any() else float(np.min(head_local[head_mask, 1]))
    else:
        face_z_cut = 0.0
        face_y_low = 0.0

    face_mask = head_mask & ~hair_mask & (forward_score >= face_z_cut) & (head_local[:, 1] >= face_y_low) & ~seam_mask
    head_skin_mask = head_mask & ~hair_mask & ~face_mask & ~seam_mask

    # stylized coat/collar heuristic: body verts high on torso near neck in world Y
    body_y = pos[:, 1]
    clothing_mask = body_mask & (body_y >= float(np.quantile(body_y, 0.88)))

    region_masks = {
        "BODY": body_mask & ~clothing_mask,
        "CLOTHING_ACCESSORY": clothing_mask,
        "HAIR": hair_mask,
        "HEAD_SKIN": head_skin_mask & ~face_mask,
        "FACE_IDENTITY_REGION": face_mask,
        "NECK_TRANSITION": neck_transition,
    }

    # resolve overlaps: priority FACE > HAIR > NECK_TRANSITION > HEAD_SKIN > CLOTHING > BODY
    priority = [
        "FACE_IDENTITY_REGION",
        "HAIR",
        "NECK_TRANSITION",
        "HEAD_SKIN",
        "CLOTHING_ACCESSORY",
        "BODY",
    ]
    final = np.full(len(pos), "BODY", dtype=object)
    for name in reversed(priority):
        final[region_masks[name]] = name

    tri_regions: dict[str, int] = {r: 0 for r in REGIONS}
    for t in range(0, len(indices), 3):
        tri = indices[t : t + 3]
        counts: dict[str, int] = {}
        for vi in tri:
            counts[final[int(vi)]] = counts.get(final[int(vi)], 0) + 1
        tri_regions[max(counts, key=counts.get)] += 1

    vert_counts = {r: int((final == r).sum()) for r in REGIONS}

    return {
        "gltf": gltf,
        "bin_blob": bytearray(bin_blob),
        "pos": pos,
        "pos_acc": pos_acc,
        "indices": indices,
        "joints": joints,
        "weights": weights,
        "roles": roles,
        "head_ji": head_ji,
        "neck_ji": neck_ji,
        "head_world": head_world,
        "head_local": head_local,
        "face_forward": face_forward,
        "region_labels": final,
        "vert_counts": vert_counts,
        "tri_counts": tri_regions,
        "head_w": head_w,
        "neck_w": neck_w,
        "seam_mask": seam_mask,
    }


def align_identity_to_head(identity_verts: np.ndarray, mesh: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    """Similarity transform: identity MakeHuman space -> Meshy head-local frame."""
    pos = mesh["pos"]
    face_idx = np.where(mesh["region_labels"] == "FACE_IDENTITY_REGION")[0]
    head_idx = np.where(mesh["region_labels"] == "HEAD_SKIN")[0]
    use_idx = face_idx if len(face_idx) >= 40 else np.where(mesh["region_labels"] != "BODY")[0]

    src = identity_verts
    # identity head roughly centered; use y/z for face
    src_face = src[(src[:, 1] > 6.8) & (src[:, 2] > 0.8)]
    if len(src_face) < 50:
        src_face = src

    tgt_pts = mesh["head_local"][use_idx]
    src_ctr = src_face.mean(axis=0)
    tgt_ctr = tgt_pts.mean(axis=0)
    src_scale = float(np.linalg.norm(src_face - src_ctr, axis=1).mean())
    tgt_scale = float(np.linalg.norm(tgt_pts - tgt_ctr, axis=1).mean())
    scale = tgt_scale / max(src_scale, 1e-9)

    src_aligned = (src - src_ctr) * scale + tgt_ctr
    meta = {
        "sourceCentroid": src_ctr.tolist(),
        "targetCentroid": tgt_ctr.tolist(),
        "uniformScale": scale,
        "identitySourceVertCount": int(len(src)),
        "identityFaceSubsetCount": int(len(src_face)),
    }
    return src_aligned, meta


def nearest_identity_targets(
    face_verts_head_local: np.ndarray, identity_head_local: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Brute-force nearest neighbor (no scipy)."""
    targets = np.empty_like(face_verts_head_local)
    dists = np.empty(len(face_verts_head_local), dtype=np.float64)
    chunk = 512
    for i in range(0, len(face_verts_head_local), chunk):
        block = face_verts_head_local[i : i + chunk]
        d2 = ((block[:, None, :] - identity_head_local[None, :, :]) ** 2).sum(axis=2)
        nn = np.argmin(d2, axis=1)
        targets[i : i + chunk] = identity_head_local[nn]
        dists[i : i + chunk] = np.sqrt(d2[np.arange(len(block)), nn])
    return targets, dists


def face_landmarks_head_local(pos_head_local: np.ndarray, labels: np.ndarray) -> dict[str, np.ndarray]:
    face = pos_head_local[labels == "FACE_IDENTITY_REGION"]
    if len(face) < 20:
        face = pos_head_local[labels != "BODY"]
    return {
        "faceCenter": face.mean(axis=0),
        "noseTip": face[np.argmax(face @ np.array([0, 0.15, 1.0]))],
        "leftEye": face[np.argmin(face[:, 0])],
        "rightEye": face[np.argmax(face[:, 0])],
        "mouthCenter": face[np.argmin(face[:, 1])],
        "forehead": face[np.argmax(face[:, 1])],
    }


def identity_landmarks_head_local(id_verts: np.ndarray) -> dict[str, np.ndarray]:
    face = id_verts[(id_verts[:, 1] > 6.8) & (id_verts[:, 2] > 0.8)]
    if len(face) < 20:
        face = id_verts
    return {
        "faceCenter": face.mean(axis=0),
        "noseTip": face[np.argmax(face[:, 2])],
        "leftEye": face[np.argmin(face[:, 0])],
        "rightEye": face[np.argmax(face[:, 0])],
        "mouthCenter": face[np.argmin(face[:, 1])],
        "forehead": face[np.argmax(face[:, 1])],
    }


def median_edge_length(pos: np.ndarray, indices: np.ndarray, vert_mask: np.ndarray) -> float:
    sel = set(np.where(vert_mask)[0].tolist())
    lengths: list[float] = []
    for t in range(0, len(indices), 3):
        tri = [int(indices[t + k]) for k in range(3)]
        if not all(v in sel for v in tri):
            continue
        for a, b in ((0, 1), (1, 2), (2, 0)):
            lengths.append(float(np.linalg.norm(pos[tri[a]] - pos[tri[b]])))
    return float(np.median(lengths)) if lengths else 1.0


def patch_position_buffer(gltf: dict, bin_blob: bytearray, acc_idx: int, positions: np.ndarray) -> None:
    f2 = load_fast02()
    accessor = gltf["accessors"][acc_idx]
    bv = gltf["bufferViews"][accessor["bufferView"]]
    _, comp_size, np_dtype = f2.COMPONENT_TYPE[accessor["componentType"]]
    ncomp = f2.TYPE_COMPONENTS[accessor["type"]]
    start = bv.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = bv.get("byteStride", comp_size * ncomp)
    count = accessor["count"]
    pos_f32 = positions.astype(np.float32)
    if stride == comp_size * ncomp:
        bin_blob[start : start + count * 12] = pos_f32.tobytes()
        return
    for i in range(count):
        row_start = start + i * stride
        bin_blob[row_start : row_start + 12] = pos_f32[i].tobytes()


def write_glb(gltf: dict, bin_blob: bytes | bytearray, out_path: Path) -> None:
    json_bytes = json.dumps(gltf, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    json_pad = (4 - len(json_bytes) % 4) % 4
    json_bytes += b" " * json_pad
    bin_bytes = bytes(bin_blob)
    bin_pad = (4 - len(bin_bytes) % 4) % 4
    bin_bytes += b"\x00" * bin_pad
    total = 12 + 8 + len(json_bytes) + 8 + len(bin_bytes)
    with out_path.open("wb") as f:
        f.write(b"glTF")
        f.write(struct.pack("<II", 2, total))
        f.write(struct.pack("<I4s", len(json_bytes), b"JSON"))
        f.write(json_bytes)
        f.write(struct.pack("<I4s", len(bin_bytes), b"BIN\x00"))
        f.write(bin_bytes)


def hash_glb_animations(gltf: dict, bin_blob: bytes | bytearray) -> str:
    payload = json.dumps(gltf.get("animations", []), sort_keys=True).encode()
    # animation samplers reference input/output accessors — include their bytes
    for anim in gltf.get("animations", []):
        for sampler in anim.get("samplers", []):
            for key in ("input", "output"):
                acc = sampler.get(key)
                if acc is None:
                    continue
                f2 = load_fast02()
                arr = f2.read_accessor(gltf, bytes(bin_blob), acc)
                payload += arr.tobytes()
    return sha256_bytes(payload)


def hash_glb_materials_uv(gltf: dict, bin_blob: bytes | bytearray) -> str:
    f2 = load_fast02()
    payload = json.dumps({"materials": gltf.get("materials", []), "textures": gltf.get("textures", [])}, sort_keys=True).encode()
    prim = gltf["meshes"][0]["primitives"][0]
    if "TEXCOORD_0" in prim.get("attributes", {}):
        uv = f2.read_accessor(gltf, bytes(bin_blob), prim["attributes"]["TEXCOORD_0"])
        payload += uv.tobytes()
    return sha256_bytes(payload)


def run_fast03(
    working_root: Path,
    canonical_sha: str,
    identity_skin: Path,
) -> dict[str, Any]:
    f2 = load_fast02()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    baseline = working_root / "baseline" / "Idle_15_withSkin_WORKING_BASELINE.glb"
    evidence_dir = working_root / "evidence"
    semantic_dir = working_root / "semantic"
    proof_dir = working_root / "proof"
    for d in (evidence_dir, semantic_dir, proof_dir):
        d.mkdir(parents=True, exist_ok=True)

    baseline_sha = sha256_file(baseline)
    if baseline_sha.lower() != canonical_sha.lower():
        raise RuntimeError(f"Working baseline SHA mismatch: {baseline_sha} != {canonical_sha}")

    ledger_path = working_root / "mutation_ledger.json"
    ledger: dict[str, Any] = {
        "ledgerId": f"FAST-03_mutation_ledger_{ts}",
        "lane": "FAST_PRODUCT",
        "canonicalGlbSha256": canonical_sha.lower(),
        "workingBaselinePath": str(baseline),
        "workingBaselineSha256AtFreeze": baseline_sha.lower(),
        "formalLaneTouch": False,
        "identityLayer": "NURION user identity (DerivedHead v1 basis skin reference)",
        "presentationLayer": "Deferred — FAST-03D HOLD",
        "entries": [],
    }

    mesh = build_mesh_data(f2, baseline)

    # --- FAST-03A: semantic separation (no geometry mutation) ---
    membership = {
        "stage": "FAST-03A",
        "method": "skin_weight_head_local_heuristic_v1",
        "vertexCounts": mesh["vert_counts"],
        "triangleCounts": mesh["tri_counts"],
        "vertexMembership": {r: np.where(mesh["region_labels"] == r)[0].astype(int).tolist() for r in REGIONS},
        "headNeckSeam": {
            "seamVertexCount": int(mesh["seam_mask"].sum()),
            "neckTransitionVertexCount": int((mesh["region_labels"] == "NECK_TRANSITION").sum()),
        },
    }
    membership_path = semantic_dir / "FAST-03A_semantic_region_membership.json"
    membership_path.write_text(json.dumps(membership, indent=2), encoding="utf-8")

    ledger["entries"].append(
        {
            "id": "FAST-03A",
            "type": "SEMANTIC_REGION_SEPARATION",
            "mutation": 0,
            "output": str(membership_path),
            "note": "Vertex membership evidence only; no visual geometry change",
        }
    )

    # --- FAST-03B: Path-A feasibility proof ---
    identity_verts = parse_obj_verts(identity_skin)
    identity_aligned, align_meta = align_identity_to_head(identity_verts, mesh)

    face_idx = np.where(mesh["region_labels"] == "FACE_IDENTITY_REGION")[0]
    face_head_local = mesh["head_local"][face_idx]
    targets_local, nn_dists = nearest_identity_targets(face_head_local, identity_aligned)

    # map targets back to world space
    head_world_inv = np.linalg.inv(mesh["head_world"])
    targets_world = (head_world_inv @ np.c_[targets_local, np.ones(len(targets_local))].T).T[:, :3]

    proof_positions = mesh["pos"].copy()
    blend = 0.55  # minimal proof — not full identity lock
    proof_positions[face_idx] = mesh["pos"][face_idx] + blend * (targets_world - mesh["pos"][face_idx])

    med_edge = median_edge_length(mesh["pos"], mesh["indices"], mesh["region_labels"] == "FACE_IDENTITY_REGION")
    max_disp = float(np.max(np.linalg.norm(proof_positions[face_idx] - mesh["pos"][face_idx], axis=1)))
    mean_nn = float(np.mean(nn_dists))

    mesh_landmarks = face_landmarks_head_local(mesh["head_local"], mesh["region_labels"])
    id_landmarks = identity_landmarks_head_local(identity_aligned)
    head_height = float(
        np.ptp(mesh["pos"][mesh["region_labels"] != "BODY"][:, 1])
        if np.any(mesh["region_labels"] != "BODY")
        else float(np.ptp(mesh["pos"][:, 1]))
    )
    landmark_errors = {
        k: float(np.linalg.norm(mesh_landmarks[k] - id_landmarks[k])) for k in mesh_landmarks
    }
    mean_landmark_err = float(np.mean(list(landmark_errors.values())))
    landmark_err_frac = mean_landmark_err / max(head_height, 1e-9)

    covered = float(np.mean(nn_dists < med_edge * 1.5))

    non_face_moved = float(
        np.max(
            np.linalg.norm(
                proof_positions[np.isin(np.arange(len(proof_positions)), face_idx, invert=True)]
                - mesh["pos"][np.isin(np.arange(len(proof_positions)), face_idx, invert=True)],
                axis=1,
            )
        )
        if len(proof_positions) > len(face_idx)
        else 0.0
    )

    proof_gltf = copy.deepcopy(mesh["gltf"])
    proof_bin = bytearray(mesh["bin_blob"])
    patch_position_buffer(proof_gltf, proof_bin, mesh["pos_acc"], proof_positions)
    proof_glb = proof_dir / "FAST-03B_path_a_proof.glb"
    write_glb(proof_gltf, proof_bin, proof_glb)

    baseline_anim_hash = hash_glb_animations(mesh["gltf"], mesh["bin_blob"])
    proof_anim_hash = hash_glb_animations(proof_gltf, proof_bin)
    baseline_matuv_hash = hash_glb_materials_uv(mesh["gltf"], mesh["bin_blob"])
    proof_matuv_hash = hash_glb_materials_uv(proof_gltf, proof_bin)

    path_a_checks = {
        "faceRegionVertexCount": int(len(face_idx)),
        "faceRegionVertexMin": MIN_FACE_VERTS,
        "faceRegionVertexPass": len(face_idx) >= MIN_FACE_VERTS,
        "maxDisplacement": max_disp,
        "medianEdgeLengthFace": med_edge,
        "maxDisplacementEdgeRatio": max_disp / max(med_edge, 1e-9),
        "maxDisplacementEdgeRatioMax": MAX_DISP_EDGE_RATIO,
        "displacementRatioPass": (max_disp / max(med_edge, 1e-9)) <= MAX_DISP_EDGE_RATIO,
        "meanNearestIdentityDistance": mean_nn,
        "identityCoverageFraction": covered,
        "identityCoverageMin": MIN_IDENTITY_COVERAGE,
        "identityCoveragePass": covered >= MIN_IDENTITY_COVERAGE,
        "landmarkErrorsHeadLocal": landmark_errors,
        "meanLandmarkErrorHeadLocal": mean_landmark_err,
        "landmarkErrorHeadHeightFraction": landmark_err_frac,
        "landmarkErrorMaxFraction": MAX_LANDMARK_ERROR_HEAD_FRAC,
        "landmarkPass": landmark_err_frac <= MAX_LANDMARK_ERROR_HEAD_FRAC,
        "nonFaceVertexMaxDisplacement": non_face_moved,
        "nonFaceZeroPass": non_face_moved < 1e-6,
        "deformationScope": "FACE_IDENTITY_REGION only",
        "proofBlendFactor": blend,
    }
    path_a_pass = all(
        [
            path_a_checks["faceRegionVertexPass"],
            path_a_checks["displacementRatioPass"],
            path_a_checks["identityCoveragePass"],
            path_a_checks["landmarkPass"],
            path_a_checks["nonFaceZeroPass"],
        ]
    )

    regression = {
        "idleAnimationHashBaseline": baseline_anim_hash,
        "idleAnimationHashProof": proof_anim_hash,
        "idleAnimationUnchanged": baseline_anim_hash == proof_anim_hash,
        "materialUvHashBaseline": baseline_matuv_hash,
        "materialUvHashProof": proof_matuv_hash,
        "materialUvUnchanged": baseline_matuv_hash == proof_matuv_hash,
        "hairBodyVertexRegression": path_a_checks["nonFaceZeroPass"],
        "headNeckSeamPreserved": path_a_checks["nonFaceZeroPass"],
    }

    proof_record = {
        "stage": "FAST-03B",
        "path": "A_FACE_SURFACE_IDENTITY_ADAPT",
        "identityReference": {
            "path": str(identity_skin),
            "sha256": sha256_file(identity_skin),
            "classification": "FAST_IDENTITY_REFERENCE_ONLY",
        },
        "alignment": align_meta,
        "feasibility": path_a_checks,
        "regression": regression,
        "proofGlb": str(proof_glb),
        "proofGlbSha256": sha256_file(proof_glb),
        "pathAFeasible": path_a_pass,
    }
    proof_path = evidence_dir / "FAST-03B_path_a_feasibility_proof.json"
    proof_path.write_text(json.dumps(proof_record, indent=2), encoding="utf-8")

    ledger["entries"].append(
        {
            "id": "FAST-03B",
            "type": "PATH_A_IDENTITY_FEASIBILITY_PROOF",
            "mutation": 1,
            "scope": "FACE_IDENTITY_REGION geometry only (proof GLB)",
            "output": str(proof_glb),
            "evidence": str(proof_path),
        }
    )

    # --- FAST-03C: Identity path gate ---
    path_scores = {
        "A_FACE_SURFACE_IDENTITY_ADAPT": 0,
        "B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK": 0,
        "C_HEAD_REPLACEMENT_REQUIRED": 0,
    }
    rationale: list[str] = []

    if path_a_pass:
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] += 5
        rationale.append("Path-A proof passed all feasibility gates on FACE_IDENTITY_REGION.")
    else:
        rationale.append("Path-A proof failed one or more feasibility gates.")
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 3
        if not path_a_checks["landmarkPass"] or not path_a_checks["identityCoveragePass"]:
            path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 2
            rationale.append("Landmark/coverage deficit suggests broader HEAD_SKIN adaptation while preserving neck.")
        if not path_a_checks["displacementRatioPass"]:
            path_scores["C_HEAD_REPLACEMENT_REQUIRED"] += 2
            rationale.append("High displacement/edge ratio indicates topology constraint on surface-only adapt.")

    if mesh["vert_counts"]["NECK_TRANSITION"] > 0:
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 1
        rationale.append("NECK_TRANSITION region defined — B preserves seam if A fails.")

    ordered = sorted(path_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    if path_a_pass:
        recommended = "A_FACE_SURFACE_IDENTITY_ADAPT"
        label = "A - FACE_SURFACE_IDENTITY_ADAPT"
        gate_verdict = "A_CANDIDATE_LOCK_PENDING_USER"
    elif ordered[0][0].startswith("B") or path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] >= path_scores["C_HEAD_REPLACEMENT_REQUIRED"]:
        recommended = "B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"
        label = "B - HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"
        gate_verdict = "B_PROMOTION_REQUIRED"
    else:
        recommended = "C_HEAD_REPLACEMENT_REQUIRED"
        label = "C - HEAD_REPLACEMENT_REQUIRED"
        gate_verdict = "C_ESCALATION"

    gate = {
        "stage": "FAST-03C",
        "stopGate": True,
        "fast03dHold": True,
        "fast04Hold": True,
        "scores": path_scores,
        "recommendedPath": recommended,
        "recommendedPathLabel": label,
        "gateVerdict": gate_verdict,
        "pathALock": path_a_pass,
        "rationale": rationale,
        "identityPresentationSeparation": {
            "identityLayer": "FACE_IDENTITY_REGION / HEAD_SKIN adaptation only in 03B proof",
            "presentationLayer": "HOLD — jaw/blink/viseme deferred to FAST-03D after user LOCK",
            "rule": "Presentation deformation must not redefine Identity geometry",
        },
    }
    gate_path = evidence_dir / "FAST-03C_identity_path_gate.json"
    gate_path.write_text(json.dumps(gate, indent=2), encoding="utf-8")

    ledger["entries"].append(
        {
            "id": "FAST-03C",
            "type": "IDENTITY_PATH_GATE",
            "mutation": 0,
            "recommendedPath": recommended,
            "output": str(gate_path),
        }
    )
    ledger["workingBaselineSha256Current"] = baseline_sha.lower()
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    receipt = {
        "receiptId": f"FAST-03_stop_gate_{ts}",
        "timestampUtc": ts,
        "lane": "FAST_PRODUCT",
        "stage": "FAST-03",
        "verdict": gate_verdict,
        "stopGate": True,
        "fast03dStatus": "HOLD",
        "fast04Status": "HOLD",
        "integrity": {
            "canonicalGlbSha256": canonical_sha.lower(),
            "workingBaselineSha256": baseline_sha.lower(),
            "workingBaselinePath": str(baseline),
            "canonicalImmutable": True,
            "formalLaneTouch": False,
        },
        "semanticRegions": {
            "vertexCounts": mesh["vert_counts"],
            "triangleCounts": mesh["tri_counts"],
            "membershipArtifact": str(membership_path),
        },
        "headNeckSeamPreservation": {
            "neckTransitionVertices": mesh["vert_counts"]["NECK_TRANSITION"],
            "seamBandVertices": int(mesh["seam_mask"].sum()),
            "nonFaceDisplacementInProof": non_face_moved,
            "preserved": non_face_moved < 1e-6,
        },
        "pathADeformationScope": {
            "region": "FACE_IDENTITY_REGION",
            "vertexCount": int(len(face_idx)),
            "maxDisplacement": max_disp,
            "medianEdgeLength": med_edge,
            "proofBlendFactor": blend,
        },
        "regression": regression,
        "identityFeasibility": {
            "pathAFeasible": path_a_pass,
            "checks": path_a_checks,
            "proofArtifact": str(proof_path),
            "proofGlb": str(proof_glb),
        },
        "identityPathGate": gate,
        "mutationLedger": str(ledger_path),
        "artifacts": {
            "03A": str(membership_path),
            "03B": str(proof_path),
            "03C": str(gate_path),
            "proofGlb": str(proof_glb),
        },
    }
    receipt_path = evidence_dir / "FAST-03_stop_gate_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")

    return receipt


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--working-root",
        type=Path,
        default=ROOT / "fast_track/working/meshy_silver_starlight",
    )
    parser.add_argument(
        "--canonical-sha",
        default="a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1",
    )
    parser.add_argument("--identity-skin", type=Path, default=IDENTITY_SKIN)
    args = parser.parse_args()

    receipt = run_fast03(args.working_root, args.canonical_sha, args.identity_skin)
    print(json.dumps({"verdict": receipt["verdict"], "pathAFeasible": receipt["identityFeasibility"]["pathAFeasible"]}, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
