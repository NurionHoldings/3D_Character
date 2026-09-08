"""Gate 5 Expression–Eye Matching parameters (does not alter Gate1–4B)."""

from __future__ import annotations

import hashlib
import json

GATE5_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate5",
    "schema": "NURION_GATE5_EXPRESSION_MATCH_PARAMETERS",
    "requiredGate4aParameterHash": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
    "requiredGate4bParameterHash": "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61",
    "requiredGate2ParameterHash": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "requiredGate3ParameterHash": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
    "states": [
        "NEUTRAL",
        "FRIENDLY_SMILE",
        "EXPLAINING",
        "EMPATHY",
        "FOCUS",
        "SURPRISE",
        "THINKING",
        "SPEAKING",
    ],
    # Per-state eye reaction at intensity=1.0 (scaled by intensity 0..1)
    "recipes": {
        "NEUTRAL": {
            "gazeYaw": 0.0,
            "gazePitch": 0.0,
            "gazeStability": 1.0,
            "openness": 1.0,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.0,
            "auxGlance": None,
        },
        "FRIENDLY_SMILE": {
            "gazeYaw": 0.0,
            "gazePitch": -0.12,
            "gazeStability": 0.85,
            "openness": 0.96,
            "lowerLidRaise": 0.28,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.0,
            "auxGlance": None,
        },
        "EXPLAINING": {
            "gazeYaw": 0.0,
            "gazePitch": 0.0,
            "gazeStability": 0.70,
            "openness": 1.0,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.15,
            "auxGlance": {"yaw": 0.35, "pitch": 0.08, "hold": True},
        },
        "EMPATHY": {
            "gazeYaw": 0.0,
            "gazePitch": -0.06,
            "gazeStability": 0.90,
            "openness": 0.88,
            "lowerLidRaise": 0.10,
            "blinkAmount": 0.18,
            "blinkSuppress": 0.0,
            "auxGlance": None,
        },
        "FOCUS": {
            "gazeYaw": 0.0,
            "gazePitch": 0.0,
            "gazeStability": 1.0,
            "openness": 0.97,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.55,
            "auxGlance": None,
        },
        "SURPRISE": {
            "gazeYaw": 0.0,
            "gazePitch": 0.10,
            "gazeStability": 1.0,
            "openness": 1.0,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.70,
            "auxGlance": None,
        },
        "THINKING": {
            "gazeYaw": 0.08,
            "gazePitch": 0.42,
            "gazeStability": 0.60,
            "openness": 0.94,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.05,
            "blinkSuppress": 0.0,
            "auxGlance": {"yaw": 0.0, "pitch": 0.0, "hold": True, "returnToUser": True},
        },
        "SPEAKING": {
            "gazeYaw": 0.0,
            "gazePitch": 0.0,
            "gazeStability": 0.80,
            "openness": 1.0,
            "lowerLidRaise": 0.0,
            "blinkAmount": 0.0,
            "blinkSuppress": 0.85,
            "auxGlance": None,
            "sentenceBoundaryBlink": 0.55,
        },
    },
    "blend": {
        "transitionSamples": 8,
        "maxPopGazeEyeUnits": 0.15,
        "maxPopLidEyeUnits": 0.40,
        "maxNeutralReturnEyeUnits": 0.02,
        "maxLRDesyncEyeUnits": 0.05,
    },
    "limits": {
        "maxDomeBaseDriftEyeUnits": 1e-6,
        "maxGazeEscapeEyeUnits": 0.02,
        "maxLidRangeEscape": 1e-6,
        "maxBlinkExpressionConflict": 0,
    },
    "gaze": {
        "userTargetEyeUnits": 40.0,
        "auxScale": 0.55,
        "focusMotionScale": 0.25,
    },
    "lid": {
        "maxLowerRaiseShare": 0.35,
        "minOpenness": 0.55,
        "maxBlinkAmount": 0.85,
    },
    "faceBoneGeneration": "HOLD",
    "eyebrowRig": "HOLD",
    "lipSync": "HOLD",
    "headBodyMotion": "HOLD",
    "beautyMaterial": "HOLD",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
