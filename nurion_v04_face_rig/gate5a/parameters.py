"""v0.4 Gate 5A — Offline Speech Alignment parameters (hash-critical)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
GATE4_FROZEN = "0502b73954f8328042c5cf5de3fe7e7ac9e7dc0059e8958d4e51709c5e575c8a"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

# Pinned aligner identity — included in parameter hash
ALIGNER_MODEL = "NURION_ForcedAlign_EnergyEnvelope"
ALIGNER_MODEL_VERSION = "0.4.0-gate5a.1"
KOREAN_PRONUNCIATION_RULESET = "NURION_KO_PRON_v1"
AUDIO_DECODER = "stdlib_wave_pcm16_mono"
NORMALIZATION_POLICY = "peak_rms_16k_mono_pcm16"

GATE5A_PARAMETERS = {
    "schema": "NURION_V04_GATE5A_OFFLINE_SPEECH_ALIGNMENT_PARAMETERS",
    "version": "0.4.0-gate5a",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "gate1to4Mutation": "DENY",
    "microphone": "INACTIVE",
    "realTimeStreaming": "HOLD",
    "liveAvatar": "HOLD",
    "voiceGeneration": "OUT_OF_SCOPE",
    "fullExpression": "HOLD",
    "headBodyMotion": "HOLD",
    "sourceRigApplication": "DENY",
    "gate5b": "HOLD_UNTIL_5A_PASS",
    "path": "FORCED_ALIGNMENT",
    "asrWithoutTranscript": "SEPARATE_PATH_INACTIVE",
    "alignerModel": ALIGNER_MODEL,
    "alignerModelVersion": ALIGNER_MODEL_VERSION,
    "koreanPronunciationRuleset": KOREAN_PRONUNCIATION_RULESET,
    "audioDecoder": AUDIO_DECODER,
    "normalizationPolicy": NORMALIZATION_POLICY,
    "acceptedSampleRates": [16000, 48000],
    "targetSampleRate": 16000,
    "frameMs": 10,
    "hopMs": 5,
    "vadEnergyFloor": 0.02,
    "vadMinSpeechMs": 40,
    "vadMinSilenceMs": 80,
    "padLeadMs": 40,
    "padTrailMs": 80,
    "lowConfidenceThreshold": 0.55,
    "mediumConfidenceThreshold": 0.75,
    "determinismRuns": 3,
    "phonemeDurationPriorMs": {
        "CLOSED": 70,
        "OPEN": 110,
        "WIDE": 100,
        "ROUND": 110,
        "NARROW": 90,
        "TEETH": 80,
        "TONGUE_LIMITED": 75,
        "RESTRICTED": 55,
        "REST": 80,
    },
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5A_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
