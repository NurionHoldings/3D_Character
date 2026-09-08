"""v0.4 Gate 8C — Fresh Holdout Validation (RC.1 frozen)."""

from __future__ import annotations

import hashlib
import json

RC1_PACKAGE = "NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
GATE7_FROZEN = "1784696fb7513c7e693ada2faff48a3ae3413b3bf4f7aa9b5641442d2d5f258f"
GATE8A_FROZEN = "92f06ec3e0874e8b4df2e5ec3bd35f7b6177dd07035c7da2824a2431a659617c"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

# Prior development / CV / reference / style-stress — ineligible for Fresh Holdout.
BANNED_MODEL_SHA256 = {
    "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d": "tennis",
    "eb439a016f1edfcbab17a7f9ea39bfa44dabdf2b0ececf14a1a77d7224e0d60e": "captain_15",
    "62b466495050ba2058398b7ebc5106c548ae76eab4df39ceb3e7d2f817d2973c": "hyerie_15",
    "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927": "AILAWFRIEND_character_15",
}

BANNED_NAME_SUBSTRINGS = [
    "tennis",
    "captain",
    "hyerie",
    "ailawfriend",
    "ailaw_friend",
]

GATE8C_PARAMETERS = {
    "schema": "NURION_V04_GATE8C_FRESH_HOLDOUT_PARAMETERS",
    "version": "0.4.0-gate8c",
    "rc1Package": RC1_PACKAGE,
    "rc1Sha256": RC1_SHA256,
    "rc1Repack": "DENY",
    "gate7ParameterHash": GATE7_FROZEN,
    "gate8aParameterHash": GATE8A_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "releaseCandidate": True,
    "supportedDomain": "LIMITED",
    "humanSpeech": "PASS_WITH_LIMITATIONS",
    "sealed": False,
    "holdout": "WAITING",
    "finalSeal": "HOLD",
    "manualCorrection": 0,
    "parameterTuning": 0,
    "core14TimelineChange": "DENY",
    "sourceCharacterMutation": "DENY",
    "retryAfterEdit": "DENY",
    "intermediateOutputReuse": "DENY",
    "cleanSceneRebuild": True,
    "determinismRuns": 3,
    "forceRestPose": True,
    "timelines": "dist/v0.4/gate6/human_gate4_timelines",
    "coreOnlyForPass": True,
    "stressEvidence": True,
    "asr": "INACTIVE",
    "microphone": "INACTIVE",
    "realTime": "INACTIVE",
    "fullUnrestricted": "HOLD",
    "verdicts": [
        "HOLDOUT_PASS",
        "PASS_WITH_LIMITATIONS",
        "ASSET_INELIGIBLE",
        "ALGORITHM_FAIL",
        "WAITING_FOR_NEW_ASSET",
    ],
    "pipeline": [
        "ASSET_ELIGIBILITY",
        "CLEAN_IMPORT_REST",
        "FROZEN_GATE1_7",
        "CORE14_LIP_SYNC",
        "V03_EYE_GAZE_BLINK",
        "MULTIVIEW_CONFLICT",
        "FPS_24_30_60",
        "DETERMINISM_3X",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE8C_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
