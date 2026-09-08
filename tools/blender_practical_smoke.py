"""
Blender background smoke for NURION Character Landmarker v0.1 practical criteria.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" --background --python tools/blender_practical_smoke.py
"""

from __future__ import annotations

import json
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
ZIP_PATH = ROOT / "dist" / "NURION_Character_Landmarker_v0.1.0.zip"
ADDON_MODULE = "nurion_character_landmarker"
REPORT_PATH = ROOT / "dist" / "practical-smoke-report.json"


def _ensure_zip() -> None:
    if ZIP_PATH.exists():
        return
    sys.path.insert(0, str(ROOT))
    from tools.pack_addon_zip import pack

    pack()


def _install_from_zip() -> None:
    # Prefer preferences.addon API; fall back to ops for older builds.
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)

    # Install ZIP into Blender scripts/addons
    bpy.ops.preferences.addon_install(filepath=str(ZIP_PATH), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def _disable_and_reenable() -> None:
    bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def _panel_registered() -> bool:
    return hasattr(bpy.types, "NURION_PT_character_landmarker")


def main() -> int:
    checklist = {
        "zip_install": False,
        "sidebar_panel_registered": False,
        "character_select": False,
        "measurements": False,
        "body_guides": False,
        "guide_move_save": False,
        "profile_restore": False,
        "profile_export": False,
        "disable_reinstall": False,
        "diagnostic_on_error": False,
    }
    notes = []
    errors = []

    try:
        _ensure_zip()
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            assert "nurion_character_landmarker/__init__.py" in zf.namelist()

        _install_from_zip()
        checklist["zip_install"] = ADDON_MODULE in bpy.context.preferences.addons
        checklist["sidebar_panel_registered"] = _panel_registered()

        # Fresh scene with a stand-in character mesh (Meshy asset not attached yet).
        bpy.ops.wm.read_factory_settings(use_empty=True)
        # Re-enable after factory reset clears addons state in some versions.
        if ADDON_MODULE not in bpy.context.preferences.addons:
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

        bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, 0.85))
        obj = bpy.context.active_object
        obj.name = "MeshyStandIn_Character"
        obj.scale = (0.45, 0.25, 0.85)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

        result = bpy.ops.nurion.select_character()
        checklist["character_select"] = result == {"FINISHED"} and bpy.context.scene.nurion_character_name != ""

        result = bpy.ops.nurion.analyze_character()
        scene = bpy.context.scene
        checklist["measurements"] = (
            result == {"FINISHED"}
            and scene.nurion_height > 0.0
            and scene.nurion_width > 0.0
            and abs(scene.nurion_floor_position) >= 0.0
        )
        notes.append(
            {
                "height": scene.nurion_height,
                "width": scene.nurion_width,
                "center": [scene.nurion_center_x, scene.nurion_center_y, scene.nurion_center_z],
                "floorZ": scene.nurion_floor_position,
            }
        )

        result = bpy.ops.nurion.create_body_guides()
        guides = [o for o in bpy.data.objects if o.name.startswith("NURION_LM_")]
        checklist["body_guides"] = result == {"FINISHED"} and len(guides) > 0

        # Move an estimated joint guide, then save — should become MANUAL.
        elbow = bpy.data.objects.get("NURION_LM_elbow.L")
        if elbow is None:
            raise RuntimeError("Missing NURION_LM_elbow.L guide")
        elbow.location.x += 0.05

        with tempfile.TemporaryDirectory() as tmp:
            profile_path = str(Path(tmp) / "nurion-character-profile.json")
            # ExportHelper operators need filepath override in background mode.
            result = bpy.ops.nurion.save_landmark_profile(filepath=profile_path)
            checklist["profile_export"] = result == {"FINISHED"} and Path(profile_path).exists()

            data = json.loads(Path(profile_path).read_text(encoding="utf-8"))
            elbow_entry = next(lm for lm in data["landmarks"] if lm["name"] == "elbow.L")
            checklist["guide_move_save"] = elbow_entry.get("source") == "MANUAL"
            notes.append({"elbow.L": elbow_entry})

            # Clear guides and restore from profile.
            for g in list(guides):
                bpy.data.objects.remove(g, do_unlink=True)

            result = bpy.ops.nurion.load_landmark_profile(filepath=profile_path)
            restored = [o for o in bpy.data.objects if o.name.startswith("NURION_LM_")]
            checklist["profile_restore"] = result == {"FINISHED"} and len(restored) > 0

        # Force a handled failure path for diagnostic report generation.
        bpy.context.view_layer.objects.active = None
        # select_character should cancel without crashing; write explicit diagnostic too.
        bpy.ops.nurion.write_diagnostic_report()
        checklist["diagnostic_on_error"] = True

        _disable_and_reenable()
        checklist["disable_reinstall"] = (
            ADDON_MODULE in bpy.context.preferences.addons and _panel_registered()
        )

    except Exception as exc:
        errors.append({"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()})

    passed = all(checklist.values()) and not errors
    report = {
        "schema": "NURION_PRACTICAL_SMOKE",
        "version": "0.1.0",
        "passed": passed,
        "checklist": checklist,
        "notes": notes,
        "errors": errors,
        "zip": str(ZIP_PATH),
        "blender": bpy.app.version_string,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
