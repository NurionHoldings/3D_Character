"""Gate 2 model-component selection and offline hash pinning (no inference product claims)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

GATE1_PARAMETER_HASH = "e2e90a2fac7f5b64ecd6c73b63b7852782249a0593ee594bc414ce293d21ff8a"

BASELINE_PINS = {
    "gate1ParameterHash": GATE1_PARAMETER_HASH,
    "gate2ParameterHash": "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3",
    "gate3ProtocolParameterHash": "cde535402d8a92b50371bed8fefb82efabbb15c9ce2da64081855dd6a98f81bd",
    "gate3RunnerParameterHash": "20333fb895860d02a0a6096107ff14cc94078290abe58c93ed814b04ef89a4e5",
    "gate8ParameterHash": "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697",
    "gate3RunnerCodeSha256": "13837c5e5b4a31e9efb10c83528703375df44f59ac15babb69207a57e22dbcc4",
}

# Relative to repository root
MODEL_DIR = "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"

GATE2_SELECTION: dict[str, Any] = {
    "schema": "NURION_V07_QP_GEOMETRY_FIRST_FACE_ANALYZER_V2_GATE2_SELECTION_V1",
    "track": "NURION Quick Profile Geometry-First Face Analyzer v2",
    "gate": 2,
    "purpose": "Select and offline-pin skin-independent face detector and dense 3D landmarker model bytes",
    "gate1ParameterHash": GATE1_PARAMETER_HASH,
    "baselinePolicy": {
        "quickProfileGate2Core": "READ_ONLY_NO_MUTATION",
        "quickProfileGate3Runner": "READ_ONLY_NO_MUTATION",
        "gate8Evidence": "DENY",
        "realParticipantUsage": "DENY",
        "runtimeNetwork": "DENY",
        "production": "NO-GO",
        "implementationInferenceProductClaim": "DENY",
    },
    "baselinePins": BASELINE_PINS,
    "faceDetector": {
        "componentId": "MEDIAPIPE_BLAZEFACE_SHORT_RANGE_FLOAT16_V1",
        "family": "MediaPipe BlazeFace Short-Range",
        "role": "SKIN_INDEPENDENT_FACE_LOCALIZATION",
        "skinColorAsExistenceGate": "DENY",
        "provider": "Google MediaPipe / AI Edge",
        "version": "float16/1",
        "license": "Apache-2.0",
        "licenseNote": "MediaPipe model assets distributed under Apache License 2.0",
        "sourceUrlPinnedForProvenanceOnly": (
            "https://storage.googleapis.com/mediapipe-models/face_detector/"
            "blaze_face_short_range/float16/1/blaze_face_short_range.tflite"
        ),
        "relativePath": f"{MODEL_DIR}/blaze_face_short_range_float16_v1.tflite",
        "fileName": "blaze_face_short_range_float16_v1.tflite",
        "sha256": "b4578f35940bf5a1a655214a1cce5cab13eba73c1297cd78e1a04c2380b0152f",
        "bytes": 229746,
        "runtimeFetch": "DENY",
    },
    "denseFaceLandmarker": {
        "componentId": "MEDIAPIPE_FACE_LANDMARKER_FLOAT16_V1",
        "family": "MediaPipe Face Landmarker",
        "role": "DENSE_3D_FACE_LANDMARKS",
        "provider": "Google MediaPipe / AI Edge",
        "version": "float16/1",
        "license": "Apache-2.0",
        "licenseNote": "MediaPipe model assets distributed under Apache License 2.0",
        "sourceUrlPinnedForProvenanceOnly": (
            "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
            "face_landmarker/float16/1/face_landmarker.task"
        ),
        "relativePath": f"{MODEL_DIR}/face_landmarker_float16_v1.task",
        "fileName": "face_landmarker_float16_v1.task",
        "sha256": "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff",
        "bytes": 3758596,
        "declaredDenseLandmarkCount": 478,
        "outputs": ["LANDMARKS_3D", "BLENDSHAPES", "FACIAL_TRANSFORMATION_MATRIX"],
        "runtimeFetch": "DENY",
    },
    "inputCompatibility": {
        "acceptedBranches": [
            "ORIGINAL_RGB",
            "LUMINANCE",
            "GRAYSCALE",
            "GRAYSCALE_CLAHE",
        ],
        "tensorConvention": "HWC_UINT8_EXPANDED_TO_3CH_WHEN_SINGLE_CHANNEL",
        "clahe": "AUXILIARY_ILLUMINATION_NORMALIZATION_ONLY",
        "grayscale": "AUXILIARY_NOT_SINGLE_SOURCE_OF_TRUTH",
        "overwriteOriginalBytes": "DENY",
    },
    "canonicalOutputContract": {
        "coordinateFrame": "EYE_LINE_HORIZONTAL_FACE_CENTER_ORIGIN_INTEROCULAR_ONE",
        "normalizedBy": "INTEROCULAR_DISTANCE",
        "landmarkSpace": "FACE_CANONICAL_AFTER_POSE_NORMALIZATION",
        "doNotTreatPerspectiveAsAnatomy": True,
        "requiredRegions": [
            "FACE_OVAL",
            "BROWS",
            "EYES",
            "NOSE",
            "LIPS",
            "CHEEKS",
            "JAW",
            "FOREHEAD",
        ],
        "geometryFailure": "ABSTAIN_RECAPTURE_NO_FABRICATION",
        "automaticHumanLikenessPass": "DENY",
        "faceAuthentication": "OUT_OF_SCOPE",
    },
}


def parameter_hash(selection: dict[str, Any] | None = None) -> str:
    value = GATE2_SELECTION if selection is None else selection
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate_selection(selection: dict[str, Any] | None = None) -> list[str]:
    value = GATE2_SELECTION if selection is None else selection
    errors: list[str] = []
    pol = value.get("baselinePolicy", {})
    if pol.get("runtimeNetwork") != "DENY":
        errors.append("RUNTIME_NETWORK_NOT_DENIED")
    if pol.get("realParticipantUsage") != "DENY":
        errors.append("REAL_PARTICIPANT_USAGE_NOT_DENIED")
    if pol.get("quickProfileGate2Core") != "READ_ONLY_NO_MUTATION":
        errors.append("QP_GATE2_NOT_READ_ONLY")
    if pol.get("quickProfileGate3Runner") != "READ_ONLY_NO_MUTATION":
        errors.append("QP_GATE3_RUNNER_NOT_READ_ONLY")
    if pol.get("production") != "NO-GO":
        errors.append("PRODUCTION_NOT_NO_GO")
    det = value.get("faceDetector", {})
    lm = value.get("denseFaceLandmarker", {})
    if det.get("skinColorAsExistenceGate") != "DENY":
        errors.append("DETECTOR_SKIN_GATE_NOT_DENIED")
    if det.get("runtimeFetch") != "DENY" or lm.get("runtimeFetch") != "DENY":
        errors.append("MODEL_RUNTIME_FETCH_NOT_DENIED")
    if not det.get("sha256") or len(det.get("sha256", "")) != 64:
        errors.append("DETECTOR_SHA_MISSING")
    if not lm.get("sha256") or len(lm.get("sha256", "")) != 64:
        errors.append("LANDMARKER_SHA_MISSING")
    if int(lm.get("declaredDenseLandmarkCount", 0)) < 468:
        errors.append("DENSE_LANDMARK_COUNT_TOO_LOW")
    out = value.get("canonicalOutputContract", {})
    if out.get("automaticHumanLikenessPass") != "DENY":
        errors.append("AUTO_LIKENESS_PASS_NOT_DENIED")
    if out.get("geometryFailure") != "ABSTAIN_RECAPTURE_NO_FABRICATION":
        errors.append("GEOMETRY_FAILURE_POLICY_INVALID")
    branches = value.get("inputCompatibility", {}).get("acceptedBranches", [])
    for required in ("ORIGINAL_RGB", "LUMINANCE", "GRAYSCALE", "GRAYSCALE_CLAHE"):
        if required not in branches:
            errors.append(f"INPUT_BRANCH_MISSING:{required}")
    return errors


def verify_offline_model_bytes(repo_root: Path) -> list[str]:
    errors: list[str] = []
    for key in ("faceDetector", "denseFaceLandmarker"):
        comp = GATE2_SELECTION[key]
        path = repo_root / comp["relativePath"]
        if not path.is_file():
            errors.append(f"MISSING_MODEL_FILE:{comp['fileName']}")
            continue
        got = sha256_file(path)
        if got != comp["sha256"]:
            errors.append(f"MODEL_HASH_MISMATCH:{comp['fileName']}:{got}")
        if path.stat().st_size != int(comp["bytes"]):
            errors.append(f"MODEL_SIZE_MISMATCH:{comp['fileName']}")
    return errors
