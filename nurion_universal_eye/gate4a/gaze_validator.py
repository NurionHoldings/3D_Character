"""Validate Gate 4A gaze motion quality gates."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from .lock_guard import assert_gate123_locked
from .parameters import GATE4A_PARAMETERS, parameter_hash


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _dome_drift(before: Optional[dict], after: Optional[dict], eu: float) -> Dict:
    if before is None or after is None:
        return {"centerDriftEU": 1e9, "rotationDeltaDeg": 1e9, "ok": False}
    import math

    bl = before["location"]
    al = after["location"]
    drift = math.sqrt(sum((float(al[i]) - float(bl[i])) ** 2 for i in range(3))) / max(eu, 1e-9)
    # quaternion angle
    bq = before["rotation"]
    aq = after["rotation"]
    dot = abs(sum(float(bq[i]) * float(aq[i]) for i in range(4)))
    dot = min(1.0, max(-1.0, dot))
    ang = 2.0 * math.degrees(math.acos(dot))
    if ang > 180.0:
        ang = 360.0 - ang
    lim = GATE4A_PARAMETERS["limits"]
    ok = drift <= float(lim["maxDomeCenterDriftEyeUnits"]) and ang <= float(lim["maxDomeRotationDeltaDeg"])
    return {"centerDriftEU": round(drift, 9), "rotationDeltaDeg": round(ang, 6), "ok": ok}


def validate_gaze_motion(
    result,
    *,
    root: Optional[Path] = None,
    determinism_profiles: Optional[List[dict]] = None,
    mesh_name: str = "",
) -> dict:
    del mesh_name
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate123_locked(root)
    lim = GATE4A_PARAMETERS["limits"]
    g = GATE4A_PARAMETERS["gaze"]
    notes: List[str] = []
    gates: Dict[str, str] = {}

    # Gate1/2/3 hash unchanged
    gates["GATE1_2_3_HASH"] = "PASS"
    if result.parameter_hash != parameter_hash():
        gates["GATE4A_PARAM_SELF"] = "FAIL"
        notes.append("Gate4A parameter hash mismatch")
    else:
        gates["GATE4A_PARAM_SELF"] = "PASS"

    planes = result.convex.flat.planes
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)

    # Dome drift
    dome_ok = True
    dome_metrics = {}
    for side in ("L", "R"):
        dm = _dome_drift(result.dome_before.get(side), result.dome_after.get(side), eu)
        dome_metrics[side] = dm
        if not dm["ok"]:
            dome_ok = False
            notes.append(f"Dome.{side} transform drift")
    gates["DOME_CENTER_ROTATION_DRIFT"] = "PASS" if dome_ok else "FAIL"

    # Required objects
    import bpy

    required = [
        "NURION_GazeControl",
        "NURION_GazeAnchor.L",
        "NURION_GazeAnchor.R",
        "NURION_DiagnosticIris.L",
        "NURION_DiagnosticIris.R",
        "NURION_DiagnosticPupil.L",
        "NURION_DiagnosticPupil.R",
        "NURION_GazeSafeEllipse.L",
        "NURION_GazeSafeEllipse.R",
        "NURION_EyeDome.L",
        "NURION_EyeDome.R",
    ]
    missing = [n for n in required if bpy.data.objects.get(n) is None]
    gates["DIAGNOSTIC_OBJECTS"] = "PASS" if not missing else "FAIL"
    if missing:
        notes.append("missing: " + ", ".join(missing))

    # Iris edge escape / inside
    max_escape = 0.0
    escape_fail = False
    for fr in result.frames + result.reorder_frames:
        for side, st in fr.eyes.items():
            max_escape = max(max_escape, float(st.iris_escape_eu))
            if float(st.iris_escape_eu) > float(lim["maxIrisEdgeEscapeEyeUnits"]) or not st.inside:
                escape_fail = True
                notes.append(f"{fr.name}.{side} iris edge escape")
    gates["IRIS_EDGE_ESCAPE"] = "FAIL" if escape_fail else "PASS"

    # Surface penetration / floating of iris relative to dome height
    surf_pen = 0.0
    surf_float = 0.0
    for fr in result.frames:
        for side, st in fr.eyes.items():
            plane = planes[side]
            # expected z on dome
            from .gaze_meshes import dome_height_at

            z_exp = dome_height_at(plane, result.bulges[side], st.local_xy)
            # world along normal from plane
            n = plane.normal_out.normalized()
            z_act = float((st.world - plane.origin_world).dot(n))
            delta = z_act - z_exp
            if delta < 0:
                surf_pen = max(surf_pen, -delta / max(eu, 1e-9))
            else:
                surf_float = max(surf_float, delta / max(eu, 1e-9))
    gates["SURFACE_PENETRATION"] = (
        "PASS" if surf_pen <= float(lim["maxSurfacePenetrationEyeUnits"]) else "FAIL"
    )
    gates["SURFACE_FLOATING"] = (
        "PASS" if surf_float <= float(lim["maxSurfaceFloatingEyeUnits"]) else "FAIL"
    )
    if gates["SURFACE_PENETRATION"] == "FAIL":
        notes.append(f"surface penetration EU={surf_pen:.4f}")
    if gates["SURFACE_FLOATING"] == "FAIL":
        notes.append(f"surface floating EU={surf_float:.4f}")

    # Cross-eye / divergence on designed frames (reject list should be empty for catalog)
    cross = any(f.cross_fail for f in result.frames)
    div = any(f.divergence_fail for f in result.frames)
    gates["UNNATURAL_CROSS_EYE"] = "FAIL" if cross else "PASS"
    gates["DIVERGENCE"] = "FAIL" if div else "PASS"
    if cross:
        notes.append("unnatural cross-eye detected")
    if div:
        notes.append("outward divergence detected")

    # L/R desynchronization: both eyes must move in the same head-space direction for shared targets
    desync = 0.0
    import math

    def _uv(fr_eyes, side: str):
        e = result.ellipses[side]
        dx = float(fr_eyes[side].local_xy.x) - float(e.center_local.x)
        dy = float(fr_eyes[side].local_xy.y) - float(e.center_local.y)
        return dx / max(e.usable_rx, 1e-9), dy / max(e.usable_ry, 1e-9)

    center_fr = next((f for f in result.frames if f.name == "CENTER"), None)
    if center_fr is not None:
        c_uv = {s: _uv(center_fr.eyes, s) for s in ("L", "R")}
        for fr in result.frames:
            if fr.name not in ("LEFT", "RIGHT", "UP", "DOWN", "NEAR", "FAR"):
                continue
            for side in ("L", "R"):
                u, v = _uv(fr.eyes, side)
                cu, cv = c_uv[side]
                # magnitude of relative command difference L vs R
                pass
            uL, vL = _uv(fr.eyes, "L")
            uR, vR = _uv(fr.eyes, "R")
            duL, dvL = uL - c_uv["L"][0], vL - c_uv["L"][1]
            duR, dvR = uR - c_uv["R"][0], vR - c_uv["R"][1]
            if fr.name in ("LEFT", "RIGHT"):
                # same horizontal sign (shared look direction)
                if abs(duL) > 0.08 and abs(duR) > 0.08 and duL * duR < 0:
                    desync = max(desync, abs(duL - duR) * float(g["yawCardinalDeg"]))
            elif fr.name in ("UP", "DOWN"):
                if abs(dvL) > 0.08 and abs(dvR) > 0.08 and dvL * dvR < 0:
                    desync = max(desync, abs(dvL - dvR) * float(g["pitchCardinalDeg"]))
            else:
                # NEAR/FAR: toe-in change should be mirrored (duL up, duR down for near)
                desync = max(desync, abs((duL + duR)) * 0.5 * float(g["yawCardinalDeg"]))
    gates["LR_DESYNCHRONIZATION"] = (
        "PASS" if desync <= float(g["maxDesyncDeg"]) else "FAIL"
    )
    if gates["LR_DESYNCHRONIZATION"] == "FAIL":
        notes.append(f"L/R desync deg={desync:.3f}")

    # Center return
    cre = float(result.center_return_error_eu)
    gates["CENTER_RETURN_ERROR"] = (
        "PASS" if cre <= float(g["centerReturnMaxEyeUnits"]) else "FAIL"
    )
    if gates["CENTER_RETURN_ERROR"] == "FAIL":
        notes.append(f"center return error EU={cre:.4f}")

    # Multiview motion: frames must include cardinals + near/far + micro + reorder
    needed = {
        "CENTER",
        "LEFT",
        "RIGHT",
        "UP",
        "DOWN",
        "UP_LEFT",
        "UP_RIGHT",
        "DOWN_LEFT",
        "DOWN_RIGHT",
        "NEAR",
        "FAR",
        "MICRO_LEFT",
        "MICRO_RIGHT",
        "RETURN_CENTER",
    }
    have = {f.name for f in result.frames}
    gates["MULTIVIEW_MOTION"] = "PASS" if needed.issubset(have) and result.reorder_frames else "FAIL"
    if gates["MULTIVIEW_MOTION"] == "FAIL":
        notes.append("missing motion frames or reorder pass")

    # Determinism 3x
    det = "SKIP"
    if determinism_profiles and len(determinism_profiles) >= 3:
        # Compare stable subsets
        def stab(p):
            return {
                "parameterHash": p.get("parameterHash"),
                "ellipses": p.get("ellipses"),
                "frames": [
                    {
                        "name": f["name"],
                        "eyes": {
                            s: {"localXY": e["localXY"], "irisEscapeEU": e["irisEscapeEU"]}
                            for s, e in f["eyes"].items()
                        },
                    }
                    for f in p.get("frames", [])
                    if not str(f["name"]).startswith("FINAL_")
                ],
            }

        h0 = _sha_json(stab(determinism_profiles[0]))
        ok = all(_sha_json(stab(p)) == h0 for p in determinism_profiles[1:3])
        det = "PASS" if ok else "FAIL"
        if not ok:
            notes.append("3x determinism mismatch")
    gates["DETERMINISM_3X"] = det

    # Forbidden systems remain hold
    gates["BLINK_HOLD"] = "PASS" if GATE4A_PARAMETERS["blink"] == "HOLD" else "FAIL"
    gates["EXPRESSION_INACTIVE"] = (
        "PASS" if GATE4A_PARAMETERS["expression"] == "INACTIVE" else "FAIL"
    )

    hard = [
        "GATE1_2_3_HASH",
        "DOME_CENTER_ROTATION_DRIFT",
        "DIAGNOSTIC_OBJECTS",
        "IRIS_EDGE_ESCAPE",
        "SURFACE_PENETRATION",
        "SURFACE_FLOATING",
        "UNNATURAL_CROSS_EYE",
        "DIVERGENCE",
        "LR_DESYNCHRONIZATION",
        "CENTER_RETURN_ERROR",
        "MULTIVIEW_MOTION",
        "DETERMINISM_3X",
    ]
    fails = [k for k in hard if gates.get(k) == "FAIL"]
    verdict = "PASS" if not fails and det != "FAIL" else "FAIL"

    profile = result.to_profile()
    return {
        "schema": "NURION_GATE4A_VALIDATION_REPORT",
        "verdict": verdict,
        "gates": gates,
        "notes": notes,
        "metrics": {
            "maxIrisEscapeEU": round(max_escape, 6),
            "surfacePenetrationEU": round(surf_pen, 6),
            "surfaceFloatingEU": round(surf_float, 6),
            "centerReturnErrorEU": round(cre, 6),
            "lrDesyncDeg": round(desync, 4),
            "dome": dome_metrics,
        },
        "parameterHash": parameter_hash(),
        "profileSha256": _sha_json(profile),
        "gate123Lock": {
            "gate2ParameterHash": lock_info.get("gate2ParameterHash"),
            "gate3ParameterHash": lock_info.get("gate3ParameterHash"),
        },
        "fails": fails,
    }
