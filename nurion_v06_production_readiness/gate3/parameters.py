"""v0.6 Production Readiness Gate 3 — Blender 5.0.1 install/update/remove smoke."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import V06_RC1_SHA256

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"

ADDON_MODULE = "nurion_v06_unified_runtime"
RC1_PACKAGE = "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
RC1_SHA256 = V06_RC1_SHA256
BLENDER_VERSION_REQUIRED = (5, 0, 1)

GATE3_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE3_BLENDER_INSTALL_SMOKE_PARAMETERS",
    "version": "0.6.0-pr-gate3",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "sealedBaselineSha256": RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "rc1Repack": "DENY",
    "addonModule": ADDON_MODULE,
    "blenderVersionRequired": list(BLENDER_VERSION_REQUIRED),
    "installWrapperNote": (
        "Sealed RC.1 ZIP is evidence/runtime payload (not Blender-top-level addon layout). "
        "Gate3 builds a derived install wrapper from verified RC.1 members + bl_info shim; "
        "RC.1 bytes/hash remain immutable."
    ),
    "workflowOps": [
        "nurion_v06.select_character",
        "nurion_v06.analyze_asset",
        "nurion_v06.build_runtime",
        "nurion_v06.apply_preset",
        "nurion_v06.validate_runtime",
        "nurion_v06.export_runtime",
    ],
    "panelId": "NURION_PT_v06_unified_runtime",
    "partialActivationPublish": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "determinismRuns": 2,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
