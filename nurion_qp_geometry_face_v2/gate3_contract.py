"""Frozen candidate contract for Gate 3 offline analyzer implementation."""
from __future__ import annotations

import hashlib
import json


GATE3_CONTRACT = {
    "schema": "NURION_V07_QP_GF_FACE_V2_GATE3_CONTRACT_V1",
    "gate2OfficialParameterHash": "93d87283d3a5492d6c2773f46122f4d32cce63026bfa77f111a956fd4345fc60",
    "implementation": {
        "backendInjection": "REQUIRED",
        "expectedDenseLandmarks": 478,
        "representations": ["ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"],
        "normalization": "EYE_CENTER_INTEROCULAR_DISTANCE",
        "consensus": "LANDMARK_MEDIAN",
        "medianDisagreementMax": 0.025,
        "p95DisagreementMax": 0.06,
        "oneBranch": "GEOMETRY_REVIEW_REQUIRED",
        "branchConflict": "ABSTAIN_RECAPTURE_NO_FABRICATION",
        "skinStage": "AFTER_GEOMETRY",
        "skinUncertain": "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER",
    },
    "runtime": {
        "network": "DENY",
        "modelShaVerificationBeforeLoad": "REQUIRED",
        "currentWorkspaceOfficialModelBytes": "UNAVAILABLE",
        "currentWorkspaceMediapipeRuntime": "UNAVAILABLE",
        "actualPinnedModelInference": "NOT_EXECUTED",
    },
    "validation": {
        "syntheticOnly": True,
        "realParticipantUsage": 0,
        "P001P002P003": "DENY",
        "threeRunDeterminism": "PASS_SYNTHETIC_BACKEND_ONLY",
        "productAccuracyClaim": "DENY",
    },
    "baseline": {
        "quickProfileGate2Mutation": 0,
        "quickProfileGate3RunnerMutation": 0,
        "gate8Mutation": 0,
        "production": "NO-GO",
    },
}


def gate3_parameter_hash() -> str:
    raw = json.dumps(GATE3_CONTRACT, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
