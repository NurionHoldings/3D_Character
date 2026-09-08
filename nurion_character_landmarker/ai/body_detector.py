"""Body landmark facade — v0.1 uses ESTIMATED geometry ratios only (no AI)."""

from __future__ import annotations

from typing import Dict

from ..core.character_analyzer import CharacterAnalysis
from ..core.landmark_engine import LandmarkPoint, estimate_body_landmarks
from ..core.measurement_engine import CharacterMeasurements


def detect_body(
    analysis: CharacterAnalysis,
    measurements: CharacterMeasurements,
) -> Dict[str, LandmarkPoint]:
    return estimate_body_landmarks(analysis, measurements)
