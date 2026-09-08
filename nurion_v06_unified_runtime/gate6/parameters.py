"""v0.6 Gate 6 — Blender operator workflow parameters (Gate 1–5 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_PARAMETER_HASH_FROZEN = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_PARAMETER_HASH_FROZEN = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"
GATE4_PARAMETER_HASH_FROZEN = "a260ecd6d15502bbb5633e17b6c860955f9307fae25d777db6477c381bad5188"
GATE5_PARAMETER_HASH_FROZEN = "81885dbc3c119c08c63add3a9e45caf9860a8bcbd1e9b4363cac46ac9aa9c0be"

WORKFLOW_STEPS = [
    "SELECT_CHARACTER",
    "ANALYZE_ASSET",
    "BUILD_UNIFIED_RUNTIME",
    "APPLY_MOTION_PRESET",
    "VALIDATE_RUNTIME",
    "EXPORT",
]

GATE6_PARAMETERS = {
    "schema": "NURION_V06_GATE6_BLENDER_WORKFLOW_PARAMETERS",
    "version": "0.6.0-gate6",
    "track": "Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "gate5Mutation": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "manualCorrection": "DENY",
    "assetSpecificTuning": "DENY",
    "forceApplyIneligible": "DENY",
    "forceApplyMissingPreset": "DENY",
    "exportRequiresValidation": True,
    "orderViolationPolicy": "SAFE_ABORT",
    "workflowSteps": WORKFLOW_STEPS,
    "runtimeCollection": "NURION_UnifiedRuntime",
    "runtimeActionPrefix": "NURION_UnifiedRuntime_",
    "fpsChoices": [24, 30, 60],
    "lipsyncUnsupportedPolicy": "REST_FALLBACK",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
    "uiMustShow": [
        "classification",
        "abstainReasons",
        "lipsyncMode",
        "productionNO_GO",
        "selectedPreset",
        "validationStatus",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE6_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
