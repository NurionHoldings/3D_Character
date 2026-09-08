"""CR04 fail-closed fast-track: pin verified → P01…P06.

Consumes CR01/CR02/CR03 mechanisms without patching upstream modules.
Talking injection binds VISEME_* by name from CR02-derived morph extras (CR03 mechanism).
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import struct
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document, write_minimal_glb
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter
from fast_track.v2_cr02.facial_deformation import run_r2_deformation_proof
from fast_track.v2_cr03.glb_measure import (
    accessor_raw_bytes,
    base_skin_digests,
    canonical_sha256,
    read_f32_vec3,
    sha256_file,
)
from fast_track.v2_cr04.pins import (
    ACTIVATION_THRESHOLD,
    APPROVED_SPEC_DIGEST,
    CR,
    IDLE15_BASELINE_SHA,
    REQUIRED_VISEMES,
    RESTORATION_TOLERANCE,
    SECOND_ASSET_SHA,
    TALKING_ANIMATION_NAME,
    TALKING_TIMELINE,
)

COMPONENT_FLOAT = 5126


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _write_json(path: Path, obj: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sha256_file(path)


def _append_buffer_data(blob: bytearray, data: bytes) -> tuple[int, int]:
    while len(blob) % 4:
        blob.append(0)
    offset = len(blob)
    blob.extend(data)
    while len(blob) % 4:
        blob.append(0)
    return offset, len(data)


def _max_norm(a: np.ndarray) -> float:
    if len(a) == 0:
        return 0.0
    return float(np.linalg.norm(a, axis=1).max())


def _morph_index_map_from_mesh(mesh: dict) -> dict[str, dict[str, Any]]:
    names = list((mesh.get("extras") or {}).get("targetNames") or [])
    targets = mesh["primitives"][0].get("targets") or []
    out: dict[str, dict[str, Any]] = {}
    for req in REQUIRED_VISEMES:
        if req not in names:
            raise AssertionError(f"required morph missing: {req}")
        if names.count(req) != 1:
            raise AssertionError(f"non-deterministic morph ordering: {req}")
        idx = names.index(req)
        out[req] = {"name": req, "targetIndex": idx, "positionAccessor": targets[idx]["POSITION"]}
    return out


def inject_talking_by_name(*, input_glb: Path, output_glb: Path) -> dict[str, Any]:
    """CR03 mechanism re-applied with name-discovered morph indices (no upstream patch)."""
    gltf, bin_blob, _ = load_gltf_document(input_glb)
    assert bin_blob is not None
    before_morph = {}
    mesh = gltf["meshes"][0]
    mmap = _morph_index_map_from_mesh(mesh)
    for name, pin in mmap.items():
        before_morph[name] = hashlib.sha256(
            accessor_raw_bytes(bin_blob, gltf, pin["positionAccessor"])
        ).hexdigest()
    skin_before = base_skin_digests(bin_blob, gltf)

    gltf = copy.deepcopy(gltf)
    morph_count = len(gltf["meshes"][0]["primitives"][0]["targets"])
    nodes = gltf["nodes"]
    mesh_node = next(i for i, n in enumerate(nodes) if n.get("mesh") == 0)

    times = np.asarray([t[0] for t in TALKING_TIMELINE], dtype=np.float32)
    rows = []
    ia, io, ie = (
        mmap["VISEME_AA"]["targetIndex"],
        mmap["VISEME_OH"]["targetIndex"],
        mmap["VISEME_EE"]["targetIndex"],
    )
    for _t, aa, oh, ee in TALKING_TIMELINE:
        w = [0.0] * morph_count
        w[ia], w[io], w[ie] = aa, oh, ee
        rows.append(w)
    weights = np.asarray(rows, dtype=np.float32)

    blob = bytearray(bin_blob)
    accessors = list(gltf["accessors"])
    buffer_views = list(gltf["bufferViews"])

    t_off, t_len = _append_buffer_data(blob, times.tobytes(order="C"))
    t_bv = len(buffer_views)
    buffer_views.append({"buffer": 0, "byteOffset": t_off, "byteLength": t_len})
    t_acc = len(accessors)
    accessors.append(
        {
            "bufferView": t_bv,
            "componentType": COMPONENT_FLOAT,
            "count": int(times.shape[0]),
            "type": "SCALAR",
            "max": [float(times.max())],
            "min": [float(times.min())],
        }
    )
    w_off, w_len = _append_buffer_data(blob, weights.tobytes(order="C"))
    w_bv = len(buffer_views)
    buffer_views.append({"buffer": 0, "byteOffset": w_off, "byteLength": w_len})
    w_acc = len(accessors)
    accessors.append(
        {
            "bufferView": w_bv,
            "componentType": COMPONENT_FLOAT,
            "count": int(weights.size),
            "type": "SCALAR",
            "max": [float(weights.max())],
            "min": [float(weights.min())],
        }
    )
    gltf["accessors"] = accessors
    gltf["bufferViews"] = buffer_views
    gltf["buffers"][0]["byteLength"] = len(blob)
    gltf["meshes"][0]["weights"] = [0.0] * morph_count

    anims = list(gltf.get("animations") or [])
    talking_idx = len(anims)
    anims.append(
        {
            "name": TALKING_ANIMATION_NAME,
            "samplers": [{"input": t_acc, "interpolation": "LINEAR", "output": w_acc}],
            "channels": [{"sampler": 0, "target": {"node": mesh_node, "path": "weights"}}],
        }
    )
    gltf["animations"] = anims
    gltf.setdefault("extras", {})["NURION_V2_CR04_P04"] = {
        "mechanism": "CR03_MORPH_WEIGHT_TALKING_CONSUME",
        "morphIndexMap": mmap,
        "talkingAnimationIndex": talking_idx,
    }
    output_glb.parent.mkdir(parents=True, exist_ok=True)
    output_glb.write_bytes(write_minimal_glb(gltf, bytes(blob)))

    g2, b2, _ = load_gltf_document(output_glb)
    assert b2 is not None
    for name, pin in mmap.items():
        after = hashlib.sha256(
            accessor_raw_bytes(b2, g2, pin["positionAccessor"])
        ).hexdigest()
        if after != before_morph[name]:
            raise AssertionError(f"morph POSITION mutated: {name}")
    if base_skin_digests(b2, g2) != skin_before:
        raise AssertionError("BODY skin mutated during talking injection")

    return {
        "derivedSha256": sha256_file(output_glb),
        "morphIndexMap": mmap,
        "talkingAnimationIndex": talking_idx,
        "targetNode": mesh_node,
        "timelineDigest": canonical_sha256(
            [{"t": t, "AA": aa, "OH": oh, "EE": ee} for t, aa, oh, ee in TALKING_TIMELINE]
        ),
    }


def prove_temporal(derived_glb: Path, morph_index_map: dict) -> dict[str, Any]:
    gltf, blob, _ = load_gltf_document(derived_glb)
    assert blob is not None
    anim = next(a for a in gltf["animations"] if a.get("name") == TALKING_ANIMATION_NAME)
    ch = next(c for c in anim["channels"] if c["target"]["path"] == "weights")
    samp = anim["samplers"][ch["sampler"]]
    t_vals = np.frombuffer(accessor_raw_bytes(blob, gltf, samp["input"]), dtype="<f4").copy()
    w_flat = np.frombuffer(accessor_raw_bytes(blob, gltf, samp["output"]), dtype="<f4").copy()
    prim = gltf["meshes"][0]["primitives"][0]
    targets = prim["targets"]
    morph_count = len(targets)
    w_mat = w_flat.reshape(len(t_vals), morph_count)
    base = read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    deltas = [read_f32_vec3(blob, gltf, t["POSITION"]) for t in targets]
    ia = morph_index_map["VISEME_AA"]["targetIndex"]
    io = morph_index_map["VISEME_OH"]["targetIndex"]
    ie = morph_index_map["VISEME_EE"]["targetIndex"]
    frames = []
    positions = []
    blockers = []
    for fi, t in enumerate(t_vals.tolist()):
        w = w_mat[fi]
        vt = base + deltas[ia] * float(w[ia]) + deltas[io] * float(w[io]) + deltas[ie] * float(w[ie])
        frames.append(
            {
                "t": t,
                "wAA": float(w[ia]),
                "wOH": float(w[io]),
                "wEE": float(w[ie]),
                "maxVertexDeltaFromBase": _max_norm(vt - base),
            }
        )
        positions.append(vt)
    v0, v_aa, v_oh, v_ee, v_end = positions
    dist = {
        "AA_vs_OH": _max_norm(v_aa - v_oh),
        "AA_vs_EE": _max_norm(v_aa - v_ee),
        "OH_vs_EE": _max_norm(v_oh - v_ee),
    }
    for k, v in dist.items():
        if v <= ACTIVATION_THRESHOLD:
            blockers.append({"code": "STATES_NOT_DISTINCT", "pair": k, "v": v})
    for label, fr in (("AA", frames[1]), ("OH", frames[2]), ("EE", frames[3])):
        if fr["maxVertexDeltaFromBase"] <= ACTIVATION_THRESHOLD:
            blockers.append({"code": "ACTIVATION_FAIL", "state": label})
    start_err = _max_norm(v0 - base)
    end_err = _max_norm(v_end - base)
    if start_err > RESTORATION_TOLERANCE:
        blockers.append({"code": "START_NEUTRAL_FAIL", "error": start_err})
    if end_err > RESTORATION_TOLERANCE:
        blockers.append({"code": "END_NEUTRAL_FAIL", "error": end_err})
    digest = canonical_sha256({"frames": frames, "dist": dist, "start": start_err, "end": end_err})
    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "frames": frames,
        "stateDistinctness": dist,
        "restoration": {"startError": start_err, "endError": end_err},
        "runtimeProofDigest": digest,
        "blockers": blockers,
    }


def hardcoding_scan(repo_root: Path) -> dict[str, Any]:
    """Scan CR04 adaptation control-flow for asset-identity special casing."""
    path = repo_root / "fast_track" / "v2_cr04" / "fasttrack.py"
    blockers: list[dict[str, Any]] = []
    reviewed: list[dict[str, Any]] = []
    if not path.is_file():
        return {"status": "BLOCKED", "blockers": [{"code": "MISSING_FASTTRACK"}], "hitsReviewed": []}

    lines = path.read_text(encoding="utf-8").splitlines()
    rel = str(path.relative_to(repo_root)).replace("\\", "/")

    # Only scan run_fasttrack / inject / prove bodies — skip hardcoding_scan itself
    skip = False
    for i, line in enumerate(lines, 1):
        if line.startswith("def hardcoding_scan"):
            skip = True
            continue
        if skip:
            if line.startswith("def ") and not line.startswith("def hardcoding_scan"):
                skip = False
            else:
                continue
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        # Deny control-flow that keys off first-proof or second-asset identity for special success paths
        if re.match(r"^(if|elif)\b", stripped):
            identity = any(
                tok in stripped
                for tok in (
                    "Idle_15",
                    "Bolt_Voyager",
                    "Silver_Starlight",
                    IDLE15_BASELINE_SHA,
                    SECOND_ASSET_SHA,
                )
            )
            if identity and ("==" in stripped or "!=" in stripped):
                # Allowed: reject first-proof asset as illegal second-asset clone
                nxt = "\n".join(lines[i : min(len(lines), i + 5)])
                if "IDLE15_CLONE" in nxt or "idle15 clone" in nxt.lower():
                    reviewed.append(
                        {"file": rel, "line": i, "snippet": stripped[:160], "disposition": "ALLOWED_ANTI_CLONE"}
                    )
                    continue
                hit = {"file": rel, "line": i, "snippet": stripped[:160]}
                reviewed.append(hit)
                blockers.append({"code": "ASSET_IDENTITY_BRANCH", "hit": hit})

    return {
        "status": "PASS" if not blockers else "BLOCKED",
        "hitsReviewed": reviewed,
        "blockers": blockers,
        "policy": "No adaptation if/elif special-case on asset name/SHA except anti-clone reject",
    }


def run_fasttrack(*, track: dict[str, Any], spec_path: Path, roots: dict) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    gate = require_human_spec_gate(track, expected_change_request=CR, spec_path=spec_path)
    if gate != APPROVED_SPEC_DIGEST:
        raise PermissionError("SPEC_DIGEST_MISMATCH")

    baseline = Path(roots["baseline"])
    derived_dir = Path(roots["derived"])
    rep = Path(roots["reports"])
    ev = Path(roots["evidence"])
    derived_dir.mkdir(parents=True, exist_ok=True)
    rep.mkdir(parents=True, exist_ok=True)

    stages: dict[str, Any] = {}
    utc = _utc()

    # --- P01 ---
    before = baseline.read_bytes()
    sha = sha256_file(baseline)
    if sha != SECOND_ASSET_SHA:
        return {"stoppedAt": "P01", "status": "BLOCKED", "blockers": [{"code": "PIN_SHA_MISMATCH", "got": sha}]}
    if sha == IDLE15_BASELINE_SHA:
        return {"stoppedAt": "P01", "status": "BLOCKED", "blockers": [{"code": "IDLE15_CLONE"}]}
    gltf, blob, _ = load_gltf_document(baseline)
    assert blob is not None
    has_mesh = bool(gltf.get("meshes"))
    has_skin = bool(gltf.get("skins"))
    has_anim = bool(gltf.get("animations"))
    morph0 = len((gltf["meshes"][0]["primitives"][0].get("targets") or []))
    p01 = {
        "stage": "CR04-P01",
        "status": "PASS",
        "inputSha256": sha,
        "immutable": baseline.read_bytes() == before,
        "mesh": has_mesh,
        "skin": has_skin,
        "embeddedBodyClip": has_anim,
        "morphTargetsAtIntake": morph0,
        "capabilityGap": {
            "Blink": "MISSING",
            "Jaw": "MISSING",
            "Expression": "MISSING",
            "Viseme": "MISSING",
            "TALKING": "MISSING",
            "plan": "CR02 minimum augmentation consume",
        },
    }
    if not (has_mesh and has_skin):
        p01["status"] = "BLOCKED"
        p01["blockers"] = [{"code": "MISSING_MESH_OR_SKIN"}]
        _write_json(rep / "V2_CR04_P01_intake.json", p01)
        return {"stoppedAt": "P01", **p01}
    _write_json(rep / "V2_CR04_P01_intake.json", p01)
    stages["CR04-P01"] = "PASS"

    # --- P02 CR01 ---
    cr01 = run_flexible_adapter(baseline)
    if baseline.read_bytes() != before:
        return {"stoppedAt": "P02", "status": "BLOCKED", "blockers": [{"code": "SOURCE_MUTATED_BY_CR01"}]}
    p02 = {
        "stage": "CR04-P02",
        "status": "PASS" if cr01.get("status") == "PASS" else "BLOCKED",
        "semanticAdapterDigest": cr01.get("semanticAdapterDigest"),
        "mappingView": cr01.get("mappingView"),
        "note": "CR01 CONSUME ONLY - digest may differ from first-proof-asset Human-PASS digest (asset-specific mapping result)",
    }
    if p02["status"] != "PASS":
        p02["blockers"] = [{"code": "CR01_NOT_PASS", "detail": cr01}]
        _write_json(rep / "V2_CR04_P02_cr01.json", p02)
        return {"stoppedAt": "P02", **p02}
    _write_json(rep / "V2_CR04_P02_cr01.json", p02)
    stages["CR04-P02"] = "PASS"
    semantic_digest = cr01["semanticAdapterDigest"]

    # --- P03 CR02 ---
    face_derived = derived_dir / "SECOND_ASSET_CR02_facial_deformation.glb"
    cr02 = run_r2_deformation_proof(baseline, face_derived)
    if baseline.read_bytes() != before:
        return {"stoppedAt": "P03", "status": "BLOCKED", "blockers": [{"code": "SOURCE_MUTATED_BY_CR02"}]}
    p03 = {
        "stage": "CR04-P03",
        "status": "PASS" if cr02.get("status") == "PASS" else "BLOCKED",
        "derivedSha256": (cr02.get("derived") or {}).get("derivedSha256") or sha256_file(face_derived),
        "cr02Status": cr02.get("status"),
        "cr02Blockers": cr02.get("blockers") or [],
        "morphOrder": (cr02.get("derived") or {}).get("morphOrder"),
    }
    if cr02.get("blockers") or cr02.get("status") != "PASS":
        p03["status"] = "BLOCKED"
        p03["blockers"] = cr02.get("blockers") or [{"code": "CR02_STATUS", "status": cr02.get("status")}]
    # Also verify file morphs
    g_f, b_f, _ = load_gltf_document(face_derived)
    names = (g_f["meshes"][0].get("extras") or {}).get("targetNames") or []
    if not all(v in names for v in REQUIRED_VISEMES):
        p03["status"] = "BLOCKED"
        p03.setdefault("blockers", []).append({"code": "VISEME_MISSING_AFTER_CR02", "names": names})
    facial_digest = canonical_sha256({"names": names, "derived": p03["derivedSha256"]})
    p03["facialAugmentationDigest"] = facial_digest
    _write_json(rep / "V2_CR04_P03_cr02.json", p03)
    if p03["status"] != "PASS":
        return {"stoppedAt": "P03", **p03}
    stages["CR04-P03"] = "PASS"

    # --- P04 CR03 talking consume ---
    talk_derived = derived_dir / "SECOND_ASSET_CR03_talking_weights.glb"
    inj = inject_talking_by_name(input_glb=face_derived, output_glb=talk_derived)
    temporal = prove_temporal(talk_derived, inj["morphIndexMap"])
    p04 = {
        "stage": "CR04-P04",
        "status": temporal["status"],
        "injection": inj,
        "temporal": temporal,
        "talkingAnimationDigest": canonical_sha256(
            {"timeline": inj["timelineDigest"], "mmap": inj["morphIndexMap"], "anim": inj["talkingAnimationIndex"]}
        ),
        "blockers": temporal.get("blockers") or [],
    }
    _write_json(rep / "V2_CR04_P04_cr03_talking.json", p04)
    if p04["status"] != "PASS":
        return {"stoppedAt": "P04", **p04}
    stages["CR04-P04"] = "PASS"

    # --- P05 generalization / hardcoding / regression ---
    g_out, b_out, _ = load_gltf_document(talk_derived)
    assert b_out is not None
    g_in, b_in, _ = load_gltf_document(baseline)
    assert b_in is not None
    skin_ok = base_skin_digests(b_in, g_in) == base_skin_digests(b_out, g_out)
    # morph POSITION for visemes present; base POSITION unchanged
    anim_names = [a.get("name") for a in (g_out.get("animations") or [])]
    body_clip = any(n and TALKING_ANIMATION_NAME not in n for n in anim_names)
    talking_clip = TALKING_ANIMATION_NAME in anim_names
    scan = hardcoding_scan(Path(roots["repoRoot"]))
    p05 = {
        "stage": "CR04-P05",
        "status": "PASS",
        "bodySkinPreserved": skin_ok,
        "embeddedBodyClipPreserved": body_clip,
        "talkingClipPresent": talking_clip,
        "coexistence": body_clip and talking_clip,
        "hardcodingScan": scan,
        "blockers": [],
    }
    if not skin_ok:
        p05["blockers"].append({"code": "BODY_SKIN_REGRESSION"})
    if not (body_clip and talking_clip):
        p05["blockers"].append({"code": "COEXISTENCE_FAIL", "anims": anim_names})
    if scan["status"] != "PASS":
        p05["blockers"].extend(scan["blockers"])
    if p05["blockers"]:
        p05["status"] = "BLOCKED"
    p05["regressionDigest"] = canonical_sha256(
        {"skin_ok": skin_ok, "coexist": body_clip and talking_clip, "scan": scan["status"]}
    )
    _write_json(rep / "V2_CR04_P05_generalization.json", p05)
    if p05["status"] != "PASS":
        return {"stoppedAt": "P05", **p05}
    stages["CR04-P05"] = "PASS"

    # --- P06 seal ---
    final_sha = sha256_file(talk_derived)
    final_semantic = canonical_sha256(
        {
            "secondAssetSha": SECOND_ASSET_SHA,
            "semanticAdapterDigest": semantic_digest,
            "facialAugmentationDigest": facial_digest,
            "talkingAnimationDigest": p04["talkingAnimationDigest"],
            "runtimeProofDigest": temporal["runtimeProofDigest"],
            "regressionDigest": p05["regressionDigest"],
            "derivedSha256": final_sha,
        }
    )
    p06 = {
        "schema": "NURION_V2_CR04_P06_PROOF_SEAL_V1",
        "stage": "CR04-P06",
        "status": "PASS",
        "stages": stages | {"CR04-P06": "PASS", "CR04-P07": "HUMAN_FINAL_ONLY"},
        "secondAssetSha256": SECOND_ASSET_SHA,
        "derivedSha256": final_sha,
        "digests": {
            "semanticAdapterDigest": semantic_digest,
            "facialAugmentationDigest": facial_digest,
            "talkingAnimationDigest": p04["talkingAnimationDigest"],
            "runtimeProofDigest": temporal["runtimeProofDigest"],
            "regressionDigest": p05["regressionDigest"],
            "finalCandidateSemanticDigest": final_semantic,
        },
        "authority": {
            "CR01": "CONSUME ONLY",
            "CR02": "CONSUME ONLY",
            "CR03": "CONSUME ONLY (mechanism)",
            "CR04": "OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT",
            "EngineV2": "NOT OPEN",
        },
        "passMeans": "Second independent Meshy asset reproduced CR01->CR02->CR03 chain without asset-specific hardcoding - Agent ceiling only",
        "passDoesNotMean": [
            "ALL MESHY SUPPORTED",
            "UNIVERSAL GENERALIZATION",
            "PRODUCTION READY",
            "Engine V2 OPEN",
        ],
    }
    _write_json(rep / "V2_CR04_P06_proof_seal.json", p06)
    stages["CR04-P06"] = "PASS"

    ready = {
        "receiptId": "NURION-V2-CR04_READY_FOR_HUMAN_AUDIT",
        "changeRequestId": CR,
        "status": "READY_FOR_HUMAN_AUDIT",
        "declaredAtUtc": utc,
        "approvedSpecDigest": APPROVED_SPEC_DIGEST,
        "secondAssetSha256": SECOND_ASSET_SHA,
        "derivedSha256": final_sha,
        "finalCandidateSemanticDigest": final_semantic,
        "runtimeProofDigest": temporal["runtimeProofDigest"],
        "agentCeiling": "READY_FOR_HUMAN_AUDIT",
        "CR04-P07": "HUMAN_FINAL_ONLY",
        "CR04-G20": "HUMAN_FINAL_ONLY",
        "engineV2": "NOT_OPEN",
        "stages": stages,
    }
    _write_json(ev / "NURION-V2-CR04_READY_FOR_HUMAN_AUDIT_receipt.json", ready)

    return {
        "status": "READY_FOR_HUMAN_AUDIT",
        "stages": stages,
        "derivedSha256": final_sha,
        "finalCandidateSemanticDigest": final_semantic,
        "runtimeProofDigest": temporal["runtimeProofDigest"],
        "secondAssetSha256": SECOND_ASSET_SHA,
        "peak": {
            "AA": temporal["frames"][1]["maxVertexDeltaFromBase"],
            "OH": temporal["frames"][2]["maxVertexDeltaFromBase"],
            "EE": temporal["frames"][3]["maxVertexDeltaFromBase"],
        },
    }
