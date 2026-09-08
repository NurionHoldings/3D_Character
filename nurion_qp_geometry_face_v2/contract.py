"""Gate 1 contract for a skin-tone-independent, geometry-first face analyzer."""
from __future__ import annotations

import hashlib
import json
from typing import Any


CONTRACT: dict[str, Any] = {
    "schema": "NURION_V07_QP_GEOMETRY_FIRST_FACE_ANALYZER_V2_GATE1_CONTRACT_V1",
    "track": "NURION Quick Profile Geometry-First Face Analyzer v2",
    "gate": 1,
    "purpose": "Replace skin-center heuristics with geometry-first face shape extraction while preserving frozen v1 baselines",
    "baselinePolicy": {
        "quickProfileGate2Core": "READ_ONLY_NO_MUTATION",
        "quickProfileGate3Runner": "READ_ONLY_NO_MUTATION",
        "gate8Evidence": "DENY",
        "controlledRebaseline": "DENY_UNTIL_V2_HOLDOUT_PASS",
        "production": "NO-GO",
    },
    "baselinePins": {
        "gate2ParameterHash": "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3",
        "gate3ProtocolParameterHash": "cde535402d8a92b50371bed8fefb82efabbb15c9ce2da64081855dd6a98f81bd",
        "gate3RunnerParameterHash": "20333fb895860d02a0a6096107ff14cc94078290abe58c93ed814b04ef89a4e5",
        "gate8ParameterHash": "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697",
    },
    "inputContract": {
        "required": ["SINGLE_IMAGE", "HEIGHT_CM", "WEIGHT_KG"],
        "acceptedPose": ["FRONTAL", "WEAK_LEFT_45", "WEAK_RIGHT_45"],
        "originalImageMutation": "DENY",
        "faceAuthentication": "OUT_OF_SCOPE",
        "identityRecognitionClaim": "DENY",
        "participantEvidenceCounting": "DENY",
    },
    "analysisOrder": [
        "INPUT_INTEGRITY_AND_QUALITY",
        "SKIN_INDEPENDENT_FACE_LOCALIZATION",
        "MULTI_REPRESENTATION_GEOMETRY",
        "LANDMARK_CONSENSUS",
        "CAMERA_AND_HEAD_POSE_NORMALIZATION",
        "SHAPE_FIRST_CANONICAL_FIT",
        "GEOMETRY_IDENTITY_LAYER",
        "ALBEDO_AND_SKIN_TONE_AFTER_GEOMETRY",
        "DISCLOSURE_AND_ABSTAIN",
    ],
    "faceLocalization": {
        "primary": "MODEL_BASED_FACE_DETECTOR",
        "skinColorAsExistenceGate": "DENY",
        "centerSkinOccupancyAsExistenceGate": "DENY",
        "backgroundColorAsExistenceGate": "DENY",
        "minimumKeypoints": ["LEFT_EYE", "RIGHT_EYE", "NOSE_TIP", "MOUTH_CENTER"],
        "multipleDominantFaces": "ABSTAIN",
    },
    "representations": {
        "branches": [
            "ORIGINAL_RGB",
            "LUMINANCE",
            "GRAYSCALE",
            "GRAYSCALE_CLAHE",
            "EDGE_GRADIENT_AUXILIARY",
        ],
        "grayscaleHighContrastRole": "AUXILIARY_NOT_SINGLE_SOURCE_OF_TRUTH",
        "claheRole": "LOCAL_ILLUMINATION_NORMALIZATION_AUXILIARY",
        "edgeRole": "CONTOUR_SUPPORT_ONLY",
        "transformedImageOverwriteOriginal": "DENY",
    },
    "landmarkContract": {
        "primaryCapability": "DENSE_3D_FACE_LANDMARKS",
        "preferredMinimumDenseLandmarks": 468,
        "requiredRegions": ["FACE_OVAL", "BROWS", "EYES", "NOSE", "LIPS", "CHEEKS", "JAW", "FOREHEAD"],
        "consensusMinimumSuccessfulPrimaryBranches": 2,
        "normalizedBy": "INTEROCULAR_DISTANCE",
        "maxMedianBranchDisagreement": 0.025,
        "maxP95BranchDisagreement": 0.06,
        "oneBranchOnly": "GEOMETRY_REVIEW_REQUIRED",
        "branchConflict": "ABSTAIN_RECAPTURE",
    },
    "poseNormalization": {
        "estimate": ["ROLL", "YAW", "PITCH", "CAMERA_SCALE", "PERSPECTIVE"],
        "quickProfileLimitsDeg": {"absRoll": 20.0, "absYaw": 35.0, "absPitch": 25.0},
        "coordinateFrame": "EYE_LINE_HORIZONTAL_FACE_CENTER_ORIGIN_INTEROCULAR_ONE",
        "doNotTreatPerspectiveAsAnatomy": True,
    },
    "geometryIdentityLayer": {
        "allowedSources": ["NORMALIZED_LANDMARK_RATIOS", "CONTOUR", "SHAPE_FIRST_3DMM_COEFFICIENTS"],
        "requiredRatios": [
            "FACE_WIDTH_TO_LENGTH",
            "INTEROCULAR_TO_FACE_WIDTH",
            "NOSE_LENGTH_TO_FACE_LENGTH",
            "MOUTH_WIDTH_TO_FACE_WIDTH",
            "JAW_WIDTH_TO_CHEEKBONE_WIDTH",
            "FOREHEAD_HEIGHT_TO_FACE_LENGTH",
            "VERTICAL_EYE_NOSE_MOUTH_SPACING",
            "NATURAL_LEFT_RIGHT_ASYMMETRY",
        ],
        "imageHashToShapeValues": "DENY",
        "meanRgbToShapeValues": "DENY",
        "skinToneToShapeValues": "DENY",
        "shapeBeforeTexture": True,
    },
    "skinAndAlbedo": {
        "stage": "AFTER_GEOMETRY_LOCK",
        "samplingMask": "LANDMARK_DERIVED_FACE_INTERIOR",
        "exclude": ["EYES", "BROWS", "LIPS", "HAIR", "SPECULAR", "DEEP_SHADOW", "OVEREXPOSURE"],
        "lightingConfidenceRequired": True,
        "uncertainPolicy": "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER",
        "neutralPlaceholderMeaning": "RENDER_PREVIEW_ONLY_NOT_OBSERVED_SKIN",
        "forcedWhiteToneFallback": "DENY",
        "userPaletteSelectionAllowed": True,
        "skinToneValidationClaimBeforeUserOrReliableEstimate": "DENY",
    },
    "outcomes": [
        "GEOMETRY_CONFIDENT",
        "GEOMETRY_REVIEW_REQUIRED",
        "ABSTAIN_RECAPTURE",
        "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER",
    ],
    "fallbackPolicy": {
        "rgbFailure": "TRY_LUMINANCE_GRAYSCALE_CLAHE",
        "geometrySuccessSkinFailure": "KEEP_GEOMETRY_USE_NEUTRAL_PLACEHOLDER",
        "geometryFailure": "ABSTAIN_RECAPTURE_NO_FABRICATION",
        "automaticFilterRemovalOrFaceRestoration": "DENY",
        "automaticHumanLikenessPass": "DENY",
    },
    "validationMatrix": {
        "syntheticPhotometric": [
            "LOW_LIGHT", "OVEREXPOSURE", "BACKLIGHT", "WARM_CAST", "COOL_CAST",
            "LOW_CONTRAST", "HIGH_CONTRAST", "BACKGROUND_SKIN_SIMILAR", "FACE_OFF_CENTER",
        ],
        "geometry": ["ROLL", "YAW", "PITCH", "PERSPECTIVE", "PARTIAL_OCCLUSION", "MULTIPLE_FACES"],
        "skinToneCoverage": "BROAD_TONE_AND_LIGHTING_MATRIX_WITHOUT_RACE_INFERENCE",
        "regression": ["P001_FALSE_ABSTAIN_CASE_WITH_CONSENT_ONLY", "FROZEN_GATE2_FIXTURES"],
        "cleanRuns": 3,
        "humanLikenessReviewRequired": True,
        "automatedPassIsProductAccuracy": "DENY",
    },
    "implementationDependencies": {
        "faceDetector": "MODEL_COMPONENT_REQUIRED",
        "denseFaceLandmarker": "MODEL_COMPONENT_REQUIRED",
        "imageNormalization": ["GRAYSCALE", "CLAHE", "EDGE_GRADIENT"],
        "optionalShapeFit": "3D_MORPHABLE_MODEL_OR_EQUIVALENT",
        "modelFilesMustBeHashPinned": True,
        "networkAtRuntime": "DENY",
    },
}


