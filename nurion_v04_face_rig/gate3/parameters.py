"""v0.4 Gate 3 — Viseme Shape Basis parameters."""

from __future__ import annotations

import hashlib
import json

GATE1_FROZEN = "724ec89056fd29637278834d37fde0f1ee131f5e544a3c564d62350b6c6ebd3b"
GATE2_FROZEN = "5ee7d5db769444d07f54747ce283d03a013af44619af19b3952c394bc1aeca46"
V03_RC1_SHA256 = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"

# Axis amounts in Mouth Units (1 MU = corner-to-corner distance)
GATE3_PARAMETERS = {
    "schema": "NURION_V04_GATE3_VISEME_SHAPE_BASIS_PARAMETERS",
    "version": "0.4.0-gate3",
    "gate1ParameterHash": GATE1_FROZEN,
    "gate2ParameterHash": GATE2_FROZEN,
    "v03Rc1Sha256": V03_RC1_SHA256,
    "sourceCharacterMutation": "DENY",
    "audioInput": "INACTIVE",
    "phonemeTiming": "INACTIVE",
    "automaticLipSync": "HOLD",
    "coarticulation": "HOLD",
    "fullFacialExpression": "HOLD",
    "sourceRigApplication": "DENY",
    "objects": {
        "control": "NURION_VisemeControl",
        "basis": "NURION_VisemeBasisCandidate",
        "evidence": "NURION_VisemeEvidence",
    },
    "baseVisemes": ["REST", "CLOSED", "OPEN", "WIDE", "ROUND", "NARROW", "TEETH", "TONGUE_PROXY"],
    "koreanVowels": ["ㅏ", "ㅓ", "ㅗ", "ㅜ", "ㅡ", "ㅣ", "ㅐ", "ㅔ", "ㅑ", "ㅕ", "ㅛ", "ㅠ", "ㅘ", "ㅝ", "ㅙ", "ㅞ", "ㅢ"],
    "axisLimitsMU": {
        "jawOpen": 0.35,
        "lipWide": 0.18,
        "lipRound": 0.14,
        "lipClose": 0.12,
        "upperLipRaise": 0.08,
        "lowerLipDrop": 0.10,
        "cornerPull": 0.12,
        "teethApproach": 0.06,
    },
    "baseRecipes": {
        "REST": {},
        "CLOSED": {"lipClose": 0.9, "jawOpen": 0.0},
        "OPEN": {"jawOpen": 0.85, "lowerLipDrop": 0.35},
        "WIDE": {"jawOpen": 0.25, "lipWide": 0.85, "cornerPull": 0.4},
        "ROUND": {"jawOpen": 0.35, "lipRound": 0.9, "lipWide": -0.25},
        "NARROW": {"jawOpen": 0.2, "lipWide": -0.15, "lipRound": 0.15},
        "TEETH": {"jawOpen": 0.15, "teethApproach": 0.85, "upperLipRaise": 0.35},
        "TONGUE_PROXY": {"jawOpen": 0.2, "teethApproach": 0.4, "lowerLipDrop": 0.15},
    },
    "vowelRecipes": {
        "ㅏ": {"jawOpen": 0.9, "lowerLipDrop": 0.35},
        "ㅓ": {"jawOpen": 0.7, "lipWide": 0.15},
        "ㅗ": {"jawOpen": 0.45, "lipRound": 0.85, "lipWide": -0.2},
        "ㅜ": {"jawOpen": 0.35, "lipRound": 0.95, "lipWide": -0.25},
        "ㅡ": {"jawOpen": 0.2, "lipWide": -0.1, "lipRound": 0.1},
        "ㅣ": {"jawOpen": 0.2, "lipWide": 0.85, "cornerPull": 0.35},
        "ㅐ": {"jawOpen": 0.45, "lipWide": 0.7},
        "ㅔ": {"jawOpen": 0.4, "lipWide": 0.65},
        "ㅑ": {"jawOpen": 0.85, "lowerLipDrop": 0.3, "lipWide": 0.15},
        "ㅕ": {"jawOpen": 0.65, "lipWide": 0.25},
        "ㅛ": {"jawOpen": 0.4, "lipRound": 0.8, "lipWide": -0.15},
        "ㅠ": {"jawOpen": 0.32, "lipRound": 0.9, "lipWide": -0.2},
        "ㅘ": {"jawOpen": 0.75, "lipRound": 0.45, "lowerLipDrop": 0.25},
        "ㅝ": {"jawOpen": 0.55, "lipRound": 0.55},
        "ㅙ": {"jawOpen": 0.5, "lipRound": 0.4, "lipWide": 0.35},
        "ㅞ": {"jawOpen": 0.45, "lipRound": 0.4, "lipWide": 0.3},
        "ㅢ": {"jawOpen": 0.25, "lipWide": 0.35, "lipRound": 0.15},
    },
    "sequence": [
        "REST",
        "CLOSED",
        "REST",
        "OPEN",
        "WIDE",
        "ROUND",
        "NARROW",
        "TEETH",
        "TONGUE_PROXY",
        "ㅏ",
        "ㅓ",
        "ㅗ",
        "ㅜ",
        "ㅡ",
        "ㅣ",
        "ㅐ",
        "ㅔ",
        "REST",
    ],
    "multiviewYawDeg": [0.0, 30.0, -30.0, 60.0, -60.0, 90.0, -90.0],
    "tolerances": {
        "restReturnErrorMU": 1e-4,
        "nonMouthLeakMax": 0,
        "lipIntersectionMax": 0,
        "lipOrderInversionMax": 0,
        "jawAxisDriftMax": 1e-7,
        "lrSwapMax": 0,
        "distinctMinSeparationMU": 0.01,
    },
    "determinismRuns": 3,
}


def parameter_hash() -> str:
    payload = json.dumps(GATE3_PARAMETERS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
