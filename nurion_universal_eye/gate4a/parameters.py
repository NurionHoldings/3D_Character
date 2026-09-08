"""Gate 4A Gaze Motion parameters (does not alter Gate1–3)."""

from __future__ import annotations

import hashlib
import json

GATE4A_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate4a",
    "schema": "NURION_GATE4A_GAZE_PARAMETERS",
    "requiredGate2ParameterHash": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "requiredGate3ParameterHash": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
    "ellipse": {
        "widthFromAperture": 0.92,
        "heightFromPlane": 0.72,
        "insetIrisEyeUnits": 0.02,
    },
    "iris": {
        "radiusEyeUnits": 0.22,
        "pupilRadiusScale": 0.42,
    },
    "gaze": {
        "maxOffsetEyeUnits": 0.28,
        "microOffsetEyeUnits": 0.04,
        "nearTargetEyeUnits": 8.0,
        "farTargetEyeUnits": 80.0,
        "maxConvergenceDeg": 18.0,
        "maxDivergenceDeg": 2.0,
        "maxDesyncDeg": 6.0,
        "centerReturnMaxEyeUnits": 0.02,
        "yawCardinalDeg": 12.0,
        "pitchCardinalDeg": 8.0,
        "diagonalScale": 0.75,
    },
    "limits": {
        "maxDomeCenterDriftEyeUnits": 1e-6,
        "maxDomeRotationDeltaDeg": 0.05,
        "maxIrisEdgeEscapeEyeUnits": 0.02,
        "maxSurfacePenetrationEyeUnits": 0.08,
        "maxSurfaceFloatingEyeUnits": 0.20,
    },
    "blink": "HOLD",
    "expression": "INACTIVE",
    "headMotion": "INACTIVE",
    "lipSync": "INACTIVE",
    "beautyMaterial": "HOLD",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4A_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
