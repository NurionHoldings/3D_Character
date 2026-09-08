"""
Gate 7A reinstall test: install RC ZIP, enable addon, run pipeline once.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP = (
    ROOT
    / "dist"
    / "v0.3"
    / "universal_eye"
    / "gate7a"
    / "package"
    / "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
)
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)
ADDON_MODULE = "nurion_universal_eye_calibration"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default=str(DEFAULT_ZIP))
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--mesh", default="char1")
    p.add_argument("--out", default="dist/v0.3/universal_eye/gate7a/REINSTALL_TEST.json")
    return p.parse_args(argv)


def main() -> int:
    args = _parse(sys.argv)
    zpath = Path(args.zip)
    fbx = Path(args.fbx)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    if not zpath.exists():
        raise FileNotFoundError(zpath)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(zpath), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    scene = bpy.context.scene
    scene.nurion_uec_mesh_name = args.mesh
    scene.nurion_uec_preset = "NATURAL"
    scene.nurion_uec_tier = "High"

    # Factory reset clears addons — ensure module path works via installed addon
    result = {"addonEnabled": ADDON_MODULE in bpy.context.preferences.addons}
    try:
        bpy.ops.nurion_uec.assert_locks()
        result["assertLocks"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        result["assertLocks"] = f"FAIL:{exc}"

    try:
        bpy.ops.nurion_uec.run_pipeline()
        result["runPipeline"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        result["runPipeline"] = f"FAIL:{exc}"

    missing = [
        n
        for n in (
            "NURION_EyeDome.L",
            "NURION_DiagnosticIris.L",
            "NURION_BeautyControl",
            "NURION_ExpressionControl",
        )
        if bpy.data.objects.get(n) is None
    ]
    result["missingObjects"] = missing
    result["verdict"] = (
        "PASS"
        if result.get("assertLocks") == "PASS"
        and result.get("runPipeline") == "PASS"
        and not missing
        and result.get("addonEnabled")
        else "FAIL"
    )
    result["schema"] = "NURION_GATE7A_REINSTALL_TEST"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
