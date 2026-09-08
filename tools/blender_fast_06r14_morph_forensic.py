#!/usr/bin/env python3
"""Render affected-vertex overlays for FAST-06R1.4 actuator forensic."""

from __future__ import annotations

import argparse
import json
import math
import struct
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector


def args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", type=Path, required=True)
    p.add_argument("--morph-json", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    return p.parse_args(argv)


def look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def material(name: str, color: tuple[float, float, float, float]):
    mat = bpy.data.materials.new(name)
    mat.diffuse_color = color
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = color
    bsdf.inputs["Emission Color"].default_value = color
    bsdf.inputs["Emission Strength"].default_value = 2.0
    bsdf.inputs["Roughness"].default_value = 0.5
    return mat


def raw_glb_positions(path: Path) -> np.ndarray:
    data = path.read_bytes()
    offset = 12
    gltf = None
    binary = None
    while offset + 8 <= len(data):
        length, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset : offset + length]
        offset += length
        if chunk_type == b"JSON":
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            binary = chunk
    if gltf is None or binary is None:
        raise RuntimeError("Invalid GLB")
    accessor = gltf["accessors"][gltf["meshes"][0]["primitives"][0]["attributes"]["POSITION"]]
    view = gltf["bufferViews"][accessor["bufferView"]]
    start = view.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    count = accessor["count"]
    return np.frombuffer(binary, dtype=np.float32, count=count * 3, offset=start).reshape(count, 3)


def main():
    a = args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(a.glb))
    mesh = next(o for o in bpy.data.objects if o.type == "MESH")
    morph = json.loads(a.morph_json.read_text(encoding="utf-8"))
    a.out_dir.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.world.color = (0.025, 0.025, 0.035)

    bpy.ops.object.camera_add(location=(-0.052, -0.69, 1.425))
    cam = bpy.context.object
    cam.data.lens = 62
    look_at(cam, Vector((-0.052, 0.055, 1.425)))
    scene.camera = cam

    bpy.ops.object.light_add(type="AREA", location=(0.2, -0.5, 1.7))
    bpy.context.object.data.energy = 700
    bpy.context.object.data.shape = "DISK"
    bpy.context.object.data.size = 1.0
    look_at(bpy.context.object, Vector((-0.05, 0.04, 1.43)))

    red = material("AffectedVertices", (1.0, 0.02, 0.02, 1.0))
    point_mesh = None

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh.evaluated_get(depsgraph)
    evaluated_mesh = evaluated.to_mesh()
    world = np.array([tuple(evaluated.matrix_world @ v.co) for v in evaluated_mesh.vertices])
    candidate_masks = {
        "CANDIDATE_Mouth": (
            (world[:, 0] > 0.025)
            & (world[:, 0] < 0.115)
            & (world[:, 2] > 1.385)
            & (world[:, 2] < 1.425)
            & (world[:, 1] < -0.09)
        ),
        "CANDIDATE_Eye_L": (
            (world[:, 0] > 0.01)
            & (world[:, 0] < 0.065)
            & (world[:, 2] > 1.445)
            & (world[:, 2] < 1.485)
            & (world[:, 1] < -0.075)
        ),
        "CANDIDATE_Eye_R": (
            (world[:, 0] > 0.065)
            & (world[:, 0] < 0.12)
            & (world[:, 2] > 1.445)
            & (world[:, 2] < 1.485)
            & (world[:, 1] < -0.075)
        ),
    }
    render_sets = {
        name: [Vector(tuple(world[int(row[0])])) for row in deltas]
        for name, deltas in morph["shapeKeys"].items()
    }
    render_sets.update(
        {
            name: [Vector(tuple(world[i])) for i in np.where(mask)[0]]
            for name, mask in candidate_masks.items()
        }
    )

    for morph_name, coords in render_sets.items():
        if point_mesh is None:
            bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=0.0028)
            proto = bpy.context.object
            point_mesh = proto.data.copy()
            bpy.data.objects.remove(proto, do_unlink=True)

        points = []
        for i, co in enumerate(coords):
            obj = bpy.data.objects.new(f"pt_{i}", point_mesh)
            obj.location = co
            obj.data.materials.clear()
            obj.data.materials.append(red)
            bpy.context.collection.objects.link(obj)
            points.append(obj)

        scene.render.filepath = str(a.out_dir / f"{morph_name}_affected_vertices.png")
        scene.render.film_transparent = False
        bpy.ops.render.render(write_still=True)

        for obj in points:
            bpy.data.objects.remove(obj, do_unlink=True)
    evaluated.to_mesh_clear()


if __name__ == "__main__":
    main()
