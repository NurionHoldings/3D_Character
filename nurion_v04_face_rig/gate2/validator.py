"""Gate 2 validators."""

from __future__ import annotations

from typing import Dict, List

from .face_clone import snapshot_mesh_vertices, snapshots_equal
from .parameters import GATE1_FROZEN_HASH, GATE2_PARAMETERS, V03_RC1_SHA256, parameter_hash


def verify_hashes(root) -> Dict:
    import hashlib
    from pathlib import Path

    from ..gate1.parameters import parameter_hash as g1_hash

    root = Path(root)
    pkg = root / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    h = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    g1 = g1_hash()
    return {
        "v03": "UNCHANGED" if h == V03_RC1_SHA256 else "CHANGED",
        "v03Sha256": h,
        "gate1": "UNCHANGED" if g1 == GATE1_FROZEN_HASH else "CHANGED",
        "gate1Hash": g1,
    }


def validate_guides_inside_face(landmarks, axes, head_height: float) -> Dict:
    hh = max(float(head_height), 1e-4)
    inv = axes.matrix_world_inv
    outside = 0
    for key, pos in landmarks.items():
        if key in ("head.origin",):
            continue
        loc = inv @ pos
        ok = abs(loc.x) < 0.5 * hh and -0.25 * hh < loc.y < 0.6 * hh and -0.3 * hh < loc.z < 0.85 * hh
        if not ok:
            outside += 1
    return {"guideOutsideFace": outside, "status": "PASS" if outside == 0 else "FAIL"}


def validate_lr_swap(landmarks, axes) -> Dict:
    inv = axes.matrix_world_inv
    swaps = 0
    pairs = [
        ("mouth.corner.L", "mouth.corner.R"),
        ("cheek.L", "cheek.R"),
        ("brow.inner.L", "brow.inner.R"),
        ("brow.mid.L", "brow.mid.R"),
        ("brow.outer.L", "brow.outer.R"),
    ]
    for l, r in pairs:
        if l not in landmarks or r not in landmarks:
            continue
        lx = float((inv @ landmarks[l]).x)
        rx = float((inv @ landmarks[r]).x)
        if not (lx < 0 and rx > 0):
            swaps += 1
    return {"lrSwap": swaps, "status": "PASS" if swaps == 0 else "FAIL"}


def validate_bone_hierarchy(arm_obj) -> Dict:
    required = set(GATE2_PARAMETERS["bones"]) | {"face.root"}
    have = {b.name for b in arm_obj.data.bones}
    missing = sorted(required - have)
    # parents
    parent_ok = True
    for b in arm_obj.data.bones:
        if b.name == "face.root":
            continue
        if b.parent is None:
            parent_ok = False
    return {
        "missingBones": missing,
        "parentOk": parent_ok,
        "status": "PASS" if not missing and parent_ok else "FAIL",
    }


def build_gate_report(
    *,
    source_before,
    source_after,
    clone_info: Dict,
    guide_val: Dict,
    lr_val: Dict,
    hierarchy: Dict,
    weights: Dict,
    poses: Dict,
    hashes: Dict,
    basis_before,
    basis_after,
) -> Dict:
    tol = GATE2_PARAMETERS["tolerances"]
    src_mut = 0 if snapshots_equal(source_before, source_after, eps=1e-9) else 1
    # Neutral vertex drift on candidate at rest vs source snapshot shape equality at create
    neutral_drift = 0 if clone_info.get("neutralIdenticalAtCreate") else 1

    # basis drift — compare origin/forward/up
    def basis_tuple(ax):
        return (
            round(ax.origin.x, 8),
            round(ax.origin.y, 8),
            round(ax.origin.z, 8),
            round(ax.forward.x, 8),
            round(ax.forward.y, 8),
            round(ax.forward.z, 8),
            round(ax.up.x, 8),
            round(ax.up.y, 8),
            round(ax.up.z, 8),
        )

    basis_drift = 0 if basis_tuple(basis_before) == basis_tuple(basis_after) else 1

    gates = {
        "SOURCE_MUTATION": 0 if src_mut == 0 else 1,
        "NEUTRAL_VERTEX_DRIFT": 0 if neutral_drift == 0 else 1,
        "HEAD_LOCAL_BASIS_DRIFT": 0 if basis_drift == 0 else 1,
        "GUIDE_OUTSIDE_FACE": guide_val.get("guideOutsideFace", 99),
        "LR_SWAP": lr_val.get("lrSwap", 99),
        "NON_FACE_WEIGHT_LEAK": weights.get("nonFaceWeightLeak", 99),
        "TEETH_WEIGHT_LEAK": weights.get("teethWeightLeak", 99),
        "BONE_HIERARCHY": hierarchy.get("status", "FAIL"),
        "LOW_AMPLITUDE_DEFORM": poses.get("lowAmplitudeDeform", "FAIL"),
        "NEUTRAL_RETURN_ERROR": poses.get("neutralReturn", "FAIL"),
        "V03_GATE1_HASH": "UNCHANGED"
        if hashes.get("v03") == "UNCHANGED" and hashes.get("gate1") == "UNCHANGED"
        else "CHANGED",
    }

    def ok(name, val):
        if name in ("BONE_HIERARCHY", "LOW_AMPLITUDE_DEFORM", "NEUTRAL_RETURN_ERROR", "V03_GATE1_HASH"):
            return val == "PASS" or val == "UNCHANGED"
        return val == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE2_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
        "poses": poses.get("poses"),
        "neutralReturnErrorEU": poses.get("neutralReturnErrorEU"),
    }
