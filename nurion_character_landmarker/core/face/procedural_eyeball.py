"""Create NURION standard procedural eyeballs from Eye Proxy centers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import bpy
from mathutils import Matrix, Vector

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters, generation_scope
from .eye_proxy import EyeProxyResult
from .parameters_alpha2 import FACE_ALPHA2_PARAMETERS
from .spaces import HeadFrame


@dataclass
class ProceduralEyeballResult:
    objects: Dict[str, str] = field(default_factory=dict)
    meshHashSeeds: Dict[str, str] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)


def _ensure_collection(name: str) -> bpy.types.Collection:
    col = bpy.data.collections.get(name)
    if col is None:
        col = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(col)
    return col


def _uv_sphere_mesh(name: str, radius: float, segments: int, rings: int) -> bpy.types.Mesh:
    # Deterministic UV sphere in object-local space, origin at center.
    import bmesh

    mesh = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(
        bm,
        u_segments=segments,
        v_segments=rings,
        radius=radius,
    )
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()
    return mesh


def _orient_to_forward(obj: bpy.types.Object, forward: Vector, up: Vector) -> None:
    """Align local -Y (Blender sphere default doesn't matter much) to look along forward."""
    f = forward.normalized()
    u = up.normalized()
    r = f.cross(u)
    if r.length < 1e-8:
        r = Vector((1.0, 0.0, 0.0))
    else:
        r.normalize()
    u = r.cross(f).normalized()
    # Columns = right, forward, up for a look matrix; Blender objects use -Z forward often.
    # Use quaternion from matrix with -Z as forward for iris "front".
    mat = Matrix(
        (
            (r.x, u.x, -f.x, 0.0),
            (r.y, u.y, -f.y, 0.0),
            (r.z, u.z, -f.z, 0.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    obj.matrix_world = Matrix.Translation(obj.location) @ mat


def create_procedural_eyeballs(
    proxy: EyeProxyResult,
    frame: HeadFrame,
    **kwargs,
) -> ProceduralEyeballResult:
    assert_no_gt_parameters(**kwargs)
    out = ProceduralEyeballResult()
    cfg = FACE_ALPHA2_PARAMETERS["eyeball"]
    col = _ensure_collection(cfg["collection"])

    with generation_scope("procedural_eyeball"):
        for side, obj_name in (("L", cfg["nameL"]), ("R", cfg["nameR"])):
            ckey = f"eye.center.{side}"
            if ckey not in proxy.centers:
                out.notes.append(f"missing {ckey}")
                continue
            center = proxy.centers[ckey].position
            radius = proxy.radii.get(side)
            if radius is None:
                ev = proxy.centers[ckey].evidence or {}
                radius = float(ev.get("radiusMm", 12.0)) / 1000.0

            # Remove prior NURION eyeball of same name for determinism.
            existing = bpy.data.objects.get(obj_name)
            if existing is not None:
                bpy.data.objects.remove(existing, do_unlink=True)

            mesh_name = f"{obj_name}_Mesh"
            old_mesh = bpy.data.meshes.get(mesh_name)
            if old_mesh is not None:
                bpy.data.meshes.remove(old_mesh)

            mesh = _uv_sphere_mesh(mesh_name, radius, int(cfg["segments"]), int(cfg["rings"]))
            obj = bpy.data.objects.new(obj_name, mesh)
            col.objects.link(obj)
            obj.location = center
            # Face forward using aperture normal if available.
            ap = proxy.apertures.get(side)
            forward = ap.normal_out if ap is not None else frame.forward
            _orient_to_forward(obj, forward, frame.up)
            obj["nurion_eyeball"] = True
            obj["nurion_side"] = side
            obj["nurion_method"] = FACE_ALPHA2_PARAMETERS["methods"]["eyeballMesh"]
            obj["nurion_radius_m"] = float(radius)
            obj["nurion_initial_inset_mode"] = bool(cfg["initialInsetMode"])

            # Seed hash from rounded center/radius/segments (mesh topology is fixed by params).
            seed = f"{obj_name}|{radius:.8f}|{center.x:.8f}|{center.y:.8f}|{center.z:.8f}|{cfg['segments']}|{cfg['rings']}"
            out.meshHashSeeds[obj_name] = seed
            out.objects[side] = obj_name

        out.notes.append("Created NURION standard eyeballs (identical topology L/R)")
    return out


def eyeball_center_from_object(obj_name: str) -> Optional[Vector]:
    obj = bpy.data.objects.get(obj_name)
    if obj is None:
        return None
    return obj.matrix_world.translation.copy()
