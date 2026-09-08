"""Blender operators for NURION Unified Runtime Gate 6 workflow."""

from __future__ import annotations

import json
from pathlib import Path

import bpy

from . import scene_ops
from .parameters import GATE6_PARAMETERS
from .workflow import WorkflowEngine, WorkflowState

_ENGINE: WorkflowEngine | None = None


def get_engine() -> WorkflowEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = WorkflowEngine()
    return _ENGINE


def reset_engine() -> WorkflowEngine:
    global _ENGINE
    _ENGINE = WorkflowEngine()
    return _ENGINE


def _sync_scene_props(context, ui: dict) -> None:
    scene = context.scene
    scene.nurion_v06_classification = str(ui.get("classification") or "")
    scene.nurion_v06_lipsync_mode = str(ui.get("lipsyncMode") or "")
    scene.nurion_v06_selected_preset = str(ui.get("selectedPreset") or "")
    scene.nurion_v06_validation_status = str(ui.get("validationStatus") or "")
    scene.nurion_v06_production = str(ui.get("production") or "NO-GO")
    scene.nurion_v06_abstain = ", ".join(ui.get("abstainReasons") or [])
    scene.nurion_v06_last_abort = str(ui.get("lastAbort") or "")


class NURION_OT_v06_select_character(bpy.types.Operator):
    bl_idname = "nurion_v06.select_character"
    bl_label = "Select Character"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        eng = reset_engine()
        scene = context.scene
        label = scene.nurion_v06_label or "character"
        path = scene.nurion_v06_character_path or ""
        fps = int(scene.nurion_v06_fps)
        res = eng.select_character(label=label, character_path=path, fps=int(fps))
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"ERROR"}, res.get("abort") or "SAFE_ABORT")
            return {"CANCELLED"}
        # Import FBX into current scene only (no factory reset — preserves addon registration).
        p = Path(bpy.path.abspath(path)) if path else None
        if p and p.is_file() and p.suffix.lower() == ".fbx":
            # Clear non-runtime objects lightly before import
            for obj in list(bpy.data.objects):
                if not obj.name.startswith("NURION_"):
                    bpy.data.objects.remove(obj, do_unlink=True)
            bpy.ops.import_scene.fbx(filepath=str(p), automatic_bone_orientation=True, use_anim=True)
            bpy.context.view_layer.update()
        self.report({"INFO"}, f"Selected {label}")
        return {"FINISHED"}


class NURION_OT_v06_analyze(bpy.types.Operator):
    bl_idname = "nurion_v06.analyze_asset"
    bl_label = "Analyze Asset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        eng = get_engine()
        scene = context.scene
        # Prefer explicit scene overrides for harness; else diagnose lightly
        classification = scene.nurion_v06_force_classification or ""
        if not classification:
            arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
            classification = "LIMITED" if arms else "INELIGIBLE"
        avail = [x for x in scene.nurion_v06_available_presets.split(",") if x.strip()]
        unavail = [x for x in scene.nurion_v06_unavailable_presets.split(",") if x.strip()]
        if not avail and not unavail:
            avail = ["Formal_Bow"]
            unavail = ["Idle", "Gentlemans_Bow"]
        abstain = []
        if classification == "INELIGIBLE":
            abstain.append("INELIGIBLE")
        if scene.nurion_v06_lipsync_supported == 0:
            abstain.append("LIPSYNC_TIMELINE_UNSUPPORTED")
        res = eng.analyze_asset(
            classification=classification,
            abstain_reasons=abstain,
            available_presets=avail,
            unavailable_presets=unavail,
            lipsync_supported=bool(scene.nurion_v06_lipsync_supported),
        )
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"ERROR"}, res.get("abort") or "SAFE_ABORT")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Analyze {classification}")
        return {"FINISHED"}


