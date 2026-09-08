#!/usr/bin/env python3
"""Blender: render Jake HR11 visual scenarios from timeline JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import bpy
from mathutils import Vector


def parse_args():
    argv = __import__("sys").argv
    argv = argv[argv.index("--") + 1 :] if "--" in argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", type=Path, required=True)
    p.add_argument("--timeline", type=Path, required=True)
    p.add_argument("--out-dir", type=Path, required=True)
    p.add_argument("--scenario", type=str, default="")
    return p.parse_args(argv)


def clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def find_body():
    for obj in bpy.data.objects:
        if obj.type == "MESH" and "Body" in obj.name:
            return obj
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.data.shape_keys:
            return obj
    raise RuntimeError("No shape-key body mesh found")


def reset_shapes(obj):
    if not obj.data.shape_keys:
        return
    for kb in obj.data.shape_keys.key_blocks:
        if kb.name != "Basis":
            kb.value = 0.0


def apply_weights(obj, weights: dict):
    reset_shapes(obj)
    keys = {kb.name: kb for kb in obj.data.shape_keys.key_blocks}
    # HR11R quality: allow slight overdrive on blink family only (peak seal).
    # Does not change Eye Calibration contracts — donor visual apply only.
    BLINK_FAMILY = {
        "Eye_Blink",
        "Eye_Blink_L",
        "Eye_Blink_R",
        "Eye_Squint_L",
        "Eye_Squint_R",
    }
    for name, value in weights.items():
        if name not in keys:
            continue
        v = float(value)
        if name in BLINK_FAMILY:
            v = max(0.0, min(1.15, v))
            # Ensure shape key can accept overdrive for this render session.
            try:
                keys[name].slider_max = max(float(keys[name].slider_max), 1.15)
            except Exception:
                pass
        else:
            v = max(0.0, min(1.0, v))
        keys[name].value = v


def setup_camera_light(target: Vector):
    bpy.ops.object.camera_add(location=(target.x, target.y - 0.55, target.z + 0.05))
    cam = bpy.context.object
    cam.data.lens = 85
    direction = target - cam.location
    cam.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.camera = cam
    bpy.ops.object.light_add(type="AREA", location=(target.x + 0.2, target.y - 0.4, target.z + 0.35))
    light = bpy.context.object
    light.data.energy = 250
    light.data.size = 0.8


def main():
    args = parse_args()
    data = json.loads(args.timeline.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    if args.scenario:
        scenarios = {args.scenario: scenarios[args.scenario]}

    args.out_dir.mkdir(parents=True, exist_ok=True)
    clear()
    bpy.ops.import_scene.fbx(filepath=str(args.fbx), automatic_bone_orientation=True)
    body = find_body()

    # Focus on head
    coords = [body.matrix_world @ v.co for v in body.data.vertices]
    zs = sorted(c.z for c in coords)
    ys = sorted(c.y for c in coords)
    xs = sorted(c.x for c in coords)
    target = Vector(((xs[0] + xs[-1]) * 0.5, (ys[0] + ys[-1]) * 0.45, zs[int(len(zs) * 0.78)]))
    setup_camera_light(target)

    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    scene.render.fps = 12

    manifest = {}
    for key, scenario in scenarios.items():
        out_sc = args.out_dir / key
        out_sc.mkdir(parents=True, exist_ok=True)
        paths = []
        for frame in scenario["frames"]:
            apply_weights(body, frame.get("jakeWeights") or {})
            path = out_sc / f"frame_{frame['i']:04d}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            paths.append(str(path))
        # also save first/mid/last contact sheets names
        mid = scenario["frames"][len(scenario["frames"]) // 2]["i"]
        manifest[key] = {
            "label": scenario.get("label"),
            "frameCount": len(paths),
            "frames": paths,
            "keyframes": {
                "start": paths[0],
                "mid": str(out_sc / f"frame_{mid:04d}.png"),
                "end": paths[-1],
            },
        }

    (args.out_dir / "render_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"rendered": list(manifest)}, ensure_ascii=True))


if __name__ == "__main__":
    main()
