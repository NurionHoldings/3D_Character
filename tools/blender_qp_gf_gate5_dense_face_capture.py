"""Blender renderer for Gate 5 dense identity face OBJ drafts (axis-stable)."""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VIEWS = (("front", 0.0), ("left45", 45.0), ("right45", -45.0))


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--draft-label", required=True, choices=("A", "B"))
    ap.add_argument("--resolution", type=int, default=1024)
    return ap.parse_args(argv)


def _clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in list(bpy.data.meshes):
        bpy.data.meshes.remove(block)


def _look_at(obj, target: Vector):
    # Dense draft is Z-up; keep world +Z as camera up (not Blender Y-up default).
    direction = target - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Z").to_euler()


def _load_obj_axis_stable(path: Path):
    """Parse OBJ into Blender mesh without importer axis remapping.

    Dense draft frame: X right, Y depth (nose toward -Y), Z up.
    """
    verts = []
    faces = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            parts = line.split()
            verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
        elif line.startswith("f "):
            idx = []
            for tok in line.split()[1:]:
                idx.append(int(tok.split("/")[0]) - 1)
            if len(idx) >= 3:
                faces.append(idx[:3])
    mesh = bpy.data.meshes.new("DenseIdentityFace")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    obj = bpy.data.objects.new("DenseIdentityFace", mesh)
    bpy.context.scene.collection.objects.link(obj)
    return obj


def main() -> int:
    args = _parse()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _clear_scene()
    mesh = _load_obj_axis_stable(Path(args.obj))
    bpy.context.view_layer.objects.active = mesh
    mesh.select_set(True)

    # Center on geometry bounds
    coords = [v.co.copy() for v in mesh.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    center = Vector(((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5))
    mesh.location = -center
    bpy.context.view_layer.update()

    bpy.ops.object.shade_smooth()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")

    mat = bpy.data.materials.new("DenseFaceClay")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.86, 0.74, 0.66, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.42
    mesh.data.materials.clear()
    mesh.data.materials.append(mat)

    def add_light(name, loc, energy, size=1.6):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = size
        obj = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(obj)
        obj.location = Vector(loc)
        _look_at(obj, Vector((0.0, 0.0, 0.0)))
        return obj

    # Lights in front of face (negative Y)
    add_light("Key", (0.55, -1.2, 0.55), 160)
    add_light("Fill", (-0.7, -1.0, 0.2), 60)
    add_light("Rim", (0.0, 1.2, 0.35), 80)

    world = bpy.data.worlds.new("DenseCaptureWorld")
    bpy.context.scene.world = world

    cam_data = bpy.data.cameras.new("DenseCaptureCam")
    cam_data.lens = 85
    cam = bpy.data.objects.new("DenseCaptureCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    coords = [mesh.matrix_world @ v.co for v in mesh.data.vertices]
    xs = [v.x for v in coords]
    ys = [v.y for v in coords]
    zs = [v.z for v in coords]
    span_x = max(xs) - min(xs)
    span_z = max(zs) - min(zs)
    span = max(span_x, span_z, 0.35)
    dist = span * 2.35
    # Aim slightly above geometric center (toward eyes)
    target = Vector((0.0, 0.0, (min(zs) + max(zs)) * 0.5 + 0.08 * span_z))

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    for view, yaw_deg in VIEWS:
        yaw = math.radians(yaw_deg)
        # Orbit around +Z; face front is -Y
        cam.location = target + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, 0.04 * span))
        _look_at(cam, target)
        out = out_dir / f"Draft_{args.draft_label}_{view}"
        scene.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
        print(f"WROTE {out}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
