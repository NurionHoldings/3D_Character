"""v0.6 Production Readiness Gate 5 — export compatibility & security parameters."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_production_readiness.gate1.parameters import V06_RC1_SHA256
from nurion_v06_production_readiness.gate4.parameters import WRAPPER_COMPONENT

GATE1_PARAMETER_HASH_FROZEN = "8e14f82c546ffa2e8473539513be8e37ff9e544d5ac6c15f72421bb7c6a960f2"
GATE2_PARAMETER_HASH_FROZEN = "8e661e64cdd5a26c1749b337eb6d47de56cd1511591d4479b7b34e8a3cfdf139"
GATE3_PARAMETER_HASH_FROZEN = "b4439f48784b9c536e76db83b732d871df0e305164abfc01d5951cddebccc0a3"
GATE4_PARAMETER_HASH_FROZEN = "78763351bbf9b036a3390b01d5f39e9d793f991a607f62c87ae6cd284f771e1a"

WRAPPER_SHA256_FROZEN = WRAPPER_COMPONENT["wrapperSha256"]
WRAPPER_VERSION_FROZEN = WRAPPER_COMPONENT["version"]

GATE5_PARAMETERS = {
    "schema": "NURION_V06_PR_GATE5_EXPORT_COMPAT_SECURITY_PARAMETERS",
    "version": "0.6.0-pr-gate5",
    "track": "Production Readiness",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
    "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
    "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "gate2Mutation": "DENY",
    "gate3Mutation": "DENY",
    "gate4Mutation": "DENY",
    "sealedBaselineSha256": V06_RC1_SHA256,
    "sealedBaselineMutation": "DENY",
    "rc1Repack": "DENY",
    "autoRemediate": "DENY",
    "autoRepack": "DENY",
    "wrapperComponent": {
        **WRAPPER_COMPONENT,
        "LOCKED": True,
        "officialOpsComponent": True,
    },
    "exportFormats": ["BLEND", "FBX", "GLB"],
    "fpsChoices": [24, 30, 60],
    "maxInputMb": 64,
    "sensitivePathPatterns": [
        r"(?i)(?:^|[/\\])appdata(?:[/\\]|$)",
        r"(?i)(?:^|[/\\])users(?:[/\\]|$)",
        r"(?i)(?:^|[/\\])(?:tmp|temp)(?:[/\\]|$)",
        r"(?i)(?:^|[/\\])\.ssh(?:[/\\]|$)",
        r"(?i)(?:^|[/\\])\.aws(?:[/\\]|$)",
        r"(?i)(?:^|[/\\])credentials(?:[/\\.]|$)",
        r"(?i)[a-z]:[/\\]users[/\\]",
    ],
    "forbiddenZipNamePatterns": ["../", "..\\", "/../", "\\..\\"],
    "networkImportTokens": ["urllib", "requests", "http.client", "aiohttp", "socket."],
    "envAccessTokens": ["os.environ", "os.getenv", "environ["],
    "partialExportPublish": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(GATE5_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
