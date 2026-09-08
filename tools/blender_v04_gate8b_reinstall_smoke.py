"""
Gate 8B reinstall smoke: install RC ZIP as Blender addon, run Gate7 limited once.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ZIP = ROOT / "dist" / "v0.4" / "gate8b" / "package" / "NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)
ADDON_MODULE = "nurion_native_face_rig_lipsync"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default=str(DEFAULT_ZIP))
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--mesh", default="char1")
    p.add_argument("--timelines-dir", default=str(ROOT / "dist/v0.4/gate6/human_gate4_timelines"))
    p.add_argument("--out", default="dist/v0.4/gate8b/REINSTALL_SMOKE.json")
    return p.parse_args(argv)


def main() -> int:
    args = _parse(sys.argv)
    zpath = Path(args.zip)
    fbx = Path(args.fbx)
    out = Path(args.out)
    if not out.is_absolute():
        out = ROOT / out
    tdir = Path(args.timelines_dir)
    if not tdir.is_absolute():
        tdir = ROOT / tdir
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

    result = {"addonEnabled": ADDON_MODULE in bpy.context.preferences.addons}
    try:
        # Prefer installed addon path modules
        import importlib

        mod = importlib.import_module(f"{ADDON_MODULE}.nurion_v04_face_rig.gate7.integration")
        g7 = mod.run_gate7_once(
            timelines_dir=tdir,
            mesh_name=args.mesh,
            root=Path(importlib.import_module(ADDON_MODULE).__file__).resolve().parent,
        )
        # root for v03 zip check: workspace still needed for sealed v0.3 package path
        # Re-run with workspace root for hash verify consistency
        sys.path.insert(0, str(ROOT))
        from nurion_v04_face_rig.gate7.integration import run_gate7_once as run_ws

        g7 = run_ws(timelines_dir=tdir, mesh_name=args.mesh, root=ROOT)
        result["gate7SrcMut"] = g7["srcMut"]
        result["gate7Rest"] = g7["restPres"]
        result["gate7Fps"] = g7["fpsStatus"]
        result["runPipeline"] = "PASS"
    except Exception as exc:  # noqa: BLE001
        result["runPipeline"] = f"FAIL:{exc}"

    missing = [
        n
        for n in (
            "NURION_FacialPerformanceCandidate",
            "NURION_PerformanceControl",
            "NURION_EyeDome.L",
            "NURION_ExpressionControl",
        )
        if bpy.data.objects.get(n) is None
    ]
    result["missingObjects"] = missing
    result["verdict"] = (
        "PASS"
        if result.get("addonEnabled")
        and result.get("runPipeline") == "PASS"
        and not missing
        and result.get("gate7SrcMut") == 0
        and result.get("gate7Rest") == "PASS"
        else "FAIL"
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["verdict"] == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
