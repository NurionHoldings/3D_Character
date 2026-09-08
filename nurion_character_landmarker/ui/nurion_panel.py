"""NURION CHARACTER LANDMARKER sidebar UI — v0.3a face + v0.2 body baseline."""

from __future__ import annotations

import bpy

from ..session import SESSION


class NURION_PT_character_landmarker(bpy.types.Panel):
    bl_label = "NURION CHARACTER LANDMARKER"
    bl_idname = "NURION_PT_character_landmarker"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "NURION"

    def draw_header(self, context):
        self.layout.label(text="v0.3a2")

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        layout.label(text="v0.3a2: Eye Proxy (body v0.2 SEALED)")

        box = layout.box()
        box.label(text="01 CHARACTER")
        col = box.column(align=True)
        col.operator("nurion.select_character", text="Select Character", icon="USER")
        col.operator("nurion.analyze_character", text="Analyze Character", icon="VIEWZOOM")
        if scene.nurion_character_name:
            box.label(text=f"Target: {scene.nurion_character_name}", icon="MESH_DATA")

        box = layout.box()
        box.label(text="02 MEASUREMENTS")
        col = box.column(align=True)
        col.label(text="MEASURED")
        col.prop(scene, "nurion_height", text="Height")
        col.prop(scene, "nurion_width", text="Width")
        row = col.row(align=True)
        row.prop(scene, "nurion_center_x", text="Cx")
        row.prop(scene, "nurion_center_y", text="Cy")
        row.prop(scene, "nurion_center_z", text="Cz")
        col.prop(scene, "nurion_floor_position", text="Floor Position")
        col.separator()
        col.label(text="ESTIMATED (ratios)")
        col.prop(scene, "nurion_shoulder_width", text="Shoulder Width")
        col.prop(scene, "nurion_hip_width", text="Hip Width")
        col.prop(scene, "nurion_arm_length", text="Arm Length")
        col.prop(scene, "nurion_leg_length", text="Leg Length")
        col.prop(scene, "nurion_forward_axis", text="Forward Axis")

        box = layout.box()
        box.label(text="03 LANDMARKS")
        col = box.column(align=True)
        col.operator("nurion.create_body_guides", text="Create Body Guides", icon="EMPTY_AXIS")
        col.operator("nurion.geometry_correct_landmarks", text="Geometry Correct", icon="MOD_MESHDEFORM")
        col.operator("nurion.mirror_left_to_right", text="Mirror Left to Right", icon="MOD_MIRROR")
        col.separator()
        col.label(text="Seeds / placeholders")
        col.operator("nurion.detect_body_landmarks", text="Re-Estimate Body", icon="FILE_REFRESH")

        box = layout.box()
        box.label(text="03b FACE / EYES (v0.3a2)")
        col = box.column(align=True)
        col.operator("nurion.build_eye_proxy", text="Build Eye Proxy + Eyeballs", icon="SPHERE")
        col.operator("nurion.detect_face_landmarks", text="Detect Face (Alpha1 path)", icon="USER")
        col.operator("nurion.create_face_gt_guides", text="Create Face GT Guides", icon="EMPTY_AXIS")
        col.operator("nurion.export_face_gt", text="Export Face GT", icon="EXPORT")
        box.label(text="Meshy: proxy eyes (no native eyeball)")

        box = layout.box()
        box.label(text="04 VALIDATION / PROFILE")
        col = box.column(align=True)
        col.prop(scene, "nurion_confidence_threshold", text="Confidence", slider=True)
        col.operator("nurion.review_low_confidence", text="Review Low Confidence", icon="ERROR")
        col.operator("nurion.validate_positions", text="Validate Positions", icon="CHECKMARK")
        col.operator("nurion.save_landmark_profile", text="Save Landmark Profile", icon="EXPORT")
        col.operator("nurion.load_landmark_profile", text="Load Landmark Profile", icon="IMPORT")
        col.operator("nurion.write_diagnostic_report", text="Write Diagnostic Report", icon="TEXT")
        if scene.nurion_last_profile_path:
            box.label(text=scene.nurion_last_profile_path, icon="FILE")
        if SESSION.low_confidence:
            box.label(text=f"Review: {len(SESSION.low_confidence)}", icon="INFO")

        box = layout.box()
        box.label(text="05 RIG (preview only)")
        col = box.column(align=True)
        col.operator("nurion.generate_standard_rig", text="Generate Standard Rig", icon="ARMATURE_DATA")
        col.operator("nurion.validate_bone_structure", text="Validate Bone Structure", icon="CHECKMARK")
        box.label(text="Auto Rig READY = FALSE")

        if SESSION.last_messages:
            layout.separator()
            msg = SESSION.last_messages[0]
            layout.label(text=msg[:60] + ("…" if len(msg) > 60 else ""), icon="INFO")


CLASSES = (NURION_PT_character_landmarker,)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
