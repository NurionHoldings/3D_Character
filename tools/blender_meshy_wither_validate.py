"""
Meshy Wither biped validation for NURION Character Landmarker v0.1 SEAL gate.

Run:
  "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" --background --python tools/blender_meshy_wither_validate.py
"""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
FBX_PATH = (
    ROOT
    / "assets"
    / "wither_character_rig"
    / "Meshy_AI_Minimalist_Tennis_Out_biped"
    / "Meshy_AI_Minimalist_Tennis_Out_biped_Animation_Idle_15_withSkin.fbx"
)
ADDON_ZIP = ROOT / "dist" / "NURION_Character_Landmarker_v0.1.0.zip"
ADDON_MODULE = "nurion_character_landmarker"
OUT_DIR = ROOT / "dist" / "meshy_validation" / "wither_character_rig"
REPORT_PATH = OUT_DIR / "meshy-wither-validation-report.json"
PROFILE_PATH = OUT_DIR / "nurion-character-profile.estimated.json"
DELTAS_PATH = OUT_DIR / "manual-correction-deltas.json"

# Estimated landmark → common Mixamo/Meshy biped bone names (priority order).
BONE_CANDIDATES = {
    "pelvis": ["Hips", "hips", "Pelvis", "pelvis", "Root", "mixamorig:Hips"],
    "spine": ["Spine", "spine", "mixamorig:Spine"],
    "chest": [
        "Spine02",
        "Spine01",
        "Spine2",
        "Spine1",
        "Chest",
        "spine2",
        "mixamorig:Spine2",
        "mixamorig:Spine1",
    ],
    "neck": ["Neck", "neck", "mixamorig:Neck"],
    "head": ["Head", "head", "mixamorig:Head"],
    "shoulder.L": ["LeftArm", "LeftShoulder", "mixamorig:LeftArm", "mixamorig:LeftShoulder", "upperarm_l", "UpperArm.L"],
    "elbow.L": ["LeftForeArm", "mixamorig:LeftForeArm", "lowerarm_l", "ForeArm.L", "Elbow.L"],
    "wrist.L": ["LeftHand", "mixamorig:LeftHand", "hand_l", "Hand.L", "Wrist.L"],
    "shoulder.R": ["RightArm", "RightShoulder", "mixamorig:RightArm", "mixamorig:RightShoulder", "upperarm_r", "UpperArm.R"],
    "elbow.R": ["RightForeArm", "mixamorig:RightForeArm", "lowerarm_r", "ForeArm.R", "Elbow.R"],
    "wrist.R": ["RightHand", "mixamorig:RightHand", "hand_r", "Hand.R", "Wrist.R"],
    "hip.L": ["LeftUpLeg", "mixamorig:LeftUpLeg", "thigh_l", "Thigh.L", "UpLeg.L"],
    "knee.L": ["LeftLeg", "mixamorig:LeftLeg", "calf_l", "Shin.L", "Leg.L", "Knee.L"],
    "ankle.L": ["LeftFoot", "mixamorig:LeftFoot", "foot_l", "Foot.L", "Ankle.L"],
    "hip.R": ["RightUpLeg", "mixamorig:RightUpLeg", "thigh_r", "Thigh.R", "UpLeg.R"],
    "knee.R": ["RightLeg", "mixamorig:RightLeg", "calf_r", "Shin.R", "Leg.R", "Knee.R"],
    "ankle.R": ["RightFoot", "mixamorig:RightFoot", "foot_r", "Foot.R", "Ankle.R"],
}


