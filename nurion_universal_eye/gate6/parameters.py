"""Gate 6 Beauty Eye visual parameters (geometry/motion from Gate1–5 frozen)."""

from __future__ import annotations

import hashlib
import json

GATE6_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate6",
    "schema": "NURION_GATE6_BEAUTY_EYE_PARAMETERS",
    "requiredGate5ParameterHash": "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e",
    "requiredGate4aParameterHash": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
    "requiredGate4bParameterHash": "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61",
    "requiredGate2ParameterHash": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "requiredGate3ParameterHash": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
    "defaultPreset": "NATURAL",
    "defaultTier": "High",
    "presets": ["NATURAL", "LUMINOUS", "AI_PREMIUM"],
    "tiers": ["High", "Medium", "Low", "Fallback"],
    # Visual-only optics (does not alter Gate1–5 geometry/motion)
    "layers": {
        "limbalWidthScale": 0.14,
        "cornealLiftEyeUnits": 0.012,
        "catchlightRadiusScale": 0.18,
        "catchlightOffsetScale": 0.28,
        "catchlightMaxOffsetScale": 0.55,
        "scleraOpacity": 0.35,
        "zBiasEyeUnits": 0.004,
    },
    "emissionCaps": {
        "NATURAL": {"iris": 0.15, "pupil": 0.02, "catchlight": 1.8, "cornea": 0.05},
        "LUMINOUS": {"iris": 0.35, "pupil": 0.04, "catchlight": 2.6, "cornea": 0.12},
        "AI_PREMIUM": {"iris": 0.28, "pupil": 0.03, "catchlight": 2.2, "cornea": 0.10},
    },
    "overEmissionHardCap": 3.0,
    "limits": {
        "maxGeometryDriftEyeUnits": 1e-6,
        "maxMotionDriftEyeUnits": 1e-6,
        "maxIrisPupilDistortion": 1e-6,
        "maxCatchlightEscapeEyeUnits": 0.02,
        "maxZFightSamples": 0,
    },
    "brandPresetPolicy": {
        "engineDefault": "NATURAL",
        "arkaonAba": "AI_PREMIUM",
        "note": "Tennis evaluates candidates; universal default remains NATURAL. ARKAON ABA may select brand preset.",
    },
    "geometryMotionParameterChange": "DENY",
    "finalSeal": "HOLD",
    "freshHoldoutRequired": True,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE6_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