def parameter_hash(contract: dict[str, Any] | None = None) -> str:
    value = CONTRACT if contract is None else contract
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_contract(contract: dict[str, Any] | None = None) -> list[str]:
    value = CONTRACT if contract is None else contract
    errors: list[str] = []
    baseline = value.get("baselinePolicy", {})
    localization = value.get("faceLocalization", {})
    reps = value.get("representations", {})
    geometry = value.get("geometryIdentityLayer", {})
    skin = value.get("skinAndAlbedo", {})
    fallback = value.get("fallbackPolicy", {})

    if baseline.get("quickProfileGate2Core") != "READ_ONLY_NO_MUTATION": errors.append("GATE2_NOT_READ_ONLY")
    if baseline.get("quickProfileGate3Runner") != "READ_ONLY_NO_MUTATION": errors.append("GATE3_RUNNER_NOT_READ_ONLY")
    if baseline.get("production") != "NO-GO": errors.append("PRODUCTION_NOT_NO_GO")
    for key in ("skinColorAsExistenceGate", "centerSkinOccupancyAsExistenceGate", "backgroundColorAsExistenceGate"):
        if localization.get(key) != "DENY": errors.append(f"COLOR_GATE_NOT_DENIED:{key}")
    if reps.get("grayscaleHighContrastRole") != "AUXILIARY_NOT_SINGLE_SOURCE_OF_TRUTH": errors.append("GRAYSCALE_ROLE_INVALID")
    if reps.get("transformedImageOverwriteOriginal") != "DENY": errors.append("ORIGINAL_OVERWRITE_NOT_DENIED")
    for key in ("imageHashToShapeValues", "meanRgbToShapeValues", "skinToneToShapeValues"):
        if geometry.get(key) != "DENY": errors.append(f"INVALID_SHAPE_SOURCE:{key}")
    if geometry.get("shapeBeforeTexture") is not True: errors.append("SHAPE_NOT_BEFORE_TEXTURE")
    if skin.get("stage") != "AFTER_GEOMETRY_LOCK": errors.append("SKIN_STAGE_TOO_EARLY")
    if skin.get("forcedWhiteToneFallback") != "DENY": errors.append("WHITE_FALLBACK_NOT_DENIED")
    if skin.get("uncertainPolicy") != "SKIN_TONE_UNCERTAIN_NEUTRAL_PLACEHOLDER": errors.append("NEUTRAL_FALLBACK_MISSING")
    if fallback.get("geometryFailure") != "ABSTAIN_RECAPTURE_NO_FABRICATION": errors.append("GEOMETRY_FAILURE_FABRICATION_RISK")
    if fallback.get("automaticHumanLikenessPass") != "DENY": errors.append("AUTO_LIKENESS_PASS_NOT_DENIED")
    if value.get("implementationDependencies", {}).get("networkAtRuntime") != "DENY": errors.append("RUNTIME_NETWORK_NOT_DENIED")
    return errors
