"""Phoneme → Viseme basis mapping (Korean classes)."""

from __future__ import annotations

from typing import Dict, List

# Primary basis labels used by Gate3 recipes
PHONEME_CLASS: Dict[str, str] = {}

for s in list("ㅁㅂㅃㅍ"):
    PHONEME_CLASS[s] = "CLOSED"
for s in list("ㅏㅑ"):
    PHONEME_CLASS[s] = "OPEN"
for s in list("ㅐㅔㅒㅖㅣ"):
    PHONEME_CLASS[s] = "WIDE"
for s in list("ㅗㅛㅜㅠㅘㅝㅙㅞ"):
    PHONEME_CLASS[s] = "ROUND"
for s in list("ㅡㅢ"):
    PHONEME_CLASS[s] = "NARROW"
for s in list("ㅅㅆㅈㅉㅊ"):
    PHONEME_CLASS[s] = "TEETH"
for s in list("ㄴㄷㄸㄹㅌ"):
    PHONEME_CLASS[s] = "TONGUE_LIMITED"
for s in list("ㄱㄲㅋㅎㅇ"):
    PHONEME_CLASS[s] = "RESTRICTED"
PHONEME_CLASS[" "] = "REST"
PHONEME_CLASS["SIL"] = "REST"
PHONEME_CLASS["."] = "REST"
PHONEME_CLASS["?"] = "REST"
PHONEME_CLASS["!"] = "REST"

# Gate3-compatible axis recipes (subset)
BASIS_RECIPES: Dict[str, Dict[str, float]] = {
    "REST": {},
    "CLOSED": {"lipClose": 0.9, "jawOpen": 0.0},
    "OPEN": {"jawOpen": 0.85, "lowerLipDrop": 0.35},
    "WIDE": {"jawOpen": 0.25, "lipWide": 0.85, "cornerPull": 0.4},
    "ROUND": {"jawOpen": 0.35, "lipRound": 0.9, "lipWide": -0.25},
    "NARROW": {"jawOpen": 0.2, "lipWide": -0.15, "lipRound": 0.15},
    "TEETH": {"jawOpen": 0.15, "teethApproach": 0.85, "upperLipRaise": 0.35},
    "TONGUE_LIMITED": {"jawOpen": 0.2, "teethApproach": 0.4, "lowerLipDrop": 0.15},
    # restricted consonants lean on neighboring vowel; fallback mild open
    "RESTRICTED": {"jawOpen": 0.15},
}


def class_for(symbol: str) -> str:
    if symbol in PHONEME_CLASS:
        return PHONEME_CLASS[symbol]
    # compound jamo already covered; unknown → REST-safe
    return "REST"


def recipe_for_class(cls: str) -> Dict[str, float]:
    return dict(BASIS_RECIPES.get(cls, {}))
