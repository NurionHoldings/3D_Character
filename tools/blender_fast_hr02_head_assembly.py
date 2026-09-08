#!/usr/bin/env python3
"""FAST-HR02 — assemble HM08 DerivedHead as a separate Head-bone child mesh."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--base-glb", type=Path, required=True)
    p.add_argument("--donor-obj", type=Path, required=True)
    p.add_argument("--weight-map", type=Path, required=True)
    p.add_argument("--output-glb", type=Path, required=True)
    p.add_argument("--evidence-json", type=Path, required=True)
    p.add_argument("--preview", type=Path, required=True)
    return p.parse_args(argv)


def parse_obj(path: Path):
    vertices, uvs, faces = [], [], []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            p = line.split()
            vertices.append((float(p[1]), float(p[2]), float(p[3])))
        elif line.startswith("vt "):
            p = line.split()
            uvs.append((float(p[1]), float(p[2])))
        elif line.startswith("f "):
            face = []
            for token in line.split()[1:]:
                fields = token.split("/")
                vi = int(fields[0]) - 1
                ti = int(fields[1]) - 1 if len(fields) > 1 and fields[1] else vi
                face.append((vi, ti))
            if len(face) >= 3:
                faces.append(face)
    return vertices, uvs, faces


def create_donor(path: Path):
    raw_vertices, uvs, faces = parse_obj(path)
    # Keep the facial shell and lower jaw; existing Meshy hair/scalp remain authoritative.
    faces = [
        face
        for face in faces
        if (
            sum(raw_vertices[vi][2] for vi, _ in face) / len(face) > 0.18
            and sum(raw_vertices[vi][1] for vi, _ in face) / len(face) < 7.82
            and sum(raw_vertices[vi][1] for vi, _ in face) / len(face) > 5.72
        )
    ]
    scale = 0.075
    target_eye_center = Vector((0.0865, -0.158, 1.466))
    source_eye_center = Vector((0.0, -1.245, 7.284))
    translation = target_eye_center - source_eye_center * scale
    vertices = [
        Vector((x, -z, y)) * scale + translation
        for x, y, z in raw_vertices
    ]

    mesh = bpy.data.meshes.new("NURION_FaceHead")
    mesh.from_pydata(vertices, [], [[vi for vi, _ in face] for face in faces])
    mesh.update()
    if uvs:
        uv_layer = mesh.uv_layers.new(name="UVMap")
        for poly, face in zip(mesh.polygons, faces):
            for loop_index, (_vi, ti) in zip(poly.loop_indices, face):
                if 0 <= ti < len(uvs):
                    uv_layer.data[loop_index].uv = uvs[ti]

    obj = bpy.data.objects.new("NURION_FaceHead", mesh)
    bpy.context.scene.collection.objects.link(obj)
    for poly in mesh.polygons:
        poly.use_smooth = True

    mat = bpy.data.materials.new("NURION_FaceSkin")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.72, 0.46, 0.38, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.58
    if "Subsurface Weight" in bsdf.inputs:
        bsdf.inputs["Subsurface Weight"].default_value = 0.035
    mesh.materials.append(mat)
    return obj, scale, translation


def add_blink_shapes(donor, weight_map: Path, scale: float):
    bundle = json.loads(weight_map.read_text(encoding="utf-8"))
    eyelid = bundle["eyelidWeights"]
    donor.shape_key_add(name="Basis")
    moved = {}
    for shape_name, side, cx in (
        ("PRES_Blink_L", "LEFT", -0.308),
        ("PRES_Blink_R", "RIGHT", 0.308),
    ):
        key = donor.shape_key_add(name=shape_name)
        upper = {int(i): float(w) for i, w in eyelid[f"{side}_UPPER"].items()}
        lower = {int(i): float(w) for i, w in eyelid[f"{side}_LOWER"].items()}
        changed = set()
        for vi, w in upper.items():
            raw_x = (key.data[vi].co.x - 0.0865) / scale
            raw_y = (key.data[vi].co.z - (1.466 - 7.284 * scale)) / scale
            raw_z = -(
                key.data[vi].co.y
                - (-0.158 - (-1.245 * scale))
            ) / scale
            u = abs((raw_x - cx) / 0.18)
            canthus = max(0.0, min(1.0, (1.0 - u) / 0.30))
            if raw_y <= 7.30 or raw_z <= 1.24 or canthus <= 0.0:
                continue
            influence = min(1.0, w * 1.65) * canthus
            seam = 7.286 + 0.008 * max(0.0, 1.0 - (raw_x - cx) ** 2 / 0.18**2)
            dy = (seam - raw_y) * influence
            dz = 0.024 * influence * min(1.0, abs(dy) / 0.10)
            key.data[vi].co += Vector((0.0, -dz * scale, dy * scale))
            changed.add(vi)
        # Lower lid only settles by a sub-millimetre amount in final character scale.
        for vi, w in lower.items():
            if vi in changed:
                continue
            raw_x = (key.data[vi].co.x - 0.0865) / scale
            raw_y = (key.data[vi].co.z - (1.466 - 7.284 * scale)) / scale
            raw_z = -(
                key.data[vi].co.y
                - (-0.158 - (-1.245 * scale))
            ) / scale
            u = abs((raw_x - cx) / 0.18)
            canthus = max(0.0, min(1.0, (1.0 - u) / 0.30))
            if not (7.235 < raw_y < 7.30 and raw_z > 1.24 and canthus > 0.0):
                continue
            influence = min(1.0, w) * canthus
            key.data[vi].co.z += min(0.006, 7.286 - raw_y) * influence * scale * 0.18
            changed.add(vi)
        moved[shape_name] = len(changed)
    return moved


def create_eyelid_patch(arm, head_bone: str, side: str, cx: float, material):
    columns, rows = 11, 5
    vertices = []
    for row in range(rows):
        v = row / (rows - 1)
        for column in range(columns):
            u = -1.0 + 2.0 * column / (columns - 1)
            x = cx + u * 0.0145 * (1.0 - 0.08 * v)
            z = 1.478 - 0.003 * (u * u) + v * 0.008
            y = -0.1740 + 0.0010 * (u * u) + 0.0005 * v
            vertices.append((x, y, z))
    faces = []
    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            faces.append((a, a + 1, a + 1 + columns, a + columns))
    mesh = bpy.data.meshes.new(f"NURION_Eyelid_{side}")
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(material)
    for polygon in mesh.polygons:
        polygon.use_smooth = True
    obj = bpy.data.objects.new(f"NURION_Eyelid_{side}", mesh)
    bpy.context.scene.collection.objects.link(obj)
    obj.shape_key_add(name="Basis")
    shape_name = "PRES_Blink_L" if side == "L" else "PRES_Blink_R"
    closed = obj.shape_key_add(name=shape_name)
    for row in range(rows):
        row_weight = 1.0 - 0.78 * (row / (rows - 1))
        for column in range(columns):
            i = row * columns + column
            u = -1.0 + 2.0 * column / (columns - 1)
            neutral_lash = 1.478 - 0.003 * (u * u)
            closed_seam = 1.465 + 0.010 * (u * u)
            dz = (closed_seam - neutral_lash) * row_weight
            closed.data[i].co.z += dz
            closed.data[i].co.y -= 0.0012 * row_weight * max(0.0, 1.0 - u * u)
    world = obj.matrix_world.copy()
    obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", head_bone
    obj.matrix_world = world
    return obj


def create_eyes(arm, head_bone: str, skin_material):
    def disc(name, cx, half_width, half_height, y, material, segments=24):
        verts = [(cx, y, 1.466)]
        for i in range(segments):
            angle = 2.0 * 3.141592653589793 * i / segments
            verts.append(
                (
                    cx + half_width * __import__("math").cos(angle),
                    y,
                    1.466 + half_height * __import__("math").sin(angle),
                )
            )
        faces = [(0, i + 1, ((i + 1) % segments) + 1) for i in range(segments)]
        mesh = bpy.data.meshes.new(name)
        mesh.from_pydata(verts, [], faces)
        mesh.materials.append(material)
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(obj)
        world = obj.matrix_world.copy()
        obj.parent, obj.parent_type, obj.parent_bone = arm, "BONE", head_bone
        obj.matrix_world = world
        return obj

    created = []
    for side, x in (("L", 0.0865 - 0.308 * 0.075), ("R", 0.0865 + 0.308 * 0.075)):
        mat = bpy.data.materials.new(f"NURION_EyeWhite_{side}")
        mat.use_nodes = True
        mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.84, 0.88, 1.0)
        mat.diffuse_color = (0.82, 0.84, 0.88, 1.0)
        eye = disc(f"NURION_Eye_{side}", x, 0.0125, 0.0045, -0.1725, mat)
        created.append(eye.name)

        iris_mat = bpy.data.materials.new(f"NURION_IrisMaterial_{side}")
        iris_mat.use_nodes = True
        iris_mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.01, 0.025, 0.045, 1.0)
        iris_mat.diffuse_color = (0.035, 0.055, 0.075, 1.0)
        iris = disc(f"NURION_Iris_{side}", x, 0.0032, 0.0032, -0.1730, iris_mat, 20)
        created.append(iris.name)
        lid = create_eyelid_patch(arm, head_bone, side, x, skin_material)
        created.append(lid.name)
    return created


def look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Y").to_euler()


def render_preview(path: Path):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    scene.world.color = (0.015, 0.018, 0.025)

    bpy.ops.object.camera_add(location=(0.0865, -0.80, 1.45))
    camera = bpy.context.object
    camera.data.lens = 62
    look_at(camera, Vector((0.0865, -0.04, 1.44)))
    scene.camera = camera

    bpy.ops.object.light_add(type="AREA", location=(0.35, -0.50, 1.75))
    key = bpy.context.object
    key.data.energy = 280
    key.data.size = 1.2
    look_at(key, Vector((0.0865, -0.05, 1.44)))
    bpy.ops.object.light_add(type="AREA", location=(-0.3, -0.25, 1.40))
    fill = bpy.context.object
    fill.data.energy = 90
    fill.data.size = 1.0
    look_at(fill, Vector((0.0865, -0.05, 1.44)))
    bpy.ops.render.render(write_still=True)


def main():
    a = args()
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    bpy.ops.import_scene.gltf(filepath=str(a.base_glb))
    arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    char = next(o for o in bpy.data.objects if o.type == "MESH")
    donor, scale, translation = create_donor(a.donor_obj)

    head_bone = next((b.name for b in arm.data.bones if b.name.lower() == "head"), None)
    if head_bone is None:
        raise RuntimeError("Head bone missing")
    donor_world = donor.matrix_world.copy()
    donor.parent = arm
    donor.parent_type = "BONE"
    donor.parent_bone = head_bone
    donor.matrix_world = donor_world
    moved_vertices = add_blink_shapes(donor, a.weight_map, scale)
    eye_nodes = create_eyes(arm, head_bone, donor.data.materials[0])

    char_positions = [tuple(v.co) for v in char.data.vertices]
    render_preview(a.preview)
    closed_preview = a.preview.with_name(a.preview.stem.replace("neutral", "closed") + a.preview.suffix)
    donor.data.shape_keys.key_blocks["PRES_Blink_L"].value = 1.0
    donor.data.shape_keys.key_blocks["PRES_Blink_R"].value = 1.0
    for name in ("NURION_Eyelid_L", "NURION_Eyelid_R"):
        lid = bpy.data.objects[name]
        lid.data.shape_keys.key_blocks[
            "PRES_Blink_L" if name.endswith("_L") else "PRES_Blink_R"
        ].value = 1.0
    render_preview(closed_preview)
    donor.data.shape_keys.key_blocks["PRES_Blink_L"].value = 0.0
    donor.data.shape_keys.key_blocks["PRES_Blink_R"].value = 0.0
    for name in ("NURION_Eyelid_L", "NURION_Eyelid_R"):
        lid = bpy.data.objects[name]
        lid.data.shape_keys.key_blocks[
            "PRES_Blink_L" if name.endswith("_L") else "PRES_Blink_R"
        ].value = 0.0
    a.output_glb.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(a.output_glb),
        export_format="GLB",
        export_animations=True,
        export_skins=True,
        export_morph=True,
    )
    char_unchanged = char_positions == [tuple(v.co) for v in char.data.vertices]
    evidence = {
        "stage": "FAST-HR02",
        "assembly": "SEPARATE_HEAD_BONE_CHILD",
        "baseGlb": str(a.base_glb),
        "donorObj": str(a.donor_obj),
        "outputGlb": str(a.output_glb),
        "donorMeshName": donor.name,
        "recipientMeshName": char.name,
        "headBone": head_bone,
        "alignment": {
            "scale": scale,
            "translation": list(translation),
            "targetEyeCenter": [0.0865, -0.158, 1.466],
        },
        "oldHeadOcclusion": "DONOR_DEPTH_COVERAGE_NO_RECIPIENT_VERTEX_MUTATION",
        "morphTargets": moved_vertices,
        "eyeNodes": eye_nodes,
        "recipientVertexCount": len(char.data.vertices),
        "recipientPositionsExactInScene": char_unchanged,
        "preview": str(a.preview),
        "closedPreview": str(closed_preview),
    }
    a.evidence_json.parent.mkdir(parents=True, exist_ok=True)
    a.evidence_json.write_text(json.dumps(evidence, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
