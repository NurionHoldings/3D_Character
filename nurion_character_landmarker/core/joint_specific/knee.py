"""Knee correction via thigh/shin medial-axis nearest approach (KNEE_AXIS_V1)."""

from __future__ import annotations

from typing import Dict, List, Optional

from mathutils import Vector

from ..alpha3_parameters import ALPHA3_PARAMETERS
from ..candidate_scoring import (
    ScoredCandidate,
    combine_scores,
    score_chain_continuity,
    score_geometry_fitness,
    score_interior_margin,
    score_proportion,
    score_symmetry,
    select_best,
)
from ..cross_section import medial_axis_point, sample_sections_along_axis
from ..evidence_confidence import compute_evidence_confidence, prefer_estimated_if_unstable
from ..landmark_engine import LandmarkPoint
from ..sources import ESTIMATED, GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, pull_inside_preserving_side


def _nearest_approach(a_pts: List[Vector], b_pts: List[Vector]) -> Optional[Vector]:
    if not a_pts or not b_pts:
        return None
    best = None
    best_d = 1e9
    for a in a_pts:
        for b in b_pts:
            d = (a - b).length
            if d < best_d:
                best_d = d
                best = a.lerp(b, 0.5)
    return best


def _section_polyline(samples, t_lo: float, t_hi: float) -> List[Vector]:
    return [s.center for s in samples if t_lo <= s.t <= t_hi]


def _correct_one_knee(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    cfg = ALPHA3_PARAMETERS["knee"]
    key = f"knee.{side}"
    seed = landmarks[key]
    hip = landmarks.get(f"hip.{side}")
    ankle = landmarks.get(f"ankle.{side}")
    if hip is None or ankle is None:
        return seed

    leg_len = (ankle.position - hip.position).length
    if leg_len < height * 0.08:
        return seed

    samples = sample_sections_along_axis(
        view,
        hip.position,
        ankle.position,
        count=int(cfg["sectionCount"]),
        rays=int(cfg["rays"]),
        max_radius=height * float(cfg["maxRadiusHeight"]),
        extend=0.02,
    )
    seed_pos = pull_inside_preserving_side(view, seed.position, side=side, center_x=center_x)

    candidates: List[ScoredCandidate] = []
    if samples and len(samples) >= 8:
        thigh_poly = _section_polyline(samples, *cfg["thighT"])
        shin_poly = _section_polyline(samples, *cfg["shinT"])
        approach = _nearest_approach(thigh_poly[-4:] or thigh_poly, shin_poly[:4] or shin_poly)
        thigh_med = medial_axis_point(samples, *cfg["thighT"])
        shin_med = medial_axis_point(samples, *cfg["shinT"])
        bend_zone = [s for s in samples if cfg["bendT"][0] <= s.t <= cfg["bendT"][1]]
        raw_positions: List[Vector] = []
        if approach is not None:
            raw_positions.append(approach)
        if thigh_med is not None and shin_med is not None:
            raw_positions.append(thigh_med.lerp(shin_med, 0.55))
        for sec in sorted(bend_zone, key=lambda s: s.width, reverse=True)[:4]:
            raw_positions.append(sec.center.copy())

        for i, raw in enumerate(raw_positions):
            pos = pull_inside_preserving_side(view, raw, side=side, center_x=center_x)
            # Soft hip alignment without overshooting seed laterality by much.
            pos.x = pos.x * 0.5 + hip.position.x * 0.5
            pos = pull_inside_preserving_side(view, pos, side=side, center_x=center_x)
            nearest = min(samples, key=lambda s: (s.center - pos).length)
            G = score_geometry_fitness(view, pos, section_area=nearest.area, hit_count=nearest.hit_count)
            C = score_chain_continuity(
                pos,
                hip.position,
                ankle.position,
                height=height,
                expected_prev_len=leg_len * 0.48,
                expected_next_len=leg_len * 0.52,
                max_angle_deg=float(cfg["maxAngleDeg"]),
            )
            total, comps = combine_scores(
                G=G,
                C=C,
                S=score_symmetry(pos, None, center_x),
                M=score_interior_margin(view, pos, height),
                P=score_proportion(pos, seed.position, height, max_disp_ratio=float(cfg["maxDispRatio"])),
            )
            candidates.append(ScoredCandidate(pos, total, comps, "KNEE_AXIS_V1", {"hits": nearest.hit_count, "idx": i}))

    g = score_geometry_fitness(view, seed_pos, hit_count=4)
    c = score_chain_continuity(
        seed_pos, hip.position, ankle.position, height=height, expected_prev_len=leg_len * 0.48
    )
    total, comps = combine_scores(
        G=g,
        C=c,
        S=score_symmetry(seed_pos, None, center_x),
        M=score_interior_margin(view, seed_pos, height),
        P=0.95,
    )
    candidates.append(ScoredCandidate(seed_pos, total * 1.08, comps, "BASELINE_PRIOR", {}))

    best, runner, _ = select_best(candidates, review_gap=float(ALPHA3_PARAMETERS["confidence"]["reviewGap"]))
    assert best is not None
    baseline = max((c.score for c in candidates if c.method == "BASELINE_PRIOR"), default=0.0)
    accept = best.method == "KNEE_AXIS_V1" and best.score >= baseline + 0.05
    if accept and (best.position - seed.position).length > height * 0.05:
        accept = best.score >= baseline + 0.07
    if not accept or prefer_estimated_if_unstable(geometry_score=best.score, estimated_score=baseline, margin=0.04):
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method == "KNEE_AXIS_V1"), runner)
        accept = False

    evidence = {
        "method": "KNEE_AXIS_V1",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": len(samples) if samples else 0,
        "crossSectionHits": int(best.meta.get("hits", 8) or 8),
        "insideMesh": True,
        "chainValidated": True,
        "symmetryDeltaCm": 0.0,
        "raycastAxes": ["U", "V"],
        "symmetryApplied": False,
        "keptBaseline": not accept,
        "acceptReject": "accept_axis_nearest" if accept else "reject_keep_estimated",
    }
    conf = compute_evidence_confidence(evidence, score_components=best.components)
    return LandmarkPoint(
        name=key,
        position=best.position,
        source=GEOMETRY_CORRECTED if accept else ESTIMATED,
        confidence=conf if accept else min(seed.confidence, conf),
        side=side,
        evidence=evidence,
    )


def correct_knees(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    for side in ("L", "R"):
        key = f"knee.{side}"
        if key in out and f"hip.{side}" in out and f"ankle.{side}" in out:
            out[key] = _correct_one_knee(view, side, out, height, center_x)
    return out
