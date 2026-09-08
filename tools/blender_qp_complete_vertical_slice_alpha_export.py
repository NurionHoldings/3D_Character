"""Alpha vertical-slice Blender: head captures + GLB export from assembled blend."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VIEWS = (("front", 0.0), ("left45", 45.0), ("right45", -45.0))


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--blend", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", required=True)
    ap.add_argument("--resolution", type=int, default=768)
    ap.add_argument("--export-glb", action="store_true")
    ap.add_argument("--export-video", action="store_true")
    return ap.parse_args(argv)


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _head_target() -> Vector:
    for name in ("GT_Head", "NURION_LM_EyeCenter.L", "CTRL_HeadAim"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            if name == "NURION_LM_EyeCenter.L":
                r = bpy.data.objects.get("NURION_LM_EyeCenter.R")
                if r is not None:
                    return (obj.matrix_world.translation + r.matrix_world.translation) * 0.5
            return obj.matrix_world.translation.copy()
    mesh = next(o for o in bpy.data.objects if o.type == "MESH")
    bbox = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
    xs, ys, zs = [v.x for v in bbox], [v.y for v in bbox], [v.z for v in bbox]
    return Vector((sum(xs) / 8.0, min(ys) - 0.02, max(zs) - 0.12))


def _mesh():
    for name in ("NURION_BP_CanonicalHuman_V1", "NURION_W_CanonicalHuman_V1"):
        o = bpy.data.objects.get(name)
        if o and o.type == "MESH":
            return o
    return next(o for o in bpy.data.objects if o.type == "MESH")


def main() -> int:
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(Path(args.blend)))
    mesh = _mesh()
    head = _head_target()

    # Hide non-mesh clutter for capture
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj != mesh:
            obj.hide_render = True
        if obj.type in {"EMPTY", "ARMATURE"}:
            obj.hide_render = True

    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    def add_light(name, loc, energy):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.size = 1.5
        o = bpy.data.objects.new(name, data)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, head)

    add_light("K", (head.x + 0.45, head.y - 0.95, head.z + 0.25), 110)
    add_light("F", (head.x - 0.55, head.y - 0.7, head.z + 0.1), 45)
    add_light("R", (head.x, head.y + 1.0, head.z + 0.2), 60)

    cam_data = bpy.data.cameras.new("AlphaCam")
    cam_data.lens = 55
    cam = bpy.data.objects.new("AlphaCam", cam_data)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = args.resolution
    scene.render.resolution_y = args.resolution
    scene.render.image_settings.file_format = "PNG"
    dist = 2.05

    captures = []
    for view, yaw_deg in VIEWS:
        yaw = math.radians(yaw_deg)
        cam.location = head + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, -0.12))
        _look_at(cam, head + Vector((0.0, 0.0, -0.1)))
        path = out / f"{args.label}_{view}"
        scene.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        captures.append(f"{path.name}.png")

    glb_path = None
    if args.export_glb:
        glb_path = str(out / f"{args.label}.glb")
        bpy.ops.export_scene.gltf(filepath=glb_path, export_format="GLB", use_selection=False)

    video_path = None
    if args.export_video:
        # Short yaw sweep as homepage motion proxy (no audio).
        scene.render.image_settings.file_format = "FFMPEG"
        scene.render.ffmpeg.format = "MPEG4"
        scene.render.ffmpeg.codec = "H264"
        scene.frame_start = 1
        scene.frame_end = 36
        video_path = str(out / f"{args.label}_turntable.mp4")
        scene.render.filepath = video_path
        for f in range(1, 37):
            scene.frame_set(f)
            yaw = math.radians((f - 1) * 5.0 - 45.0)
            cam.location = head + Vector((math.sin(yaw) * dist, -math.cos(yaw) * dist, -0.12))
            _look_at(cam, head + Vector((0.0, 0.0, -0.1)))
        bpy.ops.render.render(animation=True)

    meta = {
        "label": args.label,
        "mesh": mesh.name,
        "captures": captures,
        "glb": glb_path,
        "video": video_path,
        "silentPerformanceProxy": ["NATURAL_IDLE", "EYE_CONTACT", "SERVICE_INTRO_GESTURE"],
        "production": "NO-GO",
    }
    (out / f"{args.label}_export_meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
