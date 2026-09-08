"""Gate 4B Blink Interface parameters (does not alter Gate1–4A)."""

from __future__ import annotations

import hashlib
import json

GATE4B_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate4b",
    "schema": "NURION_GATE4B_BLINK_PARAMETERS",
    "requiredGate2ParameterHash": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "requiredGate3ParameterHash": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
    "requiredGate4aParameterHash": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
    "capability": {
        "preferProceduralWhenNoNative": True,
        "nativeBoneNameHints": ["eyelid", "eye_lid", "blink", "lid_upper", "lid_lower", "upperlid", "lowerlid"],
        "nativeShapeKeyHints": ["blink", "eyeblink", "eyelid", "lidclose"],
    },
    "proxy": {
        "widthFromAperture": 1.02,
        "heightFromPlane": 0.95,
        "upperTravelShare": 0.72,
        "lowerTravelShare": 0.28,
        "openUpperInset": 0.02,
        "openLowerInset": 0.02,
        "closedOverlapEyeUnits": 0.015,
        "lidThicknessEyeUnits": 0.04,
        "surfaceGapEyeUnits": 0.03,
        "segmentsU": 16,
        "segmentsV": 6,
    },
    "limits": {
        "maxDomeIrisPupilDriftEyeUnits": 1e-6,
        "maxOpenLidDriftEyeUnits": 0.02,
        "minClosedCoverage": 0.92,
        "maxClosedGapEyeUnits": 0.06,
        "maxFacePenetrationEyeUnits": 0.08,
        "maxLidFloatingEyeUnits": 0.55,
        "maxReopenReturnEyeUnits": 0.02,
        "maxLRSwapEyeUnits": 0.05,
    },
    "states": {
        "OPEN": 0.0,
        "QUARTER": 0.25,
        "HALF": 0.50,
        "CLOSED": 1.0,
        "REOPEN": 0.0,
    },
    "rhythms": ["OPEN_CLOSE_OPEN", "OPEN_DOUBLE_BLINK_OPEN", "LEFT_ONLY", "RIGHT_ONLY", "BOTH"],
    "expression": "INACTIVE",
    "headMotion": "INACTIVE",
    "lipSync": "INACTIVE",
    "beautyMaterial": "HOLD",
    "emotionalBlinkTiming": "HOLD",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4B_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
