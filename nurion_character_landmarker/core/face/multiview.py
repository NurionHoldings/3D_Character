"""Orthographic multi-view face candidates in head-local space."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters, generation_scope
from ..sources import ESTIMATED
from ..transform_normalize import WorldMeshView
from .parameters import FACE_ALPHA1_PARAMETERS
from .spaces import HeadFrame

VIEW_DIRS = {
    "FRONT": Vector((0.0, 1.0, 0.0)),
    "LEFT": Vector((1.0, 0.0, 0.0)),
    "RIGHT": Vector((-1.0, 0.0, 0.0)),
    "TOP": Vector((0.0, 0.0, 1.0)),
    "FRONT_LEFT_45": Vector((0.7071, 0.7071, 0.0)).normalized(),
    "FRONT_RIGHT_45": Vector((-0.7071, 0.7071, 0.0)).normalized(),
}


@dataclass
class MultiviewHit:
    view: str
    name: str
    world: Vector
    depth: float


def _ray_hits(
    view: WorldMeshView,
    origin: Vector,
    direction: Vector,
    max_dist: float,
) -> Optional[Vector]:
    # Cast from outside toward head.
    start = origin - direction.normalized() * max_dist
    hit = view.bvh.ray_cast(start, direction.normalized(), max_dist * 2.0)
    if not hit or hit[0] is None:
        return None
    return hit[0].copy()


def collect_multiview_candidates(
    mesh_view: WorldMeshView,
    frame: HeadFrame,
    seeds: Dict[str, LandmarkPoint],
    **kwargs,
) -> Dict[str, List[MultiviewHit]]:
    """For each seed landmark, gather ortho depth hits from configured views."""
    assert_no_gt_parameters(**kwargs)
    views = FACE_ALPHA1_PARAMETERS["multiview"]["views"]
    max_dist = frame.head_height * 3.0
    out: Dict[str, List[MultiviewHit]] = {k: [] for k in seeds}

    with generation_scope("face_multiview"):
        for view_name in views:
            local_dir = VIEW_DIRS.get(view_name)
            if local_dir is None:
                continue
            world_dir = (
                frame.right * local_dir.x + frame.forward * local_dir.y + frame.up * local_dir.z
            ).normalized()
            for name, lp in seeds.items():
                # Offset origin slightly outside along view direction from seed.
                origin = lp.position + world_dir * (frame.head_height * 0.15)
                hit = _ray_hits(mesh_view, origin, -world_dir, max_dist)
                if hit is None:
                    continue
                depth = (hit - origin).length
                out[name].append(MultiviewHit(view=view_name, name=name, world=hit, depth=depth))
    return out


def fuse_multiview_with_geometry(
    geometry: Dict[str, LandmarkPoint],
    hits: Dict[str, List[MultiviewHit]],
    frame: HeadFrame,
) -> Dict[str, LandmarkPoint]:
    """Average geometry seed with multiview surface hits (still ESTIMATED until final correct)."""
    fused: Dict[str, LandmarkPoint] = {}
    for name, lp in geometry.items():
        mv = hits.get(name) or []
        if not mv:
            fused[name] = lp
            continue
        # Prefer hits close to geometry seed.
        close = [h for h in mv if (h.world - lp.position).length < frame.head_height * 0.08]
        use = close or mv
        avg = sum((h.world for h in use), Vector((0, 0, 0))) / len(use)
        blended = lp.position.lerp(avg, 0.45)
        evidence = dict(lp.evidence or {})
        evidence["views"] = [h.view for h in use]
        evidence["multiviewCandidateCount"] = len(use)
        evidence["method"] = FACE_ALPHA1_PARAMETERS["methods"]["multiview"]
        fused[name] = LandmarkPoint(
            name=name,
            position=blended,
            source=ESTIMATED,
            confidence=min(0.85, lp.confidence + 0.05),
            side=lp.side,
            evidence=evidence,
        )
    return fused


def create_ortho_view_empties(frame: HeadFrame, collection_name: str = "NURION_Face_Views") -> int:
    """Create empty markers for the six orthographic face views (debug / UI)."""
    import bpy

    col = bpy.data.collections.get(collection_name)
    if col is None:
        col = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(col)
    created = 0
    dist = frame.head_height * 1.8
    for name, local_dir in VIEW_DIRS.items():
        world_dir = (
            frame.right * local_dir.x + frame.forward * local_dir.y + frame.up * local_dir.z
        ).normalized()
        loc = frame.origin + world_dir * dist
        obj_name = f"NURION_FACE_VIEW_{name}"
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            obj = bpy.data.objects.new(obj_name, None)
            obj.empty_display_type = "SINGLE_ARROW"
            obj.empty_display_size = frame.head_height * 0.2
            col.objects.link(obj)
            created += 1
        obj.location = loc
        # Point arrow toward head origin.
        direction = (frame.origin - loc).normalized()
        obj.rotation_mode = "QUATERNION"
        obj.rotation_quaternion = direction.to_track_quat("-Z", "Y")
    return created
