"""Create thin diagnostic NURION_EyePlane.L/R meshes (Gate 2 only)."""

from __future__ import annotations

from typing import Dict, Tuple

from mathutils import Matrix, Vector

from .parameters import GATE2_PARAMETERS


def _ensure_material(name: str, rgba) -> "bpy.types.Material":
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
    emit.inputs["Strength"].default_value = 4.0
    trans = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    # MixShader Fac: 0 = input1 (transparent), 1 = input2 (emission).
    mix.inputs["Fac"].default_value = float(max(0.55, min(0.92, rgba[3])))
    links.new(trans.outputs["BSDF"], mix.inputs[1])
    links.new(emit.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.blend_method = "BLEND"

    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    return mat


def _basis_matrix(origin: Vector, right: Vector, up: Vector, normal_out: Vector) -> Matrix:
    return Matrix(
        (
            (right.x, up.x, normal_out.x, origin.x),
            (right.y, up.y, normal_out.y, origin.y),
            (right.z, up.z, normal_out.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def create_eye_plane_object(
    *,
    side: str,
    origin: Vector,
    right: Vector,
    up: Vector,
    normal_out: Vector,
    width: float,
    height: float,
    thickness: float,
) -> Tuple[object, Dict]:
    import bmesh
    import bpy

    name = f"NURION_EyePlane.{side}"
    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    diag = GATE2_PARAMETERS["diagnostic"]
    rgba = diag["leftRGBA"] if side == "L" else diag["rightRGBA"]

    bm = bmesh.new()
    hw, hh = width * 0.5, height * 0.5
    ht = max(thickness * 0.5, width * 0.03)
    # Main diagnostic plate (flat quad extruded slightly)
    verts = [
        bm.verts.new((-hw, -hh, 0.0)),
        bm.verts.new((hw, -hh, 0.0)),
        bm.verts.new((hw, hh, 0.0)),
        bm.verts.new((-hw, hh, 0.0)),
        bm.verts.new((-hw, -hh, ht)),
        bm.verts.new((hw, -hh, ht)),
        bm.verts.new((hw, hh, ht)),
        bm.verts.new((-hw, hh, ht)),
    ]
    bm.faces.new((verts[0], verts[1], verts[2], verts[3]))
    bm.faces.new((verts[4], verts[7], verts[6], verts[5]))
    # Crosshair ridges on outer face
    t = min(hw, hh) * 0.06
    for x0, y0, x1, y1 in (
        (-hw * 0.9, -t, hw * 0.9, t),
        (-t, -hh * 0.9, t, hh * 0.9),
    ):
        box = bmesh.ops.create_cube(bm, size=1.0)
        cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        for v in box["verts"]:
            v.co.x = v.co.x * dx + cx
            v.co.y = v.co.y * dy + cy
            v.co.z = v.co.z * (ht * 0.35) + ht * 1.15
    # Outward normal stub
    stub = bmesh.ops.create_cube(bm, size=1.0)
    for v in stub["verts"]:
        v.co.x *= t
        v.co.y *= t
        v.co.z = v.co.z * (hh * 0.45) + ht + hh * 0.25

    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.matrix_world = _basis_matrix(origin, right, up, normal_out)
    mat = _ensure_material(f"NURION_EyePlaneDiag.{side}", rgba)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    obj.hide_render = False
    obj.hide_viewport = False
    obj.show_in_front = True
    obj["nurion_gate"] = 2
    obj["nurion_kind"] = "EYE_PLANE"
    obj["nurion_side"] = side
    obj["nurion_convex"] = False
    meta = {
        "name": name,
        "width": round(float(width), 6),
        "height": round(float(height), 6),
        "thickness": round(float(thickness), 6),
        "origin": [round(float(x), 6) for x in origin],
        "normalOut": [round(float(x), 6) for x in normal_out],
    }
    return obj, meta


def remove_eye_planes() -> None:
    import bpy

    for side in ("L", "R"):
        obj = bpy.data.objects.get(f"NURION_EyePlane.{side}")
        if obj is not None:
            bpy.data.objects.remove(obj, do_unlink=True)
