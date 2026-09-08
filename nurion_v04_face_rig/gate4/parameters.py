"""v0.4 Gate 4 — Phoneme Timing & Coarticulation parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE4_PARAMETERS = {
    "schema": "NURION_V04_GATE4_PHONEME_TIMING_PARAMETERS",
    "version": "0.4.0-gate4",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "audioFeatureExtraction": "INACTIVE",
    "speechToPhoneme": "INACTIVE",
    "microphone": "INACTIVE",
    "realTimeLipSync": "HOLD",
    "emotionFullExpression": "HOLD",
    "sourceRigApplication": "DENY",
    "objects": {
        "timeline": "NURION_PhonemeTimeline",
        "solver": "NURION_CoarticulationSolver",
        "mixer": "NURION_VisemeMixer",
        "evidence": "NURION_TimingEvidence",
    },
    "fpsSet": [24, 30, 60],
    "minConsonantHoldMs": 40,
    "anticipationMs": 50,
    "releaseMs": 60,
    "maxBlendSources": 4,
    "popThresholdDelta": 0.55,
    "determinismRuns": 3,
    "axisLimitsMU": {
        "jawOpen": 0.35,
        "lipWide": 0.18,
        "lipRound": 0.14,
        "lipClose": 0.12,
        "upperLipRaise": 0.08,
        "lowerLipDrop": 0.10,
        "cornerPull": 0.12,
        "teethApproach": 0.06,
    },
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
