"""Evidence-based confidence for geometry-corrected landmarks (v0.2 alpha.3)."""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

from .candidate_scoring import clamp01


def candidate_separation_score(selected: Optional[float], runner_up: Optional[float]) -> float:
    if selected is None:
        return 0.40
    if runner_up is None:
        return 0.85
    gap = float(selected) - float(runner_up)
    # Soft floor: tied candidates still retain partial confidence.
    return clamp01(0.40 + gap / 0.20)


def compute_evidence_confidence(
    evidence: Optional[Dict[str, Any]],
    *,
    score_components: Optional[Dict[str, float]] = None,
    symmetry_dependent: bool = False,
) -> float:
    """
    confidence ≈ geometric_mean(
      geometryScore, chainScore, insideMeshScore, candidateSeparation, symmetryScore
    )
    with soft floors so a single weak factor cannot crush the product to the clamp.
    """
    ev = evidence or {}
    comps = score_components or ev.get("scoreComponents") or {}

    geometry = max(0.50, clamp01(float(comps.get("G", 0.55))))
    chain = max(0.50, clamp01(float(comps.get("C", 0.55))))
    symmetry = max(0.45, clamp01(float(comps.get("S", 0.55))))
    inside = 1.0 if ev.get("insideMesh", False) else 0.35
    separation = candidate_separation_score(ev.get("selectedScore"), ev.get("runnerUpScore"))

    factors = [geometry, chain, inside, separation, symmetry]
    log_mean = sum(math.log(max(f, 1e-6)) for f in factors) / float(len(factors))
    conf = math.exp(log_mean)

    hits = int(ev.get("crossSectionHits", 0) or 0)
    samples = int(ev.get("crossSectionSamples", 0) or 0)
    if hits < 4 and samples < 8:
        conf *= 0.80
    elif hits < 6:
        conf *= 0.92

    if symmetry_dependent or bool(ev.get("symmetryApplied", False)):
        conf *= 0.92
    if float(ev.get("symmetryDeltaCm", 0.0) or 0.0) > 4.0:
        conf *= 0.92

    if ev.get("keptBaseline") or ev.get("reverted"):
        conf *= 0.85
    if not ev.get("chainValidated", True):
        conf *= 0.80

    return float(max(0.25, min(0.95, conf)))


def prefer_estimated_if_unstable(
    *,
    geometry_score: float,
    estimated_score: float,
    margin: float = 0.02,
) -> bool:
    """True when geometry is not clearly more stable than the ESTIMATED seed."""
    return geometry_score + 1e-9 < estimated_score + margin
