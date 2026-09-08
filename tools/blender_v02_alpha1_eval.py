"""
v0.2.0-alpha.1 Geometry Correction evaluation on Wither FBX.

Writes reports under dist/v0.2/ only. Does not modify v0.1 seal artifacts.
"""

from __future__ import annotations

import hashlib
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
ADDON_ZIP = ROOT / "dist" / "v0.2" / "NURION_Character_Landmarker_v0.2.0-alpha.1.zip"
ADDON_MODULE = "nurion_character_landmarker"
OUT = ROOT / "dist" / "v0.2"
REPORTS = OUT / "reports"
PROFILES = OUT / "profiles"

BASELINE = {
    "meanError_cm": 14.097,
    "maxError_cm": 34.414,
    "worstLandmark": "wrist.L",
}

JOINTS_17 = [
    "pelvis",
    "spine",
    "chest",
    "neck",
    "head",
    "shoulder.L",
    "elbow.L",
    "wrist.L",
    "shoulder.R",
    "elbow.R",
    "wrist.R",
    "hip.L",
    "knee.L",
    "ankle.L",
    "hip.R",
    "knee.R",
    "ankle.R",
]


def _enable_addon() -> None:
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    if not ADDON_ZIP.exists():
        raise FileNotFoundError(ADDON_ZIP)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def _import_scene() -> tuple:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _enable_addon()
    bpy.ops.import_scene.fbx(filepath=str(FBX_PATH), automatic_bone_orientation=True, use_anim=False)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes.sort(key=lambda o: len(o.data.vertices), reverse=True)
    arms.sort(key=lambda o: len(o.data.bones), reverse=True)
    return meshes[0], (arms[0] if arms else None)


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _err(a: Vector, b: Vector) -> dict:
    d = b - a
    return {
        "front_x": round(float(d.x), 6),
        "side_y": round(float(d.y), 6),
        "top_z": round(float(d.z), 6),
        "euclidean": round(float(d.length), 6),
        "euclidean_cm": round(float(d.length) * 100.0, 3),
    }


