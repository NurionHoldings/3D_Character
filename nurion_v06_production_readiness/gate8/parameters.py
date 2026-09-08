"""v0.6 Production Readiness Gate 8 — final judgment parameters."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import V06_RC1_SHA256
from nurion_v06_production_readiness.gate4.parameters import WRAPPER_COMPONENT
from nurion_v06_production_readiness.gate7.parameters import (
    HOLDOUT_FBX_SHA256,
    HOLDOUT_ZIP_SHA256,
    PR_INHERITED_LIMITATIONS,
)

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_PARAMETER_HASH_FROZEN = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE5_PARAMETER_HASH_FROZEN = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE6_PARAMETER_HASH_FROZEN = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"
GATE7_PARAMETER_HASH_FROZEN = "2e34ee9082c97d9fac46ba423e3748b456700cb3f7224a161c53207430ca2a11"

WRAPPER_SHA256_FROZEN = WRAPPER_COMPONENT["wrapperSha256"]
WRAPPER_VERSION_FROZEN = WRAPPER_COMPONENT["version"]

V06_SEAL_PACKAGE_SHA256 = V06_RC1_SHA256

GATE8_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE8_FINAL_JUDGMENT_PARAMETERS",
    "version": "0.6.0-pr-gate8",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate6ParameterHash": GATE6_PARAMETER_HASH_FROZEN,
    "gate7ParameterHash": GATE7_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "gate5Mutation": "DENY",
    "gate6Mutation": "DENY",
    "gate7Mutation": "DENY",
    "sealedBaselineSha256": V06_SEAL_PACKAGE_SHA256,
    "wrapperSha256": WRAPPER_SHA256_FROZEN,
    "wrapperVersion": WRAPPER_VERSION_FROZEN,
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
    "holdoutNoveltyScopeRequired": "FRESH_WITHIN_PR_TRACK",
    "projectWideFreshHoldoutClaim": "DENY",
    "shaTruncation": "DENY",
    "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
    "panelLimitationIdsRendered": False,
    "unconditionalGo": "DENY",
    "channel": "LIMITED_INTERNAL_OPERATOR",
    "externalCustomerDeploy": "DENY",
    "unattendedAutomation": "DENY",
    "generalPublicRelease": "DENY",
    "operatorPreTrainingRequired": True,
    "exportDisclosureCheckRequired": True,
    "productionAutoActivate": "DENY",
    "judgmentSeparateFromActivation": True,
    "activationByThisGate": "DENY",
    "allowedVerdicts": ["CONDITIONAL_GO", "NO_GO", "MORE_EVIDENCE_REQUIRED"],
    "expectedTopVerdictGivenEvidence": "CONDITIONAL_GO",
    "conditionalGoReasons": [
        "PANEL_LIMITATION_IDS_RENDERED",
        "SEALED_WITH_LIMITATIONS_BASELINE",
        "CHANNEL_LIMITED_INTERNAL_OPERATOR_ONLY",
        "HOLDOUT_NOVELTY_FRESH_WITHIN_PR_TRACK_ONLY",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE8_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
