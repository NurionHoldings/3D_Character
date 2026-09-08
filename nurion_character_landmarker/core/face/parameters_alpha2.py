"""Frozen generation parameters for v0.3a-alpha.2 Meshy Eye Proxy + Procedural Eyeball."""

from __future__ import annotations

import hashlib
import json

FACE_ALPHA2_PARAMETERS = {
    "version": "0.3.0-alpha.2",
    "track": "v0.3a",
    "methods": {
        "eyeSurface": "MESHY_EYE_APERTURE_V1",
        "eyeCenter": "NURION_EYE_PROXY_V1",
        "eyeballMesh": "NURION_PROCEDURAL_EYEBALL_V1",
    },
    "aperture": {
        "heightBand": [0.52, 0.78],
        "lateralXMinHeadHeight": 0.03,
        "lateralXMaxHeadHeight": 0.28,
        "forwardYMinHeadHeight": -0.02,
        "clusterXHeadHeight": 0.045,
        "clusterZHeadHeight": 0.04,
        "innerOuterSpreadMinHeadHeight": 0.02,
    },
    "proxy": {
        "radiusFromWidth": 0.42,
        "radiusFromIpd": 0.18,
        "radiusFromHeadWidth": 0.055,
        "depthFromRadius": 0.85,
        "maxProtrusionHeadHeight": 0.008,
        "minRadiusHeadHeight": 0.012,
        "maxRadiusHeadHeight": 0.055,
        "lrRadiusDiffMax": 0.10,
    },
    "eyeball": {
        "segments": 24,
        "rings": 12,
        "collection": "NURION_Procedural_Eyes",
        "nameL": "NURION_Eyeball.L",
        "nameR": "NURION_Eyeball.R",
        "initialInsetMode": True,
    },
    "gatesAlpha2": {
        "surfaceMeanErrorMm": 5.0,
        "lrSwap": 0,
        "determinismRuns": 3,
        "radiusDiffMax": 0.10,
        "centerInsideHead": True,
        "facePenetration": 0,
        "apertureAlignMm": 5.0,
    },
}


def parameter_hash(params: dict | None = None) -> str:
    payload = json.dumps(params or FACE_ALPHA2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


FACE_ALPHA2_PARAMETER_HASH = parameter_hash(FACE_ALPHA2_PARAMETERS)
