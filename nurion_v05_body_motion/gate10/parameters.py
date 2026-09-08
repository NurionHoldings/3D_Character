"""v0.5 Gate 10 — Fresh Holdout parameters (RC.1 frozen)."""

from __future__ import annotations

import hashlib
import json

V05_RC1_PACKAGE = "NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V05_RC1_SHA256 = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_FROZEN = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
GATE4_FROZEN = "837fd79115113aa316671552d7fd4027f1e873e984c6d5ebc35239fd66e357ca"
GATE5_FROZEN = "3ac0c130af6200d73dac0d0b6b62e01196bd8588a4f820a6b146c77632a6c3ac"
GATE6_FROZEN = "92863ebff2fd45ed1421568f3dd9f1aeaa8845320caa85597205816983ee3c41"
GATE7_FROZEN = "59436fd1fc276b2dca44c0cb042bdda5e2cbe1990b13c695fafd1e43c35c792f"
GATE8_FROZEN = "fe73b4b4786f9f2180c178e3ab7a91945dd548fafbec0cc5618c8fc83fb515e6"
GATE9_FROZEN = "5b46b1e4c428686b9398e17428d7a36b1f10c5391e94434ca8e1c6fff348d332"
V04_GATE7_FROZEN = "1784696fb7513c7e693ada2faff48a3ae3413b3bf4f7aa9b5641442d2d5f258f"

# Official holdout submission (fixed before run)
HOLDOUT_ZIP_NAME = "aibaeby-bow.zip"
HOLDOUT_ZIP_SHA256 = "3703b784072e791b999c2332fb4fff951e4997560ee7f92b5b49fdc743b3d54a"

# Sibling ZIPs must not be mixed into official holdout
SIBLING_ZIP_SHA256 = {
    "5944a2db04ab7cff571fdd669b5ba74d38543ceb4a44d938da5c2a09760b5802": "aibaeby-15.zip",
    "7fe86d7314d7caa14d24f159360fb2a758fb02b47d12c2907e503a8a2a49663d": "aibaeby-vendition.zip",
}

BANNED_ZIP_SHA256 = {
    "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309": "ai-aba.bow.zip",
    "535da28538c13153a3a07c2a89a23287dbfb75634b3fae34321d172c2c705c85": "ai-aba.15.zip",
    **SIBLING_ZIP_SHA256,
}

BANNED_MODEL_SHA256 = {
    "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d": "tennis",
    "eb439a016f1edfcbab17a7f9ea39bfa44dabdf2b0ececf14a1a77d7224e0d60e": "captain_15",
    "62b466495050ba2058398b7ebc5106c548ae76eab4df39ceb3e7d2f817d2973c": "hyerie_15",
    "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927": "AILAWFRIEND_character_15",
    "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f": "ai-aba.bow_Formal_Bow",
    "552f43cf01cfdcd07728ad62eaf48d96421c4134306fd014b357eecff8b98330": "ai-aba.15",
}

BANNED_NAME_SUBSTRINGS = [
    "tennis",
    "captain",
    "hyerie",
    "ailawfriend",
    "ailaw_friend",
    "ai-aba",
    "ai_aba",
    "silver_starlight",
]

INHERITED_LIMITATIONS = [
    "FOOT_SLIDE_RESIDUAL_11",
    "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
    "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
]

GATE10_PARAMETERS = {
    "schema": "NURION_V05_GATE10_FRESH_HOLDOUT_PARAMETERS",
    "version": "0.5.0-gate10",
    "v05Rc1Package": V05_RC1_PACKAGE,
    "v05Rc1Sha256": V05_RC1_SHA256,
    "v05Rc1Repack": "DENY",
    "v04Rc1Sha256": V04_RC1_SHA256,
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5ParameterHash": GATE5_FROZEN,
    "gate6ParameterHash": GATE6_FROZEN,
    "gate7ParameterHash": GATE7_FROZEN,
    "gate8ParameterHash": GATE8_FROZEN,
    "gate9ParameterHash": GATE9_FROZEN,
    "v04Gate7ParameterHash": V04_GATE7_FROZEN,
    "holdoutZipName": HOLDOUT_ZIP_NAME,
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutCharacter": "ai-baeby",
    "holdoutMeshyName": "Lightning_Pilot",
    "holdoutAnimation": "Formal_Bow",
    "siblingZipMix": "DENY",
    "parameterTuning": "DENY",
    "manualCorrection": "DENY",
    "sourceZipFbxActionMutation": "DENY",
    "intermediateOutputReuse": "DENY",
    "supportedDomain": "LIMITED",
    "production": "NO-GO",
    "sealed": False,
    "determinismRuns": 3,
    "fpsMeaningSet": [24, 30, 60],
    "primaryTimeline": "word_확인",
    "shallowContactDepthMaxM": 0.0035,
    "inheritedLimitations": INHERITED_LIMITATIONS,
    "forceLimitationsToFullPass": "DENY",
    "verdicts": [
        "HOLDOUT_PASS",
        "PASS_WITH_LIMITATIONS",
        "ASSET_INELIGIBLE",
        "ALGORITHM_FAIL",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE10_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
