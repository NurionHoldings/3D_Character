"""
v0.2.0-alpha.2 evaluation on Wither FBX.

Writes ONLY under dist/v0.2/alpha2/. Does not modify alpha.1 or v0.1 artifacts.
"""

from __future__ import annotations

import hashlib
import json
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
ADDON_ZIP = ROOT / "dist" / "v0.2" / "NURION_Character_Landmarker_v0.2.0-alpha.2.zip"
ADDON_MODULE = "nurion_character_landmarker"
OUT = ROOT / "dist" / "v0.2" / "alpha2"
REPORTS = OUT / "reports"
PROFILES = OUT / "profiles"
ALPHA1_LOCK = ROOT / "dist" / "v0.2" / "ALPHA1_LOCK.json"

ALPHA1_METRICS = {"meanError_cm": 10.334, "maxError_cm": 25.083}
JOINTS_17 = [
    "pelvis", "spine", "chest", "neck", "head",
    "shoulder.L", "elbow.L", "wrist.L",
    "shoulder.R", "elbow.R", "wrist.R",
    "hip.L", "knee.L", "ankle.L",
    "hip.R", "knee.R", "ankle.R",
]


def _enable_addon() -> None:
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def _import():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    _enable_addon()
    bpy.ops.import_scene.fbx(filepath=str(FBX_PATH), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
    arms = sorted([o for o in bpy.data.objects if o.type == "ARMATURE"], key=lambda o: len(o.data.bones), reverse=True)
    return meshes[0], arms[0]


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _err(a: Vector, b: Vector) -> dict:
    d = b - a
    return {
        "front_x": round(float(d.x), 6),
        "side_y": round(float(d.y), 6),
        "top_z": round(float(d.z), 6),
        "euclidean_cm": round(float(d.length) * 100.0, 3),
    }


def main() -> int:
    import sys
    import json as _json

    sys.path.insert(0, str(ROOT))
    lock_path = OUT / "ALPHA2_LOCK.json"
    if lock_path.exists():
        lock = _json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("frozen"):
            raise RuntimeError(
                "alpha.2 is frozen (ALPHA2_LOCK.json). Do not re-eval; ship a new version path."
            )

    from tools.pack_v02_alpha2_zip import pack

    pack()
    # Guard: alpha1 reports directory must still exist untouched conceptually.
    if not ALPHA1_LOCK.exists():
        raise RuntimeError("ALPHA1_LOCK.json missing")

    mesh, arm = _import()

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.coordinate_solver import solve_coordinates
    from nurion_character_landmarker.core.determinism import serialize_landmarks_for_hash
    from nurion_character_landmarker.core.geometry_correction import correct_landmarks_geometry
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.leak_guard import generation_scope, reset_gt_access_log
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view, point_inside_mesh
    from nurion_character_landmarker.evaluation.gt_bones import collect_gt_landmarks
    from nurion_character_landmarker.profiles.nurion_landmark_profile import (
        NurionCharacterProfile,
        measurements_payload,
        save_profile,
    )

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    estimated = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)

    leak_fail = False
    try:
        with generation_scope("alpha2_leak"):
            collect_gt_landmarks(arm, ["pelvis"])
        leak_fail = True
    except Exception as exc:
        if type(exc).__name__ != "GroundTruthLeakError":
            raise

    try:
        correct_landmarks_geometry(mesh, estimated, armature=arm)
        leak_fail = True
    except Exception as exc:
        if type(exc).__name__ != "GroundTruthLeakError":
            raise

    reset_gt_access_log()
    geom = correct_landmarks_geometry(mesh, estimated, view=view, apply_symmetry=True)

    hashes = []
    for _ in range(3):
        run = correct_landmarks_geometry(mesh, estimated, view=view, apply_symmetry=True)
        hashes.append(hashlib.sha256(serialize_landmarks_for_hash(run.landmarks, JOINTS_17).encode()).hexdigest())
    determinism_pass = len(set(hashes)) == 1

    save_profile(
        NurionCharacterProfile(
            character_id="wither-meshy-biped",
            character_height=measurements.height.value,
            width=measurements.width.value,
            center=list(measurements.center),
            forward_axis=measurements.forward_axis,
            floor_z=measurements.floor_position.value,
            measurements=measurements_payload(measurements),
            landmarks=solve_coordinates(estimated),
        ),
        PROFILES / "wither.estimated.json",
    )
    save_profile(
        NurionCharacterProfile(
            character_id="wither-meshy-biped",
            character_height=measurements.height.value,
            width=measurements.width.value,
            center=list(measurements.center),
            forward_axis=measurements.forward_axis,
            floor_z=measurements.floor_position.value,
            measurements=measurements_payload(measurements),
            landmarks=solve_coordinates(geom.landmarks),
        ),
        PROFILES / "wither.geometry-corrected.json",
    )

    gt = collect_gt_landmarks(arm, JOINTS_17)

    def compare(landmarks: dict, label: str):
        rows = []
        for name in JOINTS_17:
            if name not in landmarks or name not in gt:
                continue
            e = _err(landmarks[name].position, Vector(gt[name]["position"]))
            rows.append(
                {
                    "landmark": name,
                    "source": landmarks[name].source,
                    "reviewRequired": landmarks[name].review_required,
                    "evidence": landmarks[name].evidence,
                    "predicted": [round(float(x), 6) for x in landmarks[name].position],
                    "gt": gt[name]["position"],
                    "errors": e,
                }
            )
        eu = [r["errors"]["euclidean_cm"] for r in rows]
        return {
            "label": label,
            "summary": {
                "mappedJoints": len(rows),
                "meanError_cm": round(sum(eu) / len(eu), 3) if eu else None,
                "maxError_cm": round(max(eu), 3) if eu else None,
                "worstLandmark": max(rows, key=lambda r: r["errors"]["euclidean_cm"])["landmark"] if rows else None,
            },
            "joints": rows,
        }

    est_cmp = compare(estimated, "ESTIMATED")
    geom_cmp = compare(geom.landmarks, "GEOMETRY_ALPHA2")

    # Load alpha1 geometry profile errors if available for worsen checks vs alpha1.
    alpha1_profile = ROOT / "dist" / "v0.2" / "profiles" / "wither.geometry-corrected.json"
    alpha1_err = {}
    if alpha1_profile.exists():
        # Recompute alpha1 errors from frozen profile positions vs current GT.
        data = json.loads(alpha1_profile.read_text(encoding="utf-8"))
        for entry in data.get("landmarks", []):
            name = entry.get("name")
            if name not in gt:
                continue
            pos = Vector(entry["position"])
            alpha1_err[name] = (pos - Vector(gt[name]["position"])).length * 100.0

    improved = worsened = 0
    worsen_over_2 = []
    per = []
    est_map = {r["landmark"]: r["errors"]["euclidean_cm"] for r in est_cmp["joints"]}
    a1_worsened = 0
    for row in geom_cmp["joints"]:
        name = row["landmark"]
        before = est_map.get(name)
        after = row["errors"]["euclidean_cm"]
        if before is not None:
            if after < before - 1e-6:
                improved += 1
            elif after > before + 1e-6:
                worsened += 1
        if name in alpha1_err:
            delta_a1 = after - alpha1_err[name]
            # Ignore sub-mm noise when counting regressions vs frozen alpha1.
            if delta_a1 > 0.5:
                a1_worsened += 1
            if delta_a1 > 2.0 + 1e-6:
                worsen_over_2.append({"landmark": name, "delta_cm": round(delta_a1, 3)})
        per.append({"landmark": name, "estimated_cm": before, "alpha2_cm": after, "alpha1_cm": alpha1_err.get(name)})

    outside = [n for n in JOINTS_17 if n in geom.landmarks and not point_inside_mesh(view, geom.landmarks[n].position)]
    swaps = geom.constraints.left_right_swaps

    def avg(names):
        vals = [r["errors"]["euclidean_cm"] for r in geom_cmp["joints"] if r["landmark"] in names]
        return round(sum(vals) / len(vals), 3) if vals else None

    wrist_l = next((r["errors"]["euclidean_cm"] for r in geom_cmp["joints"] if r["landmark"] == "wrist.L"), None)
    wrist_r = next((r["errors"]["euclidean_cm"] for r in geom_cmp["joints"] if r["landmark"] == "wrist.R"), None)
    mean_g = geom_cmp["summary"]["meanError_cm"]
    max_g = geom_cmp["summary"]["maxError_cm"]

    gates = {
        "mean_lt_8_5": bool(mean_g is not None and mean_g < 8.5),
        "max_lt_18": bool(max_g is not None and max_g < 18.0),
        "wrist_L_lt_15": bool(wrist_l is not None and wrist_l < 15.0),
        "wrist_R_lt_15": bool(wrist_r is not None and wrist_r < 15.0),
        "shoulder_avg_lt_10": bool((avg(["shoulder.L", "shoulder.R"]) or 99) < 10.0),
        "pelvis_hip_avg_lt_10": bool((avg(["pelvis", "hip.L", "hip.R"]) or 99) < 10.0),
        "alpha1_worsened_le_2": a1_worsened <= 2,
        "per_joint_worsen_le_2cm": len(worsen_over_2) == 0,
        "lr_swap_zero": len(swaps) == 0,
        "outside_zero": len(outside) == 0,
        "gt_leak_zero": not leak_fail,
        "determinism_pass": determinism_pass,
    }
    alpha_pass = all(gates.values())

    _write(REPORTS / "geometry-correction-report.json", {
        "schema": "NURION_GEOMETRY_CORRECTION_REPORT",
        "version": "0.2.0-alpha.2",
        "corrected": geom.corrected,
        "keptEstimated": geom.kept_estimated,
        "notes": geom.notes,
        "methods": ["WRIST_TRANSITION_V1", "SHOULDER_BRANCH_V1", "SIDE_HIP_V1"],
    })
    _write(REPORTS / "17-joint-error-comparison.json", {
        "schema": "NURION_17_JOINT_ERROR_COMPARISON",
        "version": "0.2.0-alpha.2",
        "alpha1": ALPHA1_METRICS,
        "estimated": est_cmp,
        "geometry": geom_cmp,
        "perJoint": per,
        "improvedVsEstimated": improved,
        "worsenedVsEstimated": worsened,
        "worsenedVsAlpha1": a1_worsened,
        "worsenOver2cmVsAlpha1": worsen_over_2,
    })
    _write(REPORTS / "outside-mesh-validation.json", {"pass": len(outside) == 0, "outsideJoints": outside})
    _write(REPORTS / "left-right-validation.json", {"pass": len(swaps) == 0, "swaps": swaps})
    _write(REPORTS / "determinism-report.json", {"pass": determinism_pass, "hashes": hashes, "runs": 3})
    _write(REPORTS / "joint-focus-metrics.json", {
        "wrist.L_cm": wrist_l,
        "wrist.R_cm": wrist_r,
        "shoulder_avg_cm": avg(["shoulder.L", "shoulder.R"]),
        "pelvis_hip_avg_cm": avg(["pelvis", "hip.L", "hip.R"]),
    })

    verdict = {
        "schema": "NURION_V0.2_ALPHA2_VERDICT",
        "version": "0.2.0-alpha.2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "package": "NURION_Character_Landmarker_v0.2.0-alpha.2.zip",
        "packageSha256": hashlib.sha256(ADDON_ZIP.read_bytes()).hexdigest(),
        "alpha1FrozenSha256": "915bb5be9894086bdd344463a2fab27c74b4ad2ef016439ed4ca0e1b8be0dc01",
        "gates": gates,
        "alphaPass": alpha_pass,
        "metrics": {
            "meanError_cm": mean_g,
            "maxError_cm": max_g,
            "wrist.L_cm": wrist_l,
            "wrist.R_cm": wrist_r,
            "shoulder_avg_cm": avg(["shoulder.L", "shoulder.R"]),
            "pelvis_hip_avg_cm": avg(["pelvis", "hip.L", "hip.R"]),
            "worsenedVsAlpha1": a1_worsened,
            "worsenOver2cmCount": len(worsen_over_2),
        },
        "finalGates_not_required": {
            "mean_lt_7": bool(mean_g is not None and mean_g < 7.0),
            "max_lt_15": bool(max_g is not None and max_g < 15.0),
        },
    }
    _write(OUT / "ALPHA2_VERDICT.json", verdict)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if alpha_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
