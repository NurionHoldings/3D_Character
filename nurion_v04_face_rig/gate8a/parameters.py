"""v0.4 Gate 8A — Full Limited Integration Regression parameters."""

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
GATE7_FROZEN = "1784696fb7513c7e693ada2faff48a3ae3413b3bf4f7aa9b5641442d2d5f258f"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE8A_PARAMETERS = {
    "schema": "NURION_V04_GATE8A_FULL_LIMITED_INTEGRATION_REGRESSION_PARAMETERS",
    "version": "0.4.0-gate8a",
    "mode": "FULL_LIMITED_INTEGRATION_REGRESSION",
    "fullUnrestricted": "HOLD",
    "intermediateOutputReuse": "DENY",
    "cleanSceneRebuild": "REQUIRED",
    "parameterTuning": "DENY",
    "gate1to7Mutation": "DENY",
    "v03Mutation": "DENY",
    "sourceCharacterMutation": "DENY",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5a1ParameterHash": GATE5A1_FROZEN,
    "gate5a2ParameterHash": GATE5A2_FROZEN,
    "gate5bParameterHash": GATE5B_FROZEN,
    "gate6ParameterHash": GATE6_FROZEN,
    "gate7ParameterHash": GATE7_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "determinismRuns": 3,
    "asr": "INACTIVE",
    "microphone": "INACTIVE",
    "realTime": "INACTIVE",
    "releaseCandidate": "HOLD_UNTIL_8A_PASS",
    "freshHoldoutRequired": True,
    "finalSeal": "HOLD",
    "excludeHumanAudioFromPackage": True,
    "pipeline": [
        "GATE1_FACE_CAPABILITY",
        "GATE2_PROCEDURAL_FACE_RIG",
        "GATE3_VISEME_SHAPE_BASIS",
        "GATE4_PHONEME_TIMING",
        "GATE5A2_FORCED_ALIGNMENT",
        "GATE5B_AUTO_LIP_SYNC",
        "GATE6_SUPPORTED_DOMAIN_POLICY",
        "GATE7_LIMITED_FACIAL_PERFORMANCE",
        "V03_EYE_GAZE_BLINK_EXPRESSION_BEAUTY_READONLY",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE8A_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
