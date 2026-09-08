"""v0.6 Production Readiness Gate 4 — longevity / memory / performance."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import V06_RC1_SHA256

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"

# Official bl_info install wrapper (separate from sealed RC.1)
WRAPPER_COMPONENT = {
    "schema": "NURION_V06_BLINFO_INSTALL_WRAPPER_COMPONENT",
    "component": "bl_info_install_wrapper",
    "version": "0.6.0-wrapper.1",
    "wrapperZip": "dist/v0.6/production_readiness/gate3/wrapper/nurion_v06_unified_runtime_from_rc1_install_wrapper.zip",
    "wrapperSha256": "1094c18a12c3fda162ac061ce2cf05f5e0633446aeef41097885c81f41ecd6e7",
    "targetRc1Package": "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip",
    "targetRc1Sha256": V06_RC1_SHA256,
    "rc1Repack": "DENY",
    "role": "OPERATIONAL_INSTALL_COMPONENT_SEPARATE_FROM_RC1",
}

GATE4_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE4_LONGEVITY_MEMORY_PERFORMANCE_PARAMETERS",
    "version": "0.6.0-pr-gate4",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "sealedBaselineSha256": V06_RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "rc1Repack": "DENY",
    "wrapperComponent": WRAPPER_COMPONENT,
    "iterations": 100,
    "fpsCycle": [24, 30, 60],
    "exportFormatCycle": ["FBX", "GLB", "BLEND"],
    "abstainEveryN": 4,
    "cleanReimportEveryN": 10,
    "memorySampleEveryN": 10,
    "failureRateFailPct": 5.0,
    "memoryGrowthFailMb": 1536.0,
    "memoryGrowthLimitationsMb": 512.0,
    "p95DurationFailSec": 120.0,
    "p95DurationLimitationsSec": 45.0,
    "objectGrowthFail": 80,
    "objectGrowthLimitations": 40,
    "actionGrowthFail": 250,
    "actionGrowthLimitations": 80,
    "handlerGrowthFail": 1,
    "tempFileGrowthFail": 120,
    "partialExportPublish": "DENY",
    "autoOptimize": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
