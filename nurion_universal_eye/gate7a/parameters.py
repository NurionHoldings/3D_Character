"""Gate 7A Integrated Regression & RC package parameters."""

from __future__ import annotations

import hashlib
import json

GATE7A_PARAMETERS = {
    "version": "0.3.0-rc.1",
    "schema": "NURION_GATE7A_INTEGRATED_REGRESSION_PARAMETERS",
    "requiredGateParams": {
        "gate2": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
        "gate3": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
        "gate4a": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
        "gate4b": "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61",
        "gate5": "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e",
        "gate6": "4fc613deb0bc0e79d2b325354adc48ac3d7a73e87ea54af52a93bc477b6ab190",
    },
    "packageName": "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip",
    "releaseCandidate": True,
    "sealed": False,
    "holdout": "WAITING",
    "intermediateOutputReuse": "DENY",
    "cleanSceneRebuild": True,
    "determinismRuns": 3,
    "defaultPreset": "NATURAL",
    "selectablePresets": ["NATURAL", "LUMINOUS", "AI_PREMIUM"],
    "tiers": ["High", "Medium", "Low", "Fallback"],
    "finalSeal": "HOLD",
    "gate7b": "WAITING_FOR_NEW_ASSET",
    "captainHoldoutEligible": False,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE7A_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
