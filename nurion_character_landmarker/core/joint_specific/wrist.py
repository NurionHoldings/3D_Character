"""Wrist correction via forearm→hand narrow-section transition (WRIST_TRANSITION_V1)."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from mathutils import Vector

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
from ..cross_section import local_minima_indices, medial_axis_point, sample_sections_along_axis
from ..landmark_engine import LandmarkPoint
from ..sources import ESTIMATED, GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, pull_inside


def _hand_direction(elbow: Vector, wrist_est: Vector) -> Vector:
    d = wrist_est - elbow
    if d.length < 1e-6:
        return Vector((1.0, 0.0, 0.0))
    return d.normalized()


def _correct_one_wrist(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    elbow_key = f"elbow.{side}"
    wrist_key = f"wrist.{side}"
    seed = landmarks[wrist_key]
    elbow = landmarks.get(elbow_key)
    if elbow is None:
        return seed

    axis_dir = _hand_direction(elbow.position, seed.position)
    # Sample beyond estimated wrist into hand region.
    hand_est = seed.position + axis_dir * (height * 0.08)
    samples = sample_sections_along_axis(
        view,
        elbow.position,
        hand_est,
        count=32,
        rays=16,
        max_radius=height * 0.12,
        extend=0.05,
    )
    if len(samples) < 6:
        return LandmarkPoint(
            name=wrist_key,
            position=pull_inside(view, seed.position),
            source=ESTIMATED,
            confidence=seed.confidence,
            side=side,
            evidence={"method": "WRIST_TRANSITION_V1", "reverted": True, "reason": "insufficient_sections"},
        )

    areas = [s.area for s in samples]
    widths = [s.width for s in samples]
    # Prefer width minima in distal half (hand transition).
    distal = [(i, samples[i]) for i in range(len(samples)) if samples[i].t >= 0.45]
    width_vals = [s.width for _, s in distal]
    local_mins = local_minima_indices(width_vals)
    candidate_indices = []
    for li in local_mins:
        candidate_indices.append(distal[li][0])
    # Also take global distal minimum width.
    if distal:
        candidate_indices.append(min(distal, key=lambda it: it[1].width)[0])
    # Forearm medial axis near transition + narrow section blend.
    forearm_medial = medial_axis_point(samples, 0.25, 0.55)
    hand_medial = medial_axis_point(samples, 0.70, 0.95)

    candidates: list[ScoredCandidate] = []
    for idx in sorted(set(candidate_indices)):
        sec = samples[idx]
        pos = sec.center.copy()
        if forearm_medial is not None:
            pos = pos.lerp(forearm_medial, 0.35)
        if hand_medial is not None:
            # Transition zone between forearm and hand medial axes.
            pos = pos.lerp(hand_medial, 0.25)
        pos = pull_inside(view, pos)

        # Chain angle constraint elbow→wrist→hand
        G, _ = None, None
        G = score_geometry_fitness(view, pos, section_area=sec.area, expected_area=max(areas) * 0.35, hit_count=sec.hit_count)
        C = score_chain_continuity(
            pos,
            elbow.position,
            hand_est,
            height=height,
            expected_prev_len=height * 0.22,
            expected_next_len=height * 0.08,
            max_angle_deg=40.0,
        )
        mirror = landmarks.get(f"wrist.{'R' if side == 'L' else 'L'}")
        S = score_symmetry(pos, mirror.position if mirror else None, center_x)
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height, max_disp_ratio=0.10)
        total, comps = combine_scores(G=G, C=C, S=S, M=M, P=P)
        candidates.append(
            ScoredCandidate(
                position=pos,
                score=total,
                components=comps,
                method="WRIST_TRANSITION_V1",
                meta={
                    "t": sec.t,
                    "width": sec.width,
                    "area": sec.area,
                    "crossSectionSamples": len(samples),
                },
            )
        )

    # Keep current/seed as strong baseline candidates to prevent alpha1 regressions.
    for baseline_pos, method, boost in (
        (pull_inside(view, seed.position), "SEED_FALLBACK", 0.95),
        (pull_inside(view, seed.position), "BASELINE_PRIOR", 1.0),
    ):
        g = score_geometry_fitness(view, baseline_pos, hit_count=4)
        c = score_chain_continuity(baseline_pos, elbow.position, hand_est, height=height, expected_prev_len=height * 0.22)
        s = score_symmetry(baseline_pos, None, center_x)
        m = score_interior_margin(view, baseline_pos, height)
        p = score_proportion(baseline_pos, seed.position, height)
        total, comps = combine_scores(G=g, C=c, S=s, M=m, P=p)
        candidates.append(ScoredCandidate(baseline_pos, total * boost, comps, method, {}))

    best, runner, review = select_best(candidates, review_gap=0.08)
    if best is None:
        return seed
    # Require clear win over baseline prior to accept transition method.
    baseline_best = max((c.score for c in candidates if c.method in ("SEED_FALLBACK", "BASELINE_PRIOR")), default=0.0)
    if best.method == "WRIST_TRANSITION_V1" and best.score < baseline_best + 0.01:
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method == "WRIST_TRANSITION_V1"), runner)

    # Left/right forearm length ratio sanity vs opposite side if present.
    chain_ok = True
    opp_elbow = landmarks.get(f"elbow.{'R' if side == 'L' else 'L'}")
    opp_wrist = landmarks.get(f"wrist.{'R' if side == 'L' else 'L'}")
    symmetry_delta_cm = 0.0
    if opp_elbow and opp_wrist:
        len_self = (best.position - elbow.position).length
        len_opp = (opp_wrist.position - opp_elbow.position).length
        if len_opp > 1e-6:
            ratio = len_self / len_opp
            if ratio < 0.75 or ratio > 1.25:
                chain_ok = False
                review = True
            symmetry_delta_cm = abs(len_self - len_opp) * 100.0

    # Prefer seed if scoring rejects chain.
    use_pos = best.position
    source = GEOMETRY_CORRECTED
    if not chain_ok and runner is not None and runner.method == "SEED_FALLBACK":
        use_pos = runner.position
        source = ESTIMATED

    evidence = {
        "method": "WRIST_TRANSITION_V1",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": len(samples),
        "insideMesh": True,
        "chainValidated": chain_ok,
        "symmetryDeltaCm": round(symmetry_delta_cm, 3),
        "raycastAxes": ["U", "V"],
        "crossSectionHits": int(best.meta.get("hit_count", best.meta.get("width", 0)) or 0),
        "symmetryApplied": False,
    }
    return LandmarkPoint(
        name=wrist_key,
        position=use_pos,
        source=source if source == GEOMETRY_CORRECTED else ESTIMATED,
        confidence=max(0.55, min(0.93, best.score)),
        side=side,
        evidence=evidence,
        # review_required overwritten in __post_init__; GEOMETRY always review in sources.
    )


def correct_wrists(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    for side in ("L", "R"):
        key = f"wrist.{side}"
        if key not in out or f"elbow.{side}" not in out:
            continue
        out[key] = _correct_one_wrist(view, side, out, height, center_x)
    return out
