"""
Run Gate 6 — Beauty Eye & Final Visual Integration.

Geometry/motion from Gate1–5 are frozen. Visual materials/layers only.
FINAL SEAL remains HOLD; fresh holdout required after this gate.

Usage:
  blender --background --python tools/blender_gate6_beauty_eye.py -- \\
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
DEFAULT_OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate6"
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

LIGHTING_SCENES = ("LOUNGE_BRIGHT", "INDOOR", "LOW_KEY")
DISTANCES = ("HERO", "UPPER_BODY", "DIAGNOSTIC")
EXPR_STATES = ("NEUTRAL", "FRIENDLY_SMILE", "EMPATHY", "SPEAKING")


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
    p.add_argument("--preset", default="NATURAL")
    p.add_argument("--tier", default="High")
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


def _setup_world(scene_name: str) -> None:
    world = bpy.data.worlds.new(f"NURION_G6_{scene_name}")
    bpy.context.scene.world = world
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    out = nodes.new("ShaderNodeOutputWorld")
    bg = nodes.new("ShaderNodeBackground")
    strength = {"LOUNGE_BRIGHT": 1.4, "INDOOR": 0.7, "LOW_KEY": 0.18}.get(scene_name, 0.7)
    color = {
        "LOUNGE_BRIGHT": (0.95, 0.93, 0.88, 1.0),
        "INDOOR": (0.75, 0.78, 0.82, 1.0),
        "LOW_KEY": (0.15, 0.16, 0.18, 1.0),
    }.get(scene_name, (0.7, 0.7, 0.7, 1.0))
    bg.inputs["Color"].default_value = color
    bg.inputs["Strength"].default_value = strength
    links.new(bg.outputs["Background"], out.inputs["Surface"])


def _render_cam(axes, out_path: Path, yaw_deg: float, dist_scale: float, do_render: bool) -> dict:
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
    cam_data = bpy.data.cameras.new(name="NURION_GATE6_CAM")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(axes.head_height * (1.2 if dist_scale < 2.0 else 1.6), 0.2)
    cam_obj = bpy.data.objects.new("NURION_GATE6_CAM_OBJ", cam_data)
    bpy.context.collection.objects.link(cam_obj)
    cam_obj.matrix_world = mat
    entry = {"imagePath": _rel(out_path), "rendered": False}
    if do_render:
        scene = bpy.context.scene
        scene.render.resolution_x = 640
        scene.render.resolution_y = 640
        scene.render.image_settings.file_format = "PNG"
        scene.camera = cam_obj
        scene.render.filepath = str(out_path)
        try:
            bpy.ops.render.render(write_still=True)
            entry["rendered"] = out_path.exists()
        except Exception as exc:  # noqa: BLE001
            entry["renderError"] = str(exc)
    return entry


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate5.expression_matching import apply_expression_pose
    from nurion_universal_eye.gate5.expression_recipes import resolve_reaction
    from nurion_universal_eye.gate6.beauty_integration import apply_beauty_stack, run_beauty_integration
    from nurion_universal_eye.gate6.beauty_validator import validate_beauty_integration
    from nurion_universal_eye.gate6.parameters import GATE6_PARAMETERS, parameter_hash

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    mesh_arg = args.mesh if args.mesh else ""
    profiles = []
    results = []
    for _i in range(3):
        r = run_beauty_integration(
            mesh_name=mesh_arg,
            root=ROOT,
            preset=args.preset,
            tier=args.tier,
            evaluate_all_presets=True,
        )
        results.append(r)
        profiles.append(r.to_profile())

    result = results[0]
    report = validate_beauty_integration(result, root=ROOT, determinism_profiles=profiles)

    evidence = {"schema": "NURION_GATE6_MULTIVIEW_EVIDENCE", "views": []}
    if not args.no_render:
        axes = result.expression.blink.gaze.convex.flat.basis.axes
        planes = result.expression.blink.gaze.convex.flat.planes
        dist_map = {"HERO": 1.35, "UPPER_BODY": 2.4, "DIAGNOSTIC": 0.95}
        ev_dir = out_dir / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        # Representative evidence matrix (full combinatorial grid is redundant for gate lock)
        plan = []
        for light in LIGHTING_SCENES:
            plan.append((light, "HERO", "NEUTRAL", True))  # multiview
        for dist_name in DISTANCES:
            plan.append(("INDOOR", dist_name, "NEUTRAL", dist_name == "HERO"))
        for state in EXPR_STATES:
            plan.append(("INDOOR", "HERO", state, state == "NEUTRAL"))
        plan.append(("LOUNGE_BRIGHT", "UPPER_BODY", "FRIENDLY_SMILE", False))
        plan.append(("LOW_KEY", "DIAGNOSTIC", "SPEAKING", False))

        seen = set()
        for light, dist_name, state, multiview in plan:
            key = (light, dist_name, state, multiview)
            if key in seen:
                continue
            seen.add(key)
            _setup_world(light)
            apply_expression_pose(
                planes=planes,
                axes=axes,
                ellipses=result.expression.ellipses,
                apertures=result.expression.apertures,
                bulges=result.expression.bulges,
                reaction=resolve_reaction(
                    state=state,
                    intensity=0.0 if state == "NEUTRAL" else 1.0,
                    speech_active=(state == "SPEAKING"),
                ),
                attention_world=None,
                face_bvh=result.expression.face_bvh,
            )
            apply_beauty_stack(
                planes=planes,
                axes=axes,
                preset=result.preset,
                tier=result.tier,
                create_layers=False,
            )
            views = EVIDENCE_VIEWS if multiview else (("FRONT", 0.0, 0.0),)
            for view, yaw, _pitch in views:
                if view not in ("FRONT", "YAW_30_L", "YAW_60_L", "LEFT_90"):
                    continue
                tag = f"{light.lower()}_{dist_name.lower()}_{state.lower()}_{view.lower()}"
                path = ev_dir / f"evidence_{tag}.png"
                entry = _render_cam(axes, path, yaw, dist_map[dist_name], True)
                entry.update(
                    {
                        "lighting": light,
                        "distance": dist_name,
                        "state": state,
                        "view": view,
                    }
                )
                evidence["views"].append(entry)

    profile = profiles[0]
    profile["assetRole"] = args.role
    profile["characterId"] = args.label
    profile["fbx"] = str(fbx).replace("\\", "/")
    profile["fbxSha256"] = _sha(fbx)
    profile["createdAt"] = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_GATE6_STATUS",
        "gate": 6,
        "name": "BEAUTY_EYE_INTEGRATION",
        "GATE1": "LOCKED_PASS",
        "GATE2": "LOCKED_PASS",
        "GATE3": "LOCKED_PASS",
        "GATE4A": "LOCKED_PASS",
        "GATE4B": "LOCKED_PASS",
        "GATE5": "LOCKED_PASS",
        "GATE5_PARAMETER": GATE6_PARAMETERS["requiredGate5ParameterHash"],
        "GATE6": report["verdict"],
        "role": args.role,
        "asset": args.label,
        "preset": result.preset,
        "tier": result.tier,
        "parameterHash": parameter_hash(),
        "profileSha256": report.get("profileSha256"),
        "fbxSha256": profile["fbxSha256"],
        "gates": report["gates"],
        "metrics": report["metrics"],
        "finalSeal": "HOLD",
        "freshHoldoutRequired": True,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": _rel(out_dir / "BEAUTY_EYE_PROFILE.json"),
            "report": _rel(out_dir / "GATE6_VALIDATION_REPORT.json"),
            "evidence": _rel(out_dir / "GATE6_MULTIVIEW_EVIDENCE.json"),
        },
    }

    _write(out_dir / "BEAUTY_EYE_PROFILE.json", profile)
    _write(out_dir / "GATE6_VALIDATION_REPORT.json", report)
    _write(out_dir / "GATE6_MULTIVIEW_EVIDENCE.json", evidence)
    _write(out_dir / "GATE6_STATUS.json", status)

    print(
        json.dumps(
            {
                "GATE6": report["verdict"],
                "parameterHash": parameter_hash(),
                "preset": result.preset,
                "fails": report.get("fails"),
                "finalSeal": "HOLD",
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
