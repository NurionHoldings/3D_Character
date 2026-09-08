"""Select and analyze a character mesh for landmarking."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from mathutils import Vector

if TYPE_CHECKING:
    import bpy


@dataclass
class CharacterAnalysis:
    object_name: str
    character_id: str
    bounds_min: Vector
    bounds_max: Vector
    dimensions: Vector
    center: Vector
    mesh_vertex_count: int = 0
    notes: list[str] = field(default_factory=list)


def get_selected_character(context: Optional["bpy.types.Context"] = None):
    import bpy

    ctx = context or bpy.context
    obj = ctx.active_object
    if obj is None or obj.type != "MESH":
        return None
    return obj


def analyze_character(obj: "bpy.types.Object") -> CharacterAnalysis:
    import bpy

    if obj.type != "MESH":
        raise ValueError("Character must be a mesh object.")

    # Evaluate modifiers so imported GLB/FBX dimensions match the viewport.
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    bbox = [eval_obj.matrix_world @ Vector(corner) for corner in eval_obj.bound_box]
    mins = Vector((min(v.x for v in bbox), min(v.y for v in bbox), min(v.z for v in bbox)))
    maxs = Vector((max(v.x for v in bbox), max(v.y for v in bbox), max(v.z for v in bbox)))
    dims = maxs - mins
    center = (mins + maxs) * 0.5
    mesh = obj.data

    return CharacterAnalysis(
        object_name=obj.name,
        character_id=obj.name.lower().replace(" ", "-"),
        bounds_min=mins,
        bounds_max=maxs,
        dimensions=dims,
        center=center,
        mesh_vertex_count=len(mesh.vertices) if mesh else 0,
        notes=[
            "MEASURED from world-space bounding box (head top / feet / extent).",
            "Joint centers are NOT measured here — they are ESTIMATED separately.",
        ],
    )
