"""Compute face landmarks and create guide empties (clone-side only)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from mathutils import Vector

from .parameters import GATE2_PARAMETERS


def _ensure_collection(name: str):
    import bpy

    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _world_verts(mesh_obj):
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    ev = mesh_obj.evaluated_get(deps)
    me = ev.to_mesh()
    try:
        mw = ev.matrix_world
        return [mw @ v.co for v in me.vertices]
    finally:
        ev.to_mesh_clear()


def _mean(pts: List[Vector]) -> Vector:
    acc = Vector((0, 0, 0))
    for p in pts:
        acc += p
    return acc / max(len(pts), 1)


def compute_landmarks(mesh_obj, axes, head_height: float) -> Dict[str, Vector]:
    """Head-local landmark extraction for guides/bones."""
    hh = max(float(head_height), 1e-4)
    inv = axes.matrix_world_inv
    mw = axes.matrix_world
    verts_w = _world_verts(mesh_obj)
    locals_ = [inv @ p for p in verts_w]

    def band(pred):
        return [verts_w[i] for i, loc in enumerate(locals_) if pred(loc)]

    # Mouth mid height ~0.12 hh
    mid_z = 0.12 * hh
    upper = band(lambda loc: abs(loc.x) < 0.18 * hh and -0.02 * hh < loc.y < 0.4 * hh and mid_z <= loc.z < 0.26 * hh)
    lower = band(lambda loc: abs(loc.x) < 0.18 * hh and -0.02 * hh < loc.y < 0.4 * hh and -0.02 * hh < loc.z < mid_z)
    # corners: lateral extremes in mouth band
    mouth = band(lambda loc: abs(loc.x) < 0.28 * hh and -0.02 * hh < loc.y < 0.42 * hh and -0.02 * hh < loc.z < 0.26 * hh)
    jaw = band(lambda loc: abs(loc.x) < 0.16 * hh and -0.05 * hh < loc.y < 0.35 * hh and -0.12 * hh < loc.z < 0.08 * hh)
    nose = band(lambda loc: abs(loc.x) < 0.08 * hh and 0.05 * hh < loc.y < 0.45 * hh and 0.22 * hh < loc.z < 0.42 * hh)
    cheek_l = band(lambda loc: -0.32 * hh < loc.x < -0.12 * hh and -0.02 * hh < loc.y < 0.35 * hh and 0.05 * hh < loc.z < 0.28 * hh)
    cheek_r = band(lambda loc: 0.12 * hh < loc.x < 0.32 * hh and -0.02 * hh < loc.y < 0.35 * hh and 0.05 * hh < loc.z < 0.28 * hh)

    def brow(side_sign: float, x0: float, x1: float):
        return band(
            lambda loc: (x0 * hh <= loc.x * side_sign <= x1 * hh if side_sign > 0 else x1 * hh <= loc.x <= x0 * hh)
            and -0.02 * hh < loc.y < 0.4 * hh
            and 0.42 * hh < loc.z < 0.62 * hh
        )

    # Simpler brow bands by x ranges
    brow_l_inner = band(lambda loc: -0.12 * hh < loc.x < -0.02 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)
    brow_l_mid = band(lambda loc: -0.22 * hh < loc.x < -0.10 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)
    brow_l_outer = band(lambda loc: -0.34 * hh < loc.x < -0.18 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)
    brow_r_inner = band(lambda loc: 0.02 * hh < loc.x < 0.12 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)
    brow_r_mid = band(lambda loc: 0.10 * hh < loc.x < 0.22 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)
    brow_r_outer = band(lambda loc: 0.18 * hh < loc.x < 0.34 * hh and 0.0 < loc.y < 0.4 * hh and 0.42 * hh < loc.z < 0.62 * hh)

    def pick(pts, fallback_local: Vector):
        if pts:
            return _mean(pts)
        return mw @ fallback_local

    # Corners from mouth set extremes
    if mouth:
        locs_m = [(inv @ p, p) for p in mouth]
        corner_l = min(locs_m, key=lambda t: t[0].x)[1]
        corner_r = max(locs_m, key=lambda t: t[0].x)[1]
    else:
        corner_l = mw @ Vector((-0.14 * hh, 0.18 * hh, mid_z))
        corner_r = mw @ Vector((0.14 * hh, 0.18 * hh, mid_z))

    jaw_pts = jaw
    jaw_c = pick(jaw_pts, Vector((0.0, 0.12 * hh, -0.02 * hh)))
    # Hinge must be distinct from center — place slightly up/back in head-local
    hinge_local = inv @ jaw_c + Vector((0.0, -0.06 * hh, 0.08 * hh))
    jaw_hinge = mw @ hinge_local

    lm = {
        "jaw.center": jaw_c,
        "jaw.hinge": jaw_hinge,
        "lip.upper.center": pick(upper, Vector((0.0, 0.20 * hh, mid_z + 0.03 * hh))),
        "lip.lower.center": pick(lower, Vector((0.0, 0.18 * hh, mid_z - 0.03 * hh))),
        "mouth.corner.L": corner_l,
        "mouth.corner.R": corner_r,
        "cheek.L": pick(cheek_l, Vector((-0.20 * hh, 0.12 * hh, 0.16 * hh))),
        "cheek.R": pick(cheek_r, Vector((0.20 * hh, 0.12 * hh, 0.16 * hh))),
        "brow.inner.L": pick(brow_l_inner, Vector((-0.06 * hh, 0.18 * hh, 0.52 * hh))),
        "brow.mid.L": pick(brow_l_mid, Vector((-0.16 * hh, 0.16 * hh, 0.52 * hh))),
        "brow.outer.L": pick(brow_l_outer, Vector((-0.26 * hh, 0.12 * hh, 0.50 * hh))),
        "brow.inner.R": pick(brow_r_inner, Vector((0.06 * hh, 0.18 * hh, 0.52 * hh))),
        "brow.mid.R": pick(brow_r_mid, Vector((0.16 * hh, 0.16 * hh, 0.52 * hh))),
        "brow.outer.R": pick(brow_r_outer, Vector((0.26 * hh, 0.12 * hh, 0.50 * hh))),
        "nose": pick(nose, Vector((0.0, 0.28 * hh, 0.32 * hh))),
        "head.origin": axes.origin.copy(),
    }
    return lm


def create_guides(landmarks: Dict[str, Vector], axes) -> Dict:
    import bpy

    col = _ensure_collection(GATE2_PARAMETERS["collections"]["guides"])
    created = {}
    # Head basis empty
    basis = bpy.data.objects.new("NURION_FG_HeadLocalAxes", None)
    basis.empty_display_type = "ARROWS"
    basis.empty_display_size = max(axes.head_height * 0.15, 0.02)
    basis.matrix_world = axes.matrix_world.copy()
    col.objects.link(basis)
    created["head.local.axes"] = basis.name

    for key, pos in landmarks.items():
        if key == "head.origin":
            continue
        name = f"NURION_FG_{key}"
        emp = bpy.data.objects.new(name, None)
        emp.empty_display_type = "SPHERE"
        emp.empty_display_size = max(axes.head_height * 0.02, 0.005)
        emp.location = pos
        col.objects.link(emp)
        created[key] = emp.name

    # Lip curves as polyline empties already covered by centers/corners; store curve samples
    curve = {
        "upper": ["mouth.corner.L", "lip.upper.center", "mouth.corner.R"],
        "lower": ["mouth.corner.L", "lip.lower.center", "mouth.corner.R"],
    }
    return {"guides": created, "curves": curve, "basisObject": basis.name}
