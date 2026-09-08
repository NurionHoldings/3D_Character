"""Build shallow EyeDome meshes from EyePlane frame (boundary locked to plane)."""

from __future__ import annotations

from typing import Dict, List, Tuple

from mathutils import Matrix, Vector

from .parameters import GATE3_PARAMETERS


def _mat(origin: Vector, right: Vector, up: Vector, normal: Vector) -> Matrix:
    return Matrix(
        (
            (right.x, up.x, normal.x, origin.x),
            (right.y, up.y, normal.y, origin.y),
            (right.z, up.z, normal.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def _material(name: str, rgba) -> object:
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
    emit.inputs["Strength"].default_value = 2.5
    trans = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = float(max(0.55, min(0.9, rgba[3])))
    links.new(trans.outputs["BSDF"], mix.inputs[1])
    links.new(emit.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    mat.blend_method = "BLEND"
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    return mat


def build_dome_local_verts(
    *,
    width: float,
    height: float,
    bulge: float,
    segments_u: int,
    segments_v: int,
) -> Tuple[List[Vector], List[Tuple[int, int, int, int]], Dict]:
    """Elliptical dome: boundary z=0, center z=bulge along +Z (plane normal)."""
    hw, hh = width * 0.5, height * 0.5
    verts: List[Vector] = []
    for j in range(segments_v + 1):
        v = j / segments_v
        for i in range(segments_u + 1):
            u = i / segments_u
            x = (u * 2.0 - 1.0) * hw
            y = (v * 2.0 - 1.0) * hh
            rn = (x / max(hw, 1e-9)) ** 2 + (y / max(hh, 1e-9)) ** 2
            if rn > 1.0:
                # clamp to ellipse boundary
                s = rn ** 0.5
                x /= s
                y /= s
                rn = 1.0
            z = float(bulge) * max(0.0, 1.0 - rn)
            verts.append(Vector((x, y, z)))
    faces = []
    for j in range(segments_v):
        for i in range(segments_u):
            a = j * (segments_u + 1) + i
            b = a + 1
            c = a + (segments_u + 1) + 1
            d = a + (segments_u + 1)
            faces.append((a, b, c, d))
    # Boundary match metric helpers
    boundary_idxs = []
    for j in range(segments_v + 1):
        for i in range(segments_u + 1):
            idx = j * (segments_u + 1) + i
            x, y, z = verts[idx]
            rn = (x / max(hw, 1e-9)) ** 2 + (y / max(hh, 1e-9)) ** 2
            if rn >= 0.98:
                boundary_idxs.append(idx)
    meta = {
        "vertexCount": len(verts),
        "faceCount": len(faces),
        "boundaryCount": len(boundary_idxs),
        "maxBulge": round(float(bulge), 6),
        "boundaryIndices": boundary_idxs,
    }
    return verts, faces, meta


def create_or_replace_dome(
    *,
    name: str,
    origin: Vector,
    right: Vector,
    up: Vector,
    normal: Vector,
    width: float,
    height: float,
    bulge: float,
    rgba,
    hide: bool = False,
) -> Tuple[object, Dict]:
    import bmesh
    import bpy

    old = bpy.data.objects.get(name)
    if old is not None:
        bpy.data.objects.remove(old, do_unlink=True)

    segs = GATE3_PARAMETERS["mesh"]
    local_verts, faces, meta = build_dome_local_verts(
        width=width,
        height=height,
        bulge=bulge,
        segments_u=int(segs["segmentsU"]),
        segments_v=int(segs["segmentsV"]),
    )
    bm = bmesh.new()
    bm_verts = [bm.verts.new((v.x, v.y, v.z)) for v in local_verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        bm.faces.new((bm_verts[f[0]], bm_verts[f[1]], bm_verts[f[2]], bm_verts[f[3]]))
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj.matrix_world = _mat(origin, right, up, normal)
    mat = _material(name + "_Mat", rgba)
    if obj.data.materials:
        obj.data.materials[0] = mat
    else:
        obj.data.materials.append(mat)
    obj.hide_render = bool(hide)
    obj.hide_viewport = bool(hide)
    obj["nurion_gate"] = 3
    obj["nurion_kind"] = "EYE_DOME"
    meta["name"] = name
    meta["hidden"] = bool(hide)
    return obj, meta


def remove_domes() -> None:
    import bpy

    for obj in list(bpy.data.objects):
        if obj.name.startswith("NURION_EyeDome"):
            bpy.data.objects.remove(obj, do_unlink=True)
