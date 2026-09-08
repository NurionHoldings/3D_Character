"""Validate Gate 5 expression–eye matching quality gates."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from .lock_guard import assert_gate1234ab_locked
from .parameters import GATE5_PARAMETERS, parameter_hash


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _drift(before: Optional[dict], after: Optional[dict], eu: float) -> float:
    if before is None or after is None:
        return 1e9
    bl, al = before["location"], after["location"]
    return math.sqrt(sum((float(al[i]) - float(bl[i])) ** 2 for i in range(3))) / max(eu, 1e-9)


def validate_expression_matching(
    result,
    *,
    root: Optional[Path] = None,
    determinism_profiles: Optional[List[dict]] = None,
) -> dict:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate1234ab_locked(root)
    lim = GATE5_PARAMETERS["limits"]
    blend = GATE5_PARAMETERS["blend"]
    notes: List[str] = []
    gates: Dict[str, str] = {}

    gates["GATE1_4B_HASH"] = "PASS"
    gates["GATE5_PARAM_SELF"] = "PASS" if result.parameter_hash == parameter_hash() else "FAIL"
    if gates["GATE5_PARAM_SELF"] == "FAIL":
        notes.append("Gate5 parameter hash mismatch")

    planes = result.blink.gaze.convex.flat.planes
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)

    # Dome base drift
    max_dome = 0.0
    for name, before in result.dome_before.items():
        max_dome = max(max_dome, _drift(before, result.dome_after.get(name), eu))
    gates["DOME_BASE_DRIFT"] = (
        "PASS" if max_dome <= float(lim["maxDomeBaseDriftEyeUnits"]) else "FAIL"
    )
    if gates["DOME_BASE_DRIFT"] == "FAIL":
        notes.append(f"dome drift EU={max_dome}")

    import bpy

    gates["EXPRESSION_CONTROL"] = (
        "PASS" if bpy.data.objects.get("NURION_ExpressionControl") is not None else "FAIL"
    )
    if gates["EXPRESSION_CONTROL"] == "FAIL":
        notes.append("missing NURION_ExpressionControl")

    # Gaze safe-ellipse escape
    max_esc = max((float(f.gaze_escape_eu) for f in result.frames), default=0.0)
    gates["GAZE_SAFE_ELLIPSE_ESCAPE"] = (
        "PASS" if max_esc <= float(lim["maxGazeEscapeEyeUnits"]) else "FAIL"
    )
    if gates["GAZE_SAFE_ELLIPSE_ESCAPE"] == "FAIL":
        notes.append(f"gaze escape EU={max_esc}")

    # Lid validated range
    max_lid_esc = max((float(f.lid_range_escape) for f in result.frames), default=0.0)
    gates["LID_VALIDATED_RANGE_ESCAPE"] = (
        "PASS" if max_lid_esc <= float(lim["maxLidRangeEscape"]) else "FAIL"
    )
    if gates["LID_VALIDATED_RANGE_ESCAPE"] == "FAIL":
        notes.append(f"lid range escape={max_lid_esc}")

    # Blink/expression conflict
    conflicts = sum(1 for f in result.frames if f.conflict)
    gates["BLINK_EXPRESSION_CONFLICT"] = (
        "PASS" if conflicts <= int(lim["maxBlinkExpressionConflict"]) else "FAIL"
    )
    if gates["BLINK_EXPRESSION_CONFLICT"] == "FAIL":
        notes.append(f"conflicts={conflicts}")

    # Transition pop
    gates["STATE_TRANSITION_POP"] = (
        "PASS"
        if result.max_transition_pop_gaze_eu <= float(blend["maxPopGazeEyeUnits"])
        and result.max_transition_pop_lid_eu <= float(blend["maxPopLidEyeUnits"])
        else "FAIL"
    )
    if gates["STATE_TRANSITION_POP"] == "FAIL":
        notes.append(
            f"pop gaze={result.max_transition_pop_gaze_eu} lid={result.max_transition_pop_lid_eu}"
        )

    # Neutral return
    gates["NEUTRAL_RETURN_ERROR"] = (
        "PASS"
        if result.neutral_return_error_eu <= float(blend["maxNeutralReturnEyeUnits"])
        else "FAIL"
    )
    if gates["NEUTRAL_RETURN_ERROR"] == "FAIL":
        notes.append(f"neutral return EU={result.neutral_return_error_eu}")

    # L/R desync
    gates["LR_DESYNCHRONIZATION"] = (
        "PASS" if result.lr_desync_eu <= float(blend["maxLRDesyncEyeUnits"]) else "FAIL"
    )
    if gates["LR_DESYNCHRONIZATION"] == "FAIL":
        notes.append(f"L/R desync EU={result.lr_desync_eu}")

    # Multiview expression match: required states exercised
    need = set(GATE5_PARAMETERS["states"])
    have = {f.state for f in result.frames}
    need_names = {
        "NEUTRAL_SOLO",
        "NEUTRAL_FINAL",
        "NEUTRAL_REPEAT",
        "HOLD_SPEAKING",
        "SPEAK_BOUNDARY_BLINK",
        "RAPID_HOLD_NEUTRAL",
    }
    have_names = {f.name for f in result.frames}
    gates["MULTIVIEW_EXPRESSION_MATCH"] = (
        "PASS" if need.issubset(have) and need_names.issubset(have_names) else "FAIL"
    )
    if gates["MULTIVIEW_EXPRESSION_MATCH"] == "FAIL":
        notes.append("missing expression coverage frames")

    # Holds
    gates["LIP_SYNC_HOLD"] = "PASS" if GATE5_PARAMETERS["lipSync"] == "HOLD" else "FAIL"
    gates["FACE_BONE_HOLD"] = (
        "PASS" if GATE5_PARAMETERS["faceBoneGeneration"] == "HOLD" else "FAIL"
    )

    # Determinism
    det = "SKIP"
    if determinism_profiles and len(determinism_profiles) >= 3:

        def stab(p):
            return {
                "parameterHash": p.get("parameterHash"),
                "frames": [
                    {
                        "name": f["name"],
                        "state": f["state"],
                        "reaction": f["reaction"],
                        "eyes": f["eyes"],
                        "lids": f["lids"],
                    }
                    for f in p.get("frames", [])
                ],
            }

        h0 = _sha_json(stab(determinism_profiles[0]))
        ok = all(_sha_json(stab(p)) == h0 for p in determinism_profiles[1:3])
        det = "PASS" if ok else "FAIL"
        if not ok:
            notes.append("3x determinism mismatch")
    gates["DETERMINISM_3X"] = det

    hard = [
        "GATE1_4B_HASH",
        "GATE5_PARAM_SELF",
        "DOME_BASE_DRIFT",
        "EXPRESSION_CONTROL",
        "GAZE_SAFE_ELLIPSE_ESCAPE",
        "LID_VALIDATED_RANGE_ESCAPE",
        "BLINK_EXPRESSION_CONFLICT",
        "STATE_TRANSITION_POP",
        "NEUTRAL_RETURN_ERROR",
        "LR_DESYNCHRONIZATION",
        "MULTIVIEW_EXPRESSION_MATCH",
        "DETERMINISM_3X",
    ]
    fails = [k for k in hard if gates.get(k) == "FAIL"]
    verdict = "PASS" if not fails else "FAIL"
    profile = result.to_profile()
    return {
        "schema": "NURION_GATE5_VALIDATION_REPORT",
        "verdict": verdict,
        "gates": gates,
        "notes": notes,
        "metrics": {
            "domeDriftEU": round(max_dome, 9),
            "maxGazeEscapeEU": round(max_esc, 6),
            "maxLidRangeEscape": round(max_lid_esc, 6),
            "conflicts": conflicts,
            "maxPopGazeEU": round(float(result.max_transition_pop_gaze_eu), 6),
            "maxPopLidEU": round(float(result.max_transition_pop_lid_eu), 6),
            "neutralReturnEU": round(float(result.neutral_return_error_eu), 6),
            "lrDesyncEU": round(float(result.lr_desync_eu), 6),
            "frameCount": len(result.frames),
        },
        "parameterHash": parameter_hash(),
        "profileSha256": _sha_json(profile),
        "gateLock": {
            "gate4aParameterHash": lock_info.get("gate4aParameterHash"),
            "gate4bParameterHash": lock_info.get("gate4bParameterHash"),
        },
        "fails": fails,
    }
