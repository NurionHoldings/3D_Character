"""
Create 10 NURION_FACE_* empties with coarse head-frame seeds (NOT Eye Proxy predictions).

Hides NURION eyeballs if present. Saves an edit .blend for manual Material Preview placement.

Usage:
  blender --background --python tools/blender_create_surface_gt_guides.py -- --fbx PATH [--label tennis]
"""

from __future__ import annotations

import argparse
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Vector

SURFACE_KEYS = [
    "eye.inner.L", "eye.inner.R",
    "eye.outer.L", "eye.outer.R",
    "eyelid.upper.L", "eyelid.upper.R",
    "eyelid.lower.L", "eyelid.lower.R",
    "iris.visualCenter.L", "iris.visualCenter.R",
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--label", default="tennis")
    return p.parse_args(argv)


def main() -> int:
    args = _parse(sys.argv)
    ROOT = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(ROOT))

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=args.fbx, automatic_bone_orientation=True, use_anim=False)
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if arms:
        arms[0].data.pose_position = "REST"
        bpy.context.view_layer.update()

    for obj in list(bpy.data.objects):
        if obj.name.startswith("NURION_Eyeball"):
            obj.hide_set(True)
            obj.hide_viewport = True

    from nurion_character_landmarker.core.face.region import evaluate_face_region
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view

    meshes = sorted(
        [o for o in bpy.data.objects if o.type == "MESH"],
        key=lambda o: len(o.data.vertices),
        reverse=True,
    )
    mesh = meshes[0]
    view = build_world_mesh_view(mesh)
    region = evaluate_face_region(mesh, view=view, forward_axis="+Y")
    if region.headFrame is None:
        raise RuntimeError("No head frame")
    fr = region.headFrame
    h = fr.head_height

    # Coarse layout seeds in head-local (not Eye Proxy outputs).
    # User must move onto true texture/surface features.
    coarse = {
        "eye.inner.L": Vector((+0.04 * h, 0.12 * h, 0.08 * h)),
        "eye.inner.R": Vector((-0.04 * h, 0.12 * h, 0.08 * h)),
        "eye.outer.L": Vector((+0.12 * h, 0.10 * h, 0.07 * h)),
        "eye.outer.R": Vector((-0.12 * h, 0.10 * h, 0.07 * h)),
        "eyelid.upper.L": Vector((+0.08 * h, 0.12 * h, 0.11 * h)),
        "eyelid.upper.R": Vector((-0.08 * h, 0.12 * h, 0.11 * h)),
        "eyelid.lower.L": Vector((+0.08 * h, 0.12 * h, 0.05 * h)),
        "eyelid.lower.R": Vector((-0.08 * h, 0.12 * h, 0.05 * h)),
        "iris.visualCenter.L": Vector((+0.08 * h, 0.13 * h, 0.08 * h)),
        "iris.visualCenter.R": Vector((-0.08 * h, 0.13 * h, 0.08 * h)),
    }

    col = bpy.data.collections.get("NURION_Surface_GT")
    if col is None:
        col = bpy.data.collections.new("NURION_Surface_GT")
        bpy.context.scene.collection.children.link(col)

    created = 0
    for name in SURFACE_KEYS:
        obj_name = f"NURION_FACE_{name}"
        obj = bpy.data.objects.get(obj_name)
        if obj is None:
            obj = bpy.data.objects.new(obj_name, None)
            obj.empty_display_type = "SPHERE"
            obj.empty_display_size = 0.008
            col.objects.link(obj)
            created += 1
        obj.location = fr.to_world(coarse[name])
        obj["nurion_landmark"] = name
        obj["nurion_source"] = "MANUAL"
        obj["nurion_domain"] = "surface_gt"
        obj["nurion_seed"] = "COARSE_HEADFRAME_NOT_PROXY"
        obj.hide_set(False)

    blend = (
        ROOT
        / "dist"
        / "v0.3"
        / "face"
        / "alpha2"
        / "annotations"
        / f"{args.label}-surface-gt-edit.blend"
    )
    blend.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    print(
        json_dumps := __import__("json").dumps(
            {
                "created": created,
                "blend": str(blend),
                "keys": SURFACE_KEYS,
                "note": "Place guides on mesh surface in Material Preview; then blender_export_surface_gt.py",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
