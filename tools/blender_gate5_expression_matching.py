"""
Run Gate 5 — Expression–Eye Matching.

Does not mutate Gate1–4B sources or parameter hashes.
Does not generate face bones, eyebrows, or lip sync.

Usage:
  blender --background --python tools/blender_gate5_expression_matching.py -- \\
    --fbx PATH --label tennis --role DEVELOPMENT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Matrix

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate5"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)

EVIDENCE_VIEWS = (
    ("FRONT", 0.0, 0.0),
    ("YAW_30_L", 30.0, 0.0),
    ("YAW_60_L", 60.0, 0.0),
    ("LEFT_90", 90.0, 0.0),
    ("RIGHT_90", -90.0, 0.0),
)

EVIDENCE_STATES = (
    "NEUTRAL",
    "FRIENDLY_SMILE",
    "EXPLAINING",
    "EMPATHY",
    "FOCUS",
    "SURPRISE",
    "THINKING",
    "SPEAKING",
)


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--label", default="tennis")
    p.add_argument("--out-dir", default="")
    p.add_argument("--mesh", default="char1")
    p.add_argument("--role", default="DEVELOPMENT", choices=["DEVELOPMENT", "CROSS_VALIDATION"])
    p.add_argument("--no-render", action="store_true")
    return p.parse_args(argv)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _render_views(axes, out_dir: Path, do_render: bool, tag: str) -> list:
    out_dir.mkdir(parents=True, exist_ok=True)
    dist = max(axes.head_height * 2.8, 0.35)
    scene = bpy.context.scene
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.image_settings.file_format = "PNG"
    views = []
    for name, yaw_deg, pitch_deg in EVIDENCE_VIEWS:
        yaw = math.radians(yaw_deg)
        pitch = math.radians(pitch_deg)
        offset = (
            -axes.forward * math.cos(yaw) * math.cos(pitch) * dist
            + axes.right * math.sin(yaw) * math.cos(pitch) * dist
            + axes.up * math.sin(pitch) * dist
        )
        loc = axes.origin + offset
        direction = (axes.origin - loc).normalized()
        up = axes.up
        right = direction.cross(up)
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
        cam_data = bpy.data.cameras.new(name=f"NURION_GATE5_{tag}_{name}")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(axes.head_height * 1.5, 0.25)
        cam_obj = bpy.data.objects.new(f"NURION_GATE5_CAM_{tag}_{name}", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.matrix_world = mat
        path = out_dir / f"evidence_{tag.lower()}_{name.lower()}.png"
        entry = {"view": name, "state": tag, "imagePath": _rel(path), "rendered": False}
        if do_render:
            scene.camera = cam_obj
            scene.render.filepath = str(path)
            try:
                bpy.ops.render.render(write_still=True)
                entry["rendered"] = path.exists()
            except Exception as exc:  # noqa: BLE001
                entry["renderError"] = str(exc)
        views.append(entry)
    return views


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate5.expression_matching import apply_expression_pose, run_expression_matching
    from nurion_universal_eye.gate5.expression_recipes import resolve_reaction
    from nurion_universal_eye.gate5.expression_validator import validate_expression_matching
    from nurion_universal_eye.gate5.parameters import GATE5_PARAMETERS, parameter_hash

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    mesh_arg = args.mesh if args.mesh else ""
    profiles = []
    results = []
    for _i in range(3):
        r = run_expression_matching(mesh_name=mesh_arg, root=ROOT, create_meshes=True)
        results.append(r)
        profiles.append(r.to_profile())

    result = results[0]
    report = validate_expression_matching(result, root=ROOT, determinism_profiles=profiles)

    evidence_views = []
    if not args.no_render:
        axes = result.blink.gaze.convex.flat.basis.axes
        planes = result.blink.gaze.convex.flat.planes
        for state in EVIDENCE_STATES:
            inten = 0.0 if state == "NEUTRAL" else 1.0
            speech = state == "SPEAKING"
            reaction = resolve_reaction(state=state, intensity=inten, speech_active=speech)
            apply_expression_pose(
                planes=planes,
                axes=axes,
                ellipses=result.ellipses,
                apertures=result.apertures,
                bulges=result.bulges,
                reaction=reaction,
                attention_world=None,
                face_bvh=result.face_bvh,
            )
            evidence_views.extend(_render_views(axes, out_dir / "evidence", True, state))

    evidence = {
        "schema": "NURION_GATE5_MULTIVIEW_EVIDENCE",
        "views": evidence_views,
        "states": list(EVIDENCE_STATES),
        "textureNote": result.texture_note,
    }

    profile = profiles[0]
    profile["assetRole"] = args.role
    profile["characterId"] = args.label
    profile["fbx"] = str(fbx).replace("\\", "/")
    profile["fbxSha256"] = _sha(fbx)
    profile["createdAt"] = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_GATE5_STATUS",
        "gate": 5,
        "name": "EXPRESSION_EYE_MATCHING",
        "GATE1": "LOCKED_PASS",
        "GATE2": "LOCKED_PASS",
        "GATE3": "LOCKED_PASS",
        "GATE4A": "LOCKED_PASS",
        "GATE4B": "LOCKED_PASS",
        "GATE4A_PARAMETER": GATE5_PARAMETERS["requiredGate4aParameterHash"],
        "GATE4B_PARAMETER": GATE5_PARAMETERS["requiredGate4bParameterHash"],
        "GATE5": report["verdict"],
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "profileSha256": report.get("profileSha256"),
        "fbxSha256": profile["fbxSha256"],
        "gates": report["gates"],
        "metrics": report["metrics"],
        "faceBoneGeneration": "HOLD",
        "eyebrowRig": "HOLD",
        "lipSync": "HOLD",
        "headBodyMotion": "HOLD",
        "beautyMaterial": "HOLD",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": _rel(out_dir / "EXPRESSION_MATCH_PROFILE.json"),
            "report": _rel(out_dir / "GATE5_VALIDATION_REPORT.json"),
            "evidence": _rel(out_dir / "GATE5_MULTIVIEW_EVIDENCE.json"),
        },
    }

    _write(out_dir / "EXPRESSION_MATCH_PROFILE.json", profile)
    _write(out_dir / "GATE5_VALIDATION_REPORT.json", report)
    _write(out_dir / "GATE5_MULTIVIEW_EVIDENCE.json", evidence)
    _write(out_dir / "GATE5_STATUS.json", status)

    print(
        json.dumps(
            {
                "GATE5": report["verdict"],
                "parameterHash": parameter_hash(),
                "fails": report.get("fails"),
                "frameCount": report["metrics"].get("frameCount"),
            },
            indent=2,
        )
    )
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
