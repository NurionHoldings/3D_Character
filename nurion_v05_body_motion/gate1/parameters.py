"""v0.5 Body Motion Retarget & Rig Correction — track parameters."""

from __future__ import annotations

import hashlib
import json

V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V04_MUTATION = "DENY"

GATE1_PARAMETERS = {
    "schema": "NURION_V05_GATE1_BODY_MOTION_DIAGNOSIS_PARAMETERS",
    "version": "0.5.0-gate1",
    "track": "Body Motion Retarget & Rig Correction",
    "seedAsset": "ai-aba.bow.zip",
    "seedZipSha256": "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309",
    "firstCriterion": "FORMAL_BOW",
    "v04Mutation": V04_MUTATION,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "correctionTarget": "CLONE_ONLY",
    "production": "NO-GO",
    "determinismRuns": 3,
    "pipeline": [
        "FORMAL_BOW_SOURCE_MOTION_RIG_DIAGNOSIS",
        "REST_BONE_AXIS_HIERARCHY",
        "JOINT_LIMITS_ABNORMAL_DEFORM",
        "FOOT_SLIDE_GROUND_LOCK",
        "BODY_CLOTHING_MESH_PENETRATION",
        "CLONE_SAFE_CORRECTION_CANDIDATE",
        "V04_FACE_EYE_LIPSYNC_SYNC_READONLY",
        "DETERMINISM_CROSS_ASSET",
        "RC_HOLDOUT_SEAL_REVIEW",
    ],
    "jointFocus": [
        "shoulder",
        "elbow",
        "wrist",
        "spine",
        "neck",
        "hip",
        "knee",
        "ankle",
    ],
    "footSlideEpsilonM": 0.008,
    "penetrationProbeSamples": 24,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE1_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
