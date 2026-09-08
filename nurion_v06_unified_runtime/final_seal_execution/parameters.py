"""v0.6 Limited Final Seal Execution — readonly hash locks (no repair/repack)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.final_seal_review.parameters import (
    GATE_HASHES_FROZEN,
    HOLDOUT_FBX_SHA256,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    RC1_PACKAGE,
    RC1_SHA256,
    V03_RC1_SHA256,
    V04_RC1_SHA256,
    V05_RC1_SHA256,
)
from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

REVIEW_VERDICT_REQUIRED = "APPROVED_FOR_LIMITED_FINAL_SEAL"
REVIEW_PARAMETER_HASH_FROZEN = "eb2bd86959b5d199fb367046daa3835b34d181883b977b0e788d43a52213768e"

SEAL_EXECUTION_PARAMETERS = {
    "schema": "NURION_V06_LIMITED_FINAL_SEAL_EXECUTION_PARAMETERS",
    "version": "0.6.0-limited-final-seal",
    "track": "Unified Character Animation Runtime",
    "mode": "READONLY_HASH_COMPARE_ONLY",
    "inPlaceRepair": "DENY",
    "rc1Repack": "DENY",
    "zipHashChange": "DENY",
    "autoSeal": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "reviewVerdictRequired": REVIEW_VERDICT_REQUIRED,
    "reviewParameterHash": REVIEW_PARAMETER_HASH_FROZEN,
    "gateHashesFrozen": GATE_HASHES_FROZEN,
    "rc1Package": RC1_PACKAGE,
    "rc1Sha256": RC1_SHA256,
    "holdoutLabel": HOLDOUT_LABEL,
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v05Rc1Sha256": V05_RC1_SHA256,
    "passVerdict": "SEALED_WITH_LIMITATIONS",
    "failVerdict": "SEAL_DENY",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(SEAL_EXECUTION_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