class NURION_OT_v06_build(bpy.types.Operator):
    bl_idname = "nurion_v06.build_runtime"
    bl_label = "Build Unified Runtime"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        eng = get_engine()
        if eng.state.classification == "INELIGIBLE":
            res = eng.build_unified_runtime()
            _sync_scene_props(context, res["ui"])
            self.report({"WARNING"}, res.get("abort") or "DENIED")
            return {"CANCELLED"}
        # Order check without completing: require ANALYZE done
        if "ANALYZE_ASSET" not in eng.state.completed:
            res = eng.build_unified_runtime()
            _sync_scene_props(context, res["ui"])
            self.report({"WARNING"}, res.get("abort") or "ORDER_VIOLATION")
            return {"CANCELLED"}

        names = [f"{GATE6_PARAMETERS['runtimeActionPrefix']}{p}" for p in eng.state.availablePresets]
        built = scene_ops.build_runtime_from_active(preset_action_names=names)
        if not built.get("ok"):
            self.report({"WARNING"}, built.get("reason") or "BUILD_FAIL")
            return {"CANCELLED"}
        res = eng.build_unified_runtime(runtime_built=True)
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"WARNING"}, res.get("abort") or "SAFE_ABORT")
            return {"CANCELLED"}
        self.report({"INFO"}, "Runtime built (isolated collection)")
        return {"FINISHED"}


class NURION_OT_v06_apply(bpy.types.Operator):
    bl_idname = "nurion_v06.apply_preset"
    bl_label = "Apply Motion Preset"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        eng = get_engine()
        scene = context.scene
        preset = scene.nurion_v06_preset_choice or "Formal_Bow"
        # Order / ABSTAIN policy first (no scene mutation on denial)
        res = eng.apply_motion_preset(preset_id=preset, dry_run=True)
        if not res["ok"]:
            _sync_scene_props(context, res["ui"])
            self.report({"WARNING"}, res.get("abort") or "SAFE_ABORT")
            return {"CANCELLED"}

        action_name = f"{GATE6_PARAMETERS['runtimeActionPrefix']}{preset}"
        applied = scene_ops.apply_runtime_preset(action_name, int(scene.nurion_v06_fps))
        if not applied.get("ok"):
            _sync_scene_props(context, eng.ui_snapshot())
            self.report({"WARNING"}, applied.get("reason") or "APPLY_FAIL")
            return {"CANCELLED"}
        res = eng.apply_motion_preset(preset_id=preset, applied=True)
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"WARNING"}, res.get("abort") or "SAFE_ABORT")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Applied {preset}")
        return {"FINISHED"}


class NURION_OT_v06_validate(bpy.types.Operator):
    bl_idname = "nurion_v06.validate_runtime"
    bl_label = "Validate Runtime"
    bl_options = {"REGISTER"}

    def execute(self, context):
        eng = get_engine()
        report = scene_ops.validate_runtime(int(context.scene.nurion_v06_fps))
        res = eng.validate_runtime(report=report, passed=bool(report.get("ok")))
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"ERROR"}, res.get("abort") or "VALIDATION_FAILED")
            return {"CANCELLED"}
        self.report({"INFO"}, "Validation PASS")
        return {"FINISHED"}


class NURION_OT_v06_export(bpy.types.Operator):
    bl_idname = "nurion_v06.export_runtime"
    bl_label = "Export Runtime"
    bl_options = {"REGISTER"}

    def execute(self, context):
        eng = get_engine()
        scene = context.scene
        out = Path(bpy.path.abspath(scene.nurion_v06_export_path or "//NURION_UnifiedRuntime_Export.fbx"))
        # Order / validation gate in engine first
        if "VALIDATE_RUNTIME" not in eng.state.completed or not eng.state.validationPassed:
            res = eng.export(export_path=str(out), wrote=False)
            # force abort path
            if res["ok"]:
                # should not happen
                pass
            _sync_scene_props(context, res["ui"])
            self.report({"WARNING"}, res.get("abort") or "EXPORT_REQUIRES_VALIDATION")
            return {"CANCELLED"}
        written = scene_ops.export_runtime(out, fmt=scene.nurion_v06_export_format)
        res = eng.export(export_path=str(out).replace("\\", "/"), wrote=bool(written.get("ok")))
        _sync_scene_props(context, res["ui"])
        if not res["ok"]:
            self.report({"WARNING"}, res.get("abort") or "EXPORT_FAIL")
            return {"CANCELLED"}
        self.report({"INFO"}, f"Exported {out.name}")
        return {"FINISHED"}


