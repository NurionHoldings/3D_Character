"""v0.4 Gate 5A.2 — Human Speech Alignment Improvement (branch; does not mutate 5A.1)."""

from __future__ import annotations

import hashlib
import json

GATE5A1_FROZEN = "fb45e97f3aa6e5c9efa0525595ff0f9695af8cfc762cd2a257992a1bf2a7ab82"
GATE5B_FROZEN = "c05a56cf78c6f2221e9ee0ef51d4126253d97dea838a481d2b81307fb79e15d7"
GATE4_FROZEN = "0502b73954f8328042c5cf5de3fe7e7ac9e7dc0059e8958d4e51709c5e575c8a"
GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE5A2_PARAMETERS = {
    "schema": "NURION_V04_GATE5A2_HUMAN_SPEECH_ALIGNMENT_PARAMETERS",
    "version": "0.4.0-gate5a.2",
    "branch": "Gate5A.2_HumanSpeechAlignmentImprovement",
    "gate5a1ParameterHash": GATE5A1_FROZEN,
    "gate5a1Mutation": "DENY",
    "gate5bParameterHash": GATE5B_FROZEN,
    "gate5bMutation": "DENY",
    "gate4ParameterHash": GATE4_FROZEN,
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "alignerModel": "NURION_ForcedAlign_ClassAware_v2",
    "alignerModelVersion": "0.4.0-gate5a.2.1",
    "koreanPronunciationRuleset": "NURION_KO_PRON_v2_LEXICON",
    "audioDecoder": "stdlib_wave_pcm16_mono",
    "normalizationPolicy": "peak_rms_16k_mono_pcm16",
    "path": "FORCED_ALIGNMENT",
    "acceptedSampleRates": [16000, 48000],
    "targetSampleRate": 16000,
    "frameMs": 10,
    "hopMs": 5,
    "vadEnergyFloor": 0.018,
    "vadMinSpeechMs": 40,
    "vadMinSilenceMs": 80,
    "breathEnergyRatio": 0.28,
    "breathMinMs": 90,
    "padLeadMs": 40,
    "padTrailMs": 80,
    "lowConfidenceThreshold": 0.55,
    "mediumConfidenceThreshold": 0.75,
    "determinismRuns": 3,
    "phonemeDurationPriorMs": {
        "CLOSED": 70,
        "OPEN": 120,
        "WIDE": 110,
        "ROUND": 120,
        "NARROW": 95,
        "TEETH": 85,
        "TONGUE_LIMITED": 75,
        "RESTRICTED": 55,
        "REST": 80,
    },
    "phonemeDurationMinMs": {
        "CLOSED": 35,
        "OPEN": 50,
        "WIDE": 45,
        "ROUND": 50,
        "NARROW": 40,
        "TEETH": 40,
        "TONGUE_LIMITED": 35,
        "RESTRICTED": 25,
        "REST": 20,
    },
    "phonemeDurationMaxMs": {
        "CLOSED": 180,
        "OPEN": 320,
        "WIDE": 300,
        "ROUND": 320,
        "NARROW": 280,
        "TEETH": 220,
        "TONGUE_LIMITED": 200,
        "RESTRICTED": 160,
        "REST": 2000,
    },
    "energyDependence": {
        "OPEN": 1.0,
        "WIDE": 1.0,
        "ROUND": 1.0,
        "NARROW": 0.85,
        "CLOSED": 0.15,
        "TEETH": 0.45,
        "TONGUE_LIMITED": 0.35,
        "RESTRICTED": 0.25,
        "REST": 0.0,
    },
    "gate5bSafetyContract": {
        "enabled": True,
        "mapLowToInsufficientForConsumer": True,
        "preserveAlignmentConfidenceField": "alignmentConfidence",
    },
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5A2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