def _enable_addon() -> None:
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        return
    if ADDON_ZIP.exists():
        bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def _import_fbx(path: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _enable_addon()
    # Blender 5 FBX import operator name.
    if hasattr(bpy.ops.import_scene, "fbx"):
        bpy.ops.import_scene.fbx(
            filepath=str(path),
            automatic_bone_orientation=True,
            use_anim=False,
        )
    else:
        raise RuntimeError("FBX importer unavailable in this Blender build")


def _object_world_bounds(obj) -> dict:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    corners = [eval_obj.matrix_world @ Vector(c) for c in eval_obj.bound_box]
    mins = Vector((min(v.x for v in corners), min(v.y for v in corners), min(v.z for v in corners)))
    maxs = Vector((max(v.x for v in corners), max(v.y for v in corners), max(v.z for v in corners)))
    dims = maxs - mins
    center = (mins + maxs) * 0.5
    return {
        "name": obj.name,
        "type": obj.type,
        "location": [round(float(x), 6) for x in obj.location],
        "rotation_euler": [round(float(x), 6) for x in obj.rotation_euler],
        "scale": [round(float(x), 6) for x in obj.scale],
        "matrix_world_translation": [round(float(x), 6) for x in obj.matrix_world.translation],
        "bounds_min": [round(float(x), 6) for x in mins],
        "bounds_max": [round(float(x), 6) for x in maxs],
        "dimensions": [round(float(x), 6) for x in dims],
        "center": [round(float(x), 6) for x in center],
        "height_z": round(float(dims.z), 6),
        "width_xy_max": round(float(max(dims.x, dims.y)), 6),
        "depth_xy_min": round(float(min(dims.x, dims.y)), 6),
        "floor_z": round(float(mins.z), 6),
    }


def _pick_character_mesh():
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if not meshes:
        return None
    # Prefer skinned / largest vertex count mesh.
    meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
    return meshes[0]


def _pick_armature():
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not arms:
        return None
    arms.sort(key=lambda o: len(o.data.bones), reverse=True)
    return arms[0]


def _bone_world_head(arm, bone_name: str) -> Vector:
    bone = arm.data.bones[bone_name]
    return arm.matrix_world @ bone.head_local


def _resolve_bone_name(arm, landmark: str) -> str | None:
    names = {b.name for b in arm.data.bones}
    for candidate in BONE_CANDIDATES.get(landmark, []):
        if candidate in names:
            return candidate
    # Fuzzy contains fallback.
    landmark_key = landmark.replace(".", "").lower()
    for name in names:
        n = name.lower().replace("mixamorig:", "").replace("_", "")
        if landmark.endswith(".L") and ("left" not in n and n.endswith("l") is False and ".l" not in name.lower()):
            continue
        if landmark.endswith(".R") and ("right" not in n and n.endswith("r") is False and ".r" not in name.lower()):
            continue
        token = landmark.split(".")[0].lower()
        aliases = {
            "shoulder": ["arm", "shoulder", "upperarm"],
            "elbow": ["forearm", "lowerarm", "elbow"],
            "wrist": ["hand", "wrist"],
            "hip": ["upleg", "thigh", "hip"],
            "knee": ["leg", "calf", "shin", "knee"],
            "ankle": ["foot", "ankle"],
            "pelvis": ["hips", "pelvis"],
            "chest": ["spine1", "spine2", "chest"],
            "spine": ["spine"],
            "neck": ["neck"],
            "head": ["head"],
        }
        for alias in aliases.get(token, [token]):
            if alias in n:
                return name
    _ = landmark_key
    return None


def _axis_errors(delta: Vector) -> dict:
    # Front view error ≈ X, side view ≈ Y, top/height ≈ Z for -Y forward characters.
    return {
        "front_x": round(float(delta.x), 6),
        "side_y": round(float(delta.y), 6),
        "top_z": round(float(delta.z), 6),
        "euclidean": round(float(delta.length), 6),
        "euclidean_cm": round(float(delta.length) * 100.0, 3),
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": "NURION_MESHY_HUMANOID_VALIDATION",
        "version": "0.1.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": {
            "sourceZip": "Wither_character-rig.zip",
            "fbx": str(FBX_PATH),
            "exists": FBX_PATH.exists(),
        },
        "blender": bpy.app.version_string,
        "status": {},
        "import": {},
        "transforms": {},
        "measurements": {},
        "boneMap": {},
        "estimatedGuides": {},
        "errors": [],
        "jointErrors": [],
        "summary": {},
        "sealRecommendation": "NOT_SEALED",
    }

    try:
        if not FBX_PATH.exists():
            raise FileNotFoundError(FBX_PATH)

        _import_fbx(FBX_PATH)
        report["status"]["fbx_import"] = "PASS"

        mesh = _pick_character_mesh()
        arm = _pick_armature()
        report["import"] = {
            "objects": [{"name": o.name, "type": o.type} for o in bpy.data.objects],
            "mesh": mesh.name if mesh else None,
            "armature": arm.name if arm else None,
            "bone_count": len(arm.data.bones) if arm else 0,
            "bone_names": [b.name for b in arm.data.bones] if arm else [],
        }
        if mesh is None:
            raise RuntimeError("No mesh found after FBX import")

        report["transforms"]["mesh"] = _object_world_bounds(mesh)
        if arm:
            report["transforms"]["armature"] = {
                "name": arm.name,
                "location": [round(float(x), 6) for x in arm.location],
                "rotation_euler": [round(float(x), 6) for x in arm.rotation_euler],
                "scale": [round(float(x), 6) for x in arm.scale],
            }

        # Scale sanity: humanoid height typically 1.4–2.2m after import.
        height = report["transforms"]["mesh"]["height_z"]
        report["status"]["transform_inspect"] = "PASS"
        report["status"]["scale_plausible"] = "PASS" if 0.8 <= height <= 2.5 else "WARN"

        bpy.context.view_layer.objects.active = mesh
        mesh.select_set(True)
        bpy.ops.nurion.select_character()
        bpy.ops.nurion.analyze_character()
        scene = bpy.context.scene
        report["measurements"] = {
            "height": scene.nurion_height,
            "width": scene.nurion_width,
            "center": [scene.nurion_center_x, scene.nurion_center_y, scene.nurion_center_z],
            "floorZ": scene.nurion_floor_position,
            "forwardAxis": scene.nurion_forward_axis,
            "shoulderWidth_EST": scene.nurion_shoulder_width,
            "hipWidth_EST": scene.nurion_hip_width,
            "armLength_EST": scene.nurion_arm_length,
            "legLength_EST": scene.nurion_leg_length,
        }
        report["status"]["measure"] = "PASS"

        bpy.ops.nurion.create_body_guides()
        guides = {
            o.name.replace("NURION_LM_", ""): {
                "position": [round(float(x), 6) for x in o.matrix_world.translation],
                "source": str(o.get("nurion_source", "ESTIMATED")),
                "confidence": float(o.get("nurion_confidence", 0.0)),
                "reviewRequired": bool(o.get("nurion_review_required", True)),
            }
            for o in bpy.data.objects
            if o.name.startswith("NURION_LM_")
        }
        report["estimatedGuides"] = guides
        report["status"]["estimated_guides"] = "PASS" if guides else "FAIL"

        bpy.ops.nurion.save_landmark_profile(filepath=str(PROFILE_PATH))
        report["status"]["profile_export"] = "PASS" if PROFILE_PATH.exists() else "FAIL"

        joint_errors = []
        deltas_for_v02 = []
        if arm is None:
            report["status"]["joint_accuracy"] = "NOT_TESTED_NO_ARMATURE"
        else:
            for landmark, candidates in BONE_CANDIDATES.items():
                bone_name = _resolve_bone_name(arm, landmark)
                report["boneMap"][landmark] = bone_name
                if bone_name is None or landmark not in guides:
                    continue
                est = Vector(guides[landmark]["position"])
                truth = _bone_world_head(arm, bone_name)
                # MANUAL correction amount = truth - estimated (move guide by this delta)
                delta = truth - est
                axis = _axis_errors(delta)
                entry = {
                    "landmark": landmark,
                    "source": guides[landmark]["source"],
                    "reviewRequired": guides[landmark]["reviewRequired"],
                    "bone": bone_name,
                    "estimated": [round(float(x), 6) for x in est],
                    "boneHead": [round(float(x), 6) for x in truth],
                    "manualCorrectionDelta": [round(float(x), 6) for x in delta],
                    "errors": axis,
                }
                joint_errors.append(entry)
                deltas_for_v02.append(
                    {
                        "name": landmark,
                        "from": "ESTIMATED",
                        "to": "MANUAL_TARGET_FROM_FBX_BONE",
                        "bone": bone_name,
                        "delta": entry["manualCorrectionDelta"],
                        "errors": axis,
                    }
                )

            report["jointErrors"] = joint_errors
            if joint_errors:
                eu = [e["errors"]["euclidean"] for e in joint_errors]
                report["summary"] = {
                    "mappedJoints": len(joint_errors),
                    "meanError_m": round(sum(eu) / len(eu), 6),
                    "meanError_cm": round((sum(eu) / len(eu)) * 100.0, 3),
                    "maxError_m": round(max(eu), 6),
                    "maxError_cm": round(max(eu) * 100.0, 3),
                    "meanAbsFront_x_cm": round(sum(abs(e["errors"]["front_x"]) for e in joint_errors) / len(joint_errors) * 100.0, 3),
                    "meanAbsSide_y_cm": round(sum(abs(e["errors"]["side_y"]) for e in joint_errors) / len(joint_errors) * 100.0, 3),
                    "meanAbsTop_z_cm": round(sum(abs(e["errors"]["top_z"]) for e in joint_errors) / len(joint_errors) * 100.0, 3),
                    "worst": max(joint_errors, key=lambda e: e["errors"]["euclidean"]),
                }
                report["status"]["joint_accuracy"] = "MEASURED_AGAINST_FBX_BONES"
            else:
                report["status"]["joint_accuracy"] = "NOT_TESTED_NO_BONE_MAP"

        deltas_payload = {
            "schema": "NURION_MANUAL_CORRECTION_DELTAS",
            "version": "0.1.0",
            "purpose": "Baseline error targets for v0.2 AI Landmarker",
            "asset": report["asset"]["sourceZip"],
            "characterMesh": mesh.name,
            "armature": arm.name if arm else None,
            "deltas": deltas_for_v02,
            "summary": report.get("summary", {}),
        }
        DELTAS_PATH.write_text(json.dumps(deltas_payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        # SEAL decision: Meshy path exercised and joint errors recorded. SEALED remains a product
        # decision; this script marks READY_FOR_SEAL_REVIEW when mapping succeeded.
        if report["status"].get("joint_accuracy") == "MEASURED_AGAINST_FBX_BONES":
            report["sealRecommendation"] = "READY_FOR_SEAL_REVIEW"
            report["status"]["meshy_humanoid_validation"] = "PASS_DATA_CAPTURED"
        else:
            report["sealRecommendation"] = "NOT_SEALED"
            report["status"]["meshy_humanoid_validation"] = "INCOMPLETE"

        report["outputs"] = {
            "report": str(REPORT_PATH),
            "estimatedProfile": str(PROFILE_PATH),
            "manualCorrectionDeltas": str(DELTAS_PATH),
        }

    except Exception as exc:
        report["errors"].append(
            {
                "type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        report["sealRecommendation"] = "NOT_SEALED"
        report["status"]["meshy_humanoid_validation"] = "FAIL"

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
