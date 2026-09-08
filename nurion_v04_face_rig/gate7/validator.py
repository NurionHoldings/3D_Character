"""Gate7 upstream hash verification + quality report."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Dict, List

from .parameters import (
    GATE1_FROZEN,
    GATE2_FROZEN,
    GATE3_FROZEN,
    GATE4_FROZEN,
    GATE5A1_FROZEN,
    GATE5A2_FROZEN,
    GATE5B_FROZEN,
    GATE6_FROZEN,
    GATE7_PARAMETERS,
    V03_RC1_SHA256,
    parameter_hash,
)


def verify_upstream(root: Path) -> Dict:
    from nurion_v04_face_rig.gate1.parameters import parameter_hash as g1
    from nurion_v04_face_rig.gate2.parameters import parameter_hash as g2
    from nurion_v04_face_rig.gate3.parameters import parameter_hash as g3
    from nurion_v04_face_rig.gate4.parameters import parameter_hash as g4
    from nurion_v04_face_rig.gate5a.parameters import parameter_hash as g5a1
    from nurion_v04_face_rig.gate5a2.parameters import parameter_hash as g5a2
    from nurion_v04_face_rig.gate5b.parameters import parameter_hash as g5b
    from nurion_v04_face_rig.gate6.parameters import parameter_hash as g6

    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    h = hashlib.sha256(pkg.read_bytes()).hexdigest() if pkg.exists() else ""
    return {
        "v03": "UNCHANGED" if h == V03_RC1_SHA256 else "CHANGED",
        "gate1": "UNCHANGED" if g1() == GATE1_FROZEN else "CHANGED",
        "gate2": "UNCHANGED" if g2() == GATE2_FROZEN else "CHANGED",
        "gate3": "UNCHANGED" if g3() == GATE3_FROZEN else "CHANGED",
        "gate4": "UNCHANGED" if g4() == GATE4_FROZEN else "CHANGED",
        "gate5a1": "UNCHANGED" if g5a1() == GATE5A1_FROZEN else "CHANGED",
        "gate5a2": "UNCHANGED" if g5a2() == GATE5A2_FROZEN else "CHANGED",
        "gate5b": "UNCHANGED" if g5b() == GATE5B_FROZEN else "CHANGED",
        "gate6": "UNCHANGED" if g6() == GATE6_FROZEN else "CHANGED",
    }


def build_validation(
    *,
    source_mutation: int,
    hashes: Dict,
    metrics: Dict,
    determinism: str,
    readability: str,
    fps_status: str,
    rest_fallback_preservation: str,
) -> Dict:
    up = (
        "UNCHANGED"
        if all(hashes.get(k) == "UNCHANGED" for k in ("v03", "gate1", "gate2", "gate3", "gate4", "gate5a1", "gate5a2", "gate5b", "gate6"))
        else "CHANGED"
    )
    gates = {
        "SOURCE_CHARACTER_MUTATION": source_mutation,
        "V03_V04_GATE1_6_HASH": up,
        "EYE_DOME_BASE_DRIFT": int(metrics.get("eyeDomeBaseDrift", 0)),
        "GAZE_SAFE_ELLIPSE_ESCAPE": int(metrics.get("gazeSafeEllipseEscape", 0)),
        "BLINK_RANGE_ESCAPE": int(metrics.get("blinkRangeEscape", 0)),
        "LIP_INTERSECTION": int(metrics.get("lipIntersection", 0)),
        "LIP_ORDER_INVERSION": int(metrics.get("lipOrderInversion", 0)),
        "NON_FACE_VERTEX_LEAK": int(metrics.get("nonFaceLeak", 0)),
        "BLINK_LIPSYNC_CONFLICT": int(metrics.get("blinkLipsyncConflict", 0)),
        "EXPRESSION_VISEME_CONFLICT": int(metrics.get("expressionVisemeConflict", 0)),
        "SILENCE_FALSE_MOTION": int(metrics.get("silenceFalseMotion", 0)),
        "LOW_CONFIDENCE_OVERDRIVE": int(metrics.get("lowConfidenceOverdrive", 0)),
        "REST_FALLBACK_PRESERVATION": rest_fallback_preservation,
        "NEUTRAL_RETURN_ERROR": 0 if float(metrics.get("neutralReturnError", 0)) <= float(GATE7_PARAMETERS["restReturnMu"]) else 1,
        "MULTIVIEW_READABILITY": readability,
        "FPS_24_30_60_CONSISTENCY": fps_status,
        "DETERMINISM_3X": determinism,
    }

    def ok(k, v):
        if k in ("V03_V04_GATE1_6_HASH", "REST_FALLBACK_PRESERVATION", "MULTIVIEW_READABILITY", "FPS_24_30_60_CONSISTENCY", "DETERMINISM_3X"):
            return v in ("PASS", "UNCHANGED")
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    return {
        "schema": "NURION_V04_GATE7_VALIDATION",
        "gates": gates,
        "fails": fails,
        "verdict": "PASS" if not fails else "FAIL",
        "parameterHash": parameter_hash(),
    }
