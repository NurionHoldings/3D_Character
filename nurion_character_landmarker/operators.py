"""Blender operators for NURION Character Landmarker."""

from __future__ import annotations

import bpy
from bpy.props import EnumProperty, StringProperty
from bpy_extras.io_utils import ExportHelper, ImportHelper

from .ai.body_detector import detect_body
from .ai.face_detector import detect_face_corrected
from .core.character_analyzer import analyze_character, get_selected_character
from .core.confidence_engine import evaluate_confidence, validate_positions
from .core.coordinate_solver import solve_coordinates
from .core.face.eye_proxy_pipeline import run_eye_proxy_pipeline
from .core.face.gt_schema import landmarks_to_gt, save_face_gt
from .core.face.multiview import create_ortho_view_empties
from .core.geometry_correction import correct_landmarks_geometry
from .core.landmark_engine import mirror_left_to_right
from .core.leak_guard import GroundTruthLeakError, reset_gt_access_log
from .core.measurement_engine import measure_character
from .diagnostics import build_report, report_exception, write_report
from .profiles.nurion_landmark_profile import (
    DEFAULT_FILENAME,
    NurionCharacterProfile,
    load_profile,
    measurements_payload,
    save_profile,
)
from .rig.bone_generator import generate_standard_rig
from .rig.face_guide_builder import (
    create_face_gt_template_guides,
    create_face_guides,
    sync_face_landmarks_from_guides,
)
from .rig.guide_builder import create_body_guides, sync_landmarks_from_guides
from .rig.rig_validator import validate_bone_structure
from .session import SESSION


def _apply_measurements_to_scene(scene, measurements) -> None:
    scene.nurion_height = measurements.height.value
    scene.nurion_width = measurements.width.value
    scene.nurion_center_x = measurements.center[0]
    scene.nurion_center_y = measurements.center[1]
    scene.nurion_center_z = measurements.center[2]
    scene.nurion_shoulder_width = measurements.shoulder_width.value
    scene.nurion_hip_width = measurements.hip_width.value
    scene.nurion_arm_length = measurements.arm_length.value
    scene.nurion_leg_length = measurements.leg_length.value
    scene.nurion_forward_axis = measurements.forward_axis
    scene.nurion_floor_position = measurements.floor_position.value


def _gather_landmarks_for_save() -> dict:
    previous = SESSION.all_landmarks()
    synced = sync_landmarks_from_guides(previous=previous, mark_moved_as_manual=True)
    if synced:
        # Split helpers/joints back into body for session continuity.
        SESSION.landmarks.body = synced
        return synced
    return previous


def _build_profile_from_session(context) -> NurionCharacterProfile:
    landmarks = _gather_landmarks_for_save()
    if not landmarks:
        raise RuntimeError("No landmarks to save. Create Body Guides first.")

    measurements = SESSION.measurements
    scene = context.scene
    if measurements:
        height = measurements.height.value
        width = measurements.width.value
        center = list(measurements.center)
        forward = measurements.forward_axis
        floor_z = measurements.floor_position.value
        meas_payload = measurements_payload(measurements)
    else:
        height = scene.nurion_height
        width = scene.nurion_width
        center = [scene.nurion_center_x, scene.nurion_center_y, scene.nurion_center_z]
        forward = scene.nurion_forward_axis
        floor_z = scene.nurion_floor_position
        meas_payload = {}

    character_id = (SESSION.character_name or scene.nurion_character_name or "character-001")
    character_id = character_id.lower().replace(" ", "-")

    return NurionCharacterProfile(
        character_id=character_id,
        character_height=float(height),
        width=float(width),
        center=[float(v) for v in center],
        forward_axis=forward,
        floor_z=float(floor_z),
        measurements=meas_payload,
        landmarks=solve_coordinates(landmarks),
    )


