"""Frozen generation parameters for v0.3a Face Alpha1 (no GT / no character branches)."""

from __future__ import annotations

import hashlib
import json

FACE_ALPHA1_PARAMETERS = {
    "version": "0.3.0-alpha.1",
    "track": "v0.3a",
    "coreKeys": [
        "eye.center.L",
        "eye.center.R",
        "eye.inner.L",
        "eye.inner.R",
        "eye.outer.L",
        "eye.outer.R",
        "nose.tip",
        "mouth.center",
        "mouth.corner.L",
        "mouth.corner.R",
        "chin",
        "ear.center.L",
        "ear.center.R",
    ],
    "methods": {
        "eyeball": "EYEBALL_ELLIPSOID_FIT_V1",
        "nose": "NOSE_PROTRUSION_V1",
        "mouth": "MOUTH_BAND_V1",
        "chin": "CHIN_LOWEST_FORWARD_V1",
        "ear": "EAR_LATERAL_PROTRUSION_V1",
        "multiview": "ORTHO_HEADLOCAL_V1",
        "fusion": "FACE_FUSION_V1",
    },
    "region": {
        "headHeightRatio": 0.22,
        "faceFrontDepthRatio": 0.35,
        "excludeNameTokens": [
            "hair",
            "eyelash",
            "glass",
            "spectacle",
            "earring",
            "accessory",
            "hat",
            "cap",
            "tongue",
            "teeth",
            "tooth",
        ],
        "eyeballNameTokens": ["eye", "eyeball", "cornea", "pupil", "sclera"],
        "minFaceVertexCount": 800,
        "minLateralGapHeadHeight": 0.08,
    },
    "eyes": {
        "searchRadiusHeadHeight": 0.045,
        "innerOuterOffsetHeadHeight": 0.018,
        "heightBand": [0.55, 0.78],
        "symmetryDeltaMaxMm": 8.0,
        "radiusSymmetryMaxRatio": 0.25,
    },
    "nose": {
        "heightBand": [0.35, 0.62],
        "midXRatio": 0.12,
    },
    "mouth": {
        "heightBand": [0.18, 0.42],
        "cornerOffsetHeadHeight": 0.028,
        "belowNoseMinHeadHeight": 0.02,
    },
    "chin": {
        "heightBand": [0.0, 0.22],
        "forwardPercentile": 0.85,
    },
    "ears": {
        "lateralXRatio": 0.72,
        "heightBand": [0.35, 0.72],
        "protrusionMinHeadHeight": 0.01,
    },
    "multiview": {
        "views": [
            "FRONT",
            "LEFT",
            "RIGHT",
            "TOP",
            "FRONT_LEFT_45",
            "FRONT_RIGHT_45",
        ],
        "raySamples": 48,
    },
    "gatesAlpha1": {
        "detectionSuccessRate": 1.0,
        "meanErrorCm": 2.0,
        "maxErrorCm": 4.0,
        "eyeCenterCm": 1.5,
        "noseTipCm": 2.0,
        "mouthCenterCm": 2.0,
        "chinCm": 2.5,
        "lrSwap": 0,
        "outsideFace": 0,
        "gtLeak": 0,
        "determinismRuns": 3,
    },
    "confidence": {
        "productClamp": [0.25, 0.95],
        "reviewBelow": 0.90,
    },
}


def parameter_hash(params: dict | None = None) -> str:
    payload = json.dumps(params or FACE_ALPHA1_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


FACE_ALPHA1_PARAMETER_HASH = parameter_hash(FACE_ALPHA1_PARAMETERS)
