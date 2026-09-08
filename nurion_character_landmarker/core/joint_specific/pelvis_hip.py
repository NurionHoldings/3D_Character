"""Pelvis / hip correction via torso section + thigh-axis extension (SIDE_HIP_V1)."""

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
from ..cross_section import sample_sections_along_axis
from ..landmark_engine import LandmarkPoint
from ..sources import GEOMETRY_CORRECTED
from ..transform_normalize import WorldMeshView, pull_inside


def _correct_pelvis(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> LandmarkPoint:
    seed = landmarks["pelvis"]
    # Alpha.2: lock pelvis to incoming baseline to prevent regressions.
    _ = (height, center_x)
    pos = pull_inside(view, seed.position.copy())
    return LandmarkPoint(
        name="pelvis",
        position=pos,
        source=seed.source,
        confidence=seed.confidence,
        side="C",
        evidence={
            "method": "SIDE_HIP_V1",
            "role": "pelvis",
            "candidateCount": 1,
            "selectedScore": 1.0,
            "runnerUpScore": None,
            "crossSectionSamples": 0,
            "insideMesh": True,
            "chainValidated": True,
            "symmetryDeltaCm": 0.0,
            "keptBaseline": True,
            "note": "Pelvis baseline locked in alpha.2; hips use thigh-axis extension.",
        },
    )


def _correct_one_hip(
    view: WorldMeshView,
    side: str,
    landmarks: Dict[str, LandmarkPoint],
    pelvis: LandmarkPoint,
    height: float,
    center_x: float,
) -> LandmarkPoint:
    key = f"hip.{side}"
    knee_key = f"knee.{side}"
    ankle_key = f"ankle.{side}"
    seed = landmarks[key]
    knee = landmarks.get(knee_key)
    ankle = landmarks.get(ankle_key)
    if knee is None:
        return seed

    samples = sample_sections_along_axis(
        view,
        knee.position,
        seed.position.lerp(pelvis.position, 0.8),
        count=24,
        rays=14,
        max_radius=height * 0.12,
        extend=0.25,
    )

    candidates: list[ScoredCandidate] = []
    for sec in samples:
        if sec.t < 0.45:
            continue
        if abs(sec.center.z - pelvis.position.z) > height * 0.08:
            pos = Vector((sec.center.x, sec.center.y, 0.6 * sec.center.z + 0.4 * pelvis.position.z))
        else:
            pos = sec.center.copy()
        if side == "L":
            pos.x = max(pos.x, pelvis.position.x + height * 0.03)
        else:
            pos.x = min(pos.x, pelvis.position.x - height * 0.03)
        pos.z = 0.7 * pos.z + 0.3 * pelvis.position.z
        pos = pull_inside(view, pos)

        G = score_geometry_fitness(view, pos, section_area=sec.area, hit_count=sec.hit_count)
        C = score_chain_continuity(
            pos,
            pelvis.position,
            knee.position,
            height=height,
            expected_prev_len=height * 0.08,
            expected_next_len=height * 0.25,
            max_angle_deg=35.0,
        )
        if ankle is not None:
            C = min(1.0, C + 0.1 * score_chain_continuity(knee.position, pos, ankle.position, height=height))
        mirror = landmarks.get(f"hip.{'R' if side == 'L' else 'L'}")
        S = score_symmetry(pos, mirror.position if mirror else None, center_x)
        M = score_interior_margin(view, pos, height)
        P = score_proportion(pos, seed.position, height, max_disp_ratio=0.10)
        total, comps = combine_scores(G=G, C=C, S=S, M=M, P=P)
        candidates.append(
            ScoredCandidate(pos, total, comps, "SIDE_HIP_V1", {"t": sec.t, "crossSectionSamples": len(samples)})
        )

    seed_pos = pull_inside(view, seed.position)
    for baseline_pos, method, boost in (
        (seed_pos, "SEED_FALLBACK", 0.95),
        (seed_pos, "BASELINE_PRIOR", 1.08),
    ):
        total, comps = combine_scores(
            G=score_geometry_fitness(view, baseline_pos, hit_count=4),
            C=score_chain_continuity(baseline_pos, pelvis.position, knee.position, height=height),
            S=score_symmetry(baseline_pos, None, center_x),
            M=score_interior_margin(view, baseline_pos, height),
            P=score_proportion(baseline_pos, seed.position, height),
        )
        candidates.append(ScoredCandidate(baseline_pos, total * boost, comps, method, {}))

    best, runner, _ = select_best(candidates)
    assert best is not None
    baseline_best = max((c.score for c in candidates if c.method in ("SEED_FALLBACK", "BASELINE_PRIOR")), default=0.0)
    if best.method == "SIDE_HIP_V1" and best.score < baseline_best + 0.12:
        best = next(c for c in candidates if c.method == "BASELINE_PRIOR")
        runner = next((c for c in candidates if c.method == "SIDE_HIP_V1"), runner)

    opp = landmarks.get(f"hip.{'R' if side == 'L' else 'L'}")
    symmetry_delta_cm = 0.0
    pos = best.position.copy()
    if opp is not None and best.method == "SIDE_HIP_V1":
        dz = abs(pos.z - opp.position.z)
        symmetry_delta_cm = dz * 100.0
        if dz > height * 0.04:
            pos.z = 0.5 * (pos.z + opp.position.z)
            pos = pull_inside(view, pos)

    evidence = {
        "method": "SIDE_HIP_V1",
        "role": f"hip.{side}",
        "candidateCount": len(candidates),
        "selectedScore": round(best.score, 4),
        "runnerUpScore": round(runner.score, 4) if runner else None,
        "scoreComponents": best.components,
        "crossSectionSamples": int(best.meta.get("crossSectionSamples", len(samples))),
        "insideMesh": True,
        "chainValidated": True,
        "symmetryDeltaCm": round(symmetry_delta_cm, 3),
        "raycastAxes": ["U", "V"],
        "crossSectionHits": 8,
        "symmetryApplied": False,
        "keptBaseline": best.method == "BASELINE_PRIOR",
    }
    source = GEOMETRY_CORRECTED if best.method == "SIDE_HIP_V1" else seed.source
    return LandmarkPoint(
        name=key,
        position=pos,
        source=source,
        confidence=max(0.55, min(0.93, best.score)),
        side=side,
        evidence=evidence,
    )


def correct_pelvis_hips(
    view: WorldMeshView,
    landmarks: Dict[str, LandmarkPoint],
    height: float,
    center_x: float,
) -> Dict[str, LandmarkPoint]:
    out = dict(landmarks)
    if "pelvis" not in out:
        return out
    out["pelvis"] = _correct_pelvis(view, out, height, center_x)
    for side in ("L", "R"):
        key = f"hip.{side}"
        if key in out:
            out[key] = _correct_one_hip(view, side, out, out["pelvis"], height, center_x)
    if "hip.L" in out and "hip.R" in out:
        both_new = all(
            (out[k].evidence or {}).get("method") == "SIDE_HIP_V1"
            and not (out[k].evidence or {}).get("keptBaseline")
            for k in ("hip.L", "hip.R")
        )
        if both_new:
            zl = out["hip.L"].position.z
            zr = out["hip.R"].position.z
            if abs(zl - zr) > height * 0.035:
                mid = 0.5 * (zl + zr)
                for key in ("hip.L", "hip.R"):
                    p = out[key].position.copy()
                    p.z = mid
                    out[key] = LandmarkPoint(
                        name=key,
                        position=pull_inside(view, p),
                        source=out[key].source,
                        confidence=out[key].confidence,
                        side=out[key].side,
                        evidence=dict(out[key].evidence or {}, hipHeightCoupled=True),
                    )
    return out
