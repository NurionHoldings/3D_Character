"""Validate Gate 4B blink quality gates."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from .lock_guard import assert_gate1234a_locked
from .parameters import GATE4B_PARAMETERS, parameter_hash


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _drift(before: Optional[dict], after: Optional[dict], eu: float) -> float:
    if before is None or after is None:
        return 1e9
    bl, al = before["location"], after["location"]
    return math.sqrt(sum((float(al[i]) - float(bl[i])) ** 2 for i in range(3))) / max(eu, 1e-9)


def validate_blink_motion(
    result,
    *,
    root: Optional[Path] = None,
    determinism_profiles: Optional[List[dict]] = None,
) -> dict:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate1234a_locked(root)
    lim = GATE4B_PARAMETERS["limits"]
    notes: List[str] = []
    gates: Dict[str, str] = {}

    gates["GATE1_4A_HASH"] = "PASS"
    gates["GATE4B_PARAM_SELF"] = "PASS" if result.parameter_hash == parameter_hash() else "FAIL"
    if gates["GATE4B_PARAM_SELF"] == "FAIL":
        notes.append("Gate4B parameter hash mismatch")

    planes = result.gaze.convex.flat.planes
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)

    # Dome/iris/pupil drift
    max_drift = 0.0
    for name, before in result.frozen_before.items():
        d = _drift(before, result.frozen_after.get(name), eu)
        max_drift = max(max_drift, d)
    gates["DOME_IRIS_PUPIL_DRIFT"] = (
        "PASS" if max_drift <= float(lim["maxDomeIrisPupilDriftEyeUnits"]) else "FAIL"
    )
    if gates["DOME_IRIS_PUPIL_DRIFT"] == "FAIL":
        notes.append(f"frozen eye drift EU={max_drift}")

    # Open-state lid drift (OPEN vs REOPEN snapshots)
    open_drift = 0.0
    for key in result.open_lid_snapshot:
        open_drift = max(
            open_drift,
            _drift(result.open_lid_snapshot.get(key), result.reopen_lid_snapshot.get(key), eu),
        )
    gates["OPEN_STATE_LID_DRIFT"] = (
        "PASS" if open_drift <= float(lim["maxOpenLidDriftEyeUnits"]) else "FAIL"
    )
    gates["REOPEN_RETURN_ERROR"] = (
        "PASS" if open_drift <= float(lim["maxReopenReturnEyeUnits"]) else "FAIL"
    )
    if gates["OPEN_STATE_LID_DRIFT"] == "FAIL":
        notes.append(f"open lid drift EU={open_drift}")

    # Objects present
    import bpy

    required = [
        "NURION_BlinkControl",
        "NURION_UpperLidProxy.L",
        "NURION_UpperLidProxy.R",
        "NURION_LowerLidProxy.L",
        "NURION_LowerLidProxy.R",
    ]
    missing = [n for n in required if bpy.data.objects.get(n) is None]
    gates["PROXY_OBJECTS"] = "PASS" if not missing else "FAIL"
    if missing:
        notes.append("missing " + ", ".join(missing))

    gates["CAPABILITY_MODE"] = (
        "PASS" if result.mode in ("PROCEDURAL_LID_PROXY", "NATIVE_LID") else "FAIL"
    )

    # Closed coverage / gap
    closed = next((s for s in result.states if s.name == "CLOSED"), None)
    cov_ok = True
    gap_ok = True
    min_cov = 1.0
    max_gap = 0.0
    if closed is None:
        cov_ok = gap_ok = False
    else:
        for side in ("L", "R"):
            c = float(closed.coverage[side]["coverage"])
            g = float(closed.coverage[side]["gapEU"])
            min_cov = min(min_cov, c)
            max_gap = max(max_gap, g)
            if c < float(lim["minClosedCoverage"]):
                cov_ok = False
            if g > float(lim["maxClosedGapEyeUnits"]):
                gap_ok = False
    gates["CLOSED_COVERAGE"] = "PASS" if cov_ok else "FAIL"
    gates["CLOSED_GAP"] = "PASS" if gap_ok else "FAIL"
    if not cov_ok:
        notes.append(f"closed coverage={min_cov}")
    if not gap_ok:
        notes.append(f"closed gap EU={max_gap}")

    # Intermediate curve sanity: edges should be monotonic OPEN→CLOSED
    mono_ok = True
    by_name = {s.name: s for s in result.states}
    seq = ["OPEN", "QUARTER", "HALF", "CLOSED"]
    if all(n in by_name for n in seq):
        for side in ("L", "R"):
            ups = [by_name[n].lid_edges[side]["upper"] for n in seq]
            lows = [by_name[n].lid_edges[side]["lower"] for n in seq]
            # upper should decrease (move down), lower increase
            for i in range(1, len(ups)):
                if ups[i] > ups[i - 1] + 1e-7:
                    mono_ok = False
                if lows[i] < lows[i - 1] - 1e-7:
                    mono_ok = False
    else:
        mono_ok = False
    gates["LID_CURVE_MONOTONIC"] = "PASS" if mono_ok else "FAIL"
    if not mono_ok:
        notes.append("lid edge curve not monotonic")

    # Face penetration / floating
    pen = float(result.face_metrics.get("penetrationEU", 99))
    flo = float(result.face_metrics.get("floatingEU", 99))
    dpen = float(result.face_metrics.get("domePenetrationEU", 0))
    dflo = float(result.face_metrics.get("domeFloatingEU", 0))
    gates["FACE_PENETRATION"] = (
        "PASS" if pen <= float(lim["maxFacePenetrationEyeUnits"]) else "FAIL"
    )
    gates["LID_FLOATING"] = (
        "PASS"
        if max(flo, dflo) <= float(lim["maxLidFloatingEyeUnits"])
        and dpen <= float(lim["maxFacePenetrationEyeUnits"])
        else "FAIL"
    )
    if gates["FACE_PENETRATION"] == "FAIL":
        notes.append(f"face penetration EU={pen}")
    if gates["LID_FLOATING"] == "FAIL":
        notes.append(f"lid floating/dome pen EU={flo}/{dflo}/{dpen}")

    # L/R swap: each lid mesh centroid must stay nearer its own EyePlane than the opposite
    swap = 0.0
    for which in ("Upper", "Lower"):
        lo = bpy.data.objects.get(f"NURION_{which}LidProxy.L")
        ro = bpy.data.objects.get(f"NURION_{which}LidProxy.R")
        if lo is None or ro is None or "L" not in planes or "R" not in planes:
            continue

        def _centroid(obj):
            pts = [obj.matrix_world @ v.co for v in obj.data.vertices]
            if not pts:
                return obj.matrix_world.translation.copy()
            acc = pts[0].copy()
            for p in pts[1:]:
                acc += p
            return acc / len(pts)

        lc, rc = _centroid(lo), _centroid(ro)
        l_origin = planes["L"].origin_world
        r_origin = planes["R"].origin_world
        if (lc - l_origin).length > (lc - r_origin).length + eu * float(lim["maxLRSwapEyeUnits"]):
            swap = max(swap, ((lc - l_origin).length - (lc - r_origin).length) / max(eu, 1e-9))
        if (rc - r_origin).length > (rc - l_origin).length + eu * float(lim["maxLRSwapEyeUnits"]):
            swap = max(swap, ((rc - r_origin).length - (rc - l_origin).length) / max(eu, 1e-9))
    gates["LR_SWAP"] = "PASS" if swap <= float(lim["maxLRSwapEyeUnits"]) else "FAIL"
    if gates["LR_SWAP"] == "FAIL":
        notes.append(f"L/R swap EU={swap}")

    # Multiview blink: required states + rhythms present
    need_states = {"OPEN", "QUARTER", "HALF", "CLOSED", "REOPEN"}
    have_states = {s.name for s in result.states}
    need_rhythms = set(GATE4B_PARAMETERS["rhythms"])
    have_rhythms = {r["name"] for r in result.rhythms}
    gates["MULTIVIEW_BLINK"] = (
        "PASS" if need_states.issubset(have_states) and need_rhythms.issubset(have_rhythms) else "FAIL"
    )
    if gates["MULTIVIEW_BLINK"] == "FAIL":
        notes.append("missing blink states or rhythms")

    # Holds
    gates["EXPRESSION_INACTIVE"] = (
        "PASS" if GATE4B_PARAMETERS["expression"] == "INACTIVE" else "FAIL"
    )
    gates["EMOTIONAL_BLINK_HOLD"] = (
        "PASS" if GATE4B_PARAMETERS["emotionalBlinkTiming"] == "HOLD" else "FAIL"
    )

    # Determinism
    det = "SKIP"
    if determinism_profiles and len(determinism_profiles) >= 3:

        def stab(p):
            return {
                "parameterHash": p.get("parameterHash"),
                "mode": p.get("mode"),
                "apertures": p.get("apertures"),
                "states": p.get("states"),
                "rhythms": p.get("rhythms"),
            }

        h0 = _sha_json(stab(determinism_profiles[0]))
        ok = all(_sha_json(stab(p)) == h0 for p in determinism_profiles[1:3])
        det = "PASS" if ok else "FAIL"
        if not ok:
            notes.append("3x determinism mismatch")
    gates["DETERMINISM_3X"] = det

    hard = [
        "GATE1_4A_HASH",
        "GATE4B_PARAM_SELF",
        "DOME_IRIS_PUPIL_DRIFT",
        "OPEN_STATE_LID_DRIFT",
        "REOPEN_RETURN_ERROR",
        "PROXY_OBJECTS",
        "CAPABILITY_MODE",
        "CLOSED_COVERAGE",
        "CLOSED_GAP",
        "LID_CURVE_MONOTONIC",
        "FACE_PENETRATION",
        "LID_FLOATING",
        "LR_SWAP",
        "MULTIVIEW_BLINK",
        "DETERMINISM_3X",
    ]
    fails = [k for k in hard if gates.get(k) == "FAIL"]
    verdict = "PASS" if not fails else "FAIL"

    profile = result.to_profile()
    return {
        "schema": "NURION_GATE4B_VALIDATION_REPORT",
        "verdict": verdict,
        "gates": gates,
        "notes": notes,
        "metrics": {
            "maxFrozenDriftEU": round(max_drift, 9),
            "openLidDriftEU": round(open_drift, 6),
            "minClosedCoverage": round(min_cov, 6),
            "maxClosedGapEU": round(max_gap, 6),
            "facePenetrationEU": round(pen, 6),
            "lidFloatingEU": round(max(flo, dflo), 6),
            "lrSwapEU": round(swap, 6),
            "mode": result.mode,
        },
        "parameterHash": parameter_hash(),
        "profileSha256": _sha_json(profile),
        "gateLock": {
            "gate2ParameterHash": lock_info.get("gate2ParameterHash"),
            "gate3ParameterHash": lock_info.get("gate3ParameterHash"),
            "gate4aParameterHash": lock_info.get("gate4aParameterHash"),
        },
        "fails": fails,
    }
