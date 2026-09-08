"""Geometry-based landmark correction via cross-section ray casts (v0.2)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from mathutils import Vector

from .chain_constraints import (
    ConstraintReport,
    apply_symmetry_correction,
    detect_left_right_swaps,
    revert_to_estimated,
    validate_chain_lengths,
)
from .landmark_engine import LandmarkPoint
from .leak_guard import assert_no_gt_parameters, generation_scope
from .sources import ESTIMATED, GEOMETRY_CORRECTED, MEASURED
from .transform_normalize import (
    WorldMeshView,
    nearest_on_mesh,
    point_inside_or_on_mesh,
    pull_inside,
    pull_inside_preserving_side,
)


JOINT_TARGETS = [
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "shoulder.L",
    "elbow.L",
    "wrist.L",
    "shoulder.R",
    "elbow.R",
    "wrist.R",
    "hip.L",
    "knee.L",
    "ankle.L",
    "hip.R",
    "knee.R",
    "ankle.R",
]

MIN_HITS = 2

# Owned by joint-specific correctors (generic star may still pre-seed non-limb joints).
JOINT_SPECIFIC_KEYS = {
    "wrist.L",
    "wrist.R",
    "shoulder.L",
    "shoulder.R",
    "pelvis",
    "hip.L",
    "hip.R",
    "elbow.L",
    "elbow.R",
    "knee.L",
    "knee.R",
    "ankle.L",
    "ankle.R",
}

# Alpha.3 limb owners: skip generic star (joint-specific builds from ESTIMATED seeds).
GENERIC_SKIP_KEYS = {
    "elbow.L",
    "elbow.R",
    "knee.L",
    "knee.R",
    "ankle.L",
    "ankle.R",
}

# Local search radius factors of character height for limb-focused casting.
LOCAL_RADIUS = {
    "pelvis": 0.18,
    "spine": 0.16,
    "chest": 0.16,
    "neck": 0.10,
    "head": 0.12,
    "shoulder.L": 0.12,
    "shoulder.R": 0.12,
    "elbow.L": 0.10,
    "elbow.R": 0.10,
    "wrist.L": 0.08,
    "wrist.R": 0.08,
    "hip.L": 0.12,
    "hip.R": 0.12,
    "knee.L": 0.10,
    "knee.R": 0.10,
    "ankle.L": 0.08,
    "ankle.R": 0.08,
}


@dataclass
class GeometryCorrectionResult:
    landmarks: Dict[str, LandmarkPoint]
    corrected: List[str] = field(default_factory=list)
    kept_estimated: List[str] = field(default_factory=list)
    constraints: ConstraintReport = field(default_factory=ConstraintReport)
    outside_rejected: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _cast_local_star(view: WorldMeshView, seed: Vector, radius: float) -> List[Vector]:
    """Cast rays from seed in XY and XZ/YZ rings; keep nearby surface hits."""
    hits: List[Vector] = []
    angles = [i * (math.pi / 4.0) for i in range(8)]  # 8 directions, deterministic
    planes = (
        lambda a: Vector((math.cos(a), math.sin(a), 0.0)),
        lambda a: Vector((math.cos(a), 0.0, math.sin(a))),
        lambda a: Vector((0.0, math.cos(a), math.sin(a))),
    )
    for plane in planes:
        for angle in angles:
            direction = plane(angle)
            if direction.length < 1e-8:
                continue
            direction.normalize()
            # Start slightly outside local radius and cast inward toward seed,
            # then also cast outward from seed — keeps limb-local hits.
            start = seed + direction * radius
            inward = view.bvh.ray_cast(start, -direction)
            if inward[0] is not None and inward[3] is not None and inward[3] <= radius * 1.25:
                hits.append(inward[0].copy())
            outward = view.bvh.ray_cast(seed, direction)
            if outward[0] is not None and outward[3] is not None and outward[3] <= radius:
                hits.append(outward[0].copy())
    return hits


def _cross_section_center(
    view: WorldMeshView,
    seed: Vector,
    joint_name: str,
) -> tuple[Optional[Vector], dict]:
    height = float(max(view.dimensions.z, 1e-3))
    radius = height * LOCAL_RADIUS.get(joint_name, 0.12)
    all_hits = _cast_local_star(view, seed, radius)
    # Also classic axis casts at seed Z for torso stability.
    span = max(float(view.dimensions.x), float(view.dimensions.y)) * 1.2 + 0.2
    axes_used: Set[str] = set()
    for axis, direction, start_off in (
        ("X", Vector((-1, 0, 0)), Vector((span, 0, 0))),
        ("X", Vector((1, 0, 0)), Vector((-span, 0, 0))),
        ("Y", Vector((0, -1, 0)), Vector((0, span, 0))),
        ("Y", Vector((0, 1, 0)), Vector((0, -span, 0))),
    ):
        origin = Vector((seed.x, seed.y, seed.z))
        result = view.bvh.ray_cast(origin + start_off, direction)
        if result[0] is None or result[3] is None:
            continue
        if result[3] > span * 2:
            continue
        # Keep only hits near the seed (avoid opposite-side body hits dominating limbs).
        if (result[0] - seed).length <= radius * 2.5:
            all_hits.append(result[0].copy())
            axes_used.add(axis)

    evidence = {
        "crossSectionHits": len(all_hits),
        "raycastAxes": sorted(axes_used) if axes_used else ["STAR"],
        "insideMesh": False,
        "symmetryApplied": False,
    }
    if len(all_hits) < MIN_HITS:
        return None, evidence

    center = Vector((0.0, 0.0, 0.0))
    for hit in all_hits:
        center += hit
    center /= float(len(all_hits))
    # Blend with seed to avoid jumping to torso for distal joints.
    blend = 0.55 if joint_name.startswith(("wrist", "ankle", "elbow", "knee")) else 0.25
    center = center.lerp(seed, blend)
    center = pull_inside(view, center, inset=max(0.005, height * 0.003))
    evidence["insideMesh"] = point_inside_or_on_mesh(view, center)
    evidence["crossSectionHits"] = len(all_hits)
    return center, evidence


def _interior_clearance(view: WorldMeshView, point: Vector) -> float:
    """Positive clearance if inside/on mesh; negative if outside."""
    if not point_inside_or_on_mesh(view, point):
        return -1.0
    _loc, _n, dist = nearest_on_mesh(view, point)
    return float(dist)


def _confidence_from_evidence(evidence: dict) -> float:
    hits = int(evidence.get("crossSectionHits", 0))
    axes = evidence.get("raycastAxes") or []
    base = 0.55 + min(hits, 16) * 0.015 + 0.05 * min(len(axes), 3)
    if evidence.get("insideMesh"):
        base += 0.05
    return max(0.5, min(0.92, base))


def _enforce_laterality(
    landmarks: Dict[str, LandmarkPoint],
    center_x: float,
    height: float = 1.0,
    view: Optional[WorldMeshView] = None,
) -> List[str]:
    """Force L joints to +X side and R joints to -X side of symmetry plane."""
    fixed: List[str] = []
    for name, point in landmarks.items():
        if not name.endswith((".L", ".R")):
            continue
        if point.source != GEOMETRY_CORRECTED:
            continue
        if name.startswith(("wrist.", "hip.", "knee.", "ankle.")):
            margin = max(0.015, height * 0.025)
        else:
            margin = 0.01
        old = point.position.copy()
        if name.endswith(".L") and point.position.x < center_x + margin:
            point.position.x = center_x + margin
            fixed.append(name)
        elif name.endswith(".R") and point.position.x > center_x - margin:
            point.position.x = center_x - margin
            fixed.append(name)
        # Never push a joint outside the mesh for laterality.
        if view is not None and name in fixed:
            side = "L" if name.endswith(".L") else "R"
            point.position = pull_inside_preserving_side(view, point.position, side=side, center_x=center_x)
            if not point_inside_or_on_mesh(view, point.position):
                point.position = old
                fixed.remove(name)
    return fixed


def correct_landmarks_geometry(
    mesh_obj,
    estimated: Dict[str, LandmarkPoint],
    *,
    view: Optional[WorldMeshView] = None,
    apply_symmetry: bool = True,
    **kwargs,
) -> GeometryCorrectionResult:
    """Geometry correction entry point. Must not receive armature / bone GT."""
    assert_no_gt_parameters(mesh_obj=mesh_obj, estimated=estimated, view=view, **kwargs)

    from .transform_normalize import build_world_mesh_view

    with generation_scope("correct_landmarks_geometry"):
        mesh_view = view or build_world_mesh_view(mesh_obj)
        height = float(mesh_view.dimensions.z)
        center_x = float(mesh_view.center.x)

        result_map: Dict[str, LandmarkPoint] = {}
        corrected: List[str] = []
        kept: List[str] = []
        outside: List[str] = []

        for name, point in estimated.items():
            if name.startswith("bounds.") or point.source == MEASURED:
                result_map[name] = LandmarkPoint(
                    name=point.name,
                    position=point.position.copy(),
                    source=point.source,
                    confidence=point.confidence,
                    side=point.side,
                    evidence=dict(point.evidence or {}),
                )

        for name in JOINT_TARGETS:
            seed_point = estimated.get(name)
            if seed_point is None:
                continue
            if name in GENERIC_SKIP_KEYS:
                # Limb joints owned by alpha.3 correctors — keep ESTIMATED seed.
                side = "L" if name.endswith(".L") else "R"
                result_map[name] = LandmarkPoint(
                    name=name,
                    position=pull_inside_preserving_side(
                        mesh_view, seed_point.position, side=side, center_x=center_x
                    ),
                    source=ESTIMATED,
                    confidence=seed_point.confidence,
                    side=seed_point.side,
                    evidence={"deferred": True, "reason": "joint_specific_owner"},
                )
                kept.append(name)
                continue
            candidate, evidence = _cross_section_center(mesh_view, seed_point.position, name)
            if candidate is None:
                # Keep estimated but pull inside if needed so outside count stays clean.
                pos = pull_inside(mesh_view, seed_point.position)
                result_map[name] = LandmarkPoint(
                    name=name,
                    position=pos,
                    source=ESTIMATED,
                    confidence=seed_point.confidence,
                    side=seed_point.side,
                    evidence={"reverted": True, "reason": "insufficient_ray_hits", **evidence},
                )
                kept.append(name)
                continue

            if not evidence.get("insideMesh", False):
                pulled = pull_inside(mesh_view, candidate)
                if point_inside_or_on_mesh(mesh_view, pulled):
                    candidate = pulled
                    evidence["insideMesh"] = True
                    evidence["pulledInside"] = True
                else:
                    pos = pull_inside(mesh_view, seed_point.position)
                    result_map[name] = LandmarkPoint(
                        name=name,
                        position=pos,
                        source=ESTIMATED,
                        confidence=seed_point.confidence,
                        side=seed_point.side,
                        evidence={"reverted": True, "reason": "outside_mesh", **evidence},
                    )
                    outside.append(name)
                    kept.append(name)
                    continue

            # Accept geometry only when it is a clearer interior center than the seed.
            hits = int(evidence.get("crossSectionHits", 0))
            displacement = (candidate - seed_point.position).length
            max_disp = height * LOCAL_RADIUS.get(name, 0.12) * 0.85
            seed_pos = pull_inside(mesh_view, seed_point.position)
            seed_clear = _interior_clearance(mesh_view, seed_pos)
            cand_clear = _interior_clearance(mesh_view, candidate)
            evidence["displacement"] = round(float(displacement), 6)
            evidence["seedClearance"] = round(seed_clear, 6)
            evidence["candidateClearance"] = round(cand_clear, 6)

            accept = (
                hits >= 4
                and bool(evidence.get("insideMesh", False))
                and displacement <= max_disp
                and cand_clear >= seed_clear + (height * 0.002)
            )
            if not accept:
                result_map[name] = LandmarkPoint(
                    name=name,
                    position=seed_pos,
                    source=ESTIMATED,
                    confidence=seed_point.confidence,
                    side=seed_point.side,
                    evidence={"reverted": True, "reason": "no_clearance_gain", **evidence},
                )
                kept.append(name)
                continue

            result_map[name] = LandmarkPoint(
                name=name,
                position=candidate,
                source=GEOMETRY_CORRECTED,
                confidence=_confidence_from_evidence(evidence),
                side=seed_point.side,
                evidence=evidence,
            )
            corrected.append(name)

        # --- Alpha.2/3 joint-specific correctors (no GT) ---
        from .evidence_confidence import compute_evidence_confidence
        from .joint_specific import (
            correct_ankles,
            correct_elbows,
            correct_knees,
            correct_pelvis_hips,
            correct_shoulders,
            correct_spine,
            correct_wrists,
        )

        result_map = correct_pelvis_hips(mesh_view, result_map, height, center_x)
        result_map = correct_spine(mesh_view, result_map, height, center_x)
        result_map = correct_shoulders(mesh_view, result_map, height, center_x)
        # Wrists before elbows preserves alpha.2 wrist quality (elbows use wrist endpoint).
        result_map = correct_wrists(mesh_view, result_map, height, center_x)
        result_map = correct_elbows(mesh_view, result_map, height, center_x)
        result_map = correct_knees(mesh_view, result_map, height, center_x)
        result_map = correct_ankles(mesh_view, result_map, height, center_x)

        owned = set(JOINT_SPECIFIC_KEYS) | {"spine", "chest"}
        for key in owned:
            point = result_map.get(key)
            if point is None:
                continue
            if point.source == GEOMETRY_CORRECTED:
                if key in kept:
                    kept.remove(key)
                if key not in corrected:
                    corrected.append(key)
            else:
                if key not in kept:
                    kept.append(key)
                if key in corrected:
                    corrected.remove(key)

        report = ConstraintReport(rejected_outside=list(outside))
        _enforce_laterality(result_map, center_x, height, mesh_view)

        swaps = detect_left_right_swaps(result_map, center_x)
        if swaps:
            for swap in swaps:
                left, right = swap.split("/")
                revert_to_estimated(result_map, estimated, [left, right])
                # Pull reverted seeds inside and enforce laterality on estimated copies.
                for key in (left, right):
                    if key in result_map:
                        side = "L" if key.endswith(".L") else "R"
                        result_map[key].position = pull_inside_preserving_side(
                            mesh_view, result_map[key].position, side=side, center_x=center_x
                        )
                    if key in corrected:
                        corrected.remove(key)
                        kept.append(key)
                report.forced_review.extend([left, right])
            _enforce_laterality(result_map, center_x, height, mesh_view)

        chain_bad = validate_chain_lengths(result_map, height)
        report.rejected_chain = chain_bad
        if chain_bad:
            revert_names: List[str] = []
            for item in chain_bad:
                revert_names.extend(item.split("->"))
            revert_to_estimated(result_map, estimated, sorted(set(revert_names)))
            for key in sorted(set(revert_names)):
                if key in result_map:
                    side = "L" if key.endswith(".L") else ("R" if key.endswith(".R") else "C")
                    if side in ("L", "R"):
                        result_map[key].position = pull_inside_preserving_side(
                            mesh_view, result_map[key].position, side=side, center_x=center_x
                        )
                    else:
                        result_map[key].position = pull_inside(mesh_view, result_map[key].position)
                if key in corrected:
                    corrected.remove(key)
                    kept.append(key)

        if apply_symmetry:
            report.symmetry_applied = apply_symmetry_correction(result_map, center_x)
            _enforce_laterality(result_map, center_x, height, mesh_view)

        # Final safety: every joint must be inside/on mesh; else reject geometry claim.
        final_outside = []
        for name in JOINT_TARGETS:
            point = result_map.get(name)
            if point is None:
                continue
            side = "L" if name.endswith(".L") else ("R" if name.endswith(".R") else "C")
            if not point_inside_or_on_mesh(mesh_view, point.position):
                if side in ("L", "R"):
                    point.position = pull_inside_preserving_side(
                        mesh_view, point.position, side=side, center_x=center_x
                    )
                else:
                    point.position = pull_inside(mesh_view, point.position)
            if not point_inside_or_on_mesh(mesh_view, point.position):
                final_outside.append(name)
                if point.source == GEOMETRY_CORRECTED:
                    revert_to_estimated(result_map, estimated, [name])
                    if side in ("L", "R"):
                        result_map[name].position = pull_inside_preserving_side(
                            mesh_view, result_map[name].position, side=side, center_x=center_x
                        )
                    else:
                        result_map[name].position = pull_inside(mesh_view, result_map[name].position)
                    if name in corrected:
                        corrected.remove(name)
                        kept.append(name)
            if point.evidence is not None:
                point.evidence["insideMesh"] = point_inside_or_on_mesh(mesh_view, point.position)
        _enforce_laterality(result_map, center_x, height, mesh_view)
        # Re-validate outside after laterality (laterality must not create new outsides).
        for name in JOINT_TARGETS:
            point = result_map.get(name)
            if point is None:
                continue
            if not point_inside_or_on_mesh(mesh_view, point.position):
                side = "L" if name.endswith(".L") else ("R" if name.endswith(".R") else "C")
                if side in ("L", "R"):
                    point.position = pull_inside_preserving_side(
                        mesh_view, point.position, side=side, center_x=center_x
                    )
                else:
                    point.position = pull_inside(mesh_view, point.position)
                if not point_inside_or_on_mesh(mesh_view, point.position):
                    final_outside.append(name)
            if point.evidence is not None:
                point.evidence["insideMesh"] = point_inside_or_on_mesh(mesh_view, point.position)

        report.rejected_outside = sorted(set(outside + final_outside))
        # Recompute swaps after all fixes — this is the reported validation value.
        report.left_right_swaps = detect_left_right_swaps(result_map, center_x)

        # Alpha.3: recompute confidence from evidence products (no fixed arbitrary values).
        for name, point in result_map.items():
            if name.startswith("bounds.") or point.source == MEASURED:
                continue
            if point.evidence:
                conf = compute_evidence_confidence(
                    point.evidence,
                    score_components=(point.evidence or {}).get("scoreComponents"),
                    symmetry_dependent=bool((point.evidence or {}).get("symmetryApplied")),
                )
                point.confidence = conf
                point.review_required = True  # alpha policy: geometry/estimated stay reviewable
                if point.evidence is not None:
                    point.evidence["confidenceFormula"] = "EVIDENCE_PRODUCT_V1"
                    point.evidence["confidence"] = round(conf, 4)

        return GeometryCorrectionResult(
            landmarks=result_map,
            corrected=sorted(set(corrected)),
            kept_estimated=sorted(set(kept)),
            constraints=report,
            outside_rejected=report.rejected_outside,
            notes=[
                "Geometry correction uses world-space BVH local star + axis casts.",
                "Alpha.3 joint-specific: ELBOW_BEND_V1, KNEE_AXIS_V1, ANKLE_TRANSITION_V2 + evidence confidence.",
                "Ground-truth bones are never consulted in this path.",
            ],
        )
