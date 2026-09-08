"""Create optical beauty layers parented to frozen iris (no Gate1–5 coord edits)."""

from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

from mathutils import Vector

from .parameters import GATE6_PARAMETERS


def _replace(name: str):
    import bpy

    old = bpy.data.objects.get(name)
    if old is not None:
        me = old.data if old.type == "MESH" else None
        bpy.data.objects.remove(old, do_unlink=True)
        if me is not None and getattr(me, "users", 1) == 0:
            bpy.data.meshes.remove(me)


def _disc(name: str, radius: float, segments: int = 28, z: float = 0.0):
    import bmesh
    import bpy

    _replace(name)
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, radius=radius, segments=segments)
    for v in bm.verts:
        v.co.z = float(z)
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj["nurion_gate"] = "6"
    return obj


def _ring(name: str, inner_r: float, outer_r: float, segments: int = 36, z: float = 0.0):
    import bmesh
    import bpy

    _replace(name)
    bm = bmesh.new()
    outer = []
    inner = []
    for i in range(segments):
        a = 2.0 * math.pi * i / segments
        c, s = math.cos(a), math.sin(a)
        outer.append(bm.verts.new((outer_r * c, outer_r * s, z)))
        inner.append(bm.verts.new((inner_r * c, inner_r * s, z)))
    bm.verts.ensure_lookup_table()
    for i in range(segments):
        j = (i + 1) % segments
        bm.faces.new((outer[i], outer[j], inner[j], inner[i]))
    me = bpy.data.meshes.new(name + "_Mesh")
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(obj)
    obj["nurion_gate"] = "6"
    return obj


def remove_beauty_layers() -> None:
    import bpy

    prefixes = (
        "NURION_LimbalRing.",
        "NURION_CornealHighlight.",
        "NURION_Catchlight.",
        "NURION_SoftSclera.",
        "NURION_BeautyControl",
    )
    for obj in list(bpy.data.objects):
        if any(obj.name.startswith(p) or obj.name == p for p in prefixes):
            me = obj.data if obj.type == "MESH" else None
            bpy.data.objects.remove(obj, do_unlink=True)
            if me is not None and getattr(me, "users", 1) == 0:
                bpy.data.meshes.remove(me)


def _iris_radius(iris_obj) -> float:
    if iris_obj is None or iris_obj.data is None:
        return 0.01
    xs = [abs(v.co.x) for v in iris_obj.data.vertices]
    ys = [abs(v.co.y) for v in iris_obj.data.vertices]
    return max(max(xs) if xs else 0.01, max(ys) if ys else 0.01)


def create_beauty_layers_for_eye(
    *,
    side: str,
    iris_obj,
    pupil_obj,
    dome_obj,
    eye_unit: float,
) -> Dict[str, object]:
    """Spawn limbal/cornea/catchlight/sclera parented to iris; local offsets only."""
    import bpy

    layers = GATE6_PARAMETERS["layers"]
    iris_r = _iris_radius(iris_obj)
    pupil_r = _iris_radius(pupil_obj) if pupil_obj else iris_r * 0.42
    zbias = float(eye_unit) * float(layers["zBiasEyeUnits"])
    corneal_z = float(eye_unit) * float(layers["cornealLiftEyeUnits"])

    limbal_outer = iris_r * (1.0 + float(layers["limbalWidthScale"]) * 0.5)
    limbal_inner = max(pupil_r * 1.05, iris_r * (1.0 - float(layers["limbalWidthScale"])))
    limbal = _ring(f"NURION_LimbalRing.{side}", limbal_inner, limbal_outer, z=zbias * 0.5)
    cornea = _disc(f"NURION_CornealHighlight.{side}", iris_r * 1.02, z=corneal_z)
    catch_r = iris_r * float(layers["catchlightRadiusScale"])
    catch = _disc(f"NURION_Catchlight.{side}", catch_r, segments=20, z=corneal_z + zbias)
    # Soft sclera: slight larger disc behind iris on dome — parent to dome
    sclera = _disc(f"NURION_SoftSclera.{side}", iris_r * 2.2, segments=40, z=-zbias)

    # Parent optical layers to iris so gaze motion carries them without editing iris coords
    if iris_obj is not None:
        for obj, zloc in (
            (limbal, zbias * 0.5),
            (cornea, corneal_z),
            (catch, corneal_z + zbias),
        ):
            obj.parent = iris_obj
            obj.location = (0.0, 0.0, zloc)
            obj.rotation_euler = (0.0, 0.0, 0.0)
            obj.scale = (1.0, 1.0, 1.0)

    if dome_obj is not None:
        sclera.parent = dome_obj
        sclera.location = (0.0, 0.0, zbias * 0.25)
        sclera.rotation_euler = (0.0, 0.0, 0.0)
        sclera.scale = (1.0, 1.0, 1.0)

    for obj in (limbal, cornea, catch, sclera):
        obj["nurion_kind"] = "BEAUTY_LAYER"
        obj["nurion_side"] = side

    return {
        "limbal": limbal,
        "cornea": cornea,
        "catchlight": catch,
        "sclera": sclera,
        "irisRadius": iris_r,
        "catchRadius": catch_r,
    }


def place_catchlight(
    *,
    catch_obj,
    iris_radius: float,
    catch_radius: float,
    light_dir_local_xy: Tuple[float, float],
    dynamic: bool,
) -> Dict:
    """Place catchlight in iris local XY; clamp so disc stays inside iris."""
    layers = GATE6_PARAMETERS["layers"]
    if catch_obj is None:
        return {"offset": [0.0, 0.0], "escapeEU": 0.0, "inside": True}
    if not dynamic:
        # Fixed catchlight — upper-left convention in iris local
        ox = -iris_radius * float(layers["catchlightOffsetScale"]) * 0.6
        oy = iris_radius * float(layers["catchlightOffsetScale"]) * 0.55
    else:
        lx, ly = float(light_dir_local_xy[0]), float(light_dir_local_xy[1])
        ln = math.hypot(lx, ly)
        if ln < 1e-8:
            lx, ly = -0.4, 0.55
            ln = math.hypot(lx, ly)
        lx /= ln
        ly /= ln
        mag = iris_radius * float(layers["catchlightOffsetScale"])
        ox, oy = lx * mag, ly * mag

    max_off = max(0.0, iris_radius * float(layers["catchlightMaxOffsetScale"]) - catch_radius)
    rn = math.hypot(ox, oy)
    if rn > max_off and rn > 1e-12:
        s = max_off / rn
        ox *= s
        oy *= s
    z = float(catch_obj.location.z)
    catch_obj.location = (ox, oy, z)
    # Escape if catchlight disc exceeds iris
    edge = math.hypot(ox, oy) + catch_radius
    escape = max(0.0, edge - iris_radius)
    return {
        "offset": [round(ox, 6), round(oy, 6)],
        "escape": round(escape, 6),
        "inside": escape <= 1e-6,
    }
