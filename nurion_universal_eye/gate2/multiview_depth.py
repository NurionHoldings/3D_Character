"""Multiview surface depth sampling for EyePlane Y (Gate 2)."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from mathutils import Vector
from mathutils.bvhtree import BVHTree

from ..gate1.universal_face_basis import HeadAxes


def build_world_bvh(mesh_obj) -> BVHTree:
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(deps)
    me = eval_obj.to_mesh()
    try:
        me.transform(eval_obj.matrix_world)
        me.calc_loop_triangles()
        return BVHTree.FromPolygons(
            [v.co.copy() for v in me.vertices],
            [tuple(tri.vertices) for tri in me.loop_triangles],
        )
    finally:
        eval_obj.to_mesh_clear()


def _ray_hit(
    bvh: BVHTree,
    origin: Vector,
    direction: Vector,
    max_dist: float,
) -> Optional[Tuple[Vector, Vector]]:
    hit = bvh.ray_cast(origin, direction.normalized(), max_dist)
    if not hit or hit[0] is None:
        return None
    loc, normal, _i, _d = hit
    return loc.copy(), (normal.copy() if normal is not None else direction.normalized())


def sample_depth_along_yaw(
    bvh: BVHTree,
    axes: HeadAxes,
    center_local: Vector,
    *,
    yaw_deg: float,
    eye_unit: float,
    ray_start_eu: float,
    max_xz_dev_eu: float = 0.55,
) -> Optional[Dict]:
    """
    Cast toward the eye aperture from a yawed frontal direction.
    Reject hits whose head-local XZ strays too far from the aperture center.
    """
    # Anchor at known local X/Z; provisional Y from center_local if available.
    seed = axes.to_world(Vector((center_local.x, float(center_local.y), center_local.z)))
    yaw = math.radians(yaw_deg)
    view_dir = (-axes.forward * math.cos(yaw) + axes.right * math.sin(yaw)).normalized()
    start = seed + view_dir * (eye_unit * ray_start_eu)
    hit = _ray_hit(bvh, start, -view_dir, eye_unit * ray_start_eu * 2.5)
    if hit is None:
        return None
    loc, normal = hit
    local = axes.to_local(loc)
    xz_err = Vector((float(local.x) - float(center_local.x), 0.0, float(local.z) - float(center_local.z))).length
    if xz_err > eye_unit * max_xz_dev_eu:
        return None
    return {
        "yawDeg": yaw_deg,
        "hitWorld": loc,
        "hitLocal": local,
        "normalWorld": normal,
        "depthLocalY": float(local.y),
        "xzErrorEyeUnits": xz_err / max(eye_unit, 1e-6),
    }


def sample_toward_world(
    bvh: BVHTree,
    axes: HeadAxes,
    target_world: Vector,
    *,
    yaw_deg: float,
    eye_unit: float,
    ray_start_eu: float,
) -> Optional[Dict]:
    """Validation ray aimed at a world target (no XZ reject)."""
    yaw = math.radians(yaw_deg)
    view_dir = (-axes.forward * math.cos(yaw) + axes.right * math.sin(yaw)).normalized()
    start = target_world + view_dir * (eye_unit * ray_start_eu)
    hit = _ray_hit(bvh, start, -view_dir, eye_unit * ray_start_eu * 2.5)
    if hit is None:
        return None
    loc, normal = hit
    return {
        "yawDeg": yaw_deg,
        "hitWorld": loc,
        "normalWorld": normal,
        "hitLocal": axes.to_local(loc),
    }


def fuse_aperture_depth(
    samples: List[Dict],
    *,
    front_w: float,
    w30: float,
    w60: float,
    forward: Vector,
) -> Tuple[Optional[Vector], Optional[Vector], Dict]:
    """Return (hit_world, normal_out, evidence). Prefer front hit; blend Y only among near-aperture samples."""
    if not samples:
        return None, None, {"method": "NO_SAMPLES"}
    weight_map = {0.0: front_w, 30.0: w30, -30.0: w30, 60.0: w60, -60.0: w60}
    front = next((s for s in samples if abs(float(s["yawDeg"])) < 1e-6), None)
    if front is None:
        front = samples[0]

    acc_y = 0.0
    wsum = 0.0
    used = []
    for s in samples:
        yaw = float(s["yawDeg"])
        w = weight_map.get(yaw, 0.15)
        # Down-weight samples with larger XZ deviation
        w *= max(0.15, 1.0 - float(s.get("xzErrorEyeUnits", 0.0)))
        acc_y += float(s["depthLocalY"]) * w
        wsum += w
        used.append(yaw)
    y = acc_y / wsum if wsum > 1e-9 else float(front["depthLocalY"])

    # Position: keep front hit XZ (stable), use fused Y
    fl = front["hitLocal"]
    # Rebuild world from fused local using caller's axes externally — return local components via hit
    hit_world = front["hitWorld"].copy()
    # Normal: front hit normal aligned to face forward
    n = front["normalWorld"].copy()
    if n.dot(forward) < 0:
        n = -n
    # Soft blend toward forward to avoid side-facing lashes
    n = (n * 0.65 + forward.normalized() * 0.35).normalized()
    return hit_world, n, {
        "method": "FRONT_XZ_FUSED_Y_V2",
        "yaws": used,
        "fusedLocalY": round(float(y), 6),
        "frontLocalY": round(float(front["depthLocalY"]), 6),
        "weightSum": round(float(wsum), 4),
    }
