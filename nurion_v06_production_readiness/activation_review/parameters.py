"""Parameters for Limited Internal Production Activation Review (read-only)."""

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

GATE8_PARAMETER_HASH_FROZEN = "b00f7694346b448743fb6940e9aab2fe38d40645c37a15c59fab688eda2c024a"
GATE7_PARAMETER_HASH_FROZEN = "2e34ee9082c97d9fac46ba423e3748b456700cb3f7224a161c53207430ca2a11"
GATE6_PARAMETER_HASH_FROZEN = "65aff0f4edced493e3dd62ac8c0d062bcdde7531d13d348a1530bf59c70f290b"
GATE5_PARAMETER_HASH_FROZEN = "d5bcfe242c856d746b1190346cfec3cc0f2959f3b6071179a1b486a0491709fe"
GATE4_PARAMETER_HASH_FROZEN = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"

ACTIVATION_REVIEW_PARAMETERS = {
    "schema": "NURION_V06_LIMITED_INTERNAL_PRODUCTION_ACTIVATION_REVIEW_PARAMETERS",
    "version": "0.6.0-activation-review",
    "track": "Limited Internal Production Activation Review",
    "product": "NURION Unified Character Animation Runtime",
    "mode": "READ_ONLY_REVIEW",
    "thisCommandActivatesProduction": "DENY",
    "activationExecution": "NOT_STARTED",
    "activation": "NOT_GRANTED",
    "deploy": "DENY",
    "conditionChange": "DENY",
    "limitationClear": "DENY",
    "limitationMutation": "DENY",
    "repack": "DENY",
    "autoRemediate": "DENY",
    "unconditionalGo": "DENY",
    "channel": "LIMITED_INTERNAL_OPERATOR",
    "externalCustomerDeploy": "DENY",
    "unattendedAutomation": "DENY",
    "generalPublicRelease": "DENY",
    "prerequisiteJudgment": "CONDITIONAL_GO",
    "prerequisiteGate8ParameterHash": GATE8_PARAMETER_HASH_FROZEN,
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate5ParameterHash": GATE5_PARAMETER_HASH_FROZEN,
    "gate6ParameterHash": GATE6_PARAMETER_HASH_FROZEN,
    "gate7ParameterHash": GATE7_PARAMETER_HASH_FROZEN,
    "gate8ParameterHash": GATE8_PARAMETER_HASH_FROZEN,
    "sealedBaselineSha256": V06_RC1_SHA256,
    "wrapperSha256": WRAPPER_COMPONENT["wrapperSha256"],
    "wrapperVersion": WRAPPER_COMPONENT["version"],
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
    "holdoutNoveltyScopeRequired": "FRESH_WITHIN_PR_TRACK",
    "projectWideFreshHoldoutClaim": "DENY",
    "inheritedLimitations": list(PR_INHERITED_LIMITATIONS),
    "requiredConditionsFrozen": [
        "PANEL_LIMITATION_IDS_RENDERED",
        "SEALED_WITH_LIMITATIONS_BASELINE",
        "CHANNEL_LIMITED_INTERNAL_OPERATOR_ONLY",
        "HOLDOUT_NOVELTY_FRESH_WITHIN_PR_TRACK_ONLY",
        "ACTIVATION_REQUIRES_SEPARATE_APPROVAL",
    ],
    "allowedVerdicts": [
        "REVIEW_PASS_AWAIT_ACTIVATION_EXECUTION_GO",
        "REVIEW_DENY",
        "MORE_EVIDENCE_REQUIRED",
    ],
    "nextIfPass": "AWAIT_ACTIVATION_EXECUTION_GO",
}


def parameter_hash() -> str:
    payload = json.dumps(ACTIVATION_REVIEW_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
