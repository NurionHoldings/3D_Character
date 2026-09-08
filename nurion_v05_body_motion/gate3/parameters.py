"""v0.5 Gate 3 — Joint Limits & Abnormal Deform (clone-only)."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
FOOT_SLIDE_INHERITED = 13

GATE3_PARAMETERS = {
    "schema": "NURION_V05_GATE3_JOINT_LIMITS_ABNORMAL_DEFORM_PARAMETERS",
    "version": "0.5.0-gate3",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v04Mutation": "DENY",
    "sourceZipFbxMutation": "DENY",
    "sourceActionMutation": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "footSlideFix": "DENY_INHERIT_TO_LATER_GATE",
    "footSlideInherited": FOOT_SLIDE_INHERITED,
    "production": "NO-GO",
    "determinismRuns": 3,
    "objects": {
        "candidateMesh": "NURION_BodyMotionCandidate",
        "candidateArmature": "NURION_BodyRigClone",
        "control": "NURION_JointLimitControl",
        "evidence": "NURION_JointLimitEvidence",
        "cloneActionPrefix": "NURION_Gate3_CloneAction",
    },
    "spineChain": ["Hips", "Spine02", "Spine01", "Spine", "neck", "Head"],
    "armChains": {
        "L": ["LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand"],
        "R": ["RightShoulder", "RightArm", "RightForeArm", "RightHand"],
    },
    "legChains": {
        "L": ["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"],
        "R": ["RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"],
    },
    # Soft anatomical / retarget safety envelopes (degrees / ratios)
    "limitsDeg": {
        "shoulderLocal": 120.0,
        "elbowLocal": 150.0,
        "wristLocal": 90.0,
        "spineLocal": 75.0,
        "neckLocal": 80.0,
        "hipLocal": 120.0,
        "kneeLocal": 150.0,
        "ankleLocal": 75.0,
    },
    "reverseJointDeg": {
        # Signed flexion below this (negative = past straight) => reverse (report)
        "elbow": -12.0,
        "knee": -12.0,
    },
    # Beyond this after correction attempt => hard FAIL; milder residuals may be limitations
    "reverseJointSevereDeg": {
        "elbow": -35.0,
        "knee": -35.0,
    },
    "reverseCorrectMaxSlerp": 0.22,
    "scaleMin": 0.85,
    "scaleMax": 1.15,
    "rotationSpikeDeg": 55.0,
    "spineRootImpactDotWarn": 0.0,
    "spineRootImpactCouplingMax": 0.35,
    "motionMeaningEpsilonM": 0.015,
    "motionSampleFrames": 16,
    "correctClampFactor": 0.92,
    "maxCorrectedKeysPerBone": 48,
    "frameStep": 1,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
