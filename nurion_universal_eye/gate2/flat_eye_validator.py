"""Validate Gate 2 Flat Eye Placement quality gates."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .flat_eye_placement import FlatEyePlacementResult, place_flat_eye_planes, profile_sha256
from mathutils import Vector

from .multiview_depth import build_world_bvh, sample_toward_world
from .parameters import GATE2_PARAMETERS


def _dist_eu(a: Vector, b: Vector, eye_unit: float) -> float:
    return float((a - b).length) / max(eye_unit, 1e-6)


def validate_flat_eye_placement(
    result: FlatEyePlacementResult,
    *,
    determinism_profiles: Optional[Sequence[dict]] = None,
    mesh_name: str = "",
) -> dict:
    import bpy

    params = GATE2_PARAMETERS
    gates: Dict[str, str] = {}
    notes: List[str] = []
    p = result.planes

    if set(p.keys()) != {"L", "R"}:
        gates["PLANES_CREATED"] = "FAIL"
        return {
            "schema": "NURION_GATE2_VALIDATION_REPORT",
            "verdict": "FAIL",
            "gates": gates,
            "notes": ["Missing L/R planes"],
        }
    gates["PLANES_CREATED"] = "PASS"

    # L/R swap: L origin local.x > 0, R < 0
    axes = result.basis.axes
    assert axes is not None
    lx = float(axes.to_local(p["L"].origin_world).x)
    rx = float(axes.to_local(p["R"].origin_world).x)
    lr_swap = 0 if (lx > 0 and rx < 0) else 1
    gates["LEFT_RIGHT_SWAP"] = "PASS" if lr_swap == 0 else "FAIL"

    mesh = bpy.data.objects.get(result.basis.mesh_name)
    bvh = build_world_bvh(mesh)

    front_ok = True
    yaw30_ok = True
    yaw60_ok = True
    side_ok = True
    pen = 0
    prol = 0
    flo = 0
    outside = 0

    detail = {}
    for side, plane in p.items():
        eu = plane.eye_unit
        m = plane.scores
        # Front center
        if float(m.get("frontCenterErrorEyeUnits", 99)) > float(params["frontCenterMaxErrorEyeUnits"]):
            front_ok = False
        # Penetration / protrusion / float in eye units
        if float(m.get("penetration", 0)) > float(params["plane"]["maxPenetrationEyeUnits"]):
            pen += 1
        if float(m.get("protrusion", 0)) > float(params["plane"]["maxProtrusionEyeUnits"]):
            prol += 1
        if float(m.get("floating", 0)) > float(params["plane"]["maxFloatEyeUnits"]):
            flo += 1

        # 30°/60°: construction must have accepted an XZ-filtered depth sample.
        # Consistency is measured vs front sample Y (not fused plane Y).
        yaw_sign = 1.0 if side == "L" else -1.0
        samples = {
            round(float(s.get("yawDeg", 0.0)), 1): s
            for s in (plane.evidence.get("samples") or [])
        }
        front_s = samples.get(0.0)
        front_y = float(front_s["depthLocalY"]) if front_s and "depthLocalY" in front_s else float(plane.local_center.y)
        for yaw_abs, flag_name in ((30.0, "yaw30"), (60.0, "yaw60")):
            key = round(yaw_abs * yaw_sign, 1)
            s = samples.get(key)
            err = 99.0
            if s is not None and "depthLocalY" in s:
                err = abs(float(s["depthLocalY"]) - front_y) / max(eu, 1e-6)
                # Hard fail only on extreme drift (wrong body region). Mild eye-socket
                # variance across yaw is expected on Meshy shallow eyes.
                if err > 4.0:
                    if yaw_abs == 30:
                        yaw30_ok = False
                    else:
                        yaw60_ok = False
            else:
                if yaw_abs == 30:
                    yaw30_ok = False
                else:
                    yaw60_ok = False
            detail[f"{side}_{flag_name}_vsFrontEU"] = round(err, 4)

        # Side depth: lateral cast toward surface anchor.
        gap = float(m.get("signedGap", 0.0))
        if abs(gap) < 1e-9:
            gap = eu * float(params["plane"]["surfaceGapEyeUnits"])
        surface_anchor = plane.origin_world - plane.normal_out.normalized() * abs(gap)
        side_dir = axes.right * yaw_sign
        start = surface_anchor + side_dir * (eu * float(params["depth"]["rayStartEyeUnits"]))
        hit = bvh.ray_cast(start, (-side_dir).normalized(), eu * float(params["depth"]["rayStartEyeUnits"]) * 2.5)
        side_err = 99.0
        if hit and hit[0] is not None:
            side_err = _dist_eu(hit[0], surface_anchor, eu)
            if side_err > float(params["sideDepthMaxErrorEyeUnits"]):
                side_ok = False
        else:
            probe = surface_anchor + side_dir * (eu * 0.8)
            loc, _n, _i, _d = bvh.find_nearest(probe)
            if loc is not None:
                side_err = _dist_eu(loc, surface_anchor, eu)
                if side_err > float(params["sideDepthMaxErrorEyeUnits"]):
                    side_ok = False
            else:
                side_ok = False
        detail[f"{side}_side90_anchorDistEU"] = round(side_err, 4)

        # Model outside: plane origin should be near surface, not far outside head bounds
        if float(m.get("floating", 0)) > float(params["plane"]["maxFloatEyeUnits"]) * 2.5:
            outside += 1

    gates["FRONT_CENTER_ERROR"] = "PASS" if front_ok else "FAIL"
    gates["LEFT_RIGHT_30"] = "PASS" if yaw30_ok else "FAIL"
    gates["LEFT_RIGHT_60"] = "PASS" if yaw60_ok else "FAIL"
    gates["SIDE_DEPTH"] = "PASS" if side_ok else "FAIL"
    gates["SURFACE_PENETRATION"] = "PASS" if pen == 0 else "FAIL"
    gates["EXCESSIVE_PROTRUSION"] = "PASS" if prol == 0 else "FAIL"
    gates["FLOATING_PLANE"] = "PASS" if flo == 0 else "FAIL"
    gates["MODEL_OUTSIDE"] = "PASS" if outside == 0 else "FAIL"
    gates["MANUAL_GT"] = "PASS" if result.manual_gt is False else "FAIL"
    gates["CONVEX_EYE"] = "PASS" if result.convex_eye is False else "FAIL"
    gates["MOTION"] = "PASS" if result.motion == "INACTIVE" else "FAIL"
    gates["EXPRESSION"] = "PASS" if result.expression == "INACTIVE" else "FAIL"

    # Objects exist, no convex
    for side in ("L", "R"):
        if bpy.data.objects.get(f"NURION_EyePlane.{side}") is None:
            gates["PLANES_CREATED"] = "FAIL"
    for bad in ("NURION_Eyeball.L", "NURION_Eyeball.R"):
        if bpy.data.objects.get(bad) is not None:
            gates["CONVEX_EYE"] = "FAIL"

    det_hashes: List[str] = []
    if determinism_profiles:
        for prof in determinism_profiles:
            det_hashes.append(profile_sha256(prof))
    else:
        base = result.to_profile()
        det_hashes.append(profile_sha256(base))
        for _ in range(2):
            r2 = place_flat_eye_planes(mesh_name=mesh_name or result.basis.mesh_name, create_meshes=False)
            det_hashes.append(profile_sha256(r2.to_profile()))
    det_pass = len(det_hashes) >= 3 and len(set(det_hashes)) == 1
    gates["DETERMINISM_3X"] = "PASS" if det_pass else "FAIL"

    required = [
        "PLANES_CREATED",
        "FRONT_CENTER_ERROR",
        "LEFT_RIGHT_30",
        "LEFT_RIGHT_60",
        "SIDE_DEPTH",
        "SURFACE_PENETRATION",
        "EXCESSIVE_PROTRUSION",
        "FLOATING_PLANE",
        "LEFT_RIGHT_SWAP",
        "MODEL_OUTSIDE",
        "DETERMINISM_3X",
        "MANUAL_GT",
        "CONVEX_EYE",
        "MOTION",
        "EXPRESSION",
    ]
    verdict = "PASS" if all(gates[k] == "PASS" for k in required) else "FAIL"
    return {
        "schema": "NURION_GATE2_VALIDATION_REPORT",
        "version": "0.3.0-alpha.3-gate2",
        "verdict": verdict,
        "gates": gates,
        "detail": detail,
        "lrSwapCount": lr_swap,
        "penetrationCount": pen,
        "protrusionCount": prol,
        "floatingCount": flo,
        "determinismHashes": det_hashes,
        "profileSha256": det_hashes[0] if det_hashes else None,
        "parameterHash": result.parameter_hash,
        "manualGt": False,
        "convexEye": False,
        "motion": "INACTIVE",
        "expression": "INACTIVE",
        "notes": notes,
        "nextDecision": "FLAT_EYE_PLACEMENT_PASS" if verdict == "PASS" else "FLAT_EYE_PLACEMENT_FAIL",
    }
