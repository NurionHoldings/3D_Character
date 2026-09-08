"""Gate 3 Convex Conversion parameters (does not alter Gate1/2)."""

from __future__ import annotations

import hashlib
import json

GATE3_PARAMETERS = {
    "version": "0.3.0-alpha.3-gate3",
    "schema": "NURION_GATE3_CONVEX_PARAMETERS",
    "requiredGate2ParameterHash": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
    "candidates": {
        "LOW": {"bulgeEyeUnits": 0.08, "label": "very_shallow"},
        "MEDIUM": {"bulgeEyeUnits": 0.16, "label": "visual_eye"},
        "HIGH": {"bulgeEyeUnits": 0.28, "label": "lively"},
    },
    "mesh": {
        "segmentsU": 16,
        "segmentsV": 12,
        "boundaryEpsilonEyeUnits": 0.02,
    },
    "limits": {
        "maxCenterDriftEyeUnits": 1e-6,
        "maxRotationDeltaDeg": 0.05,
        "maxPenetrationEyeUnits": 0.20,
        "maxProtrusionEyeUnits": 1.80,
        "maxOutsideEyeUnits": 2.00,
        "lrBulgeRelDiffMax": 0.55,
    },
    "scoring": {
        "wPenetration": 3.0,
        "wProtrusion": 1.2,
        "wBoundary": 1.5,
        "wSilhouette": 1.0,
        "wLrConsistency": 0.8,
        "planeBaselineBonus": 0.05,
    },
    "diagnostic": {
        "leftRGBA": [0.20, 0.95, 0.75, 0.70],
        "rightRGBA": [0.25, 0.55, 1.0, 0.70],
    },
    "gazeMotion": "INACTIVE",
    "blink": "INACTIVE",
    "expression": "INACTIVE",
    "headMotion": "INACTIVE",
    "lipSync": "INACTIVE",
    "beautyMaterial": "HOLD",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
