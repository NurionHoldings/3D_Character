"""
v0.2.0-alpha.3 evaluation on Wither FBX.

Writes ONLY under dist/v0.2/alpha3/. Does not modify alpha.1 / alpha.2 / v0.1 artifacts.
"""

from __future__ import annotations

import hashlib
import json
import math
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
ADDON_ZIP = ROOT / "dist" / "v0.2" / "NURION_Character_Landmarker_v0.2.0-alpha.3.zip"
ADDON_MODULE = "nurion_character_landmarker"
OUT = ROOT / "dist" / "v0.2" / "alpha3"
REPORTS = OUT / "reports"
PROFILES = OUT / "profiles"
ALPHA1_LOCK = ROOT / "dist" / "v0.2" / "ALPHA1_LOCK.json"
ALPHA2_LOCK = ROOT / "dist" / "v0.2" / "alpha2" / "ALPHA2_LOCK.json"

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


def _load_profile_errors(path: Path, gt: dict) -> dict:
    out = {}
    if not path.exists():
        return out
    data = json.loads(path.read_text(encoding="utf-8"))
    for entry in data.get("landmarks", []):
        name = entry.get("name")
        if name not in gt:
            continue
        pos = Vector(entry["position"])
        out[name] = (pos - Vector(gt[name]["position"])).length * 100.0
    return out


