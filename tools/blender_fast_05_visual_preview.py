#!/usr/bin/env python3
"""FAST-05 — Render visual preview frames (CAM_FULL / CAM_UPPER)."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--glb", type=Path, required=True)
    p.add_argument("--camera-json", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def setup_camera(loc, target, fov_deg):
    cam_data = bpy.data.cameras.new("FAST_CAM")
    cam_obj = bpy.data.objects.new("FAST_CAM", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj
    cam_obj.location = Vector(loc)
    direction = Vector(target) - Vector(loc)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_data.angle = math.radians(fov_deg)
    return cam_obj


def render_frame(glb: Path, cam: dict, out: Path, res: int = 640):
    clear_scene()
    bpy.ops.import_scene.gltf(filepath=str(glb))
    fov = cam.get("fovDeg", cam.get("fov_deg", 40.0))
    setup_camera(cam["location"], cam["target"], fov)
    bpy.context.scene.render.resolution_x = res
    bpy.context.scene.render.resolution_y = int(res * 1.125)
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)


def main():
    args = parse_args()
    cams = json.loads(args.camera_json.read_text(encoding="utf-8"))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, cam in cams.items():
        if name not in ("CAM_FULL", "CAM_UPPER"):
            continue
        render_frame(args.glb, cam, args.out_dir / f"FAST-05_preview_{name}.png")


if __name__ == "__main__":
    main()
