"""Gate 2 model selection and offline pinning contract.

Selection is not equivalent to asset approval.  A component becomes executable
only after its exact bytes, SHA-256, license evidence, and offline smoke result
are recorded.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


REGISTRY: dict[str, Any] = {
    "schema": "NURION_V07_QP_GF_FACE_V2_GATE2_MODEL_REGISTRY_V1",
    "track": "NURION Quick Profile Geometry-First Face Analyzer v2",
    "gate": 2,
    "gate1ParameterHash": "e2e90a2fac7f5b64ecd6c73b63b7852782249a0593ee594bc414ce293d21ff8a",
    "selection": {
        "faceDetector": {
            "component": "OpenCV Zoo YuNet",
            "filename": "face_detection_yunet_2026may.onnx",
            "officialSource": "https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet",
            "downloadSource": "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2026may.onnx",
            "license": "MIT",
            "licenseSource": "https://github.com/opencv/opencv_zoo/blob/main/models/face_detection_yunet/LICENSE",
            "role": "SKIN_INDEPENDENT_FACE_LOCALIZATION_AND_COARSE_KEYPOINTS",
            "runtime": "OpenCV_5_X_DNN_OR_PINNED_COMPATIBLE_RUNTIME",
            "sha256": None,
            "assetStatus": "MISSING_NOT_PINNED",
        },
        "denseFaceLandmarker": {
            "component": "Google MediaPipe Face Landmarker",
            "filename": "face_landmarker.task",
            "officialSource": "https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker",
            "downloadSource": "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/latest/face_landmarker.task",
            "license": "APACHE-2.0_MODEL_CARD_OR_DISTRIBUTION_EVIDENCE_REVIEW_REQUIRED",
            "licenseSource": "https://github.com/google-ai-edge/mediapipe/blob/master/LICENSE",
            "role": "DENSE_3D_FACE_LANDMARKS_478_AND_TRANSFORMATION_MATRIX",
            "runtime": "PINNED_MEDIAPIPE_TASKS_VISION_RUNTIME",
            "sha256": None,
            "assetStatus": "MISSING_NOT_PINNED",
        },
    },
    "executionPolicy": {
        "runtimeNetwork": "DENY",
        "unhashedModelLoad": "DENY",
        "silentModelUpgrade": "DENY",
        "skinColorFaceGate": "DENY",
        "singleRepresentationAuthority": "DENY",
        "realParticipantValidationAtGate2": "DENY",
        "faceAuthentication": "OUT_OF_SCOPE",
        "automaticSimilarityPass": "DENY",
    },
    "requiredBeforePass": [
        "EXACT_MODEL_BYTES_PRESENT",
        "FULL_SHA256_PINNED",
        "MODEL_DISTRIBUTION_LICENSE_EVIDENCE_ACCEPTED",
        "RUNTIME_PACKAGE_VERSION_AND_BYTES_PINNED",
        "OFFLINE_LOAD_SMOKE_PASS",
        "SYNTHETIC_OR_NON_PARTICIPANT_FIXTURE_INFERENCE_PASS",
        "THREE_RUN_DETERMINISM_PASS",
    ],
}


def parameter_hash(registry: dict[str, Any] | None = None) -> str:
    value = REGISTRY if registry is None else registry
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_registry(registry: dict[str, Any] | None = None) -> list[str]:
    value = REGISTRY if registry is None else registry
    errors: list[str] = []
    selection = value.get("selection", {})
    policy = value.get("executionPolicy", {})
    if value.get("gate1ParameterHash") != "e2e90a2fac7f5b64ecd6c73b63b7852782249a0593ee594bc414ce293d21ff8a":
        errors.append("GATE1_PIN_MISMATCH")
    if set(selection) != {"faceDetector", "denseFaceLandmarker"}:
        errors.append("MODEL_ROLE_SET_INVALID")
    if "478" not in selection.get("denseFaceLandmarker", {}).get("role", ""):
        errors.append("DENSE_LANDMARK_CAPABILITY_MISSING")
    for key in ("runtimeNetwork", "unhashedModelLoad", "silentModelUpgrade", "skinColorFaceGate"):
        if policy.get(key) != "DENY": errors.append(f"POLICY_NOT_DENIED:{key}")
    for name, component in selection.items():
        digest = component.get("sha256")
        status = component.get("assetStatus")
        if digest is not None and (len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest)):
            errors.append(f"INVALID_SHA256:{name}")
        if digest is None and status != "MISSING_NOT_PINNED":
            errors.append(f"UNPINNED_STATUS_INVALID:{name}")
    return errors


def pass_preconditions_met(registry: dict[str, Any] | None = None) -> bool:
    value = REGISTRY if registry is None else registry
    return not validate_registry(value) and all(
        component.get("assetStatus") == "PINNED_OFFLINE_SMOKE_PASS" and component.get("sha256")
        for component in value["selection"].values()
    )
