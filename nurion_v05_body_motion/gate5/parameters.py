"""v0.5 Gate 5 — Mesh Penetration (clone-only, mesh-based)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_FROZEN = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
GATE4_FROZEN = "837fd79115113aa316671552d7fd4027f1e873e984c6d5ebc35239fd66e357ca"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
FOOT_SLIDE_RESIDUAL_GATE4 = 11

GATE5_PARAMETERS = {
    "schema": "NURION_V05_GATE5_MESH_PENETRATION_PARAMETERS",
    "version": "0.5.0-gate5",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v04Mutation": "DENY",
    "sourceZipFbxMutation": "DENY",
    "sourceActionMutation": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "rightForeArmReCorrect": "DENY",
    "footSlideFix": "DENY_VERIFY_NO_WORSEN",
    "footSlideResidualGate4": FOOT_SLIDE_RESIDUAL_GATE4,
    "preserveGate3Action": True,
    "preserveGate4FootLock": True,
    "production": "NO-GO",
    "determinismRuns": 3,
    "objects": {
        "candidateMesh": "NURION_BodyMotionCandidate",
        "candidateArmature": "NURION_BodyRigClone",
        "control": "NURION_PenetrationControl",
        "evidence": "NURION_PenetrationEvidence",
        "cloneActionPrefix": "NURION_Gate5_CloneAction",
    },
    "regions": {
        "torso": ["Hips", "Spine", "Spine01", "Spine02", "neck", "Head"],
        "armL": ["LeftShoulder", "LeftArm", "LeftForeArm"],
        "armR": ["RightShoulder", "RightArm", "RightForeArm"],
        "handL": ["LeftHand"],
        "handR": ["RightHand"],
        "legL": ["LeftUpLeg", "LeftLeg"],
        "legR": ["RightUpLeg", "RightLeg"],
        "footL": ["LeftFoot", "LeftToeBase"],
        "footR": ["RightFoot", "RightToeBase"],
    },
    # Distal-focused pairs reduce false positives at anatomical joints on a single mesh
    "collisionPairs": [
        ["handL", "torso"],
        ["handR", "torso"],
        ["handL", "legL"],
        ["handR", "legR"],
        ["handL", "legR"],
        ["handR", "legL"],
        ["armL", "torso"],
        ["armR", "torso"],
        ["armL", "legL"],
        ["armR", "legR"],
        ["legL", "legR"],
        ["armL", "armR"],
    ],
    # For torso collisions, probe only these bones' verts (exclude shoulder/hip junctions)
    "probeBonesOverride": {
        "armL|torso": ["LeftForeArm"],
        "armR|torso": ["RightForeArm"],
        "handL|torso": ["LeftHand"],
        "handR|torso": ["RightHand"],
        "armL|legL": ["LeftForeArm", "LeftHand"],
        "armR|legR": ["RightForeArm", "RightHand"],
        "armL|armR": ["LeftForeArm", "LeftHand"],
    },
    "vertexWeightMin": 0.35,
    "probeStride": 2,
    "contactDistM": 0.0035,
    "penetrateDistM": 0.0010,
    "sustainFrames": 4,
    "areaProxyVertMin": 5,
    "requireInsideNormal": True,
    "minPenDepthM": 0.0020,
    "depthWarnM": 0.008,
    "depthFailM": 0.025,
    # Thigh–thigh closeness on Formal Bow is usually garment proximity, not hard FAIL
    "softPairs": ["legL|legR", "armL|armR"],
    "correctPushM": 0.006,
    "correctBlend": 0.45,
    "maxCorrectFrames": 48,
    "motionMeaningEpsilonM": 0.12,
    "motionSampleFrames": 16,
    "forbiddenBones": [
        "RightForeArm",
        "LeftFoot",
        "LeftToeBase",
        "RightFoot",
        "RightToeBase",
    ],
    "correctBoneByPair": {
        "handL|torso": "LeftHand",
        "armL|torso": "LeftArm",
        "handR|torso": "RightHand",
        "armR|torso": "RightArm",
        "legL|torso": "LeftUpLeg",
        "legR|torso": "RightUpLeg",
        "armL|armR": "LeftArm",
        "legL|legR": "LeftUpLeg",
        "handL|legL": "LeftHand",
        "handR|legR": "RightHand",
        "armL|legL": "LeftArm",
        "armR|legR": "RightArm",
    },
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
