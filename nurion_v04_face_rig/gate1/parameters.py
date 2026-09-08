"""v0.4 Gate 1 — Face Asset Capability Diagnosis parameters."""

from __future__ import annotations

import hashlib
import json

# v0.3 sealed baseline — READ ONLY, never mutate.
V03_RC1_PACKAGE = "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

GATE1_PARAMETERS = {
    "schema": "NURION_V04_GATE1_FACE_CAPABILITY_PARAMETERS",
    "version": "0.4.0-gate1",
    "characterMutation": 0,
    "createFaceRig": False,
    "createLipSync": False,
    "determinismRuns": 3,
    "v03BaselineMutation": "DENY",
    "v03Rc1Sha256": V03_RC1_SHA256,
    "paths": ["NATIVE_FACE_RIG", "PROCEDURAL_FACE_RIG", "LIMITED_2D_VISEME"],
    "boneNameHints": {
        "head": ["head", "neck", "skull"],
        "jaw": ["jaw", "mandible", "chin"],
        "lip": ["lip", "mouth", "oral"],
        "cheek": ["cheek", "jowl"],
        "brow": ["brow", "eyebrow", "orbit"],
        "eye": ["eye", "lid", "blink"],
        "tongue": ["tongue"],
        "teeth": ["tooth", "teeth", "dental"],
    },
    "shapeKeyHints": {
        "viseme": ["viseme", "aa", "oh", "ee", "ih", "ou", "fv", "th", "mbp", "wq"],
        "jaw": ["jaw", "open", "mouthopen", "mouth_open"],
        "smile": ["smile", "happy"],
        "brow": ["brow", "surprise", "frown"],
    },
    "meshNameHints": {
        "teeth": ["tooth", "teeth", "gum", "dental"],
        "tongue": ["tongue"],
        "face": ["face", "head", "char1"],
        "body": ["body", "torso", "char1"],
    },
}


def parameter_hash() -> str:
    payload = json.dumps(GATE1_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
