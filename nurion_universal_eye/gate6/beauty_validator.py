"""Validate Gate 6 beauty integration — visual only, no geometry/motion drift."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from .lock_guard import assert_gate12345_locked
from .parameters import GATE6_PARAMETERS, parameter_hash


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _loc_drift(a: Optional[dict], b: Optional[dict], eu: float) -> float:
    if a is None or b is None:
        return 1e9
    al, bl = a["location"], b["location"]
    return math.sqrt(sum((float(bl[i]) - float(al[i])) ** 2 for i in range(3))) / max(eu, 1e-9)


def _mesh_distortion(a: Optional[dict], b: Optional[dict]) -> float:
    if a is None or b is None or not a.get("mesh") or not b.get("mesh"):
        return 1e9
    if a["mesh"]["count"] != b["mesh"]["count"]:
        return 1.0
    aa, bb = a["mesh"]["bbox"], b["mesh"]["bbox"]
    return max(abs(float(aa[i]) - float(bb[i])) for i in range(6))


def validate_beauty_integration(
    result,
    *,
    root: Optional[Path] = None,
    determinism_profiles: Optional[List[dict]] = None,
) -> dict:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate12345_locked(root)
    lim = GATE6_PARAMETERS["limits"]
    notes: List[str] = []
    gates: Dict[str, str] = {}

    gates["GATE1_5_HASH"] = "PASS"
    gates["GATE6_PARAM_SELF"] = "PASS" if result.parameter_hash == parameter_hash() else "FAIL"

    planes = result.expression.blink.gaze.convex.flat.planes
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)

    # Geometry drift on planes/domes/iris/pupil transforms + mesh signature
    max_g = 0.0
    max_dist = 0.0
    for name, before in result.geometry_before.items():
        after = result.geometry_after.get(name)
        max_g = max(max_g, _loc_drift(before, after, eu))
        if "Iris" in name or "Pupil" in name or "EyeDome" in name:
            max_dist = max(max_dist, _mesh_distortion(before, after))
    gates["GEOMETRY_DRIFT"] = (
        "PASS" if max_g <= float(lim["maxGeometryDriftEyeUnits"]) else "FAIL"
    )
    gates["IRIS_PUPIL_DISTORTION"] = (
        "PASS" if max_dist <= float(lim["maxIrisPupilDistortion"]) else "FAIL"
    )
    if gates["GEOMETRY_DRIFT"] == "FAIL":
        notes.append(f"geometry drift EU={max_g}")
    if gates["IRIS_PUPIL_DISTORTION"] == "FAIL":
        notes.append(f"iris/pupil distortion={max_dist}")

    # Motion drift: dome/plane must not move when expression changes under beauty stack
    max_m = 0.0
    for name, before in result.motion_before.items():
        max_m = max(max_m, _loc_drift(before, result.motion_after.get(name), eu))
    # After smile→neutral, dome/plane should match motion_before (both neutral endpoints)
    gates["MOTION_DRIFT"] = (
        "PASS" if max_m <= float(lim["maxMotionDriftEyeUnits"]) else "FAIL"
    )
    if gates["MOTION_DRIFT"] == "FAIL":
        notes.append(f"motion drift EU={max_m}")

    import bpy

    required_high = [
        "NURION_BeautyControl",
        "NURION_LimbalRing.L",
        "NURION_LimbalRing.R",
        "NURION_CornealHighlight.L",
        "NURION_CornealHighlight.R",
        "NURION_Catchlight.L",
        "NURION_Catchlight.R",
        "NURION_SoftSclera.L",
        "NURION_SoftSclera.R",
    ]
    missing = [n for n in required_high if bpy.data.objects.get(n) is None]
    gates["BEAUTY_LAYERS"] = "PASS" if not missing else "FAIL"
    if missing:
        notes.append("missing " + ", ".join(missing))

    # Catchlight escape
    max_c = 0.0
    for side, c in result.catchlight.items():
        max_c = max(max_c, float(c.get("escapeEU", 99)))
    gates["CATCHLIGHT_ESCAPE"] = (
        "PASS" if max_c <= float(lim["maxCatchlightEscapeEyeUnits"]) else "FAIL"
    )
    if gates["CATCHLIGHT_ESCAPE"] == "FAIL":
        notes.append(f"catchlight escape EU={max_c}")

    # Over-emission
    hard = float(GATE6_PARAMETERS["overEmissionHardCap"])
    gates["OVER_EMISSION"] = "PASS" if float(result.over_emission) <= hard else "FAIL"
    if gates["OVER_EMISSION"] == "FAIL":
        notes.append(f"over emission={result.over_emission}")

    # Z-fighting heuristic: beauty layer local Z separations
    zfight = 0
    for side in ("L", "R"):
        zs = []
        for name in (
            f"NURION_DiagnosticIris.{side}",
            f"NURION_LimbalRing.{side}",
            f"NURION_CornealHighlight.{side}",
            f"NURION_Catchlight.{side}",
        ):
            obj = bpy.data.objects.get(name)
            if obj is None:
                continue
            zs.append(float(obj.location.z) if obj.parent else float(obj.matrix_world.translation.z))
        # If parented, compare local z
        iris = bpy.data.objects.get(f"NURION_DiagnosticIris.{side}")
        if iris is not None:
            locals_z = []
            for name in (
                f"NURION_LimbalRing.{side}",
                f"NURION_CornealHighlight.{side}",
                f"NURION_Catchlight.{side}",
            ):
                obj = bpy.data.objects.get(name)
                if obj is not None and obj.parent == iris:
                    locals_z.append(round(float(obj.location.z), 5))
            if len(locals_z) != len(set(locals_z)):
                zfight += 1
    gates["Z_FIGHTING"] = "PASS" if zfight <= int(lim["maxZFightSamples"]) else "FAIL"
    if gates["Z_FIGHTING"] == "FAIL":
        notes.append("z-fighting layer overlap")

    # Multiview visual quality: presets evaluated + default NATURAL
    gates["MULTIVIEW_VISUAL_QUALITY"] = (
        "PASS"
        if set(GATE6_PARAMETERS["presets"]).issubset(set(result.evaluated_presets.keys()))
        and result.preset == GATE6_PARAMETERS["defaultPreset"]
        else "FAIL"
    )
    if gates["MULTIVIEW_VISUAL_QUALITY"] == "FAIL":
        notes.append("preset evaluation / default NATURAL incomplete")

    # Mobile distance readability — all tiers produced reports
    gates["MOBILE_DISTANCE_READABILITY"] = (
        "PASS" if set(GATE6_PARAMETERS["tiers"]).issubset(set(result.tier_reports.keys())) else "FAIL"
    )
    gates["LOW_TIER_FALLBACK"] = (
        "PASS" if "Low" in result.tier_reports and "Fallback" in result.tier_reports else "FAIL"
    )

    gates["FINAL_SEAL_HOLD"] = "PASS" if GATE6_PARAMETERS["finalSeal"] == "HOLD" else "FAIL"
    gates["FRESH_HOLDOUT_REQUIRED"] = (
        "PASS" if GATE6_PARAMETERS["freshHoldoutRequired"] is True else "FAIL"
    )

    det = "SKIP"
    if determinism_profiles and len(determinism_profiles) >= 3:

        def stab(p):
            return {
                "parameterHash": p.get("parameterHash"),
                "appliedPreset": p.get("appliedPreset"),
                "catchlight": p.get("catchlight"),
                "evaluatedPresets": p.get("evaluatedPresets"),
                "geometryAfter": p.get("geometryAfter"),
            }

        h0 = _sha_json(stab(determinism_profiles[0]))
        ok = all(_sha_json(stab(p)) == h0 for p in determinism_profiles[1:3])
        det = "PASS" if ok else "FAIL"
        if not ok:
            notes.append("3x determinism mismatch")
    gates["DETERMINISM_3X"] = det

    hard_gates = [
        "GATE1_5_HASH",
        "GATE6_PARAM_SELF",
        "GEOMETRY_DRIFT",
        "MOTION_DRIFT",
        "IRIS_PUPIL_DISTORTION",
        "BEAUTY_LAYERS",
        "CATCHLIGHT_ESCAPE",
        "OVER_EMISSION",
        "Z_FIGHTING",
        "MULTIVIEW_VISUAL_QUALITY",
        "MOBILE_DISTANCE_READABILITY",
        "LOW_TIER_FALLBACK",
        "DETERMINISM_3X",
    ]
    fails = [k for k in hard_gates if gates.get(k) == "FAIL"]
    verdict = "PASS" if not fails else "FAIL"
    profile = result.to_profile()
    return {
        "schema": "NURION_GATE6_VALIDATION_REPORT",
        "verdict": verdict,
        "gates": gates,
        "notes": notes,
        "metrics": {
            "geometryDriftEU": round(max_g, 9),
            "motionDriftEU": round(max_m, 9),
            "irisPupilDistortion": round(max_dist, 9),
            "catchlightEscapeEU": round(max_c, 6),
            "overEmissionMax": round(float(result.over_emission), 4),
            "zFightSamples": zfight,
            "preset": result.preset,
            "tier": result.tier,
        },
        "parameterHash": parameter_hash(),
        "profileSha256": _sha_json(profile),
        "gateLock": {
            "gate5ParameterHash": lock_info.get("gate5ParameterHash"),
            "gate4aParameterHash": lock_info.get("gate4aParameterHash"),
            "gate4bParameterHash": lock_info.get("gate4bParameterHash"),
        },
        "fails": fails,
        "finalSeal": "HOLD",
        "freshHoldoutRequired": True,
    }
