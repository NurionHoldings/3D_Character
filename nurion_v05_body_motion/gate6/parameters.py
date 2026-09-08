"""v0.5 Gate 6 — Clone-Safe Correction Candidate (integrated Action)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_FROZEN = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
GATE4_FROZEN = "837fd79115113aa316671552d7fd4027f1e873e984c6d5ebc35239fd66e357ca"
GATE5_FROZEN = "3ac0c130af6200d73dac0d0b6b62e01196bd8588a4f820a6b146c77632a6c3ac"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
FOOT_SLIDE_RESIDUAL_GATE4 = 11

GATE6_PARAMETERS = {
    "schema": "NURION_V05_GATE6_CLONE_SAFE_CORRECTION_CANDIDATE_PARAMETERS",
    "version": "0.5.0-gate6",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5ParameterHash": GATE5_FROZEN,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v04Mutation": "DENY",
    "sourceZipFbxMutation": "DENY",
    "sourceActionMutation": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "rightForeArmReCorrect": "DENY",
    "footSlideFix": "DENY_REMEASURE_ONLY",
    "footSlideResidualGate4": FOOT_SLIDE_RESIDUAL_GATE4,
    "forceLimitationsToZero": "DENY",
    "production": "NO-GO",
    "determinismRuns": 3,
    "fpsMeaningSet": [24, 30, 60],
    "objects": {
        "candidateMesh": "NURION_BodyMotionCandidate",
        "candidateArmature": "NURION_BodyRigClone",
        "candidateAction": "NURION_BodyMotionCandidateAction",
        "control": "NURION_CandidateControl",
        "evidence": "NURION_CandidateEvidence",
        "cloneActionPrefix": "NURION_Gate6_CloneAction",
    },
    "spineChain": ["Hips", "Spine02", "Spine01", "Spine", "neck", "Head"],
    "motionMeaningEpsilonM": 0.12,
    "motionSampleFrames": 16,
    "fpsPoseEpsilonM": 1e-5,
    "keyDedupFrameEps": 1e-4,
    "keyRedundantValueEps": 1e-5,
    "shallowContactDepthMaxM": 0.008,
    "shallowContactAccept": True,
    "slideWorsenTol": 0,
    "restLengthRelEps": 1e-5,
    "axisDotMin": 0.25,
    "gate3MinKeysExpected": 20,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE6_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