def main() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)
    PROFILES.mkdir(parents=True, exist_ok=True)

    # Ensure package exists.
    sys.path.insert(0, str(ROOT))
    from tools.pack_v02_zip import pack

    pack()
    mesh, arm = _import_scene()

    # Import after addon enable to avoid duplicated module class identities.
    import importlib
    import nurion_character_landmarker
    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.determinism import serialize_landmarks_for_hash
    from nurion_character_landmarker.core.geometry_correction import correct_landmarks_geometry
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.leak_guard import generation_scope, reset_gt_access_log
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view, point_inside_mesh
    from nurion_character_landmarker.evaluation.gt_bones import collect_gt_landmarks
    from nurion_character_landmarker.profiles.nurion_landmark_profile import (
        NurionCharacterProfile,
        measurements_payload,
        save_profile,
    )
    from nurion_character_landmarker.core.coordinate_solver import solve_coordinates

    def _is_gt_leak(exc: BaseException) -> bool:
        return type(exc).__name__ == "GroundTruthLeakError"

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)

    # --- Generation path (NO armature) ---
    reset_gt_access_log()
    estimated = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)

    leak_fail = False
    leak_notes = []
    try:
        with generation_scope("alpha1_leak_probe"):
            collect_gt_landmarks(arm, ["pelvis"])
        leak_fail = True
        leak_notes.append("GT access did not raise inside generation_scope")
    except Exception as exc:
        if _is_gt_leak(exc):
            leak_notes.append("GT access correctly blocked during generation_scope")
        else:
            raise

    try:
        correct_landmarks_geometry(mesh, estimated, armature=arm)
        leak_fail = True
        leak_notes.append("armature kwarg was not rejected")
    except Exception as exc:
        if _is_gt_leak(exc):
            leak_notes.append("armature kwarg correctly rejected")
        else:
            raise

    reset_gt_access_log()
    geom = correct_landmarks_geometry(mesh, estimated, view=view, apply_symmetry=True)

    # Determinism: 3 runs
    hashes = []
    payloads = []
    for _ in range(3):
        run = correct_landmarks_geometry(mesh, estimated, view=view, apply_symmetry=True)
        text = serialize_landmarks_for_hash(run.landmarks, JOINTS_17)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        hashes.append(digest)
        payloads.append(text)
    determinism_pass = len(set(hashes)) == 1

    # Save profiles
    est_profile = NurionCharacterProfile(
        character_id="wither-meshy-biped",
        character_height=measurements.height.value,
        width=measurements.width.value,
        center=list(measurements.center),
        forward_axis=measurements.forward_axis,
        floor_z=measurements.floor_position.value,
        measurements=measurements_payload(measurements),
        landmarks=solve_coordinates(estimated),
    )
    geom_profile = NurionCharacterProfile(
        character_id="wither-meshy-biped",
        character_height=measurements.height.value,
        width=measurements.width.value,
        center=list(measurements.center),
        forward_axis=measurements.forward_axis,
        floor_z=measurements.floor_position.value,
        measurements=measurements_payload(measurements),
        landmarks=solve_coordinates(geom.landmarks),
    )
    save_profile(est_profile, PROFILES / "wither.estimated.json")
    save_profile(geom_profile, PROFILES / "wither.geometry-corrected.json")

    # --- Evaluation path (GT bones OK here) ---
    gt = collect_gt_landmarks(arm, JOINTS_17) if arm else {}

    def compare(landmarks: dict, label: str) -> dict:
        rows = []
        for name in JOINTS_17:
            if name not in landmarks or name not in gt:
                continue
            est = landmarks[name].position
            truth = Vector(gt[name]["position"])
            e = _err(est, truth)
            rows.append(
                {
                    "landmark": name,
                    "source": landmarks[name].source,
                    "reviewRequired": landmarks[name].review_required,
                    "bone": gt[name]["bone"],
                    "predicted": [round(float(x), 6) for x in est],
                    "gt": gt[name]["position"],
                    "errors": e,
                }
            )
        eu = [r["errors"]["euclidean"] for r in rows]
        summary = {
            "label": label,
            "mappedJoints": len(rows),
            "meanError_cm": round(sum(eu) / len(eu) * 100.0, 3) if eu else None,
            "maxError_cm": round(max(eu) * 100.0, 3) if eu else None,
            "worstLandmark": max(rows, key=lambda r: r["errors"]["euclidean"])["landmark"] if rows else None,
            "meanAbsX_cm": round(sum(abs(r["errors"]["front_x"]) for r in rows) / len(rows) * 100.0, 3) if rows else None,
            "meanAbsY_cm": round(sum(abs(r["errors"]["side_y"]) for r in rows) / len(rows) * 100.0, 3) if rows else None,
            "meanAbsZ_cm": round(sum(abs(r["errors"]["top_z"]) for r in rows) / len(rows) * 100.0, 3) if rows else None,
        }
        return {"summary": summary, "joints": rows}

    est_cmp = compare(estimated, "ESTIMATED")
    geom_cmp = compare(geom.landmarks, "GEOMETRY_CORRECTED_MIXED")

    improved = worsened = unchanged = 0
    improved_changed = worsened_changed = 0
    per_joint = []
    est_map = {r["landmark"]: r["errors"]["euclidean_cm"] for r in est_cmp["joints"]}
    for row in geom_cmp["joints"]:
        name = row["landmark"]
        before = est_map.get(name)
        after = row["errors"]["euclidean_cm"]
        delta = None if before is None else round(after - before, 3)
        changed = row["source"] == "GEOMETRY_CORRECTED"
        if before is not None:
            if after < before - 1e-6:
                improved += 1
                if changed:
                    improved_changed += 1
            elif after > before + 1e-6:
                worsened += 1
                if changed:
                    worsened_changed += 1
            else:
                unchanged += 1
        per_joint.append(
            {
                "landmark": name,
                "source": row["source"],
                "estimated_cm": before,
                "geometry_cm": after,
                "delta_cm": delta,
                "changed": changed,
            }
        )

    # Outside mesh validation on final GEOMETRY_CORRECTED points
    outside = []
    for name in JOINTS_17:
        p = geom.landmarks.get(name)
        if p is None:
            continue
        inside = point_inside_mesh(view, p.position)
        if not inside:
            outside.append(name)

    lr_swaps = geom.constraints.left_right_swaps

    mean_g = geom_cmp["summary"]["meanError_cm"]
    max_g = geom_cmp["summary"]["maxError_cm"]

    alpha_gates = {
        "mean_lt_baseline_14_097": bool(mean_g is not None and mean_g < BASELINE["meanError_cm"]),
        "max_lt_baseline_34_414": bool(max_g is not None and max_g < BASELINE["maxError_cm"]),
        "improved_gt_worsened": improved > worsened,
        "lr_swap_zero": len(lr_swaps) == 0,
        "outside_mesh_zero": len(outside) == 0,
        "determinism_pass": determinism_pass,
        "gt_leak_guard_pass": not leak_fail,
    }
    # Partial success must not mark overall success.
    alpha_pass = all(alpha_gates.values())

    geometry_report = {
        "schema": "NURION_GEOMETRY_CORRECTION_REPORT",
        "version": "0.2.0-alpha.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "asset": str(FBX_PATH),
        "mesh": mesh.name,
        "corrected": geom.corrected,
        "keptEstimated": geom.kept_estimated,
        "outsideRejected": geom.outside_rejected,
        "chainRejected": geom.constraints.rejected_chain,
        "symmetryApplied": geom.constraints.symmetry_applied,
        "notes": geom.notes,
        "leakGuard": {"pass": not leak_fail, "notes": leak_notes},
        "counts": {
            "corrected": len(geom.corrected),
            "keptEstimated": len(geom.kept_estimated),
            "improved": improved,
            "worsened": worsened,
            "unchanged": unchanged,
        },
    }
    _write_json(REPORTS / "geometry-correction-report.json", geometry_report)

    comparison = {
        "schema": "NURION_17_JOINT_ERROR_COMPARISON",
        "version": "0.2.0-alpha.1",
        "baseline_v0_1": BASELINE,
        "estimated": est_cmp,
        "geometry": geom_cmp,
        "perJointDelta": per_joint,
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
    }
    _write_json(REPORTS / "17-joint-error-comparison.json", comparison)

    _write_json(
        REPORTS / "outside-mesh-validation.json",
        {
            "schema": "NURION_OUTSIDE_MESH_VALIDATION",
            "version": "0.2.0-alpha.1",
            "outsideCount": len(outside),
            "outsideJoints": outside,
            "pass": len(outside) == 0,
        },
    )
    _write_json(
        REPORTS / "left-right-validation.json",
        {
            "schema": "NURION_LEFT_RIGHT_VALIDATION",
            "version": "0.2.0-alpha.1",
            "swapCount": len(lr_swaps),
            "swaps": lr_swaps,
            "pass": len(lr_swaps) == 0,
        },
    )
    _write_json(
        REPORTS / "determinism-report.json",
        {
            "schema": "NURION_DETERMINISM_REPORT",
            "version": "0.2.0-alpha.1",
            "runs": 3,
            "hashes": hashes,
            "pass": determinism_pass,
        },
    )

    alpha_report = {
        "schema": "NURION_V0.2_ALPHA1_VERDICT",
        "version": "0.2.0-alpha.1",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "package": "NURION_Character_Landmarker_v0.2.0-alpha.1.zip",
        "packageSha256": hashlib.sha256(ADDON_ZIP.read_bytes()).hexdigest(),
        "alphaGates": alpha_gates,
        "alphaPass": alpha_pass,
        "metrics": {
            "meanError_cm": mean_g,
            "maxError_cm": max_g,
            "improved": improved,
            "worsened": worsened,
            "improvedChangedOnly": improved_changed,
            "worsenedChangedOnly": worsened_changed,
            "lrSwaps": len(lr_swaps),
            "outsideMesh": len(outside),
        },
        "finalGates_not_required_for_alpha1": {
            "mean_lt_7": bool(mean_g is not None and mean_g < 7.0),
            "max_lt_15": bool(max_g is not None and max_g < 15.0),
        },
        "note": "Alpha.1 validates improvement direction, not final quality gates.",
    }
    _write_json(OUT / "ALPHA1_VERDICT.json", alpha_report)
    print(json.dumps(alpha_report, indent=2, ensure_ascii=False))
    return 0 if alpha_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
