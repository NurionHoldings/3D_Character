"""v0.6 Gate 4 — Body + Face + Eye bind parameters (Gate 1–3 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_PARAMETER_HASH_FROZEN = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_PARAMETER_HASH_FROZEN = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"

GATE4_PARAMETERS = {
    "schema": "NURION_V06_GATE4_BODY_FACE_EYE_BIND_PARAMETERS",
    "version": "0.6.0-gate4",
    "track": "Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "production": "NO-GO",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "manualCorrection": "DENY",
    "assetSpecificTuning": "DENY",
    "correctionTarget": "RUNTIME_LAYER_ONLY",
    "determinismRuns": 3,
    "fpsMeaningSet": [24, 30, 60],
    "fpsPoseEpsilonM": 1e-5,
    "eyeHeadDoubleEpsilonM": 0.0015,
    "timelineAlignEpsilonMs": 40.0,
    "motionSampleFrames": 16,
    "primaryTimeline": "word_확인",
    "timelinesDir": "dist/v0.4/gate6/human_gate4_timelines",
    "eyeAttachRole": "HEAD",
    "objects": {
        "control": "NURION_UnifiedRuntime_Control",
        "coordinator": "NURION_UnifiedRuntime_Coordinator",
        "evidence": "NURION_UnifiedRuntime_Evidence",
        "eyeL": "NURION_UnifiedRuntime_Eye.L",
        "eyeR": "NURION_UnifiedRuntime_Eye.R",
    },
    "lipsyncUnsupportedPolicy": "REST_FALLBACK",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
