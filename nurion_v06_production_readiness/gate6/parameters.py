"""v0.6 Production Readiness Gate 6 — parameters."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import INHERITED_LIMITATIONS, V06_RC1_SHA256
from nurion_v06_production_readiness.gate4.parameters import WRAPPER_COMPONENT

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_PARAMETER_HASH_FROZEN = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_PARAMETER_HASH_FROZEN = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"

WRAPPER_SHA256_FROZEN = WRAPPER_COMPONENT["wrapperSha256"]
WRAPPER_VERSION_FROZEN = WRAPPER_COMPONENT["version"]

# Gate5 harness accuracy notes (not product mutations)
GATE5_HARNESS_CORRECTIONS = [
    {
        "id": "HARNESS_BLEND_REOPEN_STRUCTURAL",
        "kind": "VERIFICATION_ACCURACY",
        "productMutation": "DENY",
        "summary": "BLEND reopen compares Armature/Skin/Action/FPS/Eye structure; Scene RNA UI props require addon registration.",
    },
    {
        "id": "HARNESS_PATH_SCAN_PATHLIKE_ONLY",
        "kind": "VERIFICATION_ACCURACY",
        "productMutation": "DENY",
        "summary": "Sensitive path scan uses path-like strings only; rejects binary substring false positives (e.g. .aws).",
    },
]

REQUIRED_DOC_SECTIONS = [
    "INSTALL_UPDATE_REMOVE_WRAPPER",
    "FIXED_WORKFLOW_VALIDATE_BEFORE_EXPORT",
    "CLASSIFICATION_LIMITED_INELIGIBLE_ABSTAIN",
    "REST_FALLBACK_AND_UNSUPPORTED_PRESETS",
    "INHERITED_LIMITATIONS_FOUR",
    "PARTIAL_EXPORT_DENY_AND_RETRY",
    "ERROR_CODES_OPERATOR_ACTIONS",
    "RC1_WRAPPER_FULL_SHA256",
    "PRODUCTION_NO_GO_CHANNEL",
]

FORBIDDEN_DOC_PHRASES = [
    "production ready",
    "production-go",
    "production go",
    "limitations cleared",
    "auto-clear",
    "auto clear",
    "full unqualified pass",
    "safe for unrestricted production",
]

ERROR_CATALOG = [
    {
        "code": "ORDER_VIOLATION",
        "operatorAction": "Restart from the required prior step (Select→Analyze→Build→Apply→Validate→Export).",
        "logHint": "SAFE_ABORT / lastAbort + completedSteps in ui_snapshot / diagnosis log",
    },
    {
        "code": "EXPORT_REQUIRES_VALIDATION",
        "operatorAction": "Run Validate Runtime successfully before Export. Do not publish partial files.",
        "logHint": "validationPassed=false; export CANCELLED; publish dir must stay empty",
    },
    {
        "code": "FORCE_APPLY_INELIGIBLE_DENIED",
        "operatorAction": "Treat asset as INELIGIBLE/ABSTAIN. Do not force build/apply. Replace or repair source asset out-of-band.",
        "logHint": "classification=INELIGIBLE; abstainReasons includes INELIGIBLE",
    },
    {
        "code": "FORCE_APPLY_MISSING_PRESET_DENIED",
        "operatorAction": "Select an available preset (e.g. Idle/Formal_Bow). Unavailable presets remain ABSTAIN.",
        "logHint": "unavailablePresets list; ABSTAIN message in UI",
    },
    {
        "code": "VALIDATION_FAILED",
        "operatorAction": "Inspect eye/FPS validation report; fix runtime build; do not export.",
        "logHint": "validationStatus=FAIL; validationReport fields",
    },
    {
        "code": "UNSUPPORTED_FPS",
        "operatorAction": "Use FPS 24, 30, or 60 only.",
        "logHint": "SAFE_ABORT detail UNSUPPORTED_FPS",
    },
]

GATE6_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE6_OPS_DOCS_UI_PARAMETERS",
    "version": "0.6.0-pr-gate6",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "gate5Mutation": "DENY",
    "sealedBaselineSha256": V06_RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "rc1Repack": "DENY",
    "autoClearLimitations": "DENY",
    "misleadingCopy": "DENY",
    "wrapperComponent": {
        **WRAPPER_COMPONENT,
        "LOCKED": True,
        "officialOpsComponent": True,
    },
    "channel": "LIMITED_INTERNAL_OPERATOR",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "inheritedLimitations": list(INHERITED_LIMITATIONS),
    "requiredDocSections": REQUIRED_DOC_SECTIONS,
    "forbiddenDocPhrases": FORBIDDEN_DOC_PHRASES,
    "errorCatalog": ERROR_CATALOG,
    "gate5HarnessCorrections": GATE5_HARNESS_CORRECTIONS,
    "sealedPanelLimitationIdRender": "NOT_PRESENT_KNOWN_GAP",
    "limitationDisclosureSurfaces": [
        "OPS_OPERATOR_GUIDE",
        "UI_SNAPSHOT_inheritedLimitationsFromV05",
        "EXPORT_DISCLOSURE_SIDECAR",
        "SEALED_GATE6_PARAMETERS",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE6_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
