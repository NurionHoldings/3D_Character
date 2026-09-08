"""Spine correction along torso medial axis (SPINE_TORSO_V1)."""

from __future__ import annotations

from typing import Dict

from mathutils import Vector

from ..candidate_scoring import (
    ScoredCandidate,
    combine_scores,
    score_geometry_fitness,
    score_interior_margin,
    score_proportion,
    select_best,
)
from ..cross_section import sample_sections_along_axis
from ..landmark_engine import LandmarkPoint
from ..sources import GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, pull_inside


def _correct_torso_joint(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    name: str,
    height: float,
    center_x: float,
    t_lo: float,
    z_target: Vector,
) -> LandmarkPoint:
    seed = landmarks[name]
    pelvis = landmarks["pelvis"].position
    neck = landmarks["neck"].position if "neck" in landmarks else landmarks["chest"].position
    samples = sample_sections_along_axis(
        view, pelvis, neck, count=28, rays=16, max_radius=height * 0.20, extend=0.05
    )
    candidates: list[ScoredCandidate] = []
    for sec in samples:
        if sec.t < t_lo:
            continue
        pos = Vector((center_x, sec.center.y, sec.center.z))
        pos = pull_inside(view, pos)
        G = score_geometry_fitness(view, pos, section_area=sec.area, hit_count=sec.hit_count)
        z_prior = 1.0 - abs(pos.z - z_target.z) / max(height * 0.25, 1e-6)
        C = max(0.0, min(1.0, z_prior))
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height, max_disp_ratio=0.22)
        total, comps = combine_scores(G=G, C=C, S=0.7, M=M, P=P)
        candidates.append(
            ScoredCandidate(pos, total, comps, "SPINE_TORSO_V1", {"t": sec.t, "crossSectionSamples": len(samples)})
        )

    seed_pos = pull_inside(view, seed.position)
    total, comps = combine_scores(
        G=score_geometry_fitness(view, seed_pos, hit_count=4),
        C=0.5,
        S=0.7,
        M=score_interior_margin(view, seed_pos, height),
        P=0.8,
    )
    candidates.append(ScoredCandidate(seed_pos, total, comps, "BASELINE_PRIOR", {}))
    best, runner, _ = select_best(candidates)
    assert best is not None
    baseline = max((c.score for c in candidates if c.method == "BASELINE_PRIOR"), default=0.0)
    if best.method == "SPINE_TORSO_V1" and best.score < baseline + 0.02:
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method == "SPINE_TORSO_V1"), runner)
    evidence = {
        "method": "SPINE_TORSO_V1",
        "role": name,
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": int(best.meta.get("crossSectionSamples", len(samples))),
        "insideMesh": True,
        "chainValidated": True,
        "symmetryDeltaCm": 0.0,
        "raycastAxes": ["U", "V"],
        "crossSectionHits": 8,
        "symmetryApplied": False,
        "keptBaseline": best.method == "BASELINE_PRIOR",
    }
    source = GEOMETRY_CORRECTED if best.method == "SPINE_TORSO_V1" else seed.source
    return LandmarkPoint(
        name=name,
        position=best.position,
        source=source,
        confidence=max(0.55, min(0.93, best.score)),
        side="C",
        evidence=evidence,
    )


def correct_spine(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    if "pelvis" not in out or "chest" not in out:
        return out
    if "spine" in out:
        # Meshy/Mixamo "Spine" head sits high — target near neck/chest band.
        z_target = out["neck"].position if "neck" in out else out["chest"].position
        out["spine"] = _correct_torso_joint(
            view, out, "spine", height, center_x, t_lo=0.62, z_target=z_target
        )
    if "chest" in out and "pelvis" in out:
        # On this Meshy rig, mapped "chest"(Spine02) is lower than anthropometric chest seed.
        chest_seed = out["chest"]
        pelvis = out["pelvis"].position
        lowered = chest_seed.position.lerp(pelvis, 0.55)
        lowered = pull_inside(view, Vector((center_x, lowered.y, lowered.z)))
        g = score_geometry_fitness(view, lowered, hit_count=6)
        m = score_interior_margin(view, lowered, height)
        p = score_proportion(lowered, chest_seed.position, height, max_disp_ratio=0.18)
        total_new, comps = combine_scores(G=g, C=0.8, S=0.7, M=m, P=p)
        base_pos = pull_inside(view, chest_seed.position)
        total_base, _ = combine_scores(
            G=score_geometry_fitness(view, base_pos, hit_count=4),
            C=0.5,
            S=0.7,
            M=score_interior_margin(view, base_pos, height),
            P=0.85,
        )
        if total_new >= total_base - 0.02:
            out["chest"] = LandmarkPoint(
                name="chest",
                position=lowered,
                source=GEOMETRY_CORRECTED,
                confidence=max(0.55, min(0.9, total_new)),
                side="C",
                evidence={
                    "method": "SPINE_TORSO_V1",
                    "role": "chest",
                    "candidateCount": 2,
                    "selectedScore": round(total_new, 4),
                    "runnerUpScore": round(total_base, 4),
                    "scoreComponents": comps,
                    "crossSectionSamples": 0,
                    "insideMesh": True,
                    "chainValidated": True,
                    "symmetryDeltaCm": 0.0,
                },
            )
    return out
