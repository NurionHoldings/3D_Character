"""UI panel for NURION Unified Character Animation Runtime v0.6."""

from __future__ import annotations

import bpy

from .parameters import GATE6_PARAMETERS


class NURION_PT_v06_unified_runtime(bpy.types.Panel):
    bl_label = "NURION Unified Runtime"
    bl_idname = "NURION_PT_v06_unified_runtime"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NURION"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="v0.6 Unified Runtime", icon="INFO")
        box.label(text=f"Production: {scene.nurion_v06_production or 'NO-GO'}")
        box.label(text="Manual correction: 0")

        box = layout.box()
        box.label(text="Status")
        col = box.column(align=True)
        col.label(text=f"Class: {scene.nurion_v06_classification or '-'}")
        col.label(text=f"Lipsync: {scene.nurion_v06_lipsync_mode or '-'}")
        col.label(text=f"Preset: {scene.nurion_v06_selected_preset or '-'}")
        col.label(text=f"Validate: {scene.nurion_v06_validation_status or '-'}")
        if scene.nurion_v06_abstain:
            col.label(text=f"ABSTAIN: {scene.nurion_v06_abstain}")
        if scene.nurion_v06_last_abort:
            col.label(text=f"Abort: {scene.nurion_v06_last_abort}")

        box = layout.box()
        box.label(text="01 Select Character")
        col = box.column(align=True)
        col.prop(scene, "nurion_v06_label", text="Label")
        col.prop(scene, "nurion_v06_character_path", text="FBX")
        col.prop(scene, "nurion_v06_fps", text="FPS")
        col.operator("nurion_v06.select_character", icon="USER")

        box = layout.box()
        box.label(text="02 Analyze Asset")
        col = box.column(align=True)
        col.operator("nurion_v06.analyze_asset", icon="VIEWZOOM")

        box = layout.box()
        box.label(text="03 Build Unified Runtime")
        col = box.column(align=True)
        col.label(text=f"Collection: {GATE6_PARAMETERS['runtimeCollection']}")
        col.operator("nurion_v06.build_runtime", icon="MOD_BUILD")

        box = layout.box()
        box.label(text="04 Apply Motion Preset")
        col = box.column(align=True)
        col.prop(scene, "nurion_v06_preset_choice", text="Preset")
        col.operator("nurion_v06.apply_preset", icon="PLAY")

        box = layout.box()
        box.label(text="05 Validate Runtime")
        col = box.column(align=True)
        col.operator("nurion_v06.validate_runtime", icon="CHECKMARK")

        box = layout.box()
        box.label(text="06 Export")
        col = box.column(align=True)
        col.prop(scene, "nurion_v06_export_path", text="Path")
        col.prop(scene, "nurion_v06_export_format", text="Format")
        col.operator("nurion_v06.export_runtime", icon="EXPORT")
        col.label(text="Validation required before export")


CLASSES = (NURION_PT_v06_unified_runtime,)


def register():
    for cls in CLASSES:
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except Exception:
            pass
