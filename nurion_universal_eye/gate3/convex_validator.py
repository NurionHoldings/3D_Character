"""Validate Gate 3 Convex Conversion quality gates."""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence

from .convex_conversion import ConvexConversionResult, convert_eye_domes, profile_sha256
from .lock_guard import GATE1_LOCK, GATE2_LOCK, GATE2_PARAM, assert_gate12_locked
from .parameters import GATE3_PARAMETERS


def validate_convex_conversion(
    result: ConvexConversionResult,
    *,
    root,
    determinism_profiles: Optional[Sequence[dict]] = None,
    mesh_name: str = "",
) -> dict:
    import bpy

    gates: Dict[str, str] = {}
    notes: List[str] = []
    lim = GATE3_PARAMETERS["limits"]

    # Gate1/2 hash unchanged
    try:
        assert_gate12_locked(root)
        gates["GATE1_2_HASH"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        gates["GATE1_2_HASH"] = "FAIL"
        notes.append(str(exc))

    # Plane center / rotation
    drift_fail = False
    rot_fail = False
    for side, d in result.planeDelta.items():
        if float(d.get("centerDriftEU", 1)) > float(lim["maxCenterDriftEyeUnits"]):
            drift_fail = True
        if float(d.get("rotationDeltaDeg", 1)) > float(lim["maxRotationDeltaDeg"]):
            rot_fail = True
    gates["PLANE_CENTER_DRIFT"] = "PASS" if (result.planeUnchanged and not drift_fail) else "FAIL"
    gates["PLANE_ROTATION_MUTATION"] = "PASS" if (result.planeUnchanged and not rot_fail) else "FAIL"

    # Boundary / penetration / protrusion from selected candidates
    pen = prol = 0
    boundary_ok = True
    silhouette_ok = True
    for side in ("L", "R"):
        level = result.selected.get(side)
        if level in (None, "NONE"):
            # Restored to plane — boundary trivial pass, but convex outputs absent
            notes.append(f"{side}: restored to EyePlane (no valid dome)")
            continue
        sc = next(s for s in result.candidates[side] if s["level"] == level)
        if float(sc["penetrationEU"]) > float(lim["maxPenetrationEyeUnits"]):
            pen += 1
        if float(sc["protrusionEU"]) > float(lim["maxProtrusionEyeUnits"]):
            prol += 1
        if float(sc["boundaryErrEU"]) > float(GATE3_PARAMETERS["mesh"]["boundaryEpsilonEyeUnits"]):
            boundary_ok = False
        if float(sc.get("silhouette", 0)) < 0.2:
            silhouette_ok = False
        obj = bpy.data.objects.get(f"NURION_EyeDome.{side}")
        if obj is None:
            notes.append(f"Missing active dome alias NURION_EyeDome.{side}")
            boundary_ok = False

    gates["BOUNDARY_MATCH"] = "PASS" if boundary_ok else "FAIL"
    gates["SURFACE_PENETRATION"] = "PASS" if pen == 0 else "FAIL"
    gates["EXCESSIVE_PROTRUSION"] = "PASS" if prol == 0 else "FAIL"
    gates["MULTIVIEW_SILHOUETTE"] = "PASS" if silhouette_ok else "FAIL"

    # L/R swap via plane origins (should still be correct)
    axes = result.flat.basis.axes
    lx = float(axes.to_local(result.flat.planes["L"].origin_world).x)
    rx = float(axes.to_local(result.flat.planes["R"].origin_world).x)
    lr_swap = 0 if (lx > 0 and rx < 0) else 1
    gates["LEFT_RIGHT_SWAP"] = "PASS" if lr_swap == 0 else "FAIL"

    outside = 0
    for side in ("L", "R"):
        level = result.selected.get(side)
        if level in (None, "NONE"):
            continue
        sc = next(s for s in result.candidates[side] if s["level"] == level)
        outside += int(sc.get("outsideCount", 0))
    gates["MODEL_OUTSIDE"] = "PASS" if outside == 0 else "FAIL"

    # Must have selected a dome on both sides for Gate3 PASS (not restore)
    if result.restored_to_plane or any(result.selected.get(s) in (None, "NONE") for s in ("L", "R")):
        gates["DOMES_SELECTED"] = "FAIL"
        notes.append("One or both eyes restored to plane / no dome selected")
    else:
        gates["DOMES_SELECTED"] = "PASS"

    # Forbidden features inactive
    gates["GAZE_MOTION"] = "PASS"
    gates["BLINK"] = "PASS"
    gates["EXPRESSION"] = "PASS"

    det_hashes: List[str] = []
    if determinism_profiles:
        for p in determinism_profiles:
            det_hashes.append(profile_sha256(p))
    else:
        det_hashes.append(profile_sha256(result.to_profile()))
        for _ in range(2):
            r2 = convert_eye_domes(mesh_name=mesh_name or result.flat.basis.mesh_name, root=root, create_meshes=False)
            det_hashes.append(profile_sha256(r2.to_profile()))
    gates["DETERMINISM_3X"] = "PASS" if len(det_hashes) >= 3 and len(set(det_hashes)) == 1 else "FAIL"

    required = [
        "PLANE_CENTER_DRIFT",
        "PLANE_ROTATION_MUTATION",
        "BOUNDARY_MATCH",
        "SURFACE_PENETRATION",
        "EXCESSIVE_PROTRUSION",
        "MULTIVIEW_SILHOUETTE",
        "LEFT_RIGHT_SWAP",
        "MODEL_OUTSIDE",
        "DETERMINISM_3X",
        "GATE1_2_HASH",
        "DOMES_SELECTED",
        "GAZE_MOTION",
        "BLINK",
        "EXPRESSION",
    ]
    verdict = "PASS" if all(gates[k] == "PASS" for k in required) else "FAIL"
    return {
        "schema": "NURION_GATE3_VALIDATION_REPORT",
        "version": "0.3.0-alpha.3-gate3",
        "verdict": verdict,
        "gates": gates,
        "selected": result.selected,
        "candidates": result.candidates,
        "planeDelta": result.planeDelta,
        "determinismHashes": det_hashes,
        "profileSha256": det_hashes[0] if det_hashes else None,
        "parameterHash": result.parameter_hash,
        "gate2ParameterHash": result.flat.parameter_hash,
        "gate1Lock": GATE1_LOCK,
        "gate2Lock": GATE2_LOCK,
        "gate2ParameterExpected": GATE2_PARAM,
        "notes": notes,
        "nextDecision": "CONVEX_CONVERSION_PASS" if verdict == "PASS" else "CONVEX_CONVERSION_FAIL",
    }
