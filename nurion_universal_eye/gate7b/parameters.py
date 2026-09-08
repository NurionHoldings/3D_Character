"""Gate 7B Fresh Holdout — frozen RC.1 policy (no parameter tuning)."""

from __future__ import annotations

import hashlib
import json

# Frozen RC.1 package — DO NOT repack or mutate.
RC1_PACKAGE = "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

# Assets already used in development / CV — ineligible for holdout.
BANNED_MODEL_SHA256 = {
    "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d": "tennis",
    "eb439a016f1edfcbab17a7f9ea39bfa44dabdf2b0ececf14a1a77d7224e0d60e": "captain_15",
}

GATE7B_PARAMETERS = {
    "version": "0.3.0-rc.1",
    "schema": "NURION_GATE7B_FRESH_HOLDOUT_PARAMETERS",
    "rc1Package": RC1_PACKAGE,
    "rc1Sha256": RC1_SHA256,
    "releaseCandidate": True,
    "sealed": False,
    "holdout": "WAITING",
    "finalSeal": "HOLD",
    "manualCorrection": 0,
    "parameterTuning": 0,
    "retryAfterEdit": "DENY",
    "intermediateOutputReuse": "DENY",
    "cleanSceneRebuild": True,
    "determinismRuns": 3,
    "forceRestPose": True,
    "captainHoldoutEligible": False,
    "tennisHoldoutEligible": False,
    "requiredGateParams": {
        "gate2": "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5",
        "gate3": "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f",
        "gate4a": "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35",
        "gate4b": "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61",
        "gate5": "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e",
        "gate6": "4fc613deb0bc0e79d2b325354adc48ac3d7a73e87ea54af52a93bc477b6ab190",
    },
    "verdicts": ["HOLDOUT_PASS", "ASSET_INELIGIBLE", "ALGORITHM_FAIL", "WAITING_FOR_NEW_ASSET"],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE7B_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
