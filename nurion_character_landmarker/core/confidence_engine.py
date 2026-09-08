"""Confidence scoring and low-confidence review helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from .landmark_engine import LandmarkPoint
from .sources import ESTIMATED, MEASURED

DEFAULT_THRESHOLD = 0.75


@dataclass
class ConfidenceReport:
    threshold: float
    low_confidence: List[str]
    review_required: List[str]
    average: float


def evaluate_confidence(
    landmarks: Dict[str, LandmarkPoint],
    threshold: float = DEFAULT_THRESHOLD,
) -> ConfidenceReport:
    if not landmarks:
        return ConfidenceReport(threshold=threshold, low_confidence=[], review_required=[], average=0.0)

    values = [p.confidence for p in landmarks.values()]
    low = sorted(name for name, p in landmarks.items() if p.confidence < threshold and p.source != MEASURED)
    review = sorted(name for name, p in landmarks.items() if p.review_required)
    avg = sum(values) / len(values)
    return ConfidenceReport(threshold=threshold, low_confidence=low, review_required=review, average=avg)


def validate_positions(landmarks: Dict[str, LandmarkPoint]) -> List[str]:
    """Return human-readable validation issues."""
    issues: List[str] = []
    required = ["pelvis", "shoulder.L", "shoulder.R", "hip.L", "hip.R", "ankle.L", "ankle.R"]
    for key in required:
        if key not in landmarks:
            issues.append(f"Missing required landmark: {key}")

    if "shoulder.L" in landmarks and "shoulder.R" in landmarks:
        if landmarks["shoulder.L"].position.x < landmarks["shoulder.R"].position.x:
            issues.append("shoulder.L.x is not greater than shoulder.R.x (check left/right).")

    if "ankle.L" in landmarks and "pelvis" in landmarks:
        if landmarks["ankle.L"].position.z > landmarks["pelvis"].position.z:
            issues.append("Ankle Z is above pelvis Z.")

    estimated = [n for n, p in landmarks.items() if p.source == ESTIMATED and not n.startswith("bounds.")]
    if estimated:
        issues.append(
            f"{len(estimated)} joint landmarks are ESTIMATED — move guides and save as MANUAL before rig use."
        )

    return issues
