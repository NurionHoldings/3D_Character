"""v0.6 Gate 5 — Motion Preset parameters (Gate 1–4 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_PARAMETER_HASH_FROZEN = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_PARAMETER_HASH_FROZEN = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"
GATE4_PARAMETER_HASH_FROZEN = "a260ecd6d15502bbb5633e17b6c860955f9307fae25d777db6477c381bad5188"

PRESET_ACTION_PREFIX = "NURION_UnifiedRuntime_"

GATE5_PARAMETERS = {
    "schema": "NURION_V06_GATE5_MOTION_PRESET_PARAMETERS",
    "version": "0.6.0-gate5",
    "track": "Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "production": "NO-GO",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "manualCorrection": "DENY",
    "assetSpecificTuning": "DENY",
    "correctionTarget": "RUNTIME_ACTION_LAYER_ONLY",
    "determinismRuns": 3,
    "fpsMeaningSet": [24, 30, 60],
    "fpsPoseEpsilonM": 1e-5,
    "eyeHeadDoubleEpsilonM": 0.0015,
    "motionSampleFrames": 12,
    "presetActionPrefix": PRESET_ACTION_PREFIX,
    "presets": [
        {
            "id": "Formal_Bow",
            "actionName": "NURION_UnifiedRuntime_Formal_Bow",
            "nameHints": ["formal_bow", "formalbow"],
        },
        {
            "id": "Idle",
            "actionName": "NURION_UnifiedRuntime_Idle",
            "nameHints": ["idle_15", "idle15", "idle"],
        },
        {
            "id": "Gentlemans_Bow",
            "actionName": "NURION_UnifiedRuntime_Gentlemans_Bow",
            "nameHints": ["gentlemans_bow", "gentleman_s_bow", "gentleman"],
        },
    ],
    "lipsyncUnsupportedPolicy": "REST_FALLBACK",
    "missingPresetPolicy": "ABSTAIN",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
