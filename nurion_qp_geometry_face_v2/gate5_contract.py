"""Gate 5 — dense identity face draft from 478 Geometry Identity landmarks."""
from __future__ import annotations

import hashlib
import json


GATE5_CONTRACT = {
    "schema": "NURION_V07_QP_GF_FACE_V2_GATE5_CONTRACT_V1",
    "gate": 5,
    "purpose": "CONVERT_478_GEOMETRY_IDENTITY_LANDMARKS_TO_DENSE_IDENTITY_FACE_DRAFT_MESH",
    "gate4OfficialParameterHash": "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4",
    "gate3OfficialParameterHash": "160662e0a954643883be1ae154817cffabf83fced2a429bce63f47ddbb936f5e",
    "input": {
        "denseLandmarks": 478,
        "source": "GEOMETRY_FIRST_V2_CONSENSUS_OR_FIXTURE",
        "lowPolyCanonicalProxyAsIdentityEvidence": "DENY",
    },
    "mesh": {
        "topology": "MEDIAPIPE_FACEMESH_TESSELATION_OFFLINE_PINNED",
        "requiredExpressedRegions": [
            "EYES",
            "EYELIDS",
            "NOSE",
            "NOSE_ALAE",
            "LIPS",
            "MOUTH",
            "JAWLINE",
        ],
        "naturalMode": "LANDMARK_SURFACE_AS_IS",
        "polishedMode": "MILD_SYMMETRY_SMOOTH_PROXY_NOT_PHOTOREAL",
    },
    "qualityClaims": {
        "photorealAutomaticPass": "DENY",
        "identityReviewableFaceResolutionTarget": "REQUIRED",
        "production": "NO-GO",
        "countsAsGate8ParticipantEvidence": "DENY",
    },
    "validation": {
        "synthetic": "REQUIRED",
        "realParticipantUsageAtImplementation": 0,
        "P001P002P003IdentityReviewOnLowPolyCaptures": "HOLD",
    },
    "baseline": {
        "gate4Mutation": 0,
        "quickProfileCoreMutation": 0,
        "production": "NO-GO",
    },
}


def gate5_parameter_hash() -> str:
    raw = json.dumps(GATE5_CONTRACT, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
