"""v0.4 Gate 6 — Human Speech Quality Validation parameters (measurement only)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
GATE4_FROZEN = "0502b73954f8328042c5cf5de3fe7e7ac9e7dc0059e8958d4e51709c5e575c8a"
GATE5A_FROZEN = "fb45e97f3aa6e5c9efa0525595ff0f9695af8cfc762cd2a257992a1bf2a7ab82"
GATE5A2_FROZEN = "ce88c09ea44a2ecddeb45aa310e79d7cbddef7a1d03555b6d5edaa5628e843bd"
GATE5B_FROZEN = "c05a56cf78c6f2221e9ee0ef51d4126253d97dea838a481d2b81307fb79e15d7"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE6_PARAMETERS = {
    "schema": "NURION_V04_GATE6_HUMAN_SPEECH_QUALITY_PARAMETERS",
    "version": "0.4.0-gate6.2",
    "mode": "MEASUREMENT_ONLY_NO_PARAM_TUNING",
    "alignerBranch": "Gate5A.2",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5aParameterHash": GATE5A_FROZEN,
    "gate5a2ParameterHash": GATE5A2_FROZEN,
    "gate5bParameterHash": GATE5B_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "gate1to5Mutation": "DENY",
    "sourceCharacterMutation": "DENY",
    "asr": "INACTIVE",
    "transcriptFreeLipSync": "INACTIVE",
    "microphone": "HOLD",
    "realTime": "HOLD",
    "fullExpressionIntegration": "HOLD_UNTIL_GATE6_PASS",
    "headBodyMotion": "HOLD",
    "excludeHumanAudioFromInstallZip": True,
    "acceptedSampleRates": [16000, 48000],
    "preferredSampleRate": 48000,
    "minUtterances": 10,
    "minTotalSpeechMs": 60000,
    "minSpeakersPrimary": 1,
    "onsetOffsetToleranceMs": 400,
    "breathFalsePhonemeEnergyRatio": 0.35,
    "determinismRuns": 3,
    "failureTaxonomy": [
        "FAIL_ALIGNMENT",
        "ASSET_INVALID",
        "PASS_WITH_LIMITATIONS",
        "PASS",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE6_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
