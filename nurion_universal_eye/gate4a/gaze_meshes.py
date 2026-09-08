"""Diagnostic gaze meshes: safe ellipse, iris, pupil (does not touch EyeDome transform)."""

from __future__ import annotations

import math
from typing import Tuple

from mathutils import Matrix, Vector


def _plane_mat(origin: Vector, right: Vector, up: Vector, normal: Vector) -> Matrix:
    return Matrix(
        (
            (right.x, up.x, normal.x, origin.x),
            (right.y, up.y, normal.y, origin.y),
            (right.z, up.z, normal.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def _material(name: str, rgba, strength: float = 3.0):
    import bpy

    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputMaterial")
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (rgba[0], rgba[1], rgba[2], 1.0)
    emit.inputs["Strength"].default_value = float(strength)
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    if hasattr(mat, "blend_method"):
        mat.blend_method = "OPAQUE"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    return mat


def _replace_object(name: str):
    import bpy

    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me is not None and getattr(me, "users", 1) == 0:
            bpy.data.meshes.remove(me)


def create_disc(
    *,
    name: str,
    radius: float,
    rgba,
    segments: int = 32,
    z_lift: float = 0.0,
) -> object:
    import bmesh
    import bpy

    _replace_object(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=segments)
    for v in bm.verts:
        v.co.z = float(z_lift)
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    mat = _material(name + "_Mat", rgba)
    obj.data.materials.append(mat)
    obj["nurion_gate"] = "4A"
    return obj


def create_ellipse_ring(
    *,
    name: str,
    rx: float,
    ry: float,
    rgba,
    segments: int = 64,
    thickness: float = 0.0008,
) -> object:
    import bmesh
    import bpy

    _replace_object(name)
    bm = bmesh.new()
    # thin annular ellipse as a flat ribbon
    verts_outer = []
    verts_inner = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        c, s = math.cos(a), math.sin(a)
        verts_outer.append(bm.verts.new((rx * c, ry * s, 0.0)))
        scale = max(0.85, 1.0 - thickness / max(min(rx, ry), 1e-6))
        verts_inner.append(bm.verts.new((rx * scale * c, ry * scale * s, 0.0)))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((verts_outer[i], verts_outer[j], verts_inner[j], verts_inner[i]))
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    mat = _material(name + "_Mat", rgba, strength=2.0)
    obj.data.materials.append(mat)
    obj["nurion_gate"] = "4A"
    obj["nurion_kind"] = "GAZE_SAFE_ELLIPSE"
    return obj


def place_on_plane_frame(
    obj,
    *,
    origin: Vector,
    right: Vector,
    up: Vector,
    normal: Vector,
    local_xy: Vector,
    dome_z: float,
) -> None:
    """Place object so its local XY sits on dome surface at (x,y,z)."""
    world = origin + right * float(local_xy.x) + up * float(local_xy.y) + normal * float(dome_z)
    # slight outward bias so iris sits on top of dome visually
    world = world + normal * 1e-4
    obj.matrix_world = _plane_mat(world, right, up, normal)


def remove_gaze_diagnostics() -> None:
    import bpy

    prefixes = (
        "NURION_GazeControl",
        "NURION_GazeAnchor.",
        "NURION_DiagnosticIris.",
        "NURION_DiagnosticPupil.",
        "NURION_GazeSafeEllipse.",
        "NURION_GazeTarget.",
    )
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) for p in prefixes):
            me = obj.data if obj.type == "MESH" else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if me is not None and getattr(me, "users", 1) == 0:
                bpy.data.meshes.remove(me)


def dome_height_at(plane, bulge: float, local_xy: Vector) -> float:
    hw = 0.5 * float(plane.width)
    hh = 0.5 * float(plane.height)
    x, y = float(local_xy.x), float(local_xy.y)
    rn = (x / max(hw, 1e-9)) ** 2 + (y / max(hh, 1e-9)) ** 2
    if rn > 1.0:
        return 0.0
    return float(bulge) * max(0.0, 1.0 - rn)


def create_empty(name: str, location: Vector) -> object:
    import bpy

    _replace_object(name)
    obj = bpy.data.objects.new(name, None)
    obj.empty_display_type = "PLAIN_AXES"
    obj.empty_display_size = 0.02
    bpy.context.collection.objects.link(obj)
    obj.location = location
    obj["nurion_gate"] = "4A"
    return obj
