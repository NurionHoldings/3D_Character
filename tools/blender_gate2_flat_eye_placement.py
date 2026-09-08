"""
Run Gate 2 — Flat Eye Placement (Tennis development / Captain cross-validation).

Does not modify locked Gate 1 sources. Creates only NURION_EyePlane.L/R.

Usage:
  blender --background --python tools/blender_gate2_flat_eye_placement.py -- \\
    --fbx PATH --label tennis
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
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate2"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)

EVIDENCE_VIEWS = (
    ("FRONT", 0.0, 0.0),
    ("THREE_QUARTER_L", 35.0, 0.0),
    ("THREE_QUARTER_R", -35.0, 0.0),
    ("LEFT_90", 90.0, 0.0),
    ("RIGHT_90", -90.0, 0.0),
    ("TOP", 0.0, 55.0),
    ("BOTTOM", 0.0, -35.0),
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


def _render_evidence(axes, out_dir: Path, do_render: bool) -> dict:
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
        cam_data = bpy.data.cameras.new(name=f"NURION_GATE2_{name}")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(axes.head_height * 1.5, 0.25)
        cam_obj = bpy.data.objects.new(f"NURION_GATE2_CAM_{name}", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        cam_obj.matrix_world = mat
        path = out_dir / f"evidence_{name.lower()}.png"
        entry = {"view": name, "imagePath": _rel(path), "rendered": False}
        if do_render:
            scene.camera = cam_obj
            scene.render.filepath = str(path)
            try:
                bpy.ops.render.render(write_still=True)
                entry["rendered"] = path.exists()
            except Exception as exc:  # noqa: BLE001
                entry["renderError"] = str(exc)
        views.append(entry)
    return {"schema": "NURION_GATE2_MULTIVIEW_EVIDENCE", "views": views}


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate2.flat_eye_placement import assert_gate1_sources_locked, place_flat_eye_planes
    from nurion_universal_eye.gate2.flat_eye_validator import validate_flat_eye_placement
    from nurion_universal_eye.gate2.parameters import parameter_hash

    assert_gate1_sources_locked(ROOT)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    profiles = []
    results = []
    for i in range(3):
        create = i == 0
        r = place_flat_eye_planes(mesh_name=args.mesh, create_meshes=create, root=ROOT)
        results.append(r)
        profiles.append(r.to_profile())

    result = results[0]
    report = validate_flat_eye_placement(
        result,
        determinism_profiles=profiles,
        mesh_name=args.mesh,
    )
    evidence = _render_evidence(result.basis.axes, out_dir / "evidence", do_render=not args.no_render)

    profile = profiles[0]
    profile["assetRole"] = args.role
    profile["characterId"] = args.label
    profile["fbx"] = str(fbx).replace("\\", "/")
    profile["fbxSha256"] = _sha(fbx)
    profile["createdAt"] = datetime.now(timezone.utc).isoformat()
    profile["gate1Locked"] = True

    status = {
        "schema": "NURION_GATE2_STATUS",
        "gate": 2,
        "name": "FLAT_EYE_PLACEMENT",
        "GATE1": "LOCKED_PASS",
        "GATE2": report["verdict"],
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "profileSha256": report.get("profileSha256"),
        "fbxSha256": profile["fbxSha256"],
        "gates": report["gates"],
        "manualGt": False,
        "convexEye": False,
        "motion": "INACTIVE",
        "expression": "INACTIVE",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": _rel(out_dir / "FLAT_EYE_PLACEMENT_PROFILE.json"),
            "report": _rel(out_dir / "GATE2_VALIDATION_REPORT.json"),
            "evidence": _rel(out_dir / "GATE2_MULTIVIEW_EVIDENCE.json"),
        },
    }

    _write(out_dir / "FLAT_EYE_PLACEMENT_PROFILE.json", profile)
    _write(out_dir / "GATE2_VALIDATION_REPORT.json", report)
    _write(out_dir / "GATE2_MULTIVIEW_EVIDENCE.json", evidence)
    _write(out_dir / "GATE2_STATUS.json", status)

    # Track-level status (do not rewrite Gate1 lock files)
    root_status = {
        "track": "NURION Universal Eye Calibration Alpha3",
        "designReset": True,
        "gate1": "LOCKED_PASS",
        "gate1CrossValidation": "PASS",
        "gate2": report["verdict"],
        "gate2Asset": args.label,
        "gate2Role": args.role,
        "convexMotionExpression": "HOLD",
        "nextDecision": report["nextDecision"],
        "sealed": False,
        "parameterChangeDeniedForGate1": True,
        "gate2ParameterHash": parameter_hash(),
    }
    _write(ROOT / "STATUS.json", root_status)

    print(json.dumps({"verdict": report["verdict"], "gates": report["gates"], "out": str(out_dir)}, indent=2))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
