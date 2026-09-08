"""Mouth boundary / deformable density (read-only geometry probe)."""

from __future__ import annotations

from typing import Dict, List, Tuple


def probe_mouth_boundary(mesh_obj, axes, head_height: float) -> Dict:
    """Detect upper/lower lip boundary candidates in head-local space."""
    import bpy
    from mathutils import Vector

    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    me = ev.to_mesh()
    upper: List[Tuple[float, float, float]] = []
    lower: List[Tuple[float, float, float]] = []
    deform_pool = 0
    try:
        mw = ev.matrix_world
        inv = axes.matrix_world_inv
        hh = max(float(head_height), 1e-4)
        # Mouth aperture band
        for v in me.vertices:
            w = mw @ v.co
            loc = inv @ w
            x, y, z = float(loc.x), float(loc.y), float(loc.z)
            # frontal mouth window
            if abs(x) > 0.22 * hh:
                continue
            if y < -0.02 * hh or y > 0.45 * hh:
                continue
            if z < -0.02 * hh or z > 0.28 * hh:
                continue
            deform_pool += 1
            # split by relative height around estimated mouth mid (~0.12 hh)
            mid = 0.12 * hh
            if z >= mid:
                upper.append((x, y, z))
            else:
                lower.append((x, y, z))
    finally:
        ev.to_mesh_clear()

    # Boundary quality: need enough verts on both sides + lateral span
    def span(pts):
        if not pts:
            return 0.0
        xs = [p[0] for p in pts]
        return max(xs) - min(xs)

    upper_ok = len(upper) >= 25 and span(upper) > 0.08 * head_height
    lower_ok = len(lower) >= 25 and span(lower) > 0.08 * head_height
    resolved = upper_ok and lower_ok

    # Open-mouth deformable density estimate (verts available to move for jaw open)
    density_class = "HIGH" if deform_pool >= 400 else ("MEDIUM" if deform_pool >= 120 else ("LOW" if deform_pool >= 40 else "INSUFFICIENT"))

    return {
        "mouthBoundary": "RESOLVED" if resolved else "FAIL",
        "upperLipCandidateCount": len(upper),
        "lowerLipCandidateCount": len(lower),
        "upperSpanEU": round(span(upper) / max(head_height, 1e-6), 6),
        "lowerSpanEU": round(span(lower) / max(head_height, 1e-6), 6),
        "deformableMouthVertexCount": deform_pool,
        "openMouthDeformDensity": density_class,
        "notes": [] if resolved else ["insufficient upper/lower lip boundary candidates"],
    }
