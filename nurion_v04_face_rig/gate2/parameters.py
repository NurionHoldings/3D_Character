"""v0.4 Gate 2 — Procedural Face Guide & Neutral Rig Candidate parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN_HASH = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE2_PARAMETERS = {
    "schema": "NURION_V04_GATE2_PROCEDURAL_FACE_GUIDE_PARAMETERS",
    "version": "0.4.0-gate2",
    "gate1ParameterHash": GATE1_FROZEN_HASH,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "visemeGeneration": "DENY",
    "lipSyncGeneration": "DENY",
    "fullExpressionGeneration": "DENY",
    "workOnCloneOnly": True,
    "collections": {
        "candidate": "NURION_FaceCandidate",
        "guides": "NURION_FaceGuideCollection",
        "rig": "NURION_NeutralFaceRigCandidate",
    },
    "bones": [
        "jaw",
        "lip.upper.center",
        "lip.lower.center",
        "mouth.corner.L",
        "mouth.corner.R",
        "cheek.L",
        "cheek.R",
        "brow.inner.L",
        "brow.mid.L",
        "brow.outer.L",
        "brow.inner.R",
        "brow.mid.R",
        "brow.outer.R",
    ],
    "diagnosticAmplitudes": {
        "jawOpen": 0.10,
        "corner": 0.05,
        "lip": 0.05,
        "cheek": 0.03,
        "brow": 0.05,
    },
    "weight": {
        "maxInfluenceBones": 4,
        "jawRadiusEU": 0.22,
        "lipRadiusEU": 0.10,
        "cornerRadiusEU": 0.09,
        "cheekRadiusEU": 0.14,
        "browRadiusEU": 0.10,
        "nonFaceWeightMax": 1e-6,
        "teethInwardYEU": 0.10,
    },
    "tolerances": {
        "neutralVertexDriftEU": 1e-7,
        "headLocalBasisDrift": 1e-7,
        "neutralReturnErrorEU": 1e-6,
        "guideOutsideFaceMax": 0,
        "lrSwapMax": 0,
        "nonFaceWeightLeakMax": 0,
        "teethWeightLeakMax": 0,
    },
    "determinismRuns": 3,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
