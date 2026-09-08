"""v0.6 Gate 1 — frozen parameters and sealed baseline hashes."""

from __future__ import annotations

import hashlib
import json

V02_SHA256 = "679190e443d5814c6f7a7c41dcc7a62a52a0b02a6697e7485358d6a8853b02b2"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_RC1_SHA256 = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"

V03_PACKAGE = "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V04_PACKAGE = "NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V05_PACKAGE = "NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"

V03_PACKAGE_REL = "dist/v0.3/universal_eye/gate7a/package/" + V03_PACKAGE
V04_PACKAGE_REL = "dist/v0.4/gate8b/package/" + V04_PACKAGE
V05_PACKAGE_REL = "dist/v0.5/gate9/package/" + V05_PACKAGE

INHERITED_V05_LIMITATIONS = [
    "FOOT_SLIDE_RESIDUAL_11",
    "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
    "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
    "HOLDOUT_FOOT_SLIDE_9",
]

GATE1_PARAMETERS = {
    "schema": "NURION_V06_GATE1_UNIFIED_CONTRACT_PARAMETERS",
    "version": "0.6.0-gate1",
    "track": "Unified Character Animation Runtime",
    "product": "NURION Unified Character Animation Runtime",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "sealedBaselineMutation": "DENY",
    "repackSealedRc": "DENY",
    "inPlaceRepair": "DENY",
    "limitationAutoClear": "DENY",
    "sourceCharacterMutation": "DENY",
    "correctionTarget": "CLONE_OR_RUNTIME_LAYER_ONLY",
    "determinismRuns": 3,
    "supportedFps": [24, 30, 60],
    "primaryFaceTimeline": "word_확인",
    "candidateBodyAction": "NURION_BodyMotionCandidateAction",
    "unifiedRuntimeActionPrefix": "NURION_UnifiedRuntime_",
    "motionPresets": [
        "Formal_Bow",
        "Idle",
        "Gentlemans_Bow",
    ],
    "readonlyBaselines": {
        "v0.2": {"sha256": V02_SHA256, "role": "IMMUTABLE_LANDMARKER"},
        "v0.3": {
            "package": V03_PACKAGE,
            "path": V03_PACKAGE_REL,
            "sha256": V03_RC1_SHA256,
            "role": "SEALED_READONLY_UNIVERSAL_EYE",
            "status": "SEALED",
        },
        "v0.4": {
            "package": V04_PACKAGE,
            "path": V04_PACKAGE_REL,
            "sha256": V04_RC1_SHA256,
            "role": "SEALED_READONLY_NATIVE_FACE_LIPSYNC",
            "status": "SEALED_LIMITED_DOMAIN",
        },
        "v0.5": {
            "package": V05_PACKAGE,
            "path": V05_PACKAGE_REL,
            "sha256": V05_RC1_SHA256,
            "role": "SEALED_READONLY_BODY_MOTION",
            "status": "SEALED_WITH_LIMITATIONS",
        },
    },
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "pipeline": [
        "UNIFIED_CONTRACT_IO_SPEC",
        "AUTO_ASSET_DIAGNOSIS",
        "UNIFIED_BONE_MAPPING",
        "BODY_FACE_EYE_BIND",
        "MOTION_PRESET",
        "BLENDER_OPERATOR_WORKFLOW",
        "OUTPUT_VALIDATION",
        "FRESH_HOLDOUT_AND_RC",
    ],
    "classificationLabels": ["FULL", "LIMITED", "INELIGIBLE"],
    "abstainPolicy": "UNSUPPORTED_DIMENSION_MUST_ABSTAIN",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE1_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
