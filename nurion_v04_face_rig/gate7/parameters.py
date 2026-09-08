"""v0.4 Gate 7 — Limited Facial Performance Integration parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
GATE4_FROZEN = "0502b73954f8328042c5cf5de3fe7e7ac9e7dc0059e8958d4e51709c5e575c8a"
GATE5A1_FROZEN = "fb45e97f3aa6e5c9efa0525595ff0f9695af8cfc762cd2a257992a1bf2a7ab82"
GATE5A2_FROZEN = "ce88c09ea44a2ecddeb45aa310e79d7cbddef7a1d03555b6d5edaa5628e843bd"
GATE5B_FROZEN = "c05a56cf78c6f2221e9ee0ef51d4126253d97dea838a481d2b81307fb79e15d7"
GATE6_FROZEN = "356a32253273c73b2a65ffefe809b92b090bda65591171aa0e4100e3110872a8"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

# v0.3 eye expression / beauty locks (from STATUS)
V03_GATE5_EXPR = "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e"
V03_GATE6_BEAUTY = "4fc613deb0bc0e79d2b325354adc48ac3d7a73e87ea54af52a93bc477b6ab190"

CORE_IDS = [
    "word_보험",
    "word_분석",
    "word_상담",
    "word_확인",
    "ins_5",
    "ins_6",
    "ins_7",
    "ins_8",
    "ins_9",
    "ins_10",
    "ins_11",
    "ins_12",
    "ins_13",
    "ins_14",
]
STRESS_IDS = [
    "ai_self_cooling",
    "bottom_dock",
    "cascade",
    "test_arcaon_silicon",
]

GATE7_PARAMETERS = {
    "schema": "NURION_V04_GATE7_LIMITED_FACIAL_PERFORMANCE_PARAMETERS",
    "version": "0.4.0-gate7-limited",
    "mode": "LIMITED_INTEGRATION",
    "fullUnrestricted": "HOLD",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5a1ParameterHash": GATE5A1_FROZEN,
    "gate5a2ParameterHash": GATE5A2_FROZEN,
    "gate5bParameterHash": GATE5B_FROZEN,
    "gate6ParameterHash": GATE6_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "v03ExpressionParameterHash": V03_GATE5_EXPR,
    "v03BeautyParameterHash": V03_GATE6_BEAUTY,
    "parameterTuning": "DENY",
    "gate1to6Mutation": "DENY",
    "v03Mutation": "DENY",
    "sourceCharacterMutation": "DENY",
    "asr": "INACTIVE",
    "microphone": "INACTIVE",
    "realTime": "INACTIVE",
    "objects": {
        "candidate": "NURION_FacialPerformanceCandidate",
        "control": "NURION_PerformanceControl",
        "coordinator": "NURION_PerformanceCoordinator",
        "evidence": "NURION_PerformanceEvidence",
    },
    "allowedGrades": ["SUPPORTED", "SUPPORTED_WITH_FALLBACK"],
    "blockedInputs": [
        "ASR_NO_TRANSCRIPT",
        "REALTIME_MIC",
        "MULTI_SPEAKER",
        "STRONG_NOISE_BGM",
        "SINGING_RAP",
        "EXTREME_FAST_EMOTION",
    ],
    "expressionStatesPrimary": [
        "NEUTRAL",
        "FRIENDLY_SMILE",
        "EXPLAINING",
        "EMPATHY",
        "FOCUS",
        "SPEAKING",
    ],
    "expressionStatesHold": ["SURPRISE", "THINKING"],
    "priority": [
        "MESH_SAFETY_NEUTRAL",
        "LIP_CLOSED_CONSONANT",
        "AUDIO_VISEME_SYNC",
        "BLINK",
        "USER_GAZE",
        "EXPRESSION_INTENSITY",
        "MICRO_GAZE_ORNAMENT",
    ],
    "smileVisemeHeadroom": 0.35,
    "speakingExpressionScale": 0.45,
    "closedConsonantExpressionScale": 0.2,
    "fpsSet": [24, 30, 60],
    "determinismRuns": 3,
    "sampleStepMs": 40,
    "restReturnMu": 1e-4,
    "tongueMode": "TONGUE_LIMITED",
    "onsetSupportLimitMsCore": 453,
    "onsetSupportLimitMsStress": 1545,
    "restFallbackSegmentsDeclared": 68,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE7_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
