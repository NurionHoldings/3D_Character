"""
Face Eligibility only — does not retune frozen Alpha1 ZIP/params.

Usage:
  blender --background --python tools/blender_v03a_face_eligibility.py -- --fbx PATH [--label LABEL]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.3" / "face"
REPORTS = OUT / "reports"
ADDON_ZIP = OUT / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
ADDON_MODULE = "nurion_character_landmarker"
ALPHA1_ZIP_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"
ALPHA1_PARAM = "2bd812ee4be5c63ce1053cfa5023305e2c9a41fe021b4ca01153f7ab3f799095"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--label", default="tennis-face-eligibility")
    return p.parse_args(argv)


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    if not fbx.exists():
        raise FileNotFoundError(fbx)
    if not ADDON_ZIP.exists() or _sha(ADDON_ZIP) != ALPHA1_ZIP_SHA:
        raise RuntimeError("Frozen Alpha1 ZIP missing or hash mismatch — refuse eligibility run")

    sys.path.insert(0, str(ROOT))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted(
        [o for o in bpy.data.objects if o.type == "MESH"],
        key=lambda o: len(o.data.vertices),
        reverse=True,
    )
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError("No mesh")
    mesh = meshes[0]
    if arms:
        arms[0].data.pose_position = "REST"
        bpy.context.view_layer.update()

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.face.parameters import FACE_ALPHA1_PARAMETER_HASH
    from nurion_character_landmarker.core.face.region import evaluate_face_region
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view

    if FACE_ALPHA1_PARAMETER_HASH != ALPHA1_PARAM:
        raise RuntimeError("Parameter hash drifted from frozen Alpha1")

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    body = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)
    region = evaluate_face_region(
        mesh, view=view, body=body, forward_axis=measurements.forward_axis
    )

    # Extra humanoid face cues for Alpha1 direction eval (advisory + hard ear visibility heuristic).
    details = dict(region.details)
    face_verts = region.faceVertexWorld
    ear_visible = {"L": False, "R": False}
    if region.headFrame is not None and face_verts:
        fr = region.headFrame
        for p in face_verts:
            loc = fr.to_local(p)
            if abs(loc.x) < fr.head_height * 0.18:
                continue
            side = "L" if loc.x > 0 else "R"
            # Lateral + slightly back of forward face plane counts as ear-ish exposure.
            if loc.y < fr.head_height * 0.12 and abs(loc.z) < fr.head_height * 0.35:
                ear_visible[side] = True
    details["earRegionVisible"] = ear_visible
    both_ears = bool(ear_visible["L"] and ear_visible["R"])
    checks = dict(region.checks)
    checks["bothEarsVisibleHeuristic"] = both_ears

    eligible = bool(region.eligible and both_ears)
    reason = region.reasonCode if region.eligible else region.reasonCode
    if region.eligible and not both_ears:
        eligible = False
        reason = "FACE_ASSET_INELIGIBLE"

    report = {
        "schema": "NURION_FACE_ELIGIBILITY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx),
        "fbxSha256": _sha(fbx),
        "meshName": mesh.name,
        "armatureRestForced": bool(arms),
        "assetEligible": eligible,
        "reasonCode": "ELIGIBLE" if eligible else reason,
        "checks": checks,
        "eyeballObjects": region.eyeballObjects,
        "excludedObjects": region.excludedObjects,
        "faceVertexCount": len(face_verts),
        "details": details,
        "alpha1Frozen": {
            "packageSha256": ALPHA1_ZIP_SHA,
            "parameterHash": ALPHA1_PARAM,
            "untouched": True,
        },
        "next": (
            "ELIGIBLE — hide predictions, annotate 13 GT points, lock GT SHA, then run Alpha1 eval."
            if eligible
            else "FACE_ASSET_INELIGIBLE — obtain another face-eval character."
        ),
    }
    _write(REPORTS / "face-eligibility-report.json", report)
    _write(OUT / "FACE_ELIGIBILITY_VERDICT.json", {
        "schema": "NURION_FACE_ELIGIBILITY_VERDICT",
        "label": args.label,
        "assetEligible": eligible,
        "reasonCode": report["reasonCode"],
        "fbxSha256": report["fbxSha256"],
        "alpha1PackageSha256": ALPHA1_ZIP_SHA,
        "parameterHash": ALPHA1_PARAM,
        "report": "reports/face-eligibility-report.json",
    })
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if eligible else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
