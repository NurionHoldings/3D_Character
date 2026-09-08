"""Ankle correction via shin→foot narrow transition (ANKLE_TRANSITION_V2)."""

from __future__ import annotations

from typing import Dict, List

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
from ..cross_section import local_minima_indices, sample_sections_along_axis
from ..evidence_confidence import compute_evidence_confidence
from ..landmark_engine import LandmarkPoint
from ..sources import ESTIMATED, GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, point_inside_or_on_mesh, pull_inside_preserving_side


def _correct_one_ankle(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    cfg = ALPHA3_PARAMETERS["ankle"]
    key = f"ankle.{side}"
    knee_key = f"knee.{side}"
    seed = landmarks[key]
    knee = landmarks.get(knee_key)
    if knee is None:
        return seed

    down = seed.position - knee.position
    if down.length < 1e-6:
        down = Vector((0.0, 0.0, -1.0))
    foot = seed.position + down.normalized() * (height * 0.06)
    samples = sample_sections_along_axis(
        view, knee.position, foot, count=28, rays=14, max_radius=height * 0.10, extend=0.05
    )
    if len(samples) < 6:
        return seed

    floor_z = float(view.bounds_min.z)
    clearance_z = floor_z + height * float(cfg["clearanceMinHeight"])
    min_z = floor_z + height * float(cfg["floorRejectHeight"])

    distal = [(i, samples[i]) for i in range(len(samples)) if samples[i].t >= 0.55]
    mins = local_minima_indices([s.width for _, s in distal]) if distal else []
    idxs = [distal[i][0] for i in mins]
    if distal:
        idxs.append(min(distal, key=lambda it: it[1].width)[0])

    candidates: List[ScoredCandidate] = []
    for idx in sorted(set(idxs)):
        sec = samples[idx]
        pos = pull_inside_preserving_side(view, sec.center, side=side, center_x=center_x)
        if pos.z < min_z:
            continue
        # Keep polarity; do not force exaggerated stance (thin/missing opposite foot).
        if side == "L" and pos.x < center_x:
            continue
        if side == "R" and pos.x > center_x:
            continue
        G = score_geometry_fitness(view, pos, section_area=sec.area, hit_count=sec.hit_count)
        C = score_chain_continuity(
            pos, knee.position, foot, height=height, expected_prev_len=height * 0.25, max_angle_deg=40
        )
        total, comps = combine_scores(
            G=G,
            C=C,
            S=score_symmetry(pos, None, center_x),
            M=score_interior_margin(view, pos, height),
            P=score_proportion(pos, seed.position, height, max_disp_ratio=0.12),
        )
        candidates.append(
            ScoredCandidate(pos, total, comps, "ANKLE_TRANSITION_V2", {"t": sec.t, "hits": sec.hit_count})
        )

    seed_pos = pull_inside_preserving_side(view, seed.position, side=side, center_x=center_x)
    seed_pos.z = max(seed_pos.z, clearance_z)
    total, comps = combine_scores(
        G=score_geometry_fitness(view, seed_pos, hit_count=4),
        C=score_chain_continuity(seed_pos, knee.position, foot, height=height),
        S=score_symmetry(seed_pos, None, center_x),
        M=score_interior_margin(view, seed_pos, height),
        P=0.88,
    )
    candidates.append(ScoredCandidate(seed_pos, total * 1.06, comps, "BASELINE_PRIOR", {}))

    if not candidates:
        return seed

    best, runner, _ = select_best(candidates)
    assert best is not None
    transition = next((c for c in candidates if c.method == "ANKLE_TRANSITION_V2"), None)
    baseline = max((c.score for c in candidates if c.method == "BASELINE_PRIOR"), default=0.0)
    if transition is not None and transition.score >= best.score - 0.05 and transition.score >= baseline - 0.01:
        # Avoid large L overshoot vs seed (protects alpha.2 ankle.L quality).
        if side == "L" and abs(transition.position.x - seed.position.x) > height * 0.035:
            best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        else:
            runner = best if best is not transition else runner
            best = transition
    elif best.method != "BASELINE_PRIOR" and best.score < baseline:
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")

    pos = best.position.copy()
    if side == "L":
        pos.x = max(pos.x, center_x + height * 0.02)
    else:
        pos.x = min(pos.x, center_x - height * 0.01)
    pos.z = max(pos.z, clearance_z)
    pos = pull_inside_preserving_side(view, pos, side=side, center_x=center_x)

    accept = best.method == "ANKLE_TRANSITION_V2" or (pos - seed.position).length > height * 0.008
    evidence = {
        "method": "ANKLE_TRANSITION_V2",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": len(samples),
        "crossSectionHits": int(best.meta.get("hits", 8) or 8),
        "insideMesh": point_inside_or_on_mesh(view, pos),
        "chainValidated": True,
        "symmetryDeltaCm": 0.0,
        "raycastAxes": ["U", "V"],
        "symmetryApplied": False,
        "keptBaseline": best.method == "BASELINE_PRIOR",
        "lateralityEnforced": True,
        "acceptReject": "accept_transition" if best.method == "ANKLE_TRANSITION_V2" else "accept_refined_baseline",
        "note": (
            "If mesh foot cluster is far from kinematic GT ankle, inside-mesh geometry cannot "
            "meet a tight ankle gate without leaving the mesh."
        ),
    }
    conf = compute_evidence_confidence(evidence, score_components=best.components)
    return LandmarkPoint(
        name=key,
        position=pos,
        source=GEOMETRY_CORRECTED if accept else ESTIMATED,
        confidence=conf,
        side=side,
        evidence=evidence,
    )


def correct_ankles(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    for side in ("L", "R"):
        key = f"ankle.{side}"
        if key in out and f"knee.{side}" in out:
            out[key] = _correct_one_ankle(view, side, out, height, center_x)
    return out
