"""v0.5 Gate 2 — Bone Axis & Hierarchy Normalization parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
FOOT_SLIDE_INHERITED = 13

GATE2_PARAMETERS = {
    "schema": "NURION_V05_GATE2_BONE_AXIS_HIERARCHY_PARAMETERS",
    "version": "0.5.0-gate2",
    "gate1ParameterHash": GATE1_FROZEN,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v04Mutation": "DENY",
    "sourceZipFbxMutation": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "footSlideFix": "DENY_INHERIT_TO_GATE3",
    "footSlideInherited": FOOT_SLIDE_INHERITED,
    "production": "NO-GO",
    "determinismRuns": 3,
    "objects": {
        "candidateMesh": "NURION_BodyMotionCandidate",
        "candidateArmature": "NURION_BodyRigClone",
        "control": "NURION_BodyAxisControl",
        "evidence": "NURION_BodyAxisEvidence",
    },
    # Meshy Formal Bow: anatomical parent order (name indices are inverted).
    "chains": {
        "spine": ["Hips", "Spine02", "Spine01", "Spine", "neck", "Head"],
        "armL": ["LeftShoulder", "LeftArm", "LeftForeArm", "LeftHand"],
        "armR": ["RightShoulder", "RightArm", "RightForeArm", "RightHand"],
        "legL": ["LeftUpLeg", "LeftLeg", "LeftFoot", "LeftToeBase"],
        "legR": ["RightUpLeg", "RightLeg", "RightFoot", "RightToeBase"],
    },
    # Axis fail gates apply to limb chains; spine is continuity-primary (Hips root axis often non-colinear).
    "axisGateChains": ["armL", "armR", "legL", "legR"],
    "axisReportChains": ["spine", "armL", "armR", "legL", "legR"],
    "lrPairs": [
        ["LeftShoulder", "RightShoulder"],
        ["LeftArm", "RightArm"],
        ["LeftForeArm", "RightForeArm"],
        ["LeftHand", "RightHand"],
        ["LeftUpLeg", "RightUpLeg"],
        ["LeftLeg", "RightLeg"],
        ["LeftFoot", "RightFoot"],
        ["LeftToeBase", "RightToeBase"],
    ],
    "motionSampleFrames": 12,
    "motionDriftEpsilonM": 0.002,
    "axisDotMin": 0.25,
    "lengthRelEps": 1e-5,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
