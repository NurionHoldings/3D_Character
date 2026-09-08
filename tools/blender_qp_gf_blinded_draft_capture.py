"""Render blinded Draft A/B face captures with identical camera/lighting.

Usage (via Blender):
  blender --background BLEND --python this.py -- --out-dir DIR --draft-label A
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


VIEWS = (
    ("front", 0.0),
    ("left45", 45.0),
    ("right45", -45.0),
)


def _parse_args():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--draft-label", required=True, choices=("A", "B"))
    ap.add_argument("--resolution", type=int, default=1024)
    return ap.parse_args(argv)


def _look_at(cam, target: Vector, up: Vector = Vector((0.0, 0.0, 1.0))):
    direction = target - cam.location
    rot = direction.to_track_quat("-Z", "Y")
    # keep world up roughly stable
    cam.rotation_euler = rot.to_euler()


def _ensure_world():
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("QP_CaptureWorld")
    world = scene.world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.12, 0.12, 0.13, 1.0)
        bg.inputs[1].default_value = 0.35


def _clear_lights():
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)


def _add_light(name: str, loc, energy: float, size: float = 1.2):
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = Vector(loc)
    return obj


def _setup_lighting(head: Vector):
    _clear_lights()
    # Soft identical three-point; avoid blowing out clay materials.
    key = _add_light("CAP_KEY", (head.x + 0.45, head.y - 0.85, head.z + 0.25), 90.0, 1.6)
    _look_at(key, head)
    fill = _add_light("CAP_FILL", (head.x - 0.55, head.y - 0.65, head.z + 0.1), 40.0, 2.0)
    _look_at(fill, head)
    rim = _add_light("CAP_RIM", (0.0, head.y + 0.95, head.z + 0.2), 55.0, 1.4)
    _look_at(rim, head)


def _hide_non_subject():
    # Gate3 assembler applies shape keys to the first mesh object found;
    # in these drafts that is NURION_BP_CanonicalHuman_V1.
    keep = {"NURION_BP_CanonicalHuman_V1"}
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            hide = obj.name not in keep
            obj.hide_render = hide
            obj.hide_viewport = hide
        elif obj.type in {"EMPTY", "ARMATURE", "CAMERA"}:
            obj.hide_render = True


def _head_target() -> Vector:
    for name in ("GT_Head", "NURION_LM_EyeCenter.L", "CTRL_HeadAim"):
        obj = bpy.data.objects.get(name)
        if obj is not None:
            if name == "NURION_LM_EyeCenter.L":
                r = bpy.data.objects.get("NURION_LM_EyeCenter.R")
                if r is not None:
                    return (obj.matrix_world.translation + r.matrix_world.translation) * 0.5
            return obj.matrix_world.translation.copy()
    mesh = bpy.data.objects.get("NURION_BP_CanonicalHuman_V1")
    if mesh is None:
        mesh = next(o for o in bpy.data.objects if o.type == "MESH")
    bbox = [mesh.matrix_world @ Vector(c) for c in mesh.bound_box]
    xs = [v.x for v in bbox]
    ys = [v.y for v in bbox]
    zs = [v.z for v in bbox]
    return Vector((sum(xs) / 8.0, min(ys) - 0.02, max(zs) - 0.12))


def _ensure_capture_camera() -> bpy.types.Object:
    cam_data = bpy.data.cameras.get("QP_BlindCaptureCam") or bpy.data.cameras.new("QP_BlindCaptureCam")
    cam_data.lens = 50.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 100.0
    cam = bpy.data.objects.get("QP_BlindCaptureCam")
    if cam is None:
        cam = bpy.data.objects.new("QP_BlindCaptureCam", cam_data)
        bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    cam.hide_render = False
    return cam


def _place_camera(cam, head: Vector, yaw_deg: float, distance: float = 2.05):
    # Canonical front is -Y. Upper-body framing for low-poly canonical proxy.
    yaw = math.radians(yaw_deg)
    offset = Vector((math.sin(yaw) * distance, -math.cos(yaw) * distance, -0.15))
    cam.location = head + offset
    _look_at(cam, head + Vector((0.0, 0.0, -0.12)))


def _configure_render(resolution: int, out_path: Path):
    scene = bpy.context.scene
    # Blender 5.0.1 enum: BLENDER_EEVEE / BLENDER_WORKBENCH / CYCLES
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGB"
    scene.render.filepath = str(out_path.with_suffix(""))  # Blender appends .png
    scene.render.film_transparent = False
    if hasattr(scene, "eevee"):
        try:
            scene.eevee.taa_render_samples = 32
        except Exception:
            pass


def main() -> int:
    args = _parse_args()
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    _hide_non_subject()
    _ensure_world()
    head = _head_target()
    _setup_lighting(head)
    cam = _ensure_capture_camera()

    for view_name, yaw in VIEWS:
        _place_camera(cam, head, yaw)
        out_path = out_dir / f"Draft_{args.draft_label}_{view_name}.png"
        _configure_render(args.resolution, out_path)
        bpy.ops.render.render(write_still=True)
        print(f"WROTE {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
