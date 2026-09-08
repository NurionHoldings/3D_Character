"""Procedural upper/lower eyelid proxies over EyeDome (Gate 4B)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Tuple

from mathutils import Matrix, Vector

from .parameters import GATE4B_PARAMETERS


def _mat(origin: Vector, right: Vector, up: Vector, normal: Vector) -> Matrix:
    return Matrix(
        (
            (right.x, up.x, normal.x, origin.x),
            (right.y, up.y, normal.y, origin.y),
            (right.z, up.z, normal.z, origin.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def _material(name: str, rgba):
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
    emit.inputs["Strength"].default_value = 2.2
    bsdf = nodes.new("ShaderNodeBsdfDiffuse")
    bsdf.inputs["Color"].default_value = (rgba[0], rgba[1], rgba[2], 1.0)
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.35
    links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    links.new(emit.outputs["Emission"], mix.inputs[2])
    links.new(mix.outputs["Shader"], out.inputs["Surface"])
    if hasattr(mat, "shadow_method"):
        mat.shadow_method = "NONE"
    return mat


def _replace(name: str):
    import bpy

    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data if old.type == "MESH" else None
        bpy.data.objects.remove(old, do_unlink=True)
        if me is not None and getattr(me, "users", 1) == 0:
            bpy.data.meshes.remove(me)


def dome_z(plane, bulge: float, x: float, y: float) -> float:
    hw = 0.5 * float(plane.width)
    hh = 0.5 * float(plane.height)
    rn = (x / max(hw, 1e-9)) ** 2 + (y / max(hh, 1e-9)) ** 2
    if rn > 1.0:
        return 0.0
    return float(bulge) * max(0.0, 1.0 - rn)


@dataclass
class LidAperture:
    side: str
    center: Vector  # plane-local xy
    rx: float
    ry: float
    open_upper_y: float
    open_lower_y: float
    meet_y: float
    upper_share: float
    lower_share: float


def build_lid_aperture(plane) -> LidAperture:
    p = GATE4B_PARAMETERS["proxy"]
    eu = float(plane.eye_unit)
    origin = plane.origin_world
    right = plane.right.normalized()
    up = plane.up.normalized()
    inner = Vector(plane.aperture_inner)
    outer = Vector(plane.aperture_outer)
    mid = (inner + outer) * 0.5
    to_mid = mid - origin
    cx = float(to_mid.dot(right))
    cy = float(to_mid.dot(up))
    rx = 0.5 * (outer - inner).length * float(p["widthFromAperture"])
    ry = 0.5 * float(plane.height) * float(p["heightFromPlane"])
    rx = min(rx, 0.52 * float(plane.width))
    ry = min(ry, 0.52 * float(plane.height))
    open_u = cy + ry * (1.0 - float(p["openUpperInset"]))
    open_l = cy - ry * (1.0 - float(p["openLowerInset"]))
    # Meeting line: weighted so upper travels more
    us = float(p["upperTravelShare"])
    ls = float(p["lowerTravelShare"])
    meet = (open_u * ls + open_l * us) / max(us + ls, 1e-9)
    # slight overlap when closed
    return LidAperture(
        side=plane.side,
        center=Vector((cx, cy, 0.0)),
        rx=float(rx),
        ry=float(ry),
        open_upper_y=float(open_u),
        open_lower_y=float(open_l),
        meet_y=float(meet),
        upper_share=us,
        lower_share=ls,
    )


def lid_edges(ap: LidAperture, amount: float) -> Tuple[float, float]:
    """Return (upper_free_edge_y, lower_free_edge_y) for blink amount in [0,1]."""
    t = max(0.0, min(1.0, float(amount)))
    overlap = 0.0
    # closed overlap applied proportionally near close
    # meet with slight cross for seal
    upper = ap.open_upper_y + (ap.meet_y - ap.open_upper_y) * t
    lower = ap.open_lower_y + (ap.meet_y - ap.open_lower_y) * t
    if t >= 0.999:
        # force seal with tiny overlap in local meters via caller using eu
        upper = ap.meet_y
        lower = ap.meet_y
    return float(upper), float(lower)


def _build_lid_verts(
    *,
    plane,
    bulge: float,
    ap: LidAperture,
    y0: float,
    y1: float,
    gap: float,
    which: str,
    face_bvh=None,
) -> Tuple[List[Vector], List[Tuple[int, int, int, int]]]:
    """Tessellate a lid panel between y0..y1 over the aperture ellipse, on dome + gap.

    If face_bvh is provided, each vertex is pushed to sit just in front of the face
    skin so proxies cover the visual eye without burying into the socket mesh.
    """
    p = GATE4B_PARAMETERS["proxy"]
    su = int(p["segmentsU"])
    sv = int(p["segmentsV"])
    y_lo, y_hi = (y0, y1) if y0 <= y1 else (y1, y0)
    if y_hi - y_lo < 1e-5:
        mid = 0.5 * (y_lo + y_hi)
        y_lo, y_hi = mid - 1e-5, mid + 1e-5

    origin = plane.origin_world
    right = plane.right.normalized()
    up = plane.up.normalized()
    normal = plane.normal_out.normalized()
    eu = float(plane.eye_unit)

    verts: List[Vector] = []
    for j in range(sv + 1):
        fy = j / sv
        y = y_lo + (y_hi - y_lo) * fy
        dy = (y - float(ap.center.y)) / max(ap.ry, 1e-9)
        if abs(dy) > 1.0:
            x_half = 0.0
        else:
            x_half = ap.rx * math.sqrt(max(0.0, 1.0 - dy * dy))
        x_half *= 1.04
        for i in range(su + 1):
            fx = i / su
            x = float(ap.center.x) + (-x_half + 2.0 * x_half * fx)
            z = dome_z(plane, bulge, x, y) + gap
            if which == "upper":
                z += gap * 0.15 * fy
            else:
                z += gap * 0.15 * (1.0 - fy)
            if face_bvh is not None:
                world = origin + right * x + up * y + normal * z
                start = world + normal * (eu * 2.5)
                hit = face_bvh.ray_cast(start, -normal, eu * 5.0)
                if hit and hit[0] is not None:
                    z_face = float((hit[0] - origin).dot(normal)) + gap * 0.85
                    z = max(z, z_face)
            verts.append(Vector((x, y, z)))
    faces = []
    for j in range(sv):
        for i in range(su):
            a = j * (su + 1) + i
            b = a + 1
            c = a + (su + 1) + 1
            d = a + (su + 1)
            faces.append((a, b, c, d))
    return verts, faces


def create_or_update_lid(
    *,
    name: str,
    plane,
    bulge: float,
    ap: LidAperture,
    y0: float,
    y1: float,
    which: str,
    rgba,
    face_bvh=None,
) -> object:
    import bmesh
    import bpy

    p = GATE4B_PARAMETERS["proxy"]
    gap = float(plane.eye_unit) * float(p["surfaceGapEyeUnits"])
    local_verts, faces = _build_lid_verts(
        plane=plane,
        bulge=bulge,
        ap=ap,
        y0=y0,
        y1=y1,
        gap=gap,
        which=which,
        face_bvh=face_bvh,
    )

    obj = bpy.data.objects.get(name)
    if obj is None or obj.type != "MESH":
        _replace(name)
        me = bpy.data.meshes.new(name + "_Mesh")
        obj = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(obj)
        mat = _material(name + "_Mat", rgba)
        obj.data.materials.append(mat)
    else:
        me = obj.data

    bm = bmesh.new()
    bm_verts = [bm.verts.new((v.x, v.y, v.z)) for v in local_verts]
    bm.verts.ensure_lookup_table()
    for f in faces:
        bm.faces.new((bm_verts[f[0]], bm_verts[f[1]], bm_verts[f[2]], bm_verts[f[3]]))
    bm.to_mesh(me)
    me.update()
    bm.free()

    obj.matrix_world = _mat(
        plane.origin_world,
        plane.right.normalized(),
        plane.up.normalized(),
        plane.normal_out.normalized(),
    )
    obj["nurion_gate"] = "4B"
    obj["nurion_kind"] = "LID_PROXY"
    obj["nurion_lid"] = which
    obj["nurion_side"] = plane.side
    obj.hide_render = False
    obj.hide_viewport = False
    return obj


def remove_blink_proxies() -> None:
    import bpy

    prefixes = (
        "NURION_UpperLidProxy.",
        "NURION_LowerLidProxy.",
        "NURION_BlinkControl",
    )
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) or obj.name == p.rstrip(".") for p in prefixes):
            me = obj.data if obj.type == "MESH" else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if me is not None and getattr(me, "users", 1) == 0:
                bpy.data.meshes.remove(me)


def coverage_and_gap(ap: LidAperture, amount: float, eu: float) -> Dict:
    """Geometric aperture coverage from lid free edges (no render)."""
    upper, lower = lid_edges(ap, amount)
    p = GATE4B_PARAMETERS["proxy"]
    overlap = float(eu) * float(p["closedOverlapEyeUnits"])
    if amount >= 0.999:
        upper = ap.meet_y - 0.5 * overlap
        lower = ap.meet_y + 0.5 * overlap
    gap = max(0.0, upper - lower)
    open_span = max(1e-9, ap.open_upper_y - ap.open_lower_y)
    uncovered = max(0.0, upper - lower)
    coverage = max(0.0, min(1.0, 1.0 - uncovered / open_span))
    # at closed with overlap, gap metric uses absolute separation after overlap apply
    gap_eu = gap / max(eu, 1e-9)
    if amount >= 0.999:
        gap_eu = max(0.0, (upper - lower) / max(eu, 1e-9))  # negative overlap → 0
        if lower >= upper:
            gap_eu = 0.0
            coverage = 1.0
    return {
        "upperY": round(upper, 6),
        "lowerY": round(lower, 6),
        "gapEU": round(gap_eu, 6),
        "coverage": round(coverage, 6),
    }
