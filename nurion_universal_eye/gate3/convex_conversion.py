"""
Gate 3 — Convex Conversion.

Creates NURION_EyeDome.* from locked EyePlane.* without mutating plane pose/size.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mathutils import Matrix, Vector

from ..gate1.universal_face_basis import _v3
from ..gate2.flat_eye_placement import EyePlaneResult, FlatEyePlacementResult, place_flat_eye_planes
from ..gate2.multiview_depth import build_world_bvh
from .eye_dome_mesh import create_or_replace_dome, remove_domes
from .lock_guard import assert_gate12_locked
from .parameters import GATE3_PARAMETERS, parameter_hash


def _plane_snapshot(planes: Dict[str, EyePlaneResult]) -> dict:
    out = {}
    for side, p in planes.items():
        out[side] = {
            "origin": _v3(p.origin_world),
            "normal": _v3(p.normal_out),
            "right": _v3(p.right),
            "up": _v3(p.up),
            "width": round(float(p.width), 6),
            "height": round(float(p.height), 6),
        }
    return out


def _snapshots_equal(a: dict, b: dict, eu: float) -> Tuple[bool, dict]:
    lim = GATE3_PARAMETERS["limits"]
    detail = {}
    ok = True
    for side in ("L", "R"):
        pa, pb = a[side], b[side]
        drift = (Vector(pa["origin"]) - Vector(pb["origin"])).length / max(eu, 1e-9)
        # rotation via normal angle
        na, nb = Vector(pa["normal"]), Vector(pb["normal"])
        cos = max(-1.0, min(1.0, float(na.normalized().dot(nb.normalized()))))
        ang = math.degrees(math.acos(cos))
        detail[side] = {"centerDriftEU": round(drift, 9), "rotationDeltaDeg": round(ang, 6)}
        if drift > float(lim["maxCenterDriftEyeUnits"]) or ang > float(lim["maxRotationDeltaDeg"]):
            ok = False
        if abs(pa["width"] - pb["width"]) > 1e-9 or abs(pa["height"] - pb["height"]) > 1e-9:
            ok = False
            detail[side]["sizeMutated"] = True
    return ok, detail


def _skin_clearance_eu(bvh, plane: EyePlaneResult) -> float:
    """Positive if visible skin lies outside the frozen EyePlane along its normal."""
    eu = float(plane.eye_unit)
    nrm = plane.normal_out.normalized()
    start = plane.origin_world + nrm * (eu * 4.0)
    hit = bvh.ray_cast(start, (-nrm), eu * 8.0)
    if hit is None or hit[0] is None:
        return 0.0
    # If skin is outside the plane, clearance > 0 (plane buried / flush behind skin).
    return max(0.0, float((hit[0] - plane.origin_world).dot(nrm)) / max(eu, 1e-9))


def _world_dome_samples(plane: EyePlaneResult, total_bulge: float, n: int = 48) -> List[Tuple[Vector, float]]:
    """Sample dome points; returns (world, radial01). Boundary keeps z=0 on EyePlane."""
    hw, hh = plane.width * 0.5, plane.height * 0.5
    pts: List[Tuple[Vector, float]] = []
    pts.append((plane.origin_world + plane.normal_out * total_bulge, 0.0))
    for r_i in (0.35, 0.7, 0.95, 1.0):
        for k in range(8):
            ang = (k / 8.0) * math.tau
            x = math.cos(ang) * hw * r_i
            y = math.sin(ang) * hh * r_i
            z = total_bulge * max(0.0, 1.0 - r_i * r_i)
            p = plane.origin_world + plane.right * x + plane.up * y + plane.normal_out * z
            pts.append((p, r_i))
    return pts[:n]


def _score_candidate(
    *,
    bvh,
    plane: EyePlaneResult,
    artistic_bulge: float,
    level: str,
) -> Dict:
    eu = float(plane.eye_unit)
    lim = GATE3_PARAMETERS["limits"]
    w = GATE3_PARAMETERS["scoring"]
    clearance_eu = _skin_clearance_eu(bvh, plane)
    # Total apex height clears buried plane then adds artistic convexity (Eye Unit ratio).
    total_bulge = (clearance_eu + artistic_bulge / max(eu, 1e-9)) * eu
    samples = _world_dome_samples(plane, total_bulge)
    pen = 0.0
    prol_max = total_bulge / max(eu, 1e-9)
    outside = 0
    boundary_err = 0.0
    nrm = plane.normal_out.normalized()

    # Boundary invariant: ellipse edge stays on EyePlane (analytic z=0).
    for p, r_i in samples:
        if r_i >= 0.98:
            local_h = float((p - plane.origin_world).dot(nrm))
            boundary_err = max(boundary_err, abs(local_h) / max(eu, 1e-9))

    # Apex vs center skin — ring samples skip mesh penetration (lid/lash variance).
    apex = plane.origin_world + nrm * total_bulge
    start = plane.origin_world + nrm * (eu * 4.0)
    hit = bvh.ray_cast(start, (-nrm), eu * 8.0)
    if hit is None or hit[0] is None:
        outside = 1
    else:
        skin = hit[0]
        behind = float((skin - apex).dot(nrm))
        if behind > eu * 0.08:
            pen = behind / max(eu, 1e-9)
        ahead = float((apex - skin).dot(nrm))
        if ahead > float(lim["maxOutsideEyeUnits"]) * eu:
            outside = 1

    art_eu = artistic_bulge / max(eu, 1e-9)
    silhouette = max(0.0, 1.0 - abs(art_eu - float(GATE3_PARAMETERS["candidates"][level]["bulgeEyeUnits"])) * 0.01)
    # Prefer medium clearance-aware apex just outside skin.
    if hit is not None and hit[0] is not None:
        silhouette = max(silhouette, max(0.0, 1.0 - abs(float((apex - hit[0]).dot(nrm)) / max(eu, 1e-9) - art_eu) * 0.25))
    score = (
        1.0
        + float(w["planeBaselineBonus"])
        - float(w["wPenetration"]) * pen
        - float(w["wProtrusion"]) * max(0.0, art_eu - float(lim["maxProtrusionEyeUnits"]) * 0.5)
        - float(w["wBoundary"]) * boundary_err
        + float(w["wSilhouette"]) * silhouette
    )
    valid = (
        pen <= float(lim["maxPenetrationEyeUnits"])
        and art_eu <= float(lim["maxProtrusionEyeUnits"])
        and outside == 0
        and boundary_err <= float(GATE3_PARAMETERS["mesh"]["boundaryEpsilonEyeUnits"])
    )
    return {
        "level": level,
        "bulgeEyeUnits": round(art_eu, 6),
        "clearanceEyeUnits": round(clearance_eu, 6),
        "totalBulgeEyeUnits": round(total_bulge / max(eu, 1e-9), 6),
        "bulgeM": round(float(total_bulge), 6),
        "score": round(float(score), 4),
        "valid": valid,
        "penetrationEU": round(pen, 4),
        "protrusionEU": round(prol_max, 4),
        "boundaryErrEU": round(boundary_err, 4),
        "outsideCount": outside,
        "silhouette": round(float(silhouette), 4),
    }


@dataclass
class ConvexConversionResult:
    flat: FlatEyePlacementResult
    selected: Dict[str, str] = field(default_factory=dict)
    candidates: Dict[str, List[Dict]] = field(default_factory=dict)
    planeSnapshotBefore: dict = field(default_factory=dict)
    planeSnapshotAfter: dict = field(default_factory=dict)
    planeUnchanged: bool = True
    planeDelta: dict = field(default_factory=dict)
    parameter_hash: str = ""
    restored_to_plane: bool = False
    gate12_lock: dict = field(default_factory=dict)

    def to_profile(self) -> dict:
        return {
            "schema": "NURION_CONVEX_CONVERSION_PROFILE",
            "version": "0.3.0-alpha.3-gate3",
            "parameterHash": self.parameter_hash,
            "gate2ParameterHash": self.flat.parameter_hash,
            "selected": dict(self.selected),
            "candidates": self.candidates,
            "planeSnapshotBefore": self.planeSnapshotBefore,
            "planeSnapshotAfter": self.planeSnapshotAfter,
            "planeUnchanged": self.planeUnchanged,
            "planeDelta": self.planeDelta,
            "restoredToPlane": self.restored_to_plane,
            "gazeMotion": "INACTIVE",
            "blink": "INACTIVE",
            "expression": "INACTIVE",
            "headMotion": "INACTIVE",
            "lipSync": "INACTIVE",
            "beautyMaterial": "HOLD",
            "convexFullEyeball": False,
            "outputs": ["NURION_EyeDome.L", "NURION_EyeDome.R"],
            "planesFrozen": ["NURION_EyePlane.L", "NURION_EyePlane.R"],
        }


def convert_eye_domes(
    *,
    mesh_name: str = "",
    root: Optional[Path] = None,
    create_meshes: bool = True,
) -> ConvexConversionResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate12_locked(root)

    # Rebuild locked Gate2 planes (Gate2 code unchanged).
    flat = place_flat_eye_planes(mesh_name=mesh_name, create_meshes=True, root=root)
    if flat.parameter_hash != GATE3_PARAMETERS["requiredGate2ParameterHash"]:
        raise RuntimeError("Gate2 parameter hash mismatch under Gate3")

    before = _plane_snapshot(flat.planes)
    import bpy

    mesh = bpy.data.objects.get(flat.basis.mesh_name)
    bvh = build_world_bvh(mesh)
    params = GATE3_PARAMETERS
    diag = params["diagnostic"]

    if create_meshes:
        remove_domes()

    candidates: Dict[str, List[Dict]] = {"L": [], "R": []}
    selected: Dict[str, str] = {}
    bulges_sel: Dict[str, float] = {}

    for side, plane in flat.planes.items():
        eu = float(plane.eye_unit)
        scored = []
        for level, cfg in params["candidates"].items():
            artistic = eu * float(cfg["bulgeEyeUnits"])
            sc = _score_candidate(bvh=bvh, plane=plane, artistic_bulge=artistic, level=level)
            sc["label"] = cfg["label"]
            scored.append(sc)
        candidates[side] = scored
        valid = [s for s in scored if s["valid"]]
        pick = max(valid, key=lambda s: s["score"]) if valid else None
        if pick is None:
            selected[side] = "NONE"
            bulges_sel[side] = 0.0
        else:
            selected[side] = pick["level"]
            bulges_sel[side] = float(pick["bulgeM"])

    # L/R consistency soft preference
    if selected["L"] != "NONE" and selected["R"] != "NONE":
        bl, br = bulges_sel["L"], bulges_sel["R"]
        rel = abs(bl - br) / max(bl, br, 1e-9)
        if rel > float(params["limits"]["lrBulgeRelDiffMax"]):
            # Prefer shared level with best combined score
            best_pair = None
            best_score = -1e9
            for level in params["candidates"]:
                sl = next(s for s in candidates["L"] if s["level"] == level)
                sr = next(s for s in candidates["R"] if s["level"] == level)
                if not (sl["valid"] and sr["valid"]):
                    continue
                comb = sl["score"] + sr["score"]
                if comb > best_score:
                    best_score = comb
                    best_pair = level
            if best_pair is not None:
                selected["L"] = selected["R"] = best_pair
                bulges_sel["L"] = next(s["bulgeM"] for s in candidates["L"] if s["level"] == best_pair)
                bulges_sel["R"] = next(s["bulgeM"] for s in candidates["R"] if s["level"] == best_pair)

    restored = False
    if selected["L"] == "NONE" and selected["R"] == "NONE":
        restored = True
        if create_meshes:
            remove_domes()
    elif create_meshes:
        for side, plane in flat.planes.items():
            rgba = diag["leftRGBA"] if side == "L" else diag["rightRGBA"]
            # Create all candidates: hide non-selected
            for sc in candidates[side]:
                level = sc["level"]
                name = f"NURION_EyeDome.{side}.{level}"
                # Use scored total bulge (clearance + artistic) so apex clears skin.
                bulge = float(sc["bulgeM"])
                hide = level != selected[side] or selected[side] == "NONE"
                create_or_replace_dome(
                    name=name,
                    origin=plane.origin_world,
                    right=plane.right,
                    up=plane.up,
                    normal=plane.normal_out,
                    width=plane.width,
                    height=plane.height,
                    bulge=bulge,
                    rgba=rgba,
                    hide=hide,
                )
            # Active alias without level suffix for downstream
            if selected[side] != "NONE":
                active = bpy.data.objects.get(f"NURION_EyeDome.{side}.{selected[side]}")
                alias = f"NURION_EyeDome.{side}"
                old = bpy.data.objects.get(alias)
                if old is not None:
                    bpy.data.objects.remove(old, do_unlink=True)
                if active is not None:
                    dup = active.copy()
                    dup.data = active.data.copy()
                    dup.name = alias
                    bpy.context.collection.objects.link(dup)
                    dup.hide_render = False
                    dup.hide_viewport = False

    # Verify planes untouched in scene objects
    after = _plane_snapshot(flat.planes)
    # Also read live EyePlane object matrices if present
    for side, plane in flat.planes.items():
        obj = bpy.data.objects.get(f"NURION_EyePlane.{side}")
        if obj is not None:
            # Ensure object matrix still matches snapshot
            loc = obj.matrix_world.translation
            drift = (loc - plane.origin_world).length
            if drift > 1e-6:
                raise RuntimeError(f"EyePlane.{side} mutated during Gate3")

    mean_eu = sum(float(p.eye_unit) for p in flat.planes.values()) / 2.0
    unchanged, delta = _snapshots_equal(before, after, mean_eu)

    return ConvexConversionResult(
        flat=flat,
        selected=selected,
        candidates=candidates,
        planeSnapshotBefore=before,
        planeSnapshotAfter=after,
        planeUnchanged=unchanged,
        planeDelta=delta,
        parameter_hash=parameter_hash(),
        restored_to_plane=restored,
        gate12_lock=lock_info,
    )


def profile_sha256(profile: dict) -> str:
    payload = json.dumps(profile, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
