"""Frozen generation parameters for v0.2.0-alpha.3 (no GT / no character branches)."""

from __future__ import annotations

import hashlib
import json

from .candidate_scoring import DEFAULT_WEIGHTS

# Parameter set hashed before evaluation. Changing these requires a new alpha build.
ALPHA3_PARAMETERS = {
    "version": "0.2.0-alpha.3",
    "methods": {
        "elbow": "ELBOW_BEND_V1",
        "knee": "KNEE_AXIS_V1",
        "ankle": "ANKLE_TRANSITION_V2",
        "confidence": "EVIDENCE_PRODUCT_V1",
    },
    "scoringWeights": dict(DEFAULT_WEIGHTS),
    "elbow": {
        "sectionCount": 36,
        "rays": 16,
        "maxRadiusHeight": 0.11,
        "upperT": [0.10, 0.42],
        "forearmT": [0.58, 0.90],
        "bendT": [0.32, 0.68],
        "maxDispRatio": 0.11,
        "maxAngleDeg": 55.0,
        "acceptMarginOverBaseline": 0.015,
    },
    "knee": {
        "sectionCount": 34,
        "rays": 16,
        "maxRadiusHeight": 0.12,
        "thighT": [0.08, 0.45],
        "shinT": [0.55, 0.92],
        "bendT": [0.35, 0.70],
        "maxDispRatio": 0.12,
        "maxAngleDeg": 45.0,
        "lrHeightDeltaMaxHeight": 0.035,
        "acceptMarginOverBaseline": 0.015,
    },
    "ankle": {
        "sectionCount": 32,
        "rays": 16,
        "maxRadiusHeight": 0.10,
        "distalTMin": 0.50,
        "floorRejectHeight": 0.028,
        "clearanceMinHeight": 0.045,
        "maxDispRatio": 0.16,
        "maxAngleDeg": 40.0,
        "acceptMarginOverBaseline": 0.01,
        "stanceHeightRatio": 0.09,
        "stanceWidthRatio": 0.20,
    },
    "confidence": {
        "productClamp": [0.20, 0.95],
        "unstableMargin": 0.02,
        "reviewGap": 0.08,
    },
}


def parameter_hash(params: dict | None = None) -> str:
    payload = json.dumps(params or ALPHA3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


ALPHA3_PARAMETER_HASH = parameter_hash(ALPHA3_PARAMETERS)
