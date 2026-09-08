"""Gate 2 Flat Eye Placement parameters (independent of locked Gate 1 constants)."""

from __future__ import annotations

import hashlib
import json

GATE2_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate2",
    "schema": "NURION_GATE2_FLAT_EYE_PARAMETERS",
    "plane": {
        "widthEyeUnits": 1.25,
        "heightEyeUnits": 0.85,
        "thicknessEyeUnits": 0.10,
        "surfaceGapEyeUnits": 0.08,
        "maxProtrusionEyeUnits": 0.15,
        "maxPenetrationEyeUnits": 0.03,
        "maxFloatEyeUnits": 0.12,
    },
    "depth": {
        "yawDeg": [30.0, 60.0],
        "frontWeight": 0.70,
        "yaw30Weight": 0.18,
        "yaw60Weight": 0.12,
        "rayStartEyeUnits": 4.0,
        "maxXzDevEyeUnits": 0.40,
    },
    "frontCenterMaxErrorEyeUnits": 0.20,
    "sideDepthMaxErrorEyeUnits": 0.45,
    "yawDepthMaxErrorEyeUnits": 0.45,
    "correction": {
        "gapCandidatesEyeUnits": [0.04, 0.08, 0.12, 0.16],
        "maxIterations": 4,
    },
    "diagnostic": {
        "leftRGBA": [0.10, 0.95, 0.88, 0.55],
        "rightRGBA": [0.15, 0.40, 1.0, 0.55],
        "axisRGBA": [1.0, 1.0, 1.0, 0.85],
        "normalRGBA": [1.0, 0.85, 0.2, 0.9],
        "boundRGBA": [1.0, 0.4, 0.2, 0.7],
    },
    "manualGt": False,
    "convexEye": False,
    "motion": "INACTIVE",
    "expression": "INACTIVE",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
