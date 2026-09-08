"""v0.6 Production Readiness Gate 7 — production holdout parameters."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import INHERITED_LIMITATIONS, V06_RC1_SHA256
from nurion_v06_production_readiness.gate4.parameters import WRAPPER_COMPONENT

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_PARAMETER_HASH_FROZEN = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_PARAMETER_HASH_FROZEN = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE6_PARAMETER_HASH_FROZEN = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"

WRAPPER_SHA256_FROZEN = WRAPPER_COMPONENT["wrapperSha256"]
WRAPPER_VERSION_FROZEN = WRAPPER_COMPONENT["version"]

# Official PR-track inherited limitations (Gate1 frozen list unchanged; panel gap appended)
PR_INHERITED_LIMITATIONS = list(INHERITED_LIMITATIONS) + [
    "PANEL_LIMITATION_IDS_RENDERED",
]

# Characters / models already used in v0.6 Gate1–8 or PR Gate1–6 (must not reuse)
USED_LABELS = {
    "ai-aba.bow",
    "ai-aba",
    "ai-aba.15",
    "ai-baeby",
    "hyerie",
    "empty-control",
    "ailawfriend",
    "silver_starlight",
    "lightning_pilot",
    "pr-gate3-smoke",
    "pr-gate4",
    "pr-gate5",
    "pr-gate6",
}

USED_ZIP_SHA256 = {
    # AILAWFRIEND Idle (v0.6 Gate8 + PR gates)
    "aaf39c897f32baefe7083eb5bae5a107c5b934981773b717549b239321b18e0b": "AILAWFRIEND_Idle_15",
    # AILAWFRIEND siblings
    "5477bd7c729b12c8af7ec95567be323ae6fe5b788e3d613c354fd30713d19892": "AILAWFRIEND_Gentlemans_Bow",
    "57ee5603770613a868264b51fb0294fd49bef45790c6553216926447fee1a955": "AILAWFRIEND_Victory_Cheer",
    # Tennis (banned / probed)
    "8a04a6ad6bd0ebc93b4b5ed7f6f9fc2307a514501eb3c77135e7e6413cd2e4a4": "Monochrome_Tennis_Loo",
}

USED_FBX_SHA256 = {
    "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927": "AILAWFRIEND_Idle_15",
    "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d": "tennis_v03",
    "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f": "ai-aba.bow_Formal_Bow",
    "552f43cf01cfdcd07728ad62eaf48d96421c4134306fd014b357eecff8b98330": "ai-aba.15_Idle",
    "35470079f2ca6305688e793d5b9fe354cd49c18ed53c1e5b6c53b3735d867034": "ai-baeby_Formal_Bow",
}

# Official PR Gate7 holdout candidate (distinct Meshy family; not v0.6 formal holdout subject)
HOLDOUT_LABEL = "MINIMALIST_TENNIS_OUT"
HOLDOUT_MESHY_FAMILY = "Minimalist_Tennis_Out"
HOLDOUT_ZIP_NAME = "Wither_character-rig.zip"
HOLDOUT_ZIP_SHA256 = "dd6ca3e7055d18b838e863c5aae8a9ce597647893cc303d6ace475e84fbb6e7a"
HOLDOUT_FBX_SHA256 = "509d6a3fec38235f84adbf4c3f16ec4dccf35315f8dddd137ddb7d65f43706d4"
HOLDOUT_ANIMATION = "Idle_15"
HOLDOUT_PRESET = "Idle"

GATE7_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE7_PRODUCTION_HOLDOUT_PARAMETERS",
    "version": "0.6.0-pr-gate7",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate6ParameterHash": GATE6_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "gate5Mutation": "DENY",
    "gate6Mutation": "DENY",
    "sealedBaselineSha256": V06_RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "rc1Repack": "DENY",
    "autoRemediate": "DENY",
    "autoRepack": "DENY",
    "productionAutoAdvance": "DENY",
    "manualCorrection": 0,
    "assetSpecificTuning": 0,
    "wrapperComponent": {**WRAPPER_COMPONENT, "LOCKED": True},
    "channel": "LIMITED_INTERNAL_OPERATOR",
    "production": "NO-GO",
    "inheritedLimitations": PR_INHERITED_LIMITATIONS,
    "limitationAutoClear": "DENY",
    "panelLimitationHidden": "DENY",
    "holdout": {
        "label": HOLDOUT_LABEL,
        "meshyFamily": HOLDOUT_MESHY_FAMILY,
        "zipName": HOLDOUT_ZIP_NAME,
        "zipSha256": HOLDOUT_ZIP_SHA256,
        "fbxSha256": HOLDOUT_FBX_SHA256,
        "animation": HOLDOUT_ANIMATION,
        "preset": HOLDOUT_PRESET,
        "submissionForm": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP",
        "noveltyNote": (
            "Distinct Meshy family Minimalist_Tennis_Out / Idle_15. "
            "Not v0.6 Gate8 formal holdout (AILAWFRIEND). "
            "Not used as PR Gate1–6 workflow subject. "
            "gate8/_probe extract was screening-only; FBX hash not in v0.6 banned model set."
        ),
    },
    "determinismRuns": 3,
    "fpsChoices": [24, 30, 60],
    "exportFormats": ["BLEND", "FBX", "GLB"],
    "partialExportPublish": "DENY",
    "allowedVerdicts": [
        "PASS_WITH_LIMITATIONS",
        "HOLDOUT_PASS",
        "ASSET_INELIGIBLE",
        "ALGORITHM_FAIL",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE7_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
