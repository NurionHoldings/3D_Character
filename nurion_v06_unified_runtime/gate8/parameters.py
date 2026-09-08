"""v0.6 Gate 8 — Fresh Holdout and RC candidate parameters (Gate 1–7 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_PARAMETER_HASH_FROZEN = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_PARAMETER_HASH_FROZEN = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"
GATE4_PARAMETER_HASH_FROZEN = "a260ecd6d15502bbb5633e17b6c860955f9307fae25d777db6477c381bad5188"
GATE5_PARAMETER_HASH_FROZEN = "81885dbc3c119c08c63add3a9e45caf9860a8bcbd1e9b4363cac46ac9aa9c0be"
GATE6_PARAMETER_HASH_FROZEN = "3207531397c6372bbba4e38aebb3024fdc1e85f1792526a5f3115e36bbdf746e"
GATE7_PARAMETER_HASH_FROZEN = "32e9fe4fef0f2d534d9a623f8dbfdedc0d4b9c60a5b5fe1a104c9620c4a07833"

# Official holdout ZIP (AILAWFRIEND / AI_법률_파트너 Idle_15 withSkin)
HOLDOUT_ZIP_ALIAS = "ailawfriend-idle15-biped.zip"
HOLDOUT_ZIP_SHA256 = "aaf39c897f32baefe7083eb5bae5a107c5b934981773b717549b239321b18e0b"
HOLDOUT_FBX_SHA256 = "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927"
HOLDOUT_LABEL = "AILAWFRIEND"
HOLDOUT_MESHY_NAME = "AI_법률_파트너"
HOLDOUT_ANIMATION = "Idle_15"
HOLDOUT_PRESET_ID = "Idle"

# Gate 1–7 used characters / models (must not be reused as fresh holdout)
USED_IN_V06_GATE1_TO_7 = {
    "ai-aba.bow",
    "ai-aba",
    "ai-aba.15",
    "ai-baeby",
    "hyerie",
    "empty-control",
    "silver_starlight",
    "lightning_pilot",
}

BANNED_MODEL_SHA256 = {
    "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d": "tennis_v03",
    "eb439a016f1edfcbab17a7f9ea39bfa44dabdf2b0ececf14a1a77d7224e0d60e": "captain_15",
    "62b466495050ba2058398b7ebc5106c548ae76eab4df39ceb3e7d2f817d2973c": "hyerie_15",
    "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f": "ai-aba.bow_Formal_Bow",
    "552f43cf01cfdcd07728ad62eaf48d96421c4134306fd014b357eecff8b98330": "ai-aba.15",
    "35470079f2ca6305688e793d5b9fe354cd49c18ed53c1e5b6c53b3735d867034": "ai-baeby_Formal_Bow",
}

# Sibling animation ZIPs of same character — do not mix into this holdout run
SIBLING_ZIP_SHA256 = {
    "5477bd7c729b12c8af7ec95567be323ae6fe5b788e3d613c354fd30713d19892": "AILAWFRIEND_Gentlemans_Bow",
    "57ee5603770613a868264b51fb0294fd49bef45790c6553216926447fee1a955": "AILAWFRIEND_Victory_Cheer",
}

V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_RC1_SHA256 = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"

RC_PACKAGE_NAME = "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"

GATE8_PARAMETERS = {
    "schema": "NURION_V06_GATE8_FRESH_HOLDOUT_RC_PARAMETERS",
    "version": "0.6.0-gate8",
    "track": "Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate6ParameterHash": GATE6_PARAMETER_HASH_FROZEN,
    "gate7ParameterHash": GATE7_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "gate5Mutation": "DENY",
    "gate6Mutation": "DENY",
    "gate7Mutation": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "autoSeal": "DENY",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "manualCorrection": "DENY",
    "assetSpecificTuning": "DENY",
    "partialExportPublish": "DENY",
    "siblingZipMix": "DENY",
    "determinismRuns": 3,
    "fpsMeaningSet": [24, 30, 60],
    "holdoutZipAlias": HOLDOUT_ZIP_ALIAS,
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
    "holdoutLabel": HOLDOUT_LABEL,
    "holdoutMeshyName": HOLDOUT_MESHY_NAME,
    "holdoutAnimation": HOLDOUT_ANIMATION,
    "holdoutPresetId": HOLDOUT_PRESET_ID,
    "requiredSubmissionForm": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP",
    "rcPackageName": RC_PACKAGE_NAME,
    "lipsyncUnsupportedPolicy": "REST_FALLBACK",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
    "v03Rc1Sha256": V03_RC1_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v05Rc1Sha256": V05_RC1_SHA256,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE8_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
