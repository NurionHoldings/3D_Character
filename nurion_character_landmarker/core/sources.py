"""Landmark / measurement provenance for NURION Character Landmarker."""

from __future__ import annotations

from typing import Literal

Source = Literal[
    "MEASURED",
    "ESTIMATED",
    "MANUAL",
    "AI_DETECTED",
    "GEOMETRY_CORRECTED",
    "FACE_GEOMETRY_CORRECTED",
    "PROCEDURAL_PROXY",
]

MEASURED = "MEASURED"
ESTIMATED = "ESTIMATED"
MANUAL = "MANUAL"
AI_DETECTED = "AI_DETECTED"
GEOMETRY_CORRECTED = "GEOMETRY_CORRECTED"
FACE_GEOMETRY_CORRECTED = "FACE_GEOMETRY_CORRECTED"
PROCEDURAL_PROXY = "PROCEDURAL_PROXY"

VALID_SOURCES = {
    MEASURED,
    ESTIMATED,
    MANUAL,
    AI_DETECTED,
    GEOMETRY_CORRECTED,
    FACE_GEOMETRY_CORRECTED,
    PROCEDURAL_PROXY,
}

ESTIMATED_REVIEW_THRESHOLD = 0.75


def review_required(source: str, confidence: float, threshold: float = ESTIMATED_REVIEW_THRESHOLD) -> bool:
    if source in (ESTIMATED, GEOMETRY_CORRECTED):
        # Geometry-corrected joints still need human review in alpha.
        return True
    if source == FACE_GEOMETRY_CORRECTED:
        return confidence < 0.90
    if source == PROCEDURAL_PROXY:
        # Deterministic NURION proxy — still review until Alpha2 gates pass.
        return confidence < 0.92
    if source == AI_DETECTED:
        return confidence < threshold
    if source == MEASURED:
        return False
    return confidence < threshold
