"""v0.6 Final Seal Review — review locks only (no seal execution)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import INHERITED_V05_LIMITATIONS

GATE_HASHES_FROZEN = {
    "gate1": "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676",
    "gate2": "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e",
    "gate3": "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604",
    "gate4": "a260ecd6d15502bbb5633e17b6c860955f9307fae25d777db6477c381bad5188",
    "gate5": "81885dbc3c119c08c63add3a9e45caf9860a8bcbd1e9b4363cac46ac9aa9c0be",
    "gate6": "3207531397c6372bbba4e38aebb3024fdc1e85f1792526a5f3115e36bbdf746e",
    "gate7": "32e9fe4fef0f2d534d9a623f8dbfdedc0d4b9c60a5b5fe1a104c9620c4a07833",
    "gate8": "33fd74ae5cb123d1f3d195fa5f2eb34c39bb360e4c872cb72704a06526a7759b",
}

RC1_PACKAGE = "NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
RC1_SHA256 = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"

HOLDOUT_ZIP_SHA256 = "aaf39c897f32baefe7083eb5bae5a107c5b934981773b717549b239321b18e0b"
HOLDOUT_FBX_SHA256 = "0135661b51ad6acee657b6a2cf07f3d92ca72903c686a7246c1638e8c8e19927"
HOLDOUT_LABEL = "AILAWFRIEND"

V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_RC1_SHA256 = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"

REVIEW_PARAMETERS = {
    "schema": "NURION_V06_FINAL_SEAL_REVIEW_PARAMETERS",
    "version": "0.6.0-final-seal-review",
    "track": "Unified Character Animation Runtime",
    "gateHashesFrozen": GATE_HASHES_FROZEN,
    "rc1Package": RC1_PACKAGE,
    "rc1Sha256": RC1_SHA256,
    "holdoutLabel": HOLDOUT_LABEL,
    "holdoutZipSha256": HOLDOUT_ZIP_SHA256,
    "holdoutFbxSha256": HOLDOUT_FBX_SHA256,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "v05Rc1Sha256": V05_RC1_SHA256,
    "autoSeal": "DENY",
    "sealExecutionInThisStep": "DENY",
    "rc1Repack": "DENY",
    "production": "NO-GO",
    "productionAutoAdvance": "DENY",
    "SEALED_onPass": False,
    "passVerdict": "APPROVED_FOR_LIMITED_FINAL_SEAL",
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "limitationAutoClear": "DENY",
}


def parameter_hash() -> str:
    payload = json.dumps(REVIEW_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