class NURION_OT_select_character(bpy.types.Operator):
    bl_idname = "nurion.select_character"
    bl_label = "Select Character"
    bl_description = "Use the active mesh as the NURION character target"

    def execute(self, context):
        try:
            obj = get_selected_character(context)
            if obj is None:
                self.report({"ERROR"}, "Select a mesh character object.")
                return {"CANCELLED"}
            SESSION.character_name = obj.name
            SESSION.set_message(f"Character selected: {obj.name}")
            context.scene.nurion_character_name = obj.name
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("select_character", exc)
            self.report({"ERROR"}, f"Select failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_analyze_character(bpy.types.Operator):
    bl_idname = "nurion.analyze_character"
    bl_label = "Analyze Character"
    bl_description = "MEASURE height/width/center/floor; ESTIMATE limb proportions"

    def execute(self, context):
        try:
            obj = get_selected_character(context)
            if obj is None:
                self.report({"ERROR"}, "Select a mesh character object.")
                return {"CANCELLED"}

            analysis = analyze_character(obj)
            measurements = measure_character(analysis, forward_axis=context.scene.nurion_forward_axis)

            SESSION.character_name = obj.name
            SESSION.analysis = analysis
            SESSION.measurements = measurements
            SESSION.landmarks.body.clear()
            SESSION.landmarks.face.clear()

            scene = context.scene
            scene.nurion_character_name = obj.name
            _apply_measurements_to_scene(scene, measurements)

            SESSION.set_message(
                f"MEASURED h={measurements.height.value:.3f} w={measurements.width.value:.3f} "
                f"floorZ={measurements.floor_position.value:.3f} | ESTIMATED limb ratios"
            )
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("analyze_character", exc, {"object": getattr(context.active_object, "name", None)})
            self.report({"ERROR"}, f"Analyze failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_create_body_guides(bpy.types.Operator):
    bl_idname = "nurion.create_body_guides"
    bl_label = "Create Body Guides"
    bl_description = "Create ESTIMATED joint guides + MEASURED bounds helpers"

    def execute(self, context):
        try:
            if SESSION.analysis is None or SESSION.measurements is None:
                obj = get_selected_character(context)
                if obj is None:
                    self.report({"ERROR"}, "Select a mesh and Analyze Character first.")
                    return {"CANCELLED"}
                SESSION.analysis = analyze_character(obj)
                SESSION.measurements = measure_character(SESSION.analysis, forward_axis=context.scene.nurion_forward_axis)
                SESSION.character_name = obj.name
                context.scene.nurion_character_name = obj.name
                _apply_measurements_to_scene(context.scene, SESSION.measurements)

            SESSION.landmarks.body = detect_body(SESSION.analysis, SESSION.measurements)
            count = create_body_guides(SESSION.landmarks.body, overwrite_positions=True)
            report = evaluate_confidence(SESSION.landmarks.body)
            SESSION.low_confidence = report.low_confidence
            SESSION.set_message(
                f"Body guides ready ({count} new). Joints=ESTIMATED — move then Save Profile."
            )
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("create_body_guides", exc)
            self.report({"ERROR"}, f"Guide creation failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_geometry_correct_landmarks(bpy.types.Operator):
    bl_idname = "nurion.geometry_correct_landmarks"
    bl_label = "Geometry Correct Landmarks"
    bl_description = "v0.2: cross-section ray-cast correction (no GT bones, no AI)"

    def execute(self, context):
        try:
            obj = get_selected_character(context)
            if obj is None:
                self.report({"ERROR"}, "Select a mesh character object.")
                return {"CANCELLED"}

            estimated = SESSION.landmarks.body or sync_landmarks_from_guides(mark_moved_as_manual=False)
            if not estimated:
                if SESSION.analysis is None or SESSION.measurements is None:
                    SESSION.analysis = analyze_character(obj)
                    SESSION.measurements = measure_character(
                        SESSION.analysis, forward_axis=context.scene.nurion_forward_axis
                    )
                    _apply_measurements_to_scene(context.scene, SESSION.measurements)
                estimated = detect_body(SESSION.analysis, SESSION.measurements)
                SESSION.landmarks.body = estimated

            reset_gt_access_log()
            result = correct_landmarks_geometry(obj, estimated)
            SESSION.landmarks.body = result.landmarks
            create_body_guides(result.landmarks, overwrite_positions=True)

            msg = (
                f"GEOMETRY_CORRECTED={len(result.corrected)} kept_ESTIMATED={len(result.kept_estimated)} "
                f"outside={len(result.outside_rejected)} swaps={len(result.constraints.left_right_swaps)}"
            )
            SESSION.set_message(msg)
            if result.constraints.left_right_swaps or result.outside_rejected:
                self.report({"WARNING"}, msg)
            else:
                self.report({"INFO"}, msg)
            return {"FINISHED"}
        except GroundTruthLeakError as exc:
            path = report_exception("geometry_correct_gt_leak", exc)
            self.report({"ERROR"}, f"GT leak blocked. Diagnostic: {path}")
            return {"CANCELLED"}
        except Exception as exc:
            path = report_exception("geometry_correct_landmarks", exc)
            self.report({"ERROR"}, f"Geometry correction failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_detect_body_landmarks(bpy.types.Operator):
    bl_idname = "nurion.detect_body_landmarks"
    bl_label = "Estimate Body Landmarks"
    bl_description = "Recreate ESTIMATED joint guides (seed only, not AI)"

    def execute(self, context):
        return bpy.ops.nurion.create_body_guides()


class NURION_OT_detect_face_landmarks(bpy.types.Operator):
    bl_idname = "nurion.detect_face_landmarks"
    bl_label = "Detect Face Landmarks"
    bl_description = "v0.3a Alpha1: geometry + multiview face correction (core 13)"

    def execute(self, context):
        try:
            if SESSION.analysis is None or SESSION.measurements is None:
                self.report({"ERROR"}, "Run Analyze Character first.")
                return {"CANCELLED"}
            mesh = get_selected_character(context) or bpy.data.objects.get(SESSION.analysis.object_name)
            result = detect_face_corrected(
                SESSION.analysis,
                SESSION.measurements,
                SESSION.landmarks.body,
                mesh_obj=mesh,
            )
            if not result.region.eligible:
                SESSION.set_message(f"FACE_ASSET_INELIGIBLE: {result.region.reasonCode}")
                self.report({"ERROR"}, SESSION.last_messages[0])
                return {"CANCELLED"}
            SESSION.landmarks.face = result.landmarks
            create_face_guides(result.landmarks)
            if result.region.headFrame is not None:
                create_ortho_view_empties(result.region.headFrame)
            SESSION.set_message(
                f"Face FACE_GEOMETRY_CORRECTED: {len(result.landmarks)} "
                f"(missing={len(result.missing)} outside={len(result.rejected_outside)})"
            )
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("detect_face_landmarks", exc)
            self.report({"ERROR"}, f"Face detect failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_build_eye_proxy(bpy.types.Operator):
    bl_idname = "nurion.build_eye_proxy"
    bl_label = "Build Eye Proxy + Eyeballs"
    bl_description = "v0.3a-alpha.2: Meshy eye aperture proxy and NURION procedural eyeballs"

    def execute(self, context):
        try:
            if SESSION.analysis is None or SESSION.measurements is None:
                self.report({"ERROR"}, "Run Analyze Character first.")
                return {"CANCELLED"}
            mesh = get_selected_character(context) or bpy.data.objects.get(SESSION.analysis.object_name)
            result = run_eye_proxy_pipeline(
                mesh,
                body=SESSION.landmarks.body,
                forward_axis=SESSION.measurements.forward_axis,
                create_meshes=True,
            )
            if len(result.proxy.centers) < 2:
                SESSION.set_message("Eye Proxy incomplete: " + "; ".join(result.notes + result.proxy.notes))
                self.report({"ERROR"}, SESSION.last_messages[0])
                return {"CANCELLED"}
            SESSION.landmarks.face.update(result.landmarks)
            create_face_guides(result.landmarks)
            SESSION.set_message(
                f"Eye Proxy OK: centers={len(result.proxy.centers)} "
                f"eyeballs={list(result.eyeballs.objects.values())}"
            )
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("build_eye_proxy", exc)
            self.report({"ERROR"}, f"Eye Proxy failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_create_face_gt_guides(bpy.types.Operator):
    bl_idname = "nurion.create_face_gt_guides"
    bl_label = "Create Face GT Guides"
    bl_description = "Create full face GT empties for manual annotation (evaluation-only)"

    def execute(self, context):
        try:
            if SESSION.analysis is None or SESSION.measurements is None:
                self.report({"ERROR"}, "Run Analyze Character first.")
                return {"CANCELLED"}
            mesh = get_selected_character(context) or bpy.data.objects.get(SESSION.analysis.object_name)
            result = detect_face_corrected(
                SESSION.analysis,
                SESSION.measurements,
                SESSION.landmarks.body,
                mesh_obj=mesh,
            )
            seeds = dict(result.landmarks)
            # Seed face.center / head.top helpers for annotation layout.
            if result.region.headFrame is not None:
                from .core.landmark_engine import LandmarkPoint
                from .core.sources import ESTIMATED

                fr = result.region.headFrame
                seeds.setdefault(
                    "face.center",
                    LandmarkPoint("face.center", fr.origin.copy(), ESTIMATED, 0.4),
                )
                seeds.setdefault(
                    "head.top",
                    LandmarkPoint(
                        "head.top",
                        fr.origin + fr.up * (fr.head_height * 0.55),
                        ESTIMATED,
                        0.4,
                    ),
                )
            n = create_face_gt_template_guides(seeds)
            SESSION.set_message(f"Face GT guides ready (new={n}). Annotate then Export Face GT.")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("create_face_gt_guides", exc)
            self.report({"ERROR"}, f"Face GT guides failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_export_face_gt(bpy.types.Operator, ExportHelper):
    bl_idname = "nurion.export_face_gt"
    bl_label = "Export Face Ground Truth"
    bl_description = "Save manual face guides as evaluation-only GT (world + head-local)"
    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def invoke(self, context, event):
        self.filepath = "face-ground-truth.json"
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            if SESSION.analysis is None or SESSION.measurements is None:
                self.report({"ERROR"}, "Run Analyze Character first.")
                return {"CANCELLED"}
            mesh = get_selected_character(context) or bpy.data.objects.get(SESSION.analysis.object_name)
            prev = SESSION.landmarks.face
            synced = sync_face_landmarks_from_guides(previous=prev, mark_moved_as_manual=True)
            if not synced:
                self.report({"ERROR"}, "No face guides to export.")
                return {"CANCELLED"}
            from .core.face.region import evaluate_face_region

            region = evaluate_face_region(
                mesh,
                body=SESSION.landmarks.body,
                forward_axis=SESSION.measurements.forward_axis,
            )
            if region.headFrame is None:
                self.report({"ERROR"}, "Could not build head frame for GT export.")
                return {"CANCELLED"}
            doc = landmarks_to_gt(
                synced,
                region.headFrame,
                character_id=(SESSION.character_name or "character").lower().replace(" ", "-"),
                mesh_name=mesh.name if mesh else "",
            )
            save_face_gt(doc, self.filepath)
            SESSION.landmarks.face = synced
            SESSION.set_message(f"Face GT exported: {doc.get('annotatedCount', 0)} points")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("export_face_gt", exc)
            self.report({"ERROR"}, f"Face GT export failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_mirror_left_to_right(bpy.types.Operator):
    bl_idname = "nurion.mirror_left_to_right"
    bl_label = "Mirror Left to Right"
    bl_description = "Mirror left-side guides onto the right (source=MANUAL)"

    def execute(self, context):
        try:
            body = _gather_landmarks_for_save()
            if not body:
                self.report({"ERROR"}, "No landmarks to mirror.")
                return {"CANCELLED"}

            center_x = SESSION.analysis.center.x if SESSION.analysis else context.scene.nurion_center_x
            SESSION.landmarks.body = mirror_left_to_right(body, center_x)
            create_body_guides(SESSION.landmarks.body)
            SESSION.set_message("Mirrored L→R (right side marked MANUAL).")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("mirror_left_to_right", exc)
            self.report({"ERROR"}, f"Mirror failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_review_low_confidence(bpy.types.Operator):
    bl_idname = "nurion.review_low_confidence"
    bl_label = "Review Low Confidence"
    bl_description = "List ESTIMATED / low-confidence landmarks that need manual review"

    def execute(self, context):
        try:
            landmarks = _gather_landmarks_for_save()
            report = evaluate_confidence(landmarks, threshold=context.scene.nurion_confidence_threshold)
            SESSION.low_confidence = report.review_required or report.low_confidence
            if SESSION.low_confidence:
                msg = f"Review required ({len(SESSION.low_confidence)}): " + ", ".join(SESSION.low_confidence[:12])
                if len(SESSION.low_confidence) > 12:
                    msg += "…"
            else:
                msg = "No landmarks require review."
            SESSION.set_message(msg)
            self.report({"INFO"}, msg)
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("review_low_confidence", exc)
            self.report({"ERROR"}, f"Review failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_validate_positions(bpy.types.Operator):
    bl_idname = "nurion.validate_positions"
    bl_label = "Validate Positions"
    bl_description = "Validate landmark positions and source tags"

    def execute(self, context):
        try:
            landmarks = _gather_landmarks_for_save()
            issues = validate_positions(landmarks)
            SESSION.validation_issues = issues
            if issues:
                SESSION.set_message("Validation: " + "; ".join(issues[:3]))
                self.report({"WARNING"}, SESSION.last_messages[0])
            else:
                SESSION.set_message("Landmark positions look valid.")
                self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("validate_positions", exc)
            self.report({"ERROR"}, f"Validate failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_save_landmark_profile(bpy.types.Operator, ExportHelper):
    bl_idname = "nurion.save_landmark_profile"
    bl_label = "Save Landmark Profile"
    bl_description = "Export nurion-character-profile.json (moved guides → MANUAL)"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})
    filepath: StringProperty(subtype="FILE_PATH", default=DEFAULT_FILENAME)

    def invoke(self, context, event):
        self.filepath = DEFAULT_FILENAME
        return ExportHelper.invoke(self, context, event)

    def execute(self, context):
        try:
            profile = _build_profile_from_session(context)
            path = save_profile(profile, self.filepath)
            SESSION.last_profile_path = str(path)
            context.scene.nurion_last_profile_path = str(path)
            SESSION.set_message(f"Saved NURION Character Profile: {path}")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("save_landmark_profile", exc)
            self.report({"ERROR"}, f"Save failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_load_landmark_profile(bpy.types.Operator, ImportHelper):
    bl_idname = "nurion.load_landmark_profile"
    bl_label = "Load Landmark Profile"
    bl_description = "Restore guides and measurements from nurion-character-profile.json"

    filename_ext = ".json"
    filter_glob: StringProperty(default="*.json", options={"HIDDEN"})

    def execute(self, context):
        try:
            profile = load_profile(self.filepath)
            points = profile.landmark_points()
            if not points:
                self.report({"ERROR"}, "Profile contains no landmarks.")
                return {"CANCELLED"}

            SESSION.landmarks.body = points
            SESSION.landmarks.face.clear()
            SESSION.character_name = profile.character_id
            SESSION.last_profile_path = self.filepath

            scene = context.scene
            scene.nurion_character_name = profile.character_id
            scene.nurion_height = profile.character_height
            scene.nurion_width = profile.width
            if len(profile.center) >= 3:
                scene.nurion_center_x = profile.center[0]
                scene.nurion_center_y = profile.center[1]
                scene.nurion_center_z = profile.center[2]
            scene.nurion_forward_axis = profile.forward_axis
            scene.nurion_floor_position = profile.floor_z
            scene.nurion_last_profile_path = self.filepath

            meas = profile.measurements or {}
            if "shoulderWidth" in meas:
                scene.nurion_shoulder_width = float(meas["shoulderWidth"].get("value", 0.0))
            if "hipWidth" in meas:
                scene.nurion_hip_width = float(meas["hipWidth"].get("value", 0.0))
            if "armLength" in meas:
                scene.nurion_arm_length = float(meas["armLength"].get("value", 0.0))
            if "legLength" in meas:
                scene.nurion_leg_length = float(meas["legLength"].get("value", 0.0))

            created = create_body_guides(points, overwrite_positions=True)
            SESSION.set_message(f"Restored profile ({len(points)} landmarks, {created} new guides).")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("load_landmark_profile", exc, {"filepath": self.filepath})
            self.report({"ERROR"}, f"Load failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_write_diagnostic_report(bpy.types.Operator):
    bl_idname = "nurion.write_diagnostic_report"
    bl_label = "Write Diagnostic Report"
    bl_description = "Write a NURION diagnostic JSON report under Documents/NURION/diagnostics"

    def execute(self, context):
        try:
            scene = context.scene
            checklist = {
                "sidebar_visible": True,
                "character_select": bool(scene.nurion_character_name),
                "measurements": scene.nurion_height > 0.0,
                "body_guides": any(o.name.startswith("NURION_LM_") for o in bpy.data.objects),
                "profile_export": bool(scene.nurion_last_profile_path),
            }
            report = build_report(
                stage="manual_diagnostic",
                success=True,
                message="Manual diagnostic snapshot",
                checklist=checklist,
                extras={
                    "character": scene.nurion_character_name,
                    "height": scene.nurion_height,
                    "width": scene.nurion_width,
                    "floorZ": scene.nurion_floor_position,
                    "center": [scene.nurion_center_x, scene.nurion_center_y, scene.nurion_center_z],
                    "guide_count": sum(1 for o in bpy.data.objects if o.name.startswith("NURION_LM_")),
                    "last_profile": scene.nurion_last_profile_path,
                    "last_message": SESSION.last_messages[0] if SESSION.last_messages else "",
                },
            )
            path = write_report(report)
            SESSION.set_message(f"Diagnostic written: {path}")
            self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("write_diagnostic_report", exc)
            self.report({"ERROR"}, f"Diagnostic failed: {path}")
            return {"CANCELLED"}


class NURION_OT_generate_standard_rig(bpy.types.Operator):
    bl_idname = "nurion.generate_standard_rig"
    bl_label = "Generate Standard Rig"
    bl_description = "Preview armature from guides (Auto Rig product is separate)"

    def execute(self, context):
        try:
            landmarks = _gather_landmarks_for_save()
            if not landmarks:
                self.report({"ERROR"}, "Create Body Guides before generating a rig preview.")
                return {"CANCELLED"}

            arm = generate_standard_rig(landmarks)
            context.view_layer.objects.active = arm
            SESSION.set_message(f"Preview rig: {arm.name} (not NURION Auto Rig)")
            self.report({"WARNING"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("generate_standard_rig", exc)
            self.report({"ERROR"}, f"Rig preview failed. Diagnostic: {path}")
            return {"CANCELLED"}


class NURION_OT_validate_bone_structure(bpy.types.Operator):
    bl_idname = "nurion.validate_bone_structure"
    bl_label = "Validate Bone Structure"
    bl_description = "Validate the active armature bone structure"

    def execute(self, context):
        try:
            obj = context.active_object
            issues = validate_bone_structure(obj)
            SESSION.validation_issues = issues
            if issues:
                SESSION.set_message("Bone issues: " + "; ".join(issues))
                self.report({"WARNING"}, SESSION.last_messages[0])
            else:
                SESSION.set_message("Bone structure is valid.")
                self.report({"INFO"}, SESSION.last_messages[0])
            return {"FINISHED"}
        except Exception as exc:
            path = report_exception("validate_bone_structure", exc)
            self.report({"ERROR"}, f"Bone validate failed. Diagnostic: {path}")
            return {"CANCELLED"}


CLASSES = (
    NURION_OT_select_character,
    NURION_OT_analyze_character,
    NURION_OT_create_body_guides,
    NURION_OT_geometry_correct_landmarks,
    NURION_OT_detect_body_landmarks,
    NURION_OT_detect_face_landmarks,
    NURION_OT_build_eye_proxy,
    NURION_OT_create_face_gt_guides,
    NURION_OT_export_face_gt,
    NURION_OT_mirror_left_to_right,
    NURION_OT_review_low_confidence,
    NURION_OT_validate_positions,
    NURION_OT_save_landmark_profile,
    NURION_OT_load_landmark_profile,
    NURION_OT_write_diagnostic_report,
    NURION_OT_generate_standard_rig,
    NURION_OT_validate_bone_structure,
)


def _register_scene_props():
    scene = bpy.types.Scene
    scene.nurion_character_name = StringProperty(name="Character", default="")
    scene.nurion_height = bpy.props.FloatProperty(name="Height (MEASURED)", default=0.0, unit="LENGTH")
    scene.nurion_width = bpy.props.FloatProperty(name="Width (MEASURED)", default=0.0, unit="LENGTH")
    scene.nurion_center_x = bpy.props.FloatProperty(name="Center X", default=0.0, unit="LENGTH")
    scene.nurion_center_y = bpy.props.FloatProperty(name="Center Y", default=0.0, unit="LENGTH")
    scene.nurion_center_z = bpy.props.FloatProperty(name="Center Z", default=0.0, unit="LENGTH")
    scene.nurion_shoulder_width = bpy.props.FloatProperty(name="Shoulder Width (EST)", default=0.0, unit="LENGTH")
    scene.nurion_hip_width = bpy.props.FloatProperty(name="Hip Width (EST)", default=0.0, unit="LENGTH")
    scene.nurion_arm_length = bpy.props.FloatProperty(name="Arm Length (EST)", default=0.0, unit="LENGTH")
    scene.nurion_leg_length = bpy.props.FloatProperty(name="Leg Length (EST)", default=0.0, unit="LENGTH")
    scene.nurion_forward_axis = EnumProperty(
        name="Forward Axis",
        items=[
            ("+X", "+X", "Positive X"),
            ("-X", "-X", "Negative X"),
            ("+Y", "+Y", "Positive Y"),
            ("-Y", "-Y", "Negative Y"),
            ("+Z", "+Z", "Positive Z"),
            ("-Z", "-Z", "Negative Z"),
        ],
        default="-Y",
    )
    scene.nurion_floor_position = bpy.props.FloatProperty(name="Floor Position (MEASURED)", default=0.0, unit="LENGTH")
    scene.nurion_confidence_threshold = bpy.props.FloatProperty(
        name="Confidence Threshold",
        default=0.75,
        min=0.0,
        max=1.0,
    )
    scene.nurion_last_profile_path = StringProperty(name="Last Profile", default="", subtype="FILE_PATH")


def _unregister_scene_props():
    scene = bpy.types.Scene
    for attr in (
        "nurion_character_name",
        "nurion_height",
        "nurion_width",
        "nurion_center_x",
        "nurion_center_y",
        "nurion_center_z",
        "nurion_shoulder_width",
        "nurion_hip_width",
        "nurion_arm_length",
        "nurion_leg_length",
        "nurion_forward_axis",
        "nurion_floor_position",
        "nurion_confidence_threshold",
        "nurion_last_profile_path",
    ):
        if hasattr(scene, attr):
            delattr(scene, attr)


def register():
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    _register_scene_props()


def unregister():
    _unregister_scene_props()
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass
