"""v0.6 Production Readiness Gate 2 — failure / ABSTAIN / recovery policy."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import INHERITED_LIMITATIONS, V06_RC1_SHA256

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"

GATE2_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE2_FAILURE_ABSTAIN_RECOVERY_PARAMETERS",
    "version": "0.6.0-pr-gate2",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "sealedBaselineSha256": V06_RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "partialResultPublish": "DENY",
    "partialExportPublish": "DENY",
    "orderViolation": "SAFE_ABORT",
    "unvalidatedExport": "DENY",
    "ineligibleForceApply": "DENY",
    "missingPresetForceApply": "DENY",
    "safeRetryPolicy": {
        "allowed": True,
        "requiresSelectRestart": True,
        "clearsValidationOnReapply": True,
        "duplicateExportWithoutRevalidate": "DENY",
    },
    "classificationHandling": {
        "LIMITED": "APPLY_WITH_PUBLIC_DISCLOSURE",
        "INELIGIBLE": "ABSTAIN",
        "ABSTAIN_PATHS": ["missingPreset", "lipsyncUnsupported", "ineligible"],
    },
    "lipsyncUnsupported": "REST_FALLBACK",
    "missingPreset": "ABSTAIN",
    "operatorMessageChannels": {
        "operatorUi": ["classification", "abstainReasons", "lipsyncMode", "production", "lastAbort"],
        "errorLog": ["step", "status", "detail", "abortCode"],
        "separation": "REQUIRED",
    },
    "publicLimitations": INHERITED_LIMITATIONS,
    "limitationAutoClear": "DENY",
    "sourceMutationAllowed": 0,
    "manualCorrectionAllowed": 0,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
