"""Gate 6 — Identity-grade parametric face reconstruction contract."""
from __future__ import annotations

import hashlib
import json
from typing import Any


GATE6_CONTRACT: dict[str, Any] = {
    "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_CONTRACT_V1",
    "gate": 6,
    "purpose": "IDENTITY_GRADE_PARAMETRIC_FACE_RECONSTRUCTION_FOR_HUMAN_VS_ORIGINAL_JUDGMENT",
    "passCriterion": "HUMAN_CAN_JUDGE_EYE_NOSE_MOUTH_FACE_SHAPE_VS_ORIGINAL_NOT_MERELY_MESH_GENERATED",
    "architectureNotAllowed": [
        "IMPROVE_EXISTING_854_TRIANGLE_FACEMESH_AS_IDENTITY_GRADE",
        "REPEAT_MESH_GENERATED_ONLY_PROXY_GATES",
    ],
    "priorBaselinesReadOnly": {
        "gate5ParameterHash": "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d",
        "gate4ParameterHash": "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4",
        "gate3GfParameterHash": "160662e0a954643883be1ae154817cffabf83fced2a429bce63f47ddbb936f5e",
        "mutation": "DENY",
    },
    "selectedParametricModel": {
        "id": "NURION_PARAMETRIC_FACE_V0",
        "commercialClearance": "NURION_OWNED_CANONICAL_ASSET_PLUS_PARAMETRIC_AXES",
        "baseAsset": "NURION_CanonicalBodyPresets_V1.blend",
        "researchOnlyModels": "DENY_UNTIL_OPERATOR_COMMERCIAL_LICENSE",
        "blockedUntilCleared": ["FLAME", "DECA", "BASEL_BFM", "FACESCAPE_WEIGHTS"],
    },
    "pipeline": [
        "COMMERCIAL_LICENSE_GATE",
        "478_LANDMARK_INFER_AND_POSE_NORMALIZE",
        "PARAMETRIC_SHAPE_EXPRESSION_FIT",
        "ALBEDO_SEPARATION_AND_PHOTO_PROJECTION",
        "EYEBALL_EYELID_LIP_ORAL_JAW_STRUCTURES",
        "BIND_CANONICAL_HEAD_NECK",
        "MATCHED_FRONT_LEFT45_RIGHT45_RENDER",
        "ORIGINAL_SIDE_BY_SIDE_COMPARE_PACK",
        "MINIMUM_VISUAL_QUALITY_GATE",
        "ABSTAIN_OR_IDENTITY_REVIEW_NOT_READY_IF_BELOW",
    ],
    "qualityGate": {
        "belowThreshold": ["ABSTAIN", "IDENTITY_REVIEW_NOT_READY"],
        "skipUnnecessaryProxyReviews": True,
        "humanSelfAndInternalReview": "ONLY_WHEN_QUALITY_GATE_ALLOWS",
        "reusePinnedP001P003": "WHEN_EVALUABLE",
        "inheritConsentPinDeletion": True,
    },
    "nonNegotiable": [
        "COMMERCIAL_LICENSE",
        "ORIGINAL_AND_BASELINE_MUTATION_CHECK",
        "DETERMINISM_AND_ABSTAIN",
        "HUMAN_SIMILARITY_REVIEW_WHEN_READY",
        "PRIVACY_CONSENT_AND_DELETION",
    ],
    "claims": {
        "photorealAutomaticPass": "DENY",
        "production": "NO-GO",
        "countsAsGate8ParticipantEvidence": "DENY",
        "arkaonAutonomousProductionLearning": "DENY",
    },
}


def gate6_parameter_hash() -> str:
    raw = json.dumps(GATE6_CONTRACT, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
