"""Operators for Universal Eye Calibration RC.1."""

from __future__ import annotations

import json
from pathlib import Path

import bpy

from . import package_info


class NURION_OT_uec_run_pipeline(bpy.types.Operator):
    bl_idname = "nurion_uec.run_pipeline"
    bl_label = "Run Eye Calibration Pipeline"
    bl_description = "Clean rebuild Gate1→6 on the active/selected character mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        root = Path(__file__).resolve().parent
        # Prefer repo root when developing; addon root when installed from ZIP
        repo = root.parent if (root.parent / "nurion_universal_eye").exists() else root
        if str(repo) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(repo))
        if str(root) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(root))

        from nurion_universal_eye.gate6.beauty_integration import run_beauty_integration
        from nurion_universal_eye.gate7a.lock_registry import assert_all_gate_params_locked

        scene = context.scene
        mesh_name = scene.nurion_uec_mesh_name or ""
        preset = scene.nurion_uec_preset
        tier = scene.nurion_uec_tier
        try:
            assert_all_gate_params_locked(repo if (repo / "nurion_universal_eye").exists() else root)
            run_beauty_integration(
                mesh_name=mesh_name,
                root=repo if (repo / "nurion_universal_eye").exists() else root,
                preset=preset,
                tier=tier,
                evaluate_all_presets=False,
            )
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Pipeline PASS ({preset}/{tier})")
        return {"FINISHED"}


class NURION_OT_uec_export_status(bpy.types.Operator):
    bl_idname = "nurion_uec.export_status"
    bl_label = "Export Validation Status"
    bl_options = {"REGISTER"}

    filepath: bpy.props.StringProperty(subtype="FILE_PATH", default="//NURION_UEC_STATUS.json")

    def execute(self, context):
        scene = context.scene
        doc = {
            "schema": "NURION_UEC_RUNTIME_STATUS",
            "version": package_info.VERSION,
            "releaseCandidate": True,
            "sealed": False,
            "holdout": "WAITING",
            "preset": scene.nurion_uec_preset,
            "tier": scene.nurion_uec_tier,
            "meshName": scene.nurion_uec_mesh_name,
            "package": package_info.PACKAGE_NAME,
            "parameterHashes": package_info.GATE_PARAM_HASHES,
        }
        path = bpy.path.abspath(self.filepath)
        Path(path).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        self.report({"INFO"}, f"Wrote {path}")
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}


class NURION_OT_uec_assert_locks(bpy.types.Operator):
    bl_idname = "nurion_uec.assert_locks"
    bl_label = "Assert Gate Locks"
    bl_options = {"REGISTER"}

    def execute(self, context):
        root = Path(__file__).resolve().parent
        repo = root.parent if (root.parent / "nurion_universal_eye").exists() else root
        if str(repo) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(repo))
        if str(root) not in __import__("sys").path:
            __import__("sys").path.insert(0, str(root))
        try:
            from nurion_universal_eye.gate7a.lock_registry import assert_all_gate_params_locked

            report = assert_all_gate_params_locked(repo if (repo / "nurion_universal_eye").exists() else root)
        except Exception as exc:  # noqa: BLE001
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        self.report({"INFO"}, f"Locks OK gate6={report.get('gate6ParameterHash', '')[:16]}…")
        return {"FINISHED"}


CLASSES = (
    NURION_OT_uec_run_pipeline,
    NURION_OT_uec_export_status,
    NURION_OT_uec_assert_locks,
)


def register():
    scene = bpy.types.Scene
    scene.nurion_uec_mesh_name = bpy.props.StringProperty(name="Mesh", default="char1")
    scene.nurion_uec_preset = bpy.props.EnumProperty(
        name="Beauty Preset",
        items=[
            ("NATURAL", "NATURAL", "Engine default"),
            ("LUMINOUS", "LUMINOUS", "Clear luminous iris"),
            ("AI_PREMIUM", "AI_PREMIUM", "Restrained teal AI (ARKAON ABA option)"),
        ],
        default="NATURAL",
    )
    scene.nurion_uec_tier = bpy.props.EnumProperty(
        name="Mobile Tier",
        items=[
            ("High", "High", "Full optical stack"),
            ("Medium", "Medium", "Simplified catchlight"),
            ("Low", "Low", "Baked-style single eye look"),
            ("Fallback", "Fallback", "Static eye material"),
        ],
        default="High",
    )
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    del bpy.types.Scene.nurion_uec_mesh_name
    del bpy.types.Scene.nurion_uec_preset
    del bpy.types.Scene.nurion_uec_tier
