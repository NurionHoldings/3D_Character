"""Evaluate mesh geometry in world space without mutating object transforms."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional, Tuple

from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

if TYPE_CHECKING:
    import bpy


@dataclass
class WorldMeshView:
    """Immutable evaluation view of a mesh in world space."""

    object_name: str
    matrix_world: Matrix
    bounds_min: Vector
    bounds_max: Vector
    center: Vector
    bvh: BVHTree
    vertex_count: int
    polygon_count: int

    @property
    def dimensions(self) -> Vector:
        return self.bounds_max - self.bounds_min


def build_world_mesh_view(obj: "bpy.types.Object") -> WorldMeshView:
    """
    Build BVH in world space from the evaluated mesh.

    Original object location/rotation/scale are left unchanged.
    """
    import bpy

    if obj.type != "MESH":
        raise ValueError("WorldMeshView requires a mesh object")

    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        mesh.transform(eval_obj.matrix_world)
        mesh.calc_loop_triangles()
        bvh = BVHTree.FromPolygons(
            [v.co.copy() for v in mesh.vertices],
            [tuple(tri.vertices) for tri in mesh.loop_triangles],
        )
        xs = [v.co.x for v in mesh.vertices]
        ys = [v.co.y for v in mesh.vertices]
        zs = [v.co.z for v in mesh.vertices]
        mins = Vector((min(xs), min(ys), min(zs)))
        maxs = Vector((max(xs), max(ys), max(zs)))
        center = (mins + maxs) * 0.5
        return WorldMeshView(
            object_name=obj.name,
            matrix_world=eval_obj.matrix_world.copy(),
            bounds_min=mins,
            bounds_max=maxs,
            center=center,
            bvh=bvh,
            vertex_count=len(mesh.vertices),
            polygon_count=len(mesh.loop_triangles),
        )
    finally:
        eval_obj.to_mesh_clear()


def nearest_on_mesh(view: WorldMeshView, point: Vector) -> Tuple[Optional[Vector], Optional[Vector], float]:
    loc, normal, _index, dist = view.bvh.find_nearest(point)
    if loc is None:
        return None, None, float("inf")
    return loc.copy(), normal.copy() if normal is not None else None, float(dist)


def point_inside_or_on_mesh(view: WorldMeshView, point: Vector, surface_tol: float | None = None) -> bool:
    """
    Inside test that is robust for thin limbs:
    - odd crossings along axes, OR
    - distance to surface within tolerance (treat as on-surface / acceptable).
    """
    tol = surface_tol if surface_tol is not None else max(view.dimensions.length * 0.01, 0.01)
    _loc, _n, dist = nearest_on_mesh(view, point)
    if dist <= tol:
        return True

    directions = (
        Vector((1.0, 0.0, 0.0)),
        Vector((0.0, 1.0, 0.0)),
        Vector((0.0, 0.0, 1.0)),
    )
    inside_votes = 0
    for direction in directions:
        origin = point.copy()
        hits = 0
        for _ in range(64):
            result = view.bvh.ray_cast(origin, direction)
            if result[0] is None:
                break
            hit_loc, _normal, _index, dist = result
            hits += 1
            origin = hit_loc + direction * 1e-4
        if hits % 2 == 1:
            inside_votes += 1
    return inside_votes >= 2


# Backward-compatible alias used by older callers.
def point_inside_mesh(view: WorldMeshView, point: Vector, samples: int = 3) -> bool:
    _ = samples
    return point_inside_or_on_mesh(view, point)


def pull_inside(view: WorldMeshView, point: Vector, inset: float = 0.01) -> Vector:
    """If outside, project to nearest surface then step inward along normal."""
    loc, normal, dist = nearest_on_mesh(view, point)
    if loc is None:
        return point.copy()
    if point_inside_or_on_mesh(view, point):
        return point.copy()
    if normal is None:
        # Fallback: pull toward mesh center.
        direction = (view.center - point).normalized()
        return loc + direction * inset
    # Normal points outward; step opposite for interior.
    return loc - normal.normalized() * inset


def pull_inside_preserving_side(
    view: WorldMeshView,
    point: Vector,
    *,
    side: str,
    center_x: float,
    inset: float = 0.01,
) -> Vector:
    """pull_inside that refuses to cross the sagittal plane to the opposite limb."""
    target_x = point.x
    pos = pull_inside(view, point, inset=inset)
    crossed = (side == "L" and pos.x < center_x) or (side == "R" and pos.x > center_x)
    if not crossed and point_inside_or_on_mesh(view, pos):
        return pos

    # Prefer an outer-surface hit on the correct side (thin opposite limbs confuse nearest()).
    surface = side_surface_point(view, point, side=side, center_x=center_x, inset=inset)
    if surface is not None:
        return surface

    sign = 1.0 if side == "L" else -1.0
    seed = Vector((max(abs(target_x - center_x), abs(point.x - center_x)) * sign + center_x, point.y, point.z))
    best = seed.copy()
    for step in (0.0, 0.02, 0.04, 0.06, 0.08, 0.10):
        cand = Vector((seed.x, seed.y, seed.z))
        cand = cand.lerp(Vector((seed.x, view.center.y, seed.z)), step)
        pulled = pull_inside(view, cand, inset=inset)
        if side == "L" and pulled.x < center_x + 1e-4:
            continue
        if side == "R" and pulled.x > center_x - 1e-4:
            continue
        if point_inside_or_on_mesh(view, pulled):
            best = pulled
            break
    if side == "L":
        best.x = max(best.x, center_x + 1e-3, min(target_x, best.x) if target_x > center_x else best.x)
    else:
        best.x = min(best.x, center_x - 1e-3, max(target_x, best.x) if target_x < center_x else best.x)
    return best


def side_surface_point(
    view: WorldMeshView,
    point: Vector,
    *,
    side: str,
    center_x: float,
    inset: float = 0.01,
) -> Optional[Vector]:
    """Ray-cast from outside the correct half toward center; return an interior point on that limb."""
    sign = 1.0 if side == "L" else -1.0
    span = max(float(view.dimensions.x) * 0.6, 0.2)
    # Try a few Y/Z offsets around the request to catch thin feet / shoes.
    z0 = float(point.z)
    floor_z = float(view.bounds_min.z)
    z_candidates = (
        z0,
        z0 + 0.02,
        z0 - 0.02,
        floor_z + 0.05,
        floor_z + 0.08,
        floor_z + 0.11,
    )
    y_offsets = (0.0, 0.02, -0.02, 0.04, -0.04)
    best = None
    best_lat = -1.0
    for z in z_candidates:
        for dy in y_offsets:
            start = Vector((center_x + sign * span, point.y + dy, z))
            direction = Vector((-sign, 0.0, 0.0))
            hit = view.bvh.ray_cast(start, direction)
            if hit[0] is None:
                continue
            loc, normal, _idx, dist = hit
            if dist is None or dist > span * 1.2:
                continue
            if side == "L" and loc.x < center_x + 1e-4:
                continue
            if side == "R" and loc.x > center_x - 1e-4:
                continue
            # Prefer hits near the requested height band (ankle, not thigh).
            if abs(loc.z - z0) > max(0.18, abs(view.dimensions.z) * 0.12):
                continue
            interior = loc.copy()
            if normal is not None and normal.length > 1e-8:
                interior = loc - normal.normalized() * inset
            else:
                interior = loc + Vector((-sign * inset, 0.0, 0.0))
            lat = abs(interior.x - center_x)
            if lat > best_lat:
                best_lat = lat
                best = interior
    return best
