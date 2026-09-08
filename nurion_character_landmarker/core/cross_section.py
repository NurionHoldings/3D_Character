"""Deterministic cross-section sampling helpers for joint-specific geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from mathutils import Vector

from .transform_normalize import WorldMeshView, point_inside_or_on_mesh


@dataclass
class SectionSample:
    t: float
    origin: Vector
    width: float
    height: float
    area: float
    perimeter: float
    center: Vector
    hit_count: int


def _orthonormal_basis(axis: Vector) -> Tuple[Vector, Vector, Vector]:
    a = axis.normalized()
    # Deterministic helper axis.
    helper = Vector((0.0, 0.0, 1.0)) if abs(a.z) < 0.9 else Vector((1.0, 0.0, 0.0))
    u = a.cross(helper)
    if u.length < 1e-8:
        helper = Vector((0.0, 1.0, 0.0))
        u = a.cross(helper)
    u.normalize()
    v = a.cross(u)
    v.normalize()
    return a, u, v


def measure_section(
    view: WorldMeshView,
    origin: Vector,
    axis: Vector,
    rays: int = 16,
    max_radius: float = 0.35,
) -> Optional[SectionSample]:
    """Radial ray cast in plane ⊥ axis; estimate width/area/center."""
    if axis.length < 1e-8:
        return None
    _a, u, v = _orthonormal_basis(axis)
    hits: List[Vector] = []
    for i in range(rays):
        ang = (2.0 * math.pi * i) / float(rays)
        direction = (u * math.cos(ang) + v * math.sin(ang)).normalized()
        # Cast from outside toward origin, then from origin outward.
        start = origin + direction * max_radius
        inward = view.bvh.ray_cast(start, -direction)
        if inward[0] is not None and inward[3] is not None and inward[3] <= max_radius * 1.2:
            hits.append(inward[0].copy())
            continue
        outward = view.bvh.ray_cast(origin, direction)
        if outward[0] is not None and outward[3] is not None and outward[3] <= max_radius:
            hits.append(outward[0].copy())

    if len(hits) < 4:
        return None

    center = Vector((0.0, 0.0, 0.0))
    for h in hits:
        center += h
    center /= float(len(hits))

    # Project hits onto u/v for width/height.
    us = [(h - center).dot(u) for h in hits]
    vs = [(h - center).dot(v) for h in hits]
    width = max(us) - min(us) if us else 0.0
    height = max(vs) - min(vs) if vs else 0.0
    # Polygon-ish perimeter/area approximation from ordered angles.
    ordered = sorted(
        hits,
        key=lambda h: math.atan2((h - center).dot(v), (h - center).dot(u)),
    )
    area = 0.0
    peri = 0.0
    for i, h in enumerate(ordered):
        n = ordered[(i + 1) % len(ordered)]
        area += h.x * n.y - n.x * h.y
        peri += (n - h).length
    area = abs(area) * 0.5
    if not point_inside_or_on_mesh(view, center):
        # Keep center but mark weak via hit_count only; caller may reject.
        pass
    return SectionSample(
        t=0.0,
        origin=origin.copy(),
        width=float(width),
        height=float(height),
        area=float(area),
        perimeter=float(peri),
        center=center,
        hit_count=len(hits),
    )


def sample_sections_along_axis(
    view: WorldMeshView,
    start: Vector,
    end: Vector,
    count: int = 32,
    rays: int = 16,
    max_radius: float = 0.35,
    extend: float = 0.15,
) -> List[SectionSample]:
    """Sample count sections from start toward end, optionally past end."""
    direction = end - start
    length = direction.length
    if length < 1e-6:
        return []
    axis = direction.normalized()
    total = length * (1.0 + extend)
    samples: List[SectionSample] = []
    for i in range(count):
        t = (i + 0.5) / float(count)
        origin = start + axis * (total * t)
        sec = measure_section(view, origin, axis, rays=rays, max_radius=max_radius)
        if sec is None:
            continue
        sec.t = t
        samples.append(sec)
    return samples


def local_minima_indices(values: List[float]) -> List[int]:
    mins: List[int] = []
    for i in range(1, len(values) - 1):
        if values[i] <= values[i - 1] and values[i] <= values[i + 1]:
            mins.append(i)
    return mins


def medial_axis_point(samples: List[SectionSample], t_lo: float, t_hi: float) -> Optional[Vector]:
    chosen = [s for s in samples if t_lo <= s.t <= t_hi]
    if not chosen:
        return None
    c = Vector((0.0, 0.0, 0.0))
    for s in chosen:
        c += s.center
    c /= float(len(chosen))
    return c
