"""Shared Gate8 clean-scene pipeline fingerprint (no intermediate reuse)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from .parameters import (
    FOOT_SLIDE_RESIDUAL,
    GATE1_FROZEN,
    GATE2_FROZEN,
    GATE3_FROZEN,
    GATE4_FROZEN,
    GATE5_FROZEN,
    GATE6_FROZEN,
    GATE7_FROZEN,
    GATE8_PARAMETERS,
    TIMELINE_UID,
    V04_GATE7_FROZEN,
    V04_RC1_SHA256,
    parameter_hash,
)


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_frozen_hashes(root: Path) -> Dict:
    from nurion_v04_face_rig.gate7.parameters import parameter_hash as v04_g7_hash
    from nurion_v05_body_motion.gate1.parameters import parameter_hash as g1
    from nurion_v05_body_motion.gate2.parameters import parameter_hash as g2
    from nurion_v05_body_motion.gate3.parameters import parameter_hash as g3
    from nurion_v05_body_motion.gate4.parameters import parameter_hash as g4
    from nurion_v05_body_motion.gate5.parameters import parameter_hash as g5
    from nurion_v05_body_motion.gate6.parameters import parameter_hash as g6
    from nurion_v05_body_motion.gate7.parameters import parameter_hash as g7

    checks = {
        "gate1": g1() == GATE1_FROZEN,
        "gate2": g2() == GATE2_FROZEN,
        "gate3": g3() == GATE3_FROZEN,
        "gate4": g4() == GATE4_FROZEN,
        "gate5": g5() == GATE5_FROZEN,
        "gate6": g6() == GATE6_FROZEN,
        "gate7": g7() == GATE7_FROZEN,
        "v04Gate7": v04_g7_hash() == V04_GATE7_FROZEN,
    }
    rc1 = root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    checks["v04Rc1"] = rc1.exists() and _sha_file(rc1) == V04_RC1_SHA256
    tpath = root / GATE8_PARAMETERS["timelinesDir"] / f"{TIMELINE_UID}.json"
    checks["timelinePresent"] = tpath.exists()
    return {
        "ok": all(checks.values()),
        "checks": checks,
        "timelineSha256": _sha_file(tpath) if tpath.exists() else "",
        "v04Rc1Sha256": _sha_file(rc1) if rc1.exists() else "",
    }


def _bone_mapping(arm) -> Dict:
    required = list(GATE8_PARAMETERS["requiredBones"])
    present = [b for b in required if arm.data.bones.get(b) is not None]
    missing = [b for b in required if b not in present]
    return {
        "ok": len(missing) == 0,
        "presentCount": len(present),
        "requiredCount": len(required),
        "missing": missing,
    }


def enrich_scene_fingerprint(*, root: Path, gate7_once: Dict, seed_mode: bool) -> Dict:
    """Read clone artifacts left in scene after run_gate7_once; no prior dist reuse."""
    import bpy
    from nurion_v05_body_motion.gate2.normalize import _axis_align_score, _lr_swap_check
    from nurion_v05_body_motion.gate2.parameters import GATE2_PARAMETERS
    from nurion_v05_body_motion.gate5.penetration import _build_region_maps, _inspect_penetration
    from nurion_v05_body_motion.gate6.integrate import _action_fingerprint, _bone_action_fingerprint, _count_keys

    body_arm = bpy.data.objects.get("NURION_BodyRigClone")
    body_mesh = bpy.data.objects.get("NURION_BodyMotionCandidate")
    body_action = bpy.data.actions.get("NURION_BodyMotionCandidateAction")
    face_mesh = bpy.data.objects.get("NURION_SyncFacialPerformance")

    if body_arm is None or body_mesh is None or body_action is None:
        raise RuntimeError("Gate8 pipeline artifacts missing after clean rebuild")

    fs = int(gate7_once["fs"])
    fe = int(gate7_once["fe"])
    mapping = _bone_mapping(body_arm)
    lr = _lr_swap_check(body_arm)
    axis = {k: _axis_align_score(body_arm, v) for k, v in GATE2_PARAMETERS["chains"].items()}
    axis_fail = []
    for k in GATE2_PARAMETERS["axisGateChains"]:
        if not axis.get(k, {}).get("ok", False):
            axis_fail.append(k)

    region_maps = _build_region_maps(body_mesh)
    pen = _inspect_penetration(body_mesh, fs, fe, region_maps)
    max_depth = float(pen.get("maxDepthM") or 0.0)
    shallow_ok = max_depth <= float(GATE8_PARAMETERS["shallowContactDepthMaxM"]) + 1e-9

    keys = _count_keys(body_action)
    action_fp = _action_fingerprint(body_action)
    forearm_fp = _bone_action_fingerprint(body_action, "RightForeArm")
    tpath = root / GATE8_PARAMETERS["timelinesDir"] / f"{TIMELINE_UID}.json"
    timeline_sha = _sha_file(tpath)

    stable7 = gate7_once["stable"]
    slides = int(gate7_once["slides"])
    slide_ok = (slides <= FOOT_SLIDE_RESIDUAL) if seed_mode else True
    # Cross-asset: slides reported as body-type dependent; worsen checked vs seed residual only for seed

    face_ok = (
        bool(stable7.get("eyeHeadDoubleOk"))
        and int(stable7.get("lipIntersection", 1)) == 0
        and int(stable7.get("lipOrderInversion", 1)) == 0
        and int(stable7.get("jawNeckConflict", 1)) == 0
        and int(stable7.get("silenceFalseMotion", 1)) == 0
        and face_mesh is not None
    )

    fingerprint = {
        "bodyAction": body_action.name,
        "actionFingerprint": action_fp,
        "keysFinal": keys,
        "keysHash": _sha_json(keys),
        "forearmFingerprint": forearm_fp,
        "timelineUid": TIMELINE_UID,
        "timelineSha256": timeline_sha,
        "bowPhases": gate7_once.get("phases"),
        "speechWindow": gate7_once.get("window"),
        "slidesFinal": slides,
        "maxDepthM": round(max_depth, 6),
        "shallowContactOk": shallow_ok,
        "fpsMeaningOk": bool(stable7.get("fpsMeaningOk")),
        "faceBodyTimelineDriftOk": bool(stable7.get("faceBodyTimelineDriftOk")),
        "eyeHeadDoubleOk": bool(stable7.get("eyeHeadDoubleOk")),
        "lipIntersection": int(stable7.get("lipIntersection", 1)),
        "lipOrderInversion": int(stable7.get("lipOrderInversion", 1)),
        "jawNeckConflict": int(stable7.get("jawNeckConflict", 1)),
        "silenceFalseMotion": int(stable7.get("silenceFalseMotion", 1)),
        "gate6BodyMutation": int(stable7.get("gate6BodyMutation", 1)),
        "sourceActionMutation": int(stable7.get("sourceActionMutation", 1)),
        "boneMappingOk": bool(mapping["ok"]),
        "lrSwapCount": len(lr.get("swaps") or []),
        "axisFailChains": axis_fail,
        "faceBindOk": face_ok,
        "frameStart": fs,
        "frameEnd": fe,
        "parameterHashGate8": parameter_hash(),
        "gate7ParameterHash": GATE7_FROZEN,
        "gate6ParameterHash": GATE6_FROZEN,
    }

    # Determinism payload excludes absolute file paths / wall-clock
    det_payload = {
        "actionFingerprint": action_fp,
        "keysHash": fingerprint["keysHash"],
        "forearmFingerprint": forearm_fp,
        "timelineSha256": timeline_sha,
        "bowPhases": fingerprint["bowPhases"],
        "speechWindow": fingerprint["speechWindow"],
        "slidesFinal": slides,
        "maxDepthM": fingerprint["maxDepthM"],
        "fpsMeaningOk": fingerprint["fpsMeaningOk"],
        "faceMetrics": {
            "driftOk": fingerprint["faceBodyTimelineDriftOk"],
            "eyeHead": fingerprint["eyeHeadDoubleOk"],
            "lipI": fingerprint["lipIntersection"],
            "lipO": fingerprint["lipOrderInversion"],
            "jaw": fingerprint["jawNeckConflict"],
            "sil": fingerprint["silenceFalseMotion"],
        },
        "lrSwapCount": fingerprint["lrSwapCount"],
        "axisFailChains": axis_fail,
    }

    return {
        "fingerprint": fingerprint,
        "determinismPayload": det_payload,
        "determinismHash": _sha_json(det_payload),
        "mapping": mapping,
        "lr": lr,
        "axis": {k: {"ok": v.get("ok"), "abnormal": len(v.get("abnormal") or [])} for k, v in axis.items()},
        "pen": {"maxDepthM": max_depth, "sustainedCount": int(pen.get("sustainedCount") or 0)},
        "slideOkSeed": slide_ok,
        "faceMesh": face_mesh.name if face_mesh else None,
    }


def run_clean_pipeline_once(
    *,
    fbx_path: Path,
    mesh_name: str,
    root: Path,
    seed_mode: bool = False,
) -> Dict:
    """One clean rebuild: Gate7 (includes Gate6 G3–G5) + Gate8 enrich. No dist artifact load."""
    from nurion_v05_body_motion.gate7.sync import run_gate7_once

    g7 = run_gate7_once(fbx_path=fbx_path, mesh_name=mesh_name, root=root)
    enriched = enrich_scene_fingerprint(root=root, gate7_once=g7, seed_mode=seed_mode)
    return {"gate7": g7, **enriched}
