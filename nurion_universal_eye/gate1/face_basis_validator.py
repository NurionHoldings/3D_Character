"""Validate Gate 1 Universal Face Basis quality gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from .universal_face_basis import UniversalFaceBasis, build_universal_face_basis, profile_sha256


def _stable(profile: dict) -> dict:
    """Drop volatile paths before determinism hash if present."""
    p = json.loads(json.dumps(profile))
    p.pop("timestamp", None)
    return p


def validate_face_basis(
    basis: UniversalFaceBasis,
    *,
    evidence: Optional[dict] = None,
    determinism_profiles: Optional[Sequence[dict]] = None,
) -> dict:
    profile = basis.to_profile()
    gates: Dict[str, str] = {}
    notes: List[str] = []

    axes_ok = bool(basis.flags.get("headLocalAxesStable")) and basis.axes is not None
    gates["HEAD_LOCAL_AXES_STABLE"] = "PASS" if axes_ok else "FAIL"

    fwd_ok = bool(basis.flags.get("faceForwardResolved")) and basis.face_forward is not None
    gates["FACE_FORWARD_RESOLVED"] = "PASS" if fwd_ok else "FAIL"

    sym_ok = bool(basis.flags.get("symmetryPlaneResolved")) and basis.symmetry_normal is not None
    gates["SYMMETRY_PLANE_RESOLVED"] = "PASS" if sym_ok else "FAIL"

    lr_swap = int(basis.evidence.get("lrSwapCount", 1 if not basis.flags.get("leftRightSwapZero") else 0))
    gates["LEFT_RIGHT_SWAP"] = "PASS" if lr_swap == 0 else "FAIL"

    world_dep = 0 if basis.flags.get("worldTransformDependencyZero") else 1
    gates["WORLD_TRANSFORM_DEPENDENCY"] = "PASS" if world_dep == 0 else "FAIL"

    model_out = 0 if basis.flags.get("modelOutsideZero") else 1
    gates["MODEL_OUTSIDE"] = "PASS" if model_out == 0 else "FAIL"

    # Eyes present for unit computation (not visual eyes).
    if set(basis.eye_regions.keys()) != {"L", "R"}:
        notes.append("Eye region L/R incomplete — Eye Unit partially unresolved")
        gates["EYE_REGIONS_RESOLVED"] = "FAIL"
    else:
        gates["EYE_REGIONS_RESOLVED"] = "PASS"

    gates["MANUAL_GT_USED"] = "PASS" if basis.manual_gt_used is False else "FAIL"
    gates["VISUAL_EYE_GENERATED"] = "PASS" if basis.visual_eye_generated is False else "FAIL"

    # Determinism
    det_hashes: List[str] = []
    if determinism_profiles:
        for p in determinism_profiles:
            det_hashes.append(profile_sha256(_stable(p)))
    else:
        # Recompute 2 more times in-scene for 3× total if caller didn't supply.
        det_hashes.append(profile_sha256(_stable(profile)))
        for _ in range(2):
            b2 = build_universal_face_basis(mesh_name=basis.mesh_name)
            det_hashes.append(profile_sha256(_stable(b2.to_profile())))

    det_pass = len(det_hashes) >= 3 and len(set(det_hashes)) == 1
    gates["DETERMINISM_3X"] = "PASS" if det_pass else "FAIL"

    evidence_ok = True
    if evidence is not None:
        views = evidence.get("views") or []
        needed = {"FRONT", "LEFT_30", "LEFT_60", "LEFT_90", "RIGHT_30", "RIGHT_60", "RIGHT_90"}
        have = {v.get("view") for v in views}
        evidence_ok = needed.issubset(have)
        gates["MULTIVIEW_EVIDENCE"] = "PASS" if evidence_ok else "FAIL"
    else:
        gates["MULTIVIEW_EVIDENCE"] = "SKIP"

    required = [
        "HEAD_LOCAL_AXES_STABLE",
        "FACE_FORWARD_RESOLVED",
        "SYMMETRY_PLANE_RESOLVED",
        "LEFT_RIGHT_SWAP",
        "WORLD_TRANSFORM_DEPENDENCY",
        "MODEL_OUTSIDE",
        "DETERMINISM_3X",
        "MANUAL_GT_USED",
        "VISUAL_EYE_GENERATED",
        "EYE_REGIONS_RESOLVED",
    ]
    hard_pass = all(gates[k] == "PASS" for k in required)
    verdict = "PASS" if hard_pass else "FAIL"

    return {
        "schema": "NURION_GATE1_VALIDATION_REPORT",
        "version": "0.3.0-alpha.3-gate1",
        "verdict": verdict,
        "gates": gates,
        "lrSwapCount": lr_swap,
        "worldTransformDependency": world_dep,
        "modelOutside": model_out,
        "determinismHashes": det_hashes,
        "profileSha256": profile_sha256(_stable(profile)),
        "confidences": profile.get("confidences", {}),
        "eyeUnits": profile.get("eyeUnits", {}),
        "notes": notes,
        "manualGtUsed": False,
        "visualEyeGenerated": False,
        "nextDecision": "UNIVERSAL_FACE_BASIS_PASS" if verdict == "PASS" else "UNIVERSAL_FACE_BASIS_FAIL",
    }


def write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
