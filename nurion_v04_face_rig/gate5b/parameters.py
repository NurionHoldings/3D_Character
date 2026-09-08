"""v0.4 Gate 5B — Automatic Lip Sync Rendering parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
GATE3_FROZEN = "c3ce883f3ff56b3be6649550f0e5c53eb5ef61e2568f057b9d07e23de2d9f6bd"
GATE4_FROZEN = "0502b73954f8328042c5cf5de3fe7e7ac9e7dc0059e8958d4e51709c5e575c8a"
GATE5A_FROZEN = "fb45e97f3aa6e5c9efa0525595ff0f9695af8cfc762cd2a257992a1bf2a7ab82"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE5B_PARAMETERS = {
    "schema": "NURION_V04_GATE5B_AUTO_LIP_SYNC_PARAMETERS",
    "version": "0.4.0-gate5b",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5aParameterHash": GATE5A_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "gate1to5aMutation": "DENY",
    "asr": "INACTIVE",
    "microphone": "INACTIVE",
    "realTimeLipSync": "HOLD",
    "fullExpression": "HOLD",
    "headBodyMotion": "HOLD",
    "sourceRigApplication": "DENY",
    "objects": {
        "control": "NURION_AutoLipSyncControl",
        "action": "NURION_AutoLipSyncAction",
        "evidence": "NURION_AudioVisemeEvidence",
    },
    "fpsSet": [24, 30, 60],
    "renderFps": 30,
    "sampleStepMs": 10,
    "silenceMotionEpsilon": 0.02,
    "sealMinLipClose": 0.35,
    "syncMaxPrimaryLagMs": 80,
    "restReturnMu": 1e-4,
    "determinismRuns": 3,
    "confidenceTiers": {
        "HIGH": {"min": 0.75, "scale": 1.0},
        "MEDIUM": {"min": 0.55, "scale": 0.7},
        "LOW": {"min": 0.35, "scale": 0.4},
        "INSUFFICIENT": {"min": 0.0, "scale": 0.0},
    },
    "insufficientSafeJaw": 0.12,
    "lowConfidenceOverdriveScale": 0.45,
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
    payload = json.dumps(GATE5B_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
