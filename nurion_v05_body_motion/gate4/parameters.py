"""v0.5 Gate 4 — Foot Slide & Ground Lock (clone-only)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_FROZEN = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
FOOT_SLIDE_INHERITED = 13

# Gate1-frozen Formal Bow slide evidence (consume in Gate4)
INHERITED_SLIDE_EVENTS = [
    {"bone": "LeftFoot", "fromFrame": 21, "toFrame": 26, "horizontalM": 0.05038},
    {"bone": "LeftFoot", "fromFrame": 26, "toFrame": 31, "horizontalM": 0.08251},
    {"bone": "LeftFoot", "fromFrame": 31, "toFrame": 36, "horizontalM": 0.01048},
    {"bone": "LeftFoot", "fromFrame": 156, "toFrame": 161, "horizontalM": 0.01896},
    {"bone": "LeftFoot", "fromFrame": 161, "toFrame": 166, "horizontalM": 0.07001},
    {"bone": "LeftFoot", "fromFrame": 166, "toFrame": 171, "horizontalM": 0.0365},
    {"bone": "LeftToeBase", "fromFrame": 21, "toFrame": 26, "horizontalM": 0.03895},
    {"bone": "LeftToeBase", "fromFrame": 26, "toFrame": 31, "horizontalM": 0.1081},
    {"bone": "LeftToeBase", "fromFrame": 31, "toFrame": 36, "horizontalM": 0.01748},
    {"bone": "LeftToeBase", "fromFrame": 36, "toFrame": 41, "horizontalM": 0.00821},
    {"bone": "LeftToeBase", "fromFrame": 156, "toFrame": 161, "horizontalM": 0.02938},
    {"bone": "LeftToeBase", "fromFrame": 161, "toFrame": 166, "horizontalM": 0.08291},
    {"bone": "LeftToeBase", "fromFrame": 166, "toFrame": 171, "horizontalM": 0.02589},
]

GATE4_PARAMETERS = {
    "schema": "NURION_V05_GATE4_FOOT_SLIDE_GROUND_LOCK_PARAMETERS",
    "version": "0.5.0-gate4",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v04Mutation": "DENY",
    "sourceZipFbxMutation": "DENY",
    "sourceActionMutation": "DENY",
    "gate3ActionPreserve": "APPLY_THEN_LOCK_FEET_ONLY",
    "rightForeArmReCorrect": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "footSlideInherited": FOOT_SLIDE_INHERITED,
    "inheritedSlideEvents": INHERITED_SLIDE_EVENTS,
    "production": "NO-GO",
    "determinismRuns": 3,
    "objects": {
        "candidateMesh": "NURION_BodyMotionCandidate",
        "candidateArmature": "NURION_BodyRigClone",
        "control": "NURION_FootLockControl",
        "evidence": "NURION_FootLockEvidence",
        "cloneActionPrefix": "NURION_Gate4_CloneAction",
    },
    "footBones": ["LeftFoot", "LeftToeBase", "RightFoot", "RightToeBase"],
    "primaryFeet": ["LeftFoot", "RightFoot"],
    "toeBones": ["LeftToeBase", "RightToeBase"],
    "legChains": {
        "LeftFoot": ["Hips", "LeftUpLeg", "LeftLeg", "LeftFoot"],
        "RightFoot": ["Hips", "RightUpLeg", "RightLeg", "RightFoot"],
        "LeftToeBase": ["Hips", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"],
        "RightToeBase": ["Hips", "RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"],
    },
    # Gate1-compatible reproduce
    "footSlideEpsilonM": 0.008,
    "diagnoseFrameStepDivisor": 40,
    # Contact / lock
    "contactHeightEpsM": 0.045,
    "supportHorizSpeedMaxM": 0.012,
    "lockHorizEpsM": 0.008,
    "lockHeightEpsM": 0.015,
    "groundPercentile": 0.05,
    "forceLockInheritedWindows": True,
    # Continuous support clusters on Formal Bow (consume Gate1 windows)
    "lockClusters": [[18, 50], [150, 185]],
    # Correction distribution (sum <= 1). Arms never touched.
    "chainWeights": {
        "Hips": 0.40,
        "UpLeg": 0.22,
        "Leg": 0.18,
        "Foot": 0.15,
        "Toe": 0.05,
    },
    "forbiddenBones": ["RightForeArm", "LeftForeArm", "LeftHand", "RightHand", "LeftArm", "RightArm"],
    "motionMeaningEpsilonM": 0.12,
    "lockBlendMax": 0.55,
    "motionSampleFrames": 16,
    "heelToePitchEpsDeg": 55.0,
    "footCrossEpsM": 0.02,
    "kneeReverseSevereDeg": -35.0,
    "penetrationVolumeSpike": 1.55,
    "maxCorrectFrames": 120,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE4_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
