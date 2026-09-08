"""UI panel for NURION Universal Eye Calibration RC.1."""

from __future__ import annotations

import bpy

from . import package_info


class NURION_PT_uec_panel(bpy.types.Panel):
    bl_label = "NURION Universal Eye"
    bl_idname = "NURION_PT_uec_panel"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NURION"

    def draw_header(self, context):
        self.layout.label(text="RC.1")

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="RELEASE CANDIDATE", icon="INFO")
        box.label(text=f"v{package_info.VERSION}")
        box.label(text="SEALED = FALSE")
        box.label(text="HOLDOUT = WAITING")

        box = layout.box()
        box.label(text="01 Pipeline")
        col = box.column(align=True)
        col.prop(scene, "nurion_uec_mesh_name", text="Mesh")
        col.operator("nurion_uec.assert_locks", text="Assert Gate Locks", icon="LOCKED")
        col.operator("nurion_uec.run_pipeline", text="Run Gate1→6 Pipeline", icon="PLAY")

        box = layout.box()
        box.label(text="02 Beauty")
        col = box.column(align=True)
        col.prop(scene, "nurion_uec_preset", text="Preset")
        col.prop(scene, "nurion_uec_tier", text="Tier")
        col.label(text="Default preset: NATURAL")

        box = layout.box()
        box.label(text="03 Diagnostics")
        col = box.column(align=True)
        col.operator("nurion_uec.export_status", text="Export Validation Status", icon="EXPORT")
        col.label(text="Evidence via tools harness")


CLASSES = (NURION_PT_uec_panel,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