def _pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx = sum(xs) / len(xs)
    my = sum(ys) / len(ys)
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    denx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    deny = math.sqrt(sum((y - my) ** 2 for y in ys))
    if denx < 1e-12 or deny < 1e-12:
        return None
    return round(num / (denx * deny), 4)


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT))
    lock_path = OUT / "ALPHA3_LOCK.json"
    if lock_path.exists():
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        if lock.get("frozen"):
            raise RuntimeError(
                "alpha.3 is frozen (ALPHA3_LOCK.json). Do not re-eval; ship a new version path."
            )

    if not ALPHA1_LOCK.exists():
        raise RuntimeError("ALPHA1_LOCK.json missing")
    if not ALPHA2_LOCK.exists():
        raise RuntimeError("ALPHA2_LOCK.json missing")
    a2_lock = json.loads(ALPHA2_LOCK.read_text(encoding="utf-8"))
    if not a2_lock.get("frozen"):
        raise RuntimeError("alpha.2 must remain frozen")

    from tools.pack_v02_alpha3_zip import pack

    pack()

    mesh, arm = _import()

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.alpha3_parameters import (
        ALPHA3_PARAMETER_HASH,
        ALPHA3_PARAMETERS,
        parameter_hash,
    )
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

    # Freeze / record parameter hash BEFORE geometry generation & GT evaluation.
    live_hash = parameter_hash(ALPHA3_PARAMETERS)
    if live_hash != ALPHA3_PARAMETER_HASH:
        raise RuntimeError("ALPHA3_PARAMETER_HASH mismatch — parameters changed without freeze update")
    _write(
        REPORTS / "parameter-hash.json",
        {
            "schema": "NURION_ALPHA3_PARAMETER_HASH",
            "version": "0.2.0-alpha.3",
            "sha256": live_hash,
            "parameters": ALPHA3_PARAMETERS,
            "note": "Hashed before geometry generation and before GT evaluation.",
        },
    )

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    estimated = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)

    leak_fail = False
    try:
        with generation_scope("alpha3_leak"):
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

    # GT evaluation ONLY after geometry generation completes.
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
                    "confidence": round(float(landmarks[name].confidence), 4),
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
    geom_cmp = compare(geom.landmarks, "GEOMETRY_ALPHA3")

    alpha1_err = _load_profile_errors(
        ROOT / "dist" / "v0.2" / "profiles" / "wither.geometry-corrected.json", gt
    )
    alpha2_err = _load_profile_errors(
        ROOT / "dist" / "v0.2" / "alpha2" / "profiles" / "wither.geometry-corrected.json", gt
    )

    improved = worsened = 0
    worsen_over_15 = []
    a2_worsened = 0
    per = []
    est_map = {r["landmark"]: r["errors"]["euclidean_cm"] for r in est_cmp["joints"]}
    for row in geom_cmp["joints"]:
        name = row["landmark"]
        before = est_map.get(name)
        after = row["errors"]["euclidean_cm"]
        if before is not None:
            if after < before - 1e-6:
                improved += 1
            elif after > before + 1e-6:
                worsened += 1
        if name in alpha2_err:
            delta_a2 = after - alpha2_err[name]
            if delta_a2 > 0.5:
                a2_worsened += 1
            if delta_a2 > 1.5 + 1e-6:
                worsen_over_15.append({"landmark": name, "delta_cm": round(delta_a2, 3)})
        per.append(
            {
                "landmark": name,
                "estimated_cm": before,
                "alpha1_cm": round(alpha1_err[name], 3) if name in alpha1_err else None,
                "alpha2_cm": round(alpha2_err[name], 3) if name in alpha2_err else None,
                "alpha3_cm": after,
                "delta_alpha2_to_alpha3_cm": round(after - alpha2_err[name], 3) if name in alpha2_err else None,
            }
        )

    outside = [n for n in JOINTS_17 if n in geom.landmarks and not point_inside_mesh(view, geom.landmarks[n].position)]
    swaps = geom.constraints.left_right_swaps

    def joint_cm(name):
        return next((r["errors"]["euclidean_cm"] for r in geom_cmp["joints"] if r["landmark"] == name), None)

    mean_g = geom_cmp["summary"]["meanError_cm"]
    max_g = geom_cmp["summary"]["maxError_cm"]

    gates = {
        "mean_lt_7": bool(mean_g is not None and mean_g < 7.0),
        "max_lt_15": bool(max_g is not None and max_g < 15.0),
        "elbow_L_lt_10": bool((joint_cm("elbow.L") or 99) < 10.0),
        "elbow_R_lt_10": bool((joint_cm("elbow.R") or 99) < 10.0),
        "knee_L_lt_10": bool((joint_cm("knee.L") or 99) < 10.0),
        "knee_R_lt_10": bool((joint_cm("knee.R") or 99) < 10.0),
        "ankle_L_lt_10": bool((joint_cm("ankle.L") or 99) < 10.0),
        "ankle_R_lt_10": bool((joint_cm("ankle.R") or 99) < 10.0),
        "alpha2_worsened_le_2": a2_worsened <= 2,
        "per_joint_worsen_le_1_5cm": len(worsen_over_15) == 0,
        "lr_swap_zero": len(swaps) == 0,
        "outside_zero": len(outside) == 0,
        "gt_leak_zero": not leak_fail,
        "determinism_pass": determinism_pass,
        "parameter_hash_fixed": live_hash == ALPHA3_PARAMETER_HASH,
    }
    alpha_pass = all(gates.values())

    top5 = sorted(geom_cmp["joints"], key=lambda r: r["errors"]["euclidean_cm"], reverse=True)[:5]
    accept_reject = []
    for row in geom_cmp["joints"]:
        ev = row.get("evidence") or {}
        accept_reject.append(
            {
                "landmark": row["landmark"],
                "source": row["source"],
                "method": ev.get("method"),
                "acceptReject": ev.get("acceptReject") or ev.get("reason") or ("accepted" if row["source"] == "GEOMETRY_CORRECTED" else "kept_or_reverted"),
                "keptBaseline": ev.get("keptBaseline"),
                "reverted": ev.get("reverted"),
                "selectedScore": ev.get("selectedScore"),
                "runnerUpScore": ev.get("runnerUpScore"),
                "confidence": row.get("confidence"),
                "error_cm": row["errors"]["euclidean_cm"],
            }
        )

    confs = [r["confidence"] for r in geom_cmp["joints"]]
    errs = [r["errors"]["euclidean_cm"] for r in geom_cmp["joints"]]
    review_required = sorted(r["landmark"] for r in geom_cmp["joints"] if r["reviewRequired"])

    _write(REPORTS / "geometry-correction-report.json", {
        "schema": "NURION_GEOMETRY_CORRECTION_REPORT",
        "version": "0.2.0-alpha.3",
        "corrected": geom.corrected,
        "keptEstimated": geom.kept_estimated,
        "notes": geom.notes,
        "methods": [
            "ELBOW_BEND_V1",
            "KNEE_AXIS_V1",
            "ANKLE_TRANSITION_V2",
            "WRIST_TRANSITION_V1",
            "SHOULDER_BRANCH_V1",
            "SIDE_HIP_V1",
            "EVIDENCE_PRODUCT_V1",
        ],
        "parameterHash": live_hash,
    })
    _write(REPORTS / "17-joint-error-comparison.json", {
        "schema": "NURION_17_JOINT_ERROR_COMPARISON",
        "version": "0.2.0-alpha.3",
        "estimated": est_cmp,
        "geometry": geom_cmp,
        "perJoint": per,
        "improvedVsEstimated": improved,
        "worsenedVsEstimated": worsened,
        "worsenedVsAlpha2": a2_worsened,
        "worsenOver1_5cmVsAlpha2": worsen_over_15,
    })
    _write(REPORTS / "outside-mesh-validation.json", {"pass": len(outside) == 0, "outsideJoints": outside})
    _write(REPORTS / "left-right-validation.json", {"pass": len(swaps) == 0, "swaps": swaps})
    _write(REPORTS / "determinism-report.json", {"pass": determinism_pass, "hashes": hashes, "runs": 3})
    _write(REPORTS / "top5-worst-joints.json", {
        "schema": "NURION_TOP5_WORST_JOINTS",
        "joints": [
            {
                "landmark": r["landmark"],
                "error_cm": r["errors"]["euclidean_cm"],
                "source": r["source"],
                "confidence": r["confidence"],
            }
            for r in top5
        ],
    })
    _write(REPORTS / "alpha-progression.json", {
        "schema": "NURION_ALPHA_PROGRESSION",
        "note": "Per-joint Alpha1 → Alpha2 → Alpha3 error (cm)",
        "joints": per,
    })
    _write(REPORTS / "geometry-accept-reject.json", {
        "schema": "NURION_GEOMETRY_ACCEPT_REJECT",
        "joints": accept_reject,
    })
    _write(REPORTS / "confidence-error-correlation.json", {
        "schema": "NURION_CONFIDENCE_ERROR_CORRELATION",
        "pearson_r": _pearson(confs, errs),
        "n": len(confs),
        "pairs": [
            {"landmark": r["landmark"], "confidence": r["confidence"], "error_cm": r["errors"]["euclidean_cm"]}
            for r in geom_cmp["joints"]
        ],
        "note": "Negative r is desirable (higher confidence ↔ lower error).",
    })
    _write(REPORTS / "review-required-joints.json", {
        "schema": "NURION_REVIEW_REQUIRED_JOINTS",
        "count": len(review_required),
        "joints": review_required,
        "policy": "ESTIMATED and GEOMETRY_CORRECTED remain reviewRequired in alpha.",
    })
    _write(REPORTS / "limb-focus-metrics.json", {
        "elbow.L_cm": joint_cm("elbow.L"),
        "elbow.R_cm": joint_cm("elbow.R"),
        "knee.L_cm": joint_cm("knee.L"),
        "knee.R_cm": joint_cm("knee.R"),
        "ankle.L_cm": joint_cm("ankle.L"),
        "ankle.R_cm": joint_cm("ankle.R"),
    })

    # Mesh↔GT mismatch probe (evaluation-only; does not affect generation).
    mesh_gt = {"schema": "NURION_MESH_GT_MISMATCH", "joints": []}
    try:
        deps = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh.evaluated_get(deps)
        me = eval_obj.to_mesh()
        me.transform(eval_obj.matrix_world)
        cx = float(view.center.x)
        for side, gt_name in (("R", "ankle.R"), ("L", "ankle.L")):
            if gt_name not in gt:
                continue
            foot = []
            for vert in me.vertices:
                p = vert.co
                if p.z > 0.12:
                    continue
                if side == "R" and p.x < cx:
                    foot.append(p.copy())
                if side == "L" and p.x >= cx:
                    foot.append(p.copy())
            if not foot:
                mesh_gt["joints"].append({"landmark": gt_name, "footVerts": 0})
                continue
            mean = Vector(
                (
                    sum(p.x for p in foot) / len(foot),
                    sum(p.y for p in foot) / len(foot),
                    sum(p.z for p in foot) / len(foot) + 0.03,
                )
            )
            gt_pos = Vector(gt[gt_name]["position"])
            err = (mean - gt_pos).length * 100.0
            xs = [p.x for p in foot]
            mesh_gt["joints"].append(
                {
                    "landmark": gt_name,
                    "footVerts": len(foot),
                    "meshFootMean": [round(float(x), 4) for x in mean],
                    "gt": gt[gt_name]["position"],
                    "bestInsideError_cm": round(err, 3),
                    "meshXRange": [round(min(xs), 4), round(max(xs), 4)],
                    "gateAnkleLt10_reachable_inside_mesh": err < 10.0,
                }
            )
        eval_obj.to_mesh_clear()
        mesh_gt["blocker"] = any(
            (j.get("bestInsideError_cm") or 0) >= 10.0 for j in mesh_gt["joints"] if j.get("footVerts", 0) > 0
        )
        mesh_gt["note"] = (
            "If bestInsideError_cm >= 10 for an ankle, the FBX bone lies outside the wearable foot mesh "
            "cluster. Inside-mesh geometry cannot satisfy ankle_<10 and outside=0 simultaneously."
        )
    except Exception as exc:
        mesh_gt["error"] = str(exc)
    _write(REPORTS / "mesh-gt-mismatch.json", mesh_gt)

    verdict = {
        "schema": "NURION_V0.2_ALPHA3_VERDICT",
        "version": "0.2.0-alpha.3",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "package": "NURION_Character_Landmarker_v0.2.0-alpha.3.zip",
        "packageSha256": hashlib.sha256(ADDON_ZIP.read_bytes()).hexdigest(),
        "alpha1FrozenSha256": "915bb5be9894086bdd344463a2fab27c74b4ad2ef016439ed4ca0e1b8be0dc01",
        "alpha2FrozenSha256": "357677285373514bc5ed6e7fa9c765b26651b59b0515df63c53a1a4b6d44a2d8",
        "parameterHash": live_hash,
        "gates": gates,
        "alphaPass": alpha_pass,
        "metrics": {
            "meanError_cm": mean_g,
            "maxError_cm": max_g,
            "elbow.L_cm": joint_cm("elbow.L"),
            "elbow.R_cm": joint_cm("elbow.R"),
            "knee.L_cm": joint_cm("knee.L"),
            "knee.R_cm": joint_cm("knee.R"),
            "ankle.L_cm": joint_cm("ankle.L"),
            "ankle.R_cm": joint_cm("ankle.R"),
            "worsenedVsAlpha2": a2_worsened,
            "worsenOver1_5cmCount": len(worsen_over_15),
            "top5Worst": [
                {"landmark": r["landmark"], "error_cm": r["errors"]["euclidean_cm"]} for r in top5
            ],
        },
        "holdoutRequired": True,
        "meshGtMismatch": mesh_gt,
        "sealPolicy": (
            "Alpha3 PASS on Wither is a single-model regression success only. "
            "Do not SEAL v0.2 until a separate unused Meshy A-Pose humanoid holdout is validated."
        ),
    }
    _write(OUT / "ALPHA3_VERDICT.json", verdict)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if alpha_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
