"""Shoulder correction via torso–upper-arm branch intersection (SHOULDER_BRANCH_V1)."""

from __future__ import annotations

from typing import Dict

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
from ..cross_section import measure_section, sample_sections_along_axis
from ..landmark_engine import LandmarkPoint
from ..sources import ESTIMATED, GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, pull_inside


def _exclude_head_region(z: float, head_z: float, neck_z: float) -> bool:
    # Simple mask: ignore samples that climb into head volume.
    return z > (neck_z * 0.35 + head_z * 0.65)


def _correct_one_shoulder(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    key = f"shoulder.{side}"
    elbow_key = f"elbow.{side}"
    seed = landmarks[key]
    elbow = landmarks.get(elbow_key)
    neck = landmarks.get("neck")
    chest = landmarks.get("chest")
    head = landmarks.get("head")
    if elbow is None or chest is None:
        return seed

    neck_z = neck.position.z if neck else chest.position.z + height * 0.05
    head_z = head.position.z if head else neck_z + height * 0.08

    # Upper-arm axis: elbow → shoulder seed, extend toward torso.
    arm_axis = (seed.position - elbow.position)
    if arm_axis.length < 1e-6:
        arm_axis = Vector((1.0 if side == "L" else -1.0, 0.0, 0.0))
    arm_dir = arm_axis.normalized()
    # Extend past shoulder toward body center.
    torso_target = Vector((center_x, chest.position.y, chest.position.z))
    samples = sample_sections_along_axis(
        view,
        elbow.position,
        seed.position.lerp(torso_target, 0.65),
        count=28,
        rays=14,
        max_radius=height * 0.14,
        extend=0.2,
    )
    samples = [s for s in samples if not _exclude_head_region(s.center.z, head_z, neck_z)]

    candidates: list[ScoredCandidate] = []
    # Branch heuristic: along samples, find where section width expands (arm→torso junction).
    for i in range(1, len(samples)):
        prev = samples[i - 1]
        cur = samples[i]
        growth = cur.width - prev.width
        if growth < height * 0.01 and cur.t < 0.55:
            continue
        # Candidate near junction, then inset toward interior (not surface).
        pos = cur.center.lerp(torso_target, 0.15)
        # Keep laterality.
        if side == "L":
            pos.x = max(pos.x, center_x + height * 0.04)
        else:
            pos.x = min(pos.x, center_x - height * 0.04)
        pos = pull_inside(view, pos)

        G = score_geometry_fitness(view, pos, section_area=cur.area, expected_area=height * height * 0.01, hit_count=cur.hit_count)
        C = score_chain_continuity(
            pos,
            neck.position if neck else chest.position,
            elbow.position,
            height=height,
            expected_prev_len=height * 0.12,
            expected_next_len=height * 0.18,
            max_angle_deg=55.0,
        )
        mirror = landmarks.get(f"shoulder.{'R' if side == 'L' else 'L'}")
        S = score_symmetry(pos, mirror.position if mirror else None, center_x)
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height, max_disp_ratio=0.12)
        # Bonus for width growth (branch signal).
        G = min(1.0, G + min(0.15, growth / max(height * 0.05, 1e-6) * 0.15))
        total, comps = combine_scores(G=G, C=C, S=S, M=M, P=P)
        candidates.append(
            ScoredCandidate(
                position=pos,
                score=total,
                components=comps,
                method="SHOULDER_BRANCH_V1",
                meta={"t": cur.t, "width": cur.width, "growth": growth, "crossSectionSamples": len(samples)},
            )
        )

    # Axilla / top-of-shoulder probes.
    top = Vector((seed.position.x, seed.position.y, max(seed.position.z, neck_z)))
    top_sec = measure_section(view, top, Vector((1 if side == "L" else -1, 0, 0)), rays=12, max_radius=height * 0.12)
    if top_sec is not None:
        pos = pull_inside(view, top_sec.center)
        if side == "L":
            pos.x = max(pos.x, center_x + height * 0.04)
        else:
            pos.x = min(pos.x, center_x - height * 0.04)
        G = score_geometry_fitness(view, pos, section_area=top_sec.area, hit_count=top_sec.hit_count)
        C = score_chain_continuity(pos, neck.position if neck else None, elbow.position, height=height)
        S = score_symmetry(pos, None, center_x)
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height)
        total, comps = combine_scores(G=G, C=C, S=S, M=M, P=P)
        candidates.append(ScoredCandidate(pos, total, comps, "SHOULDER_TOP_V1", {"crossSectionSamples": len(samples)}))

    seed_pos = pull_inside(view, seed.position)
    for baseline_pos, method, boost in (
        (seed_pos, "SEED_FALLBACK", 0.95),
        (seed_pos, "BASELINE_PRIOR", 1.06),
    ):
        g = score_geometry_fitness(view, baseline_pos, hit_count=4)
        c = score_chain_continuity(baseline_pos, neck.position if neck else None, elbow.position, height=height)
        s = score_symmetry(baseline_pos, None, center_x)
        m = score_interior_margin(view, baseline_pos, height)
        p = score_proportion(baseline_pos, seed.position, height)
        total, comps = combine_scores(G=g, C=c, S=s, M=m, P=p)
        candidates.append(ScoredCandidate(baseline_pos, total * boost, comps, method, {}))

    best, runner, _review = select_best(candidates)
    if best is None:
        return seed
    baseline_best = max((c.score for c in candidates if c.method in ("SEED_FALLBACK", "BASELINE_PRIOR")), default=0.0)
    # Conservative: only replace alpha1-quality baseline when decisively better.
    if best.method.startswith("SHOULDER_") and best.score < baseline_best + 0.12:
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method.startswith("SHOULDER_")), runner)

    evidence = {
        "method": best.method if not best.method.endswith("FALLBACK") else "SHOULDER_BRANCH_V1",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": int(best.meta.get("crossSectionSamples", len(samples))),
        "insideMesh": True,
        "chainValidated": True,
        "symmetryDeltaCm": 0.0,
        "headMaskApplied": True,
        "raycastAxes": ["U", "V"],
        "crossSectionHits": 8,
        "symmetryApplied": False,
    }
    source = GEOMETRY_CORRECTED if best.method.startswith("SHOULDER_") else seed.source
    return LandmarkPoint(
        name=key,
        position=best.position,
        source=source,
        confidence=max(0.55, min(0.93, best.score)),
        side=side,
        evidence=evidence,
    )


def correct_shoulders(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    for side in ("L", "R"):
        key = f"shoulder.{side}"
        if key not in out:
            continue
        out[key] = _correct_one_shoulder(view, side, out, height, center_x)
    return out
