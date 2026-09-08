"""
Gate 7A practical video evidence (PNG sequence; optional ffmpeg MP4).

Quality evidence only — does not tune Gate parameters.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import traceback
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)

# Ordered practical shots (name, yaw_deg, dist_scale, expression, gaze_yaw_n, gaze_pitch_n, blink, note)
SHOTS = [
    ("01_front_neutral", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("02_yaw30_neutral", 30.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("03_yaw60_neutral", 60.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("04_gaze_center", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("05_gaze_left", 0.0, 1.35, "NEUTRAL", 0.85, 0.0, 0.0, "HERO"),
    ("06_gaze_right", 0.0, 1.35, "NEUTRAL", -0.85, 0.0, 0.0, "HERO"),
    ("07_gaze_up", 0.0, 1.35, "NEUTRAL", 0.0, 0.85, 0.0, "HERO"),
    ("08_gaze_down", 0.0, 1.35, "NEUTRAL", 0.0, -0.85, 0.0, "HERO"),
    ("09_near_converge", 0.0, 1.35, "FOCUS", 0.0, 0.0, 0.0, "HERO_NEAR"),
    ("10_blink_single", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 1.0, "HERO"),
    ("11_blink_open", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("12_double_blink_a", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 1.0, "HERO"),
    ("13_double_blink_b", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("14_double_blink_c", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 1.0, "HERO"),
    ("15_double_blink_d", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("16_expr_neutral", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("17_expr_smile", 0.0, 1.35, "FRIENDLY_SMILE", 0.0, -0.1, 0.0, "HERO"),
    ("18_expr_empathy", 0.0, 1.35, "EMPATHY", 0.0, -0.05, 0.15, "HERO"),
    ("19_expr_speaking", 0.0, 1.35, "SPEAKING", 0.0, 0.0, 0.0, "HERO"),
    ("20_return_neutral", 0.0, 1.35, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("21_mobile_hero", 0.0, 1.2, "NEUTRAL", 0.0, 0.0, 0.0, "HERO"),
    ("22_upper_body", 0.0, 2.4, "NEUTRAL", 0.0, 0.0, 0.0, "UPPER"),
]


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--label", default="tennis")
    p.add_argument("--mesh", default="char1")
    p.add_argument("--out-dir", default="")
    return p.parse_args(argv)


def _render(axes, path: Path, yaw_deg: float, dist_scale: float) -> bool:
    dist = max(axes.head_height * dist_scale, 0.2)
    yaw = math.radians(yaw_deg)
    offset = -axes.forward * math.cos(yaw) * dist + axes.right * math.sin(yaw) * dist
    loc = axes.origin + offset
    direction = (axes.origin - loc).normalized()
    right = direction.cross(axes.up)
    if right.length < 1e-8:
        right = axes.right.copy()
    right.normalize()
    up = right.cross(direction).normalized()
    mat = Matrix(
        (
            (right.x, up.x, -direction.x, loc.x),
            (right.y, up.y, -direction.y, loc.y),
            (right.z, up.z, -direction.z, loc.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    cam_data = bpy.data.cameras.new(name="NURION_G7A_VID")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(axes.head_height * (1.15 if dist_scale < 2.0 else 1.7), 0.2)
    cam = bpy.data.objects.new("NURION_G7A_VID_OBJ", cam_data)
    bpy.context.collection.objects.link(cam)
    cam.matrix_world = mat
    scene = bpy.context.scene
    scene.camera = cam
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.image_settings.file_format = "PNG"
    scene.render.filepath = str(path)
    try:
        bpy.ops.render.render(write_still=True)
        return path.exists()
    except Exception:
        return False


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir) if args.out_dir else ROOT / "dist/v0.3/universal_eye/gate7a" / args.label / "practical_video"
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    frames_dir = out_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate4b.blink_motion import apply_blink_amounts
    from nurion_universal_eye.gate5.expression_matching import apply_expression_pose
    from nurion_universal_eye.gate5.expression_recipes import resolve_reaction
    from nurion_universal_eye.gate5.expression_matching import _target_from_yaw_pitch
    from nurion_universal_eye.gate6.beauty_integration import apply_beauty_stack, run_beauty_integration

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    mesh = args.mesh if args.mesh else ""
    beauty = run_beauty_integration(
        mesh_name=mesh, root=ROOT, preset="NATURAL", tier="High", evaluate_all_presets=False
    )
    planes = beauty.expression.blink.gaze.convex.flat.planes
    axes = beauty.expression.blink.gaze.convex.flat.basis.axes
    eu = sum(float(p.eye_unit) for p in planes.values()) / 2.0
    apertures = beauty.expression.apertures
    bulges = beauty.expression.bulges
    face_bvh = beauty.expression.face_bvh

    catalog = []
    for idx, (name, yaw, dist, state, gy, gp, blink, note) in enumerate(SHOTS, start=1):
        reaction = resolve_reaction(
            state=state,
            intensity=0.0 if state == "NEUTRAL" else 1.0,
            speech_active=(state == "SPEAKING"),
        )
        # Override gaze via attention target
        if note == "HERO_NEAR":
            mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
            attn = mid + axes.forward.normalized() * (eu * 8.0)
        else:
            attn = _target_from_yaw_pitch(axes, planes, eu, gy, gp)
        apply_expression_pose(
            planes=planes,
            axes=axes,
            ellipses=beauty.expression.ellipses,
            apertures=apertures,
            bulges=bulges,
            reaction=reaction,
            attention_world=attn,
            face_bvh=face_bvh,
        )
        if blink > 0.01:
            apply_blink_amounts(
                planes=planes,
                apertures=apertures,
                bulges=bulges,
                amount_l=blink,
                amount_r=blink,
                face_bvh=face_bvh,
            )
        apply_beauty_stack(planes=planes, axes=axes, preset="NATURAL", tier="High", create_layers=False)
        path = frames_dir / f"{idx:02d}_{name}.png"
        ok = _render(axes, path, yaw, dist)
        catalog.append({"index": idx, "name": name, "path": str(path).replace("\\", "/"), "ok": ok, "note": note})

    # Optional ffmpeg stitch
    mp4 = out_dir / f"{args.label}_practical_video.mp4"
    ffmpeg = shutil.which("ffmpeg")
    stitched = False
    if ffmpeg:
        # concat demuxer
        lst = out_dir / "frames.txt"
        lines = []
        for c in catalog:
            if c["ok"]:
                lines.append(f"file '{Path(c['path']).as_posix()}'")
                lines.append("duration 0.5")
        if lines:
            lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
            cmd = [
                ffmpeg,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(lst),
                "-vsync",
                "vfr",
                "-pix_fmt",
                "yuv420p",
                str(mp4),
            ]
            try:
                subprocess.run(cmd, check=True, capture_output=True)
                stitched = mp4.exists()
            except Exception:
                stitched = False

    doc = {
        "schema": "NURION_GATE7A_PRACTICAL_VIDEO",
        "asset": args.label,
        "qualityEvidenceOnly": True,
        "parameterTuning": "DENY",
        "frames": catalog,
        "mp4": str(mp4).replace("\\", "/") if stitched else None,
        "stitched": stitched,
    }
    (out_dir / "PRACTICAL_VIDEO_CATALOG.json").write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"asset": args.label, "frames": len(catalog), "stitched": stitched}, indent=2))
    return 0 if all(c["ok"] for c in catalog) else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
