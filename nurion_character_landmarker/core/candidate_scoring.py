"""Multi-criteria candidate scoring for joint-specific geometry (v0.2 alpha.2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from mathutils import Vector

from .transform_normalize import WorldMeshView, nearest_on_mesh, point_inside_or_on_mesh


@dataclass
class ScoredCandidate:
    position: Vector
    score: float
    components: Dict[str, float] = field(default_factory=dict)
    method: str = ""
    meta: Dict = field(default_factory=dict)


DEFAULT_WEIGHTS = {
    "G": 0.30,  # geometry fitness
    "C": 0.25,  # chain continuity
    "S": 0.15,  # symmetry
    "M": 0.20,  # mesh interior margin
    "P": 0.10,  # proportion prior
}


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def score_geometry_fitness(
    view: WorldMeshView,
    pos: Vector,
    *,
    section_area: Optional[float] = None,
    expected_area: Optional[float] = None,
    hit_count: int = 0,
) -> float:
    inside = 1.0 if point_inside_or_on_mesh(view, pos) else 0.0
    hit_term = clamp01(hit_count / 12.0)
    area_term = 0.5
    if section_area is not None and expected_area and expected_area > 1e-8:
        ratio = section_area / expected_area
        area_term = clamp01(1.0 - abs(math_log_ratio(ratio)))
    return clamp01(0.5 * inside + 0.3 * hit_term + 0.2 * area_term)


def math_log_ratio(ratio: float) -> float:
    import math

    return math.log(max(ratio, 1e-6))


def score_chain_continuity(
    pos: Vector,
    prev: Optional[Vector],
    nxt: Optional[Vector],
    *,
    height: float,
    expected_prev_len: Optional[float] = None,
    expected_next_len: Optional[float] = None,
    max_angle_deg: float = 50.0,
) -> float:
    import math

    score = 0.5
    if prev is not None:
        d = (pos - prev).length
        if expected_prev_len:
            score += 0.25 * clamp01(1.0 - abs(d - expected_prev_len) / max(expected_prev_len, 1e-6))
        else:
            score += 0.15 * clamp01(1.0 - abs(d / max(height, 1e-6) - 0.2) / 0.2)
    if nxt is not None:
        d = (nxt - pos).length
        if expected_next_len:
            score += 0.15 * clamp01(1.0 - abs(d - expected_next_len) / max(expected_next_len, 1e-6))
    if prev is not None and nxt is not None:
        a = (pos - prev).normalized()
        b = (nxt - pos).normalized()
        if a.length > 1e-8 and b.length > 1e-8:
            ang = math.degrees(math.acos(clamp01(a.dot(b))))
            score += 0.2 * clamp01(1.0 - ang / max_angle_deg)
    return clamp01(score)


def score_symmetry(pos: Vector, mirror_pos: Optional[Vector], center_x: float) -> float:
    if mirror_pos is None:
        # Soft prior: distance from center plane should be moderate.
        return clamp01(1.0 - abs(abs(pos.x - center_x) - 0.15) / 0.3)
    mirror_x = 2.0 * center_x - pos.x
    dx = abs(mirror_pos.x - mirror_x)
    dy = abs(mirror_pos.y - pos.y)
    dz = abs(mirror_pos.z - pos.z)
    return clamp01(1.0 - (dx + dy + dz) / 0.25)


def score_interior_margin(view: WorldMeshView, pos: Vector, height: float) -> float:
    if not point_inside_or_on_mesh(view, pos):
        return 0.0
    _loc, _n, dist = nearest_on_mesh(view, pos)
    # Prefer a few centimeters inside, not surface-hugging and not too deep voids.
    target = height * 0.02
    return clamp01(1.0 - abs(dist - target) / max(target * 3.0, 1e-6))


def score_proportion(pos: Vector, seed: Vector, height: float, max_disp_ratio: float = 0.12) -> float:
    disp = (pos - seed).length / max(height, 1e-6)
    return clamp01(1.0 - disp / max_disp_ratio)


def combine_scores(
    *,
    G: float,
    C: float,
    S: float,
    M: float,
    P: float,
    weights: Optional[Dict[str, float]] = None,
) -> tuple[float, Dict[str, float]]:
    w = weights or DEFAULT_WEIGHTS
    comps = {"G": clamp01(G), "C": clamp01(C), "S": clamp01(S), "M": clamp01(M), "P": clamp01(P)}
    total = (
        w["G"] * comps["G"]
        + w["C"] * comps["C"]
        + w["S"] * comps["S"]
        + w["M"] * comps["M"]
        + w["P"] * comps["P"]
    )
    return float(total), comps


def select_best(
    candidates: List[ScoredCandidate],
    review_gap: float = 0.08,
) -> tuple[Optional[ScoredCandidate], Optional[ScoredCandidate], bool]:
    if not candidates:
        return None, None, True
    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)
    best = ordered[0]
    runner = ordered[1] if len(ordered) > 1 else None
    review = True
    if runner is not None and (best.score - runner.score) < review_gap:
        review = True
    elif best.score < 0.55:
        review = True
    else:
        # Still keep review for alpha.2 GEOMETRY_CORRECTED policy unless very decisive.
        review = (runner is None) or ((best.score - runner.score) < 0.15)
    return best, runner, review