CLASSES = (
    NURION_OT_v06_select_character,
    NURION_OT_v06_analyze,
    NURION_OT_v06_build,
    NURION_OT_v06_apply,
    NURION_OT_v06_validate,
    NURION_OT_v06_export,
)


def _register_props():
    S = bpy.types.Scene
    S.nurion_v06_label = bpy.props.StringProperty(name="Label", default="character")
    S.nurion_v06_character_path = bpy.props.StringProperty(name="Character FBX", subtype="FILE_PATH", default="")
    S.nurion_v06_fps = bpy.props.EnumProperty(
        name="FPS",
        items=[("24", "24", ""), ("30", "30", ""), ("60", "60", "")],
        default="30",
    )
    S.nurion_v06_preset_choice = bpy.props.EnumProperty(
        name="Preset",
        items=[
            ("Formal_Bow", "Formal Bow", ""),
            ("Idle", "Idle 15", ""),
            ("Gentlemans_Bow", "Gentleman's Bow", ""),
        ],
        default="Formal_Bow",
    )
    S.nurion_v06_export_path = bpy.props.StringProperty(name="Export Path", subtype="FILE_PATH", default="//NURION_UnifiedRuntime_Export.fbx")
    S.nurion_v06_export_format = bpy.props.EnumProperty(
        name="Format",
        items=[("FBX", "FBX", ""), ("GLB", "GLB", "")],
        default="FBX",
    )
    S.nurion_v06_force_classification = bpy.props.StringProperty(name="Force Classification", default="")
    S.nurion_v06_available_presets = bpy.props.StringProperty(name="Available Presets CSV", default="Formal_Bow,Idle")
    S.nurion_v06_unavailable_presets = bpy.props.StringProperty(name="Unavailable Presets CSV", default="Gentlemans_Bow")
    S.nurion_v06_lipsync_supported = bpy.props.IntProperty(name="Lipsync Supported", default=0, min=0, max=1)
    S.nurion_v06_classification = bpy.props.StringProperty(name="Classification", default="")
    S.nurion_v06_lipsync_mode = bpy.props.StringProperty(name="Lipsync Mode", default="")
    S.nurion_v06_selected_preset = bpy.props.StringProperty(name="Selected Preset", default="")
    S.nurion_v06_validation_status = bpy.props.StringProperty(name="Validation", default="")
    S.nurion_v06_production = bpy.props.StringProperty(name="Production", default="NO-GO")
    S.nurion_v06_abstain = bpy.props.StringProperty(name="ABSTAIN", default="")
    S.nurion_v06_last_abort = bpy.props.StringProperty(name="Last Abort", default="")


def _unregister_props():
    S = bpy.types.Scene
    for name in (
        "nurion_v06_label",
        "nurion_v06_character_path",
        "nurion_v06_fps",
        "nurion_v06_preset_choice",
        "nurion_v06_export_path",
        "nurion_v06_export_format",
        "nurion_v06_force_classification",
        "nurion_v06_available_presets",
        "nurion_v06_unavailable_presets",
        "nurion_v06_lipsync_supported",
        "nurion_v06_classification",
        "nurion_v06_lipsync_mode",
        "nurion_v06_selected_preset",
        "nurion_v06_validation_status",
        "nurion_v06_production",
        "nurion_v06_abstain",
        "nurion_v06_last_abort",
    ):
        if hasattr(S, name):
            delattr(S, name)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _register_props()
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    _unregister_props()
