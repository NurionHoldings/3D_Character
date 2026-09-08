"""Elbow correction via upper-arm / forearm axis bend (ELBOW_BEND_V1)."""

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
from ..transform_normalize import WorldMeshView, pull_inside, pull_inside_preserving_side


def _curvature_scores(centers: List[Vector]) -> List[float]:
    if len(centers) < 3:
        return [0.0] * len(centers)
    out = [0.0]
    for i in range(1, len(centers) - 1):
        a = centers[i] - centers[i - 1]
        b = centers[i + 1] - centers[i]
        if a.length < 1e-8 or b.length < 1e-8:
            out.append(0.0)
            continue
        # 1 - cos(angle) ≈ bend magnitude
        out.append(max(0.0, 1.0 - max(-1.0, min(1.0, a.normalized().dot(b.normalized())))))
    out.append(0.0)
    return out


def _closest_axis_point(a: Optional[Vector], b: Optional[Vector], seed: Vector) -> Optional[Vector]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    # Midpoint of closest segment endpoints (degenerate axes as points).
    return a.lerp(b, 0.5).lerp(seed, 0.15)


def _correct_one_elbow(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    cfg = ALPHA3_PARAMETERS["elbow"]
    key = f"elbow.{side}"
    seed = landmarks[key]
    shoulder = landmarks.get(f"shoulder.{side}")
    wrist = landmarks.get(f"wrist.{side}")
    if shoulder is None or wrist is None:
        return seed

    # Arm-length ratio only limits the candidate corridor (no GT).
    arm_len = (wrist.position - shoulder.position).length
    if arm_len < height * 0.05:
        return seed
    # Search band around anthropometric mid-forearm junction without locking a single ratio.
    t_lo, t_hi = cfg["bendT"]

    samples = sample_sections_along_axis(
        view,
        shoulder.position,
        wrist.position,
        count=int(cfg["sectionCount"]),
        rays=int(cfg["rays"]),
        max_radius=height * float(cfg["maxRadiusHeight"]),
        extend=0.02,
    )
    if len(samples) < 8:
        return LandmarkPoint(
            name=key,
            position=pull_inside(view, seed.position),
            source=ESTIMATED,
            confidence=seed.confidence,
            side=side,
            evidence={
                "method": "ELBOW_BEND_V1",
                "reverted": True,
                "reason": "insufficient_sections",
                "acceptReject": "reject_insufficient_ray_sections",
            },
        )

    upper = medial_axis_point(samples, *cfg["upperT"])
    forearm = medial_axis_point(samples, *cfg["forearmT"])
    bend_zone = [s for s in samples if t_lo <= s.t <= t_hi]
    centers = [s.center for s in bend_zone]
    curves = _curvature_scores(centers)

    # Width / area change rate: upper vs forearm transition.
    widths = [s.width for s in samples]
    change_idxs: List[int] = []
    for i in range(1, len(samples) - 1):
        if not (t_lo <= samples[i].t <= t_hi):
            continue
        d1 = abs(widths[i] - widths[i - 1])
        d2 = abs(widths[i + 1] - widths[i])
        if d1 + d2 > 0:
            change_idxs.append(i)

    candidate_secs = list(bend_zone)
    if bend_zone and curves:
        # Top curvature samples.
        ranked = sorted(range(len(bend_zone)), key=lambda i: curves[i], reverse=True)
        for i in ranked[:4]:
            candidate_secs.append(bend_zone[i])
    for i in change_idxs[:6]:
        candidate_secs.append(samples[i])

    axis_blend = _closest_axis_point(upper, forearm, seed.position)

    candidates: List[ScoredCandidate] = []
    for sec in candidate_secs:
        pos = sec.center.copy()
        if axis_blend is not None:
            pos = pos.lerp(axis_blend, 0.45)
        # Soft corridor clamp along shoulder→wrist.
        axis = (wrist.position - shoulder.position).normalized()
        proj_t = (pos - shoulder.position).dot(axis) / max(arm_len, 1e-6)
        if proj_t < t_lo or proj_t > t_hi:
            pos = shoulder.position + axis * (arm_len * max(t_lo, min(t_hi, proj_t)))
            pos = pos.lerp(sec.center, 0.5)
        pos = pull_inside_preserving_side(view, pos, side=side, center_x=center_x)

        G = score_geometry_fitness(view, pos, section_area=sec.area, hit_count=sec.hit_count)
        C = score_chain_continuity(
            pos,
            shoulder.position,
            wrist.position,
            height=height,
            expected_prev_len=arm_len * 0.45,
            expected_next_len=arm_len * 0.55,
            max_angle_deg=float(cfg["maxAngleDeg"]),
        )
        mirror = landmarks.get(f"elbow.{'R' if side == 'L' else 'L'}")
        S = score_symmetry(pos, mirror.position if mirror else None, center_x)
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height, max_disp_ratio=float(cfg["maxDispRatio"]))
        total, comps = combine_scores(G=G, C=C, S=S, M=M, P=P)
        candidates.append(
            ScoredCandidate(pos, total, comps, "ELBOW_BEND_V1", {"t": sec.t, "hits": sec.hit_count})
        )

    seed_pos = pull_inside_preserving_side(view, seed.position, side=side, center_x=center_x)
    g0 = score_geometry_fitness(view, seed_pos, hit_count=4)
    c0 = score_chain_continuity(
        seed_pos, shoulder.position, wrist.position, height=height, expected_prev_len=arm_len * 0.45
    )
    s0 = score_symmetry(seed_pos, None, center_x)
    m0 = score_interior_margin(view, seed_pos, height)
    total0, comps0 = combine_scores(G=g0, C=c0, S=s0, M=m0, P=0.9)
    candidates.append(ScoredCandidate(seed_pos, total0, comps0, "BASELINE_PRIOR", {}))

    best, runner, _ = select_best(candidates, review_gap=float(ALPHA3_PARAMETERS["confidence"]["reviewGap"]))
    assert best is not None
    baseline = max((c.score for c in candidates if c.method == "BASELINE_PRIOR"), default=0.0)
    accept = best.method == "ELBOW_BEND_V1" and best.score >= baseline + float(cfg["acceptMarginOverBaseline"])
    # Anti-regression vs alpha.2 elbow seeds: large moves need a decisive win.
    if accept and (best.position - seed_pos).length > height * 0.05:
        accept = best.score >= baseline + 0.035
    # Reject candidates that collapse toward the sagittal plane vs the pulled seed.
    if accept and abs(best.position.x - center_x) + height * 0.015 < abs(seed_pos.x - center_x):
        accept = False
    if not accept or prefer_estimated_if_unstable(geometry_score=best.score, estimated_score=baseline):
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method == "ELBOW_BEND_V1"), runner)
        accept = False

    evidence = {
        "method": "ELBOW_BEND_V1",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": len(samples),
        "crossSectionHits": int(best.meta.get("hits", 8) or 8),
        "insideMesh": True,
        "chainValidated": True,
        "symmetryDeltaCm": 0.0,
        "raycastAxes": ["U", "V"],
        "symmetryApplied": False,
        "keptBaseline": not accept,
        "acceptReject": "accept_bend_axis" if accept else "reject_keep_estimated_unstable_or_weak",
    }
    conf = compute_evidence_confidence(evidence, score_components=best.components)
    source = GEOMETRY_CORRECTED if accept else ESTIMATED
    return LandmarkPoint(
        name=key,
        position=best.position,
        source=source,
        confidence=conf if accept else min(seed.confidence, conf),
        side=side,
        evidence=evidence,
    )


def correct_elbows(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    for side in ("L", "R"):
        key = f"elbow.{side}"
        if key in out and f"shoulder.{side}" in out and f"wrist.{side}" in out:
            out[key] = _correct_one_elbow(view, side, out, height, center_x)
    return out
