"""v0.6 Gate 2 — automatic asset diagnosis parameters (Gate 1 frozen)."""

from __future__ import annotations

import hashlib
import json

from nurion_v06_unified_runtime.gate1.parameters import (
    INHERITED_V05_LIMITATIONS,
    V03_RC1_SHA256,
    V04_RC1_SHA256,
    V05_RC1_SHA256,
)

GATE1_PARAMETER_HASH_FROZEN = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"

GATE2_PARAMETERS = {
    "schema": "NURION_V06_GATE2_AUTO_ASSET_DIAGNOSIS_PARAMETERS",
    "version": "0.6.0-gate2",
    "track": "Unified Character Animation Runtime",
    "product": "NURION Unified Character Animation Runtime",
    "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
    "gate1Mutation": "DENY",
    "production": "NO-GO",
    "sourceCharacterMutation": "DENY",
    "sealedBaselineMutation": "DENY",
    "limitationAutoClear": "DENY",
    "correctionTarget": "NONE_DIAGNOSIS_READONLY",
    "determinismRuns": 3,
    "classificationLabels": ["FULL", "LIMITED", "INELIGIBLE"],
    "readonlyBaselines": {
        "v0.3": V03_RC1_SHA256,
        "v0.4": V04_RC1_SHA256,
        "v0.5": V05_RC1_SHA256,
    },
    "inheritedLimitationsFromV05": INHERITED_V05_LIMITATIONS,
    "motionPresetHints": [
        "formal_bow",
        "formalbow",
        "idle",
        "gentleman",
        "gentlemans_bow",
        "gentleman_s_bow",
    ],
    "faceBoneHints": [
        "jaw",
        "mouth",
        "lip",
        "teeth",
        "tongue",
        "cheek",
        "brow",
        "eyebrow",
        "eyelid",
        "viseme",
    ],
    "eyeBoneHints": [
        "eye",
        "gaze",
        "look",
        "pupil",
        "iris",
    ],
    "eyeMeshHints": [
        "eye",
        "cornea",
        "sclera",
        "iris",
        "pupil",
    ],
    "coreBoneClassesRequired": [
        "hip",
        "spine",
        "shoulder",
        "knee",
    ],
}


def parameter_hash() -> str:
    payload = json.dumps(GATE2_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
