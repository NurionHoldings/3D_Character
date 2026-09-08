"""v0.5 Gate 9 — RC Packaging & Reinstall Smoke parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_FROZEN = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_FROZEN = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
GATE4_FROZEN = "837fd79115113aa316671552d7fd4027f1e873e984c6d5ebc35239fd66e357ca"
GATE5_FROZEN = "3ac0c130af6200d73dac0d0b6b62e01196bd8588a4f820a6b146c77632a6c3ac"
GATE6_FROZEN = "92863ebff2fd45ed1421568f3dd9f1aeaa8845320caa85597205816983ee3c41"
GATE7_FROZEN = "59436fd1fc276b2dca44c0cb042bdda5e2cbe1990b13c695fafd1e43c35c792f"
GATE8_FROZEN = "fe73b4b4786f9f2180c178e3ab7a91945dd548fafbec0cc5618c8fc83fb515e6"
V04_GATE7_FROZEN = "1784696fb7513c7e693ada2faff48a3ae3413b3bf4f7aa9b5641442d2d5f258f"
V04_RC1_SHA256 = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
SEED_ZIP_SHA256 = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA256 = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"

PACKAGE_NAME = "NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
ADDON_MODULE = "nurion_body_motion_retarget"
VERSION = "0.5.0-rc.1"

INHERITED_LIMITATIONS = [
    "FOOT_SLIDE_RESIDUAL_11",
    "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
    "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
]

GATE9_PARAMETERS = {
    "schema": "NURION_V05_GATE9_RC_PACKAGING_REINSTALL_SMOKE_PARAMETERS",
    "version": VERSION,
    "packageName": PACKAGE_NAME,
    "addonModule": ADDON_MODULE,
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "gate3ParameterHash": GATE3_FROZEN,
    "gate4ParameterHash": GATE4_FROZEN,
    "gate5ParameterHash": GATE5_FROZEN,
    "gate6ParameterHash": GATE6_FROZEN,
    "gate7ParameterHash": GATE7_FROZEN,
    "gate8ParameterHash": GATE8_FROZEN,
    "v04Gate7ParameterHash": V04_GATE7_FROZEN,
    "v04Rc1Sha256": V04_RC1_SHA256,
    "seedZipSha256": SEED_ZIP_SHA256,
    "seedFbxSha256": SEED_FBX_SHA256,
    "v04Mutation": "DENY",
    "v04PackageInclude": "DENY",
    "sourceZipFbxInclude": "DENY",
    "testAssetInclude": "DENY",
    "intermediateOutputInclude": "DENY",
    "repack": "DENY",
    "parameterTuning": "DENY",
    "manualCorrection": "DENY",
    "supportedDomain": "LIMITED",
    "production": "NO-GO",
    "sealed": False,
    "releaseCandidate": True,
    "finalSeal": "HOLD",
    "holdout": "WAITING",
    "inheritedLimitations": INHERITED_LIMITATIONS,
    "primaryTimeline": "word_확인",
    "smokeRuns": 2,
    "determinismRuns": 3,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE9_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
