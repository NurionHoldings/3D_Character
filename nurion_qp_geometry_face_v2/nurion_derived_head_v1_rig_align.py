"""v1 rig local-space alignment validation — no skin mutation."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    _boundary_loops,
    parse_obj,
    sha256_file,
)
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_nd_reconstruct import (
    V1_BASELINE_SKIN_SHA,
    validate_v1_basis,
)

JAW_PIVOT_GROUP = "joint-jaw"
ORAL_LOWER_GROUPS = ("helper-lower-teeth", "helper-tongue")
ORAL_UPPER_GROUPS = ("helper-upper-teeth",)
EYE_GROUPS = (
    "helper-l-eyelashes-1",
    "helper-l-eyelashes-2",
    "helper-r-eyelashes-1",
    "helper-r-eyelashes-2",
)
FLOAT_MAX_DIST = 0.35
MOUTH_Z_MIN = 0.95


def _group_centroid(rig, group: str) -> np.ndarray | None:
    vis: set[int] = set()
    for face, g in zip(rig.faces, rig.face_groups):
        if g == group:
            for vi, _ in face:
                vis.add(vi)
    if not vis:
        return None
    return rig.verts[list(vis)].mean(axis=0)


def _mouth_anchors(skin) -> tuple[np.ndarray, np.ndarray]:
    loops = _boundary_loops(skin)
    oral: list[np.ndarray] = []
    for loop in loops:
        verts = sorted({a for e in loop for a in e})
        pts = skin.verts[verts]
        cy, cz = float(pts[:, 1].mean()), float(pts[:, 2].mean())
        if cy > 6.55 and cz > 1.0 and abs(float(pts[:, 0].mean())) < 0.38:
            oral.append(pts.mean(axis=0))
    oral.sort(key=lambda x: -x[2])
    if not oral:
        c = skin.verts.mean(axis=0)
        return c, c
    outer = oral[0]
    inner = oral[1] if len(oral) > 1 else oral[0]
    return outer, inner


def validate_rig_alignment(skin_path: Path, rig_path: Path) -> dict[str, Any]:
    reasons: list[str] = []
    skin = parse_obj(skin_path)
    rig = parse_obj(rig_path)
    mouth_outer, mouth_inner = _mouth_anchors(skin)
    jaw = _group_centroid(rig, JAW_PIVOT_GROUP)
    if jaw is None:
        reasons.append("JAW_PIVOT_MISSING")

    floating = []
    group_dist: dict[str, float] = {}
    for g in ORAL_UPPER_GROUPS:
        c = _group_centroid(rig, g)
        if c is None:
            reasons.append(f"GROUP_MISSING:{g}")
            continue
        d_mouth = float(np.linalg.norm(c - mouth_outer))
        group_dist[g] = d_mouth
        if d_mouth > FLOAT_MAX_DIST:
            floating.append(g)

    for g in ORAL_LOWER_GROUPS:
        c = _group_centroid(rig, g)
        if c is None:
            reasons.append(f"GROUP_MISSING:{g}")
            continue
        d_mouth = float(np.linalg.norm(c - mouth_inner))
        group_dist[g] = d_mouth
        if d_mouth > FLOAT_MAX_DIST:
            floating.append(g)

    for g in EYE_GROUPS:
        c = _group_centroid(rig, g)
        if c is None:
            reasons.append(f"GROUP_MISSING:{g}")
            continue
        if float(c[2]) < 1.1 or float(c[1]) < 7.0:
            floating.append(g)

    if floating:
        reasons.append(f"FLOATING_ORAL_OR_EYE:{','.join(floating)}")

    upper = _group_centroid(rig, "helper-upper-teeth")
    lower = _group_centroid(rig, "helper-lower-teeth")
    tongue = _group_centroid(rig, "helper-tongue")
    if upper is not None and lower is not None and float(lower[1]) > float(upper[1]) + 0.05:
        reasons.append("LOWER_TEETH_ABOVE_UPPER")

    if jaw is not None and lower is not None:
        jaw_to_lower = float(np.linalg.norm(lower - jaw))
        if jaw_to_lower > 0.45:
            reasons.append(f"JAW_TO_LOWER_TEETH_DIST:{jaw_to_lower:.3f}")

    return {
        "skinSha256": sha256_file(skin_path),
        "rigPath": str(rig_path.name),
        "mouthAnchorOuter": [float(mouth_outer[0]), float(mouth_outer[1]), float(mouth_outer[2])],
        "mouthAnchorInner": [float(mouth_inner[0]), float(mouth_inner[1]), float(mouth_inner[2])],
        "jawPivot": [float(jaw[0]), float(jaw[1]), float(jaw[2])] if jaw is not None else None,
        "groupDistanceToMouth": group_dist,
        "floatingOralHelpers": floating,
        "floatingOralHelperCount": len([g for g in floating if "teeth" in g or "tongue" in g]),
        "sharedLocalSpace": "MAKEHUMAN_HEAD_LOCAL_UNCHANGED",
        "skinFaceDeletion": "DENY",
        "pass": len(reasons) == 0,
        "reasons": reasons,
    }


def validate_full(basis_dir: Path, corr_path: Path) -> dict[str, Any]:
    skin_path = basis_dir / "NURION_DerivedHead_v1_basis_skin.obj"
    rig_path = basis_dir / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
    basis = validate_v1_basis(skin_path, corr_path)
    align = validate_rig_alignment(skin_path, rig_path)
    combined_reasons = list(basis.get("reasons") or []) + list(align.get("reasons") or [])
    return {
        "basisValidation": basis,
        "rigAlignment": align,
        "pass": basis.get("pass") and align.get("pass"),
        "reasons": combined_reasons,
    }
