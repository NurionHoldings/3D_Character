"""
v0.2 holdout evaluation on a NEW eligible Meshy A-Pose humanoid.

Rules:
- Alpha3 ZIP + parameter hash are FROZEN (no retune after seeing holdout results).
- Asset Eligibility Gate must PASS before quality metrics run.
- Wither quality FAIL remains separate (ASSET_GT_MISMATCH fixture).
- v0.2 SEAL is not automatic; holdout PASS only records Holdout PASS for review.

Usage:
  blender --background --python tools/blender_v02_holdout_eval.py -- --fbx PATH_TO_HOLDOUT.fbx
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
ADDON_ZIP = ROOT / "dist" / "v0.2" / "NURION_Character_Landmarker_v0.2.0-alpha.3.zip"
ADDON_MODULE = "nurion_character_landmarker"
ALPHA3_LOCK = ROOT / "dist" / "v0.2" / "alpha3" / "ALPHA3_LOCK.json"
OUT = ROOT / "dist" / "v0.2" / "holdout"
REPORTS = OUT / "reports"
PROFILES = OUT / "profiles"

# Full 64-char lowercase hex only — never truncate in locks or reports.
ALPHA3_SHA = "0310b47919ef4db4fb5363ea7287575dd66117ff4e221574c31bb1fa682da4bf"
ALPHA3_PARAM_HASH = "6b964ebb684026c5367faae6554135a634dd29f30761560925ae57f038747348"

JOINTS_17 = [
    "pelvis", "spine", "chest", "neck", "head",
    "shoulder.L", "elbow.L", "wrist.L",
    "shoulder.R", "elbow.R", "wrist.R",
    "hip.L", "knee.L", "ankle.L",
    "hip.R", "knee.R", "ankle.R",
]


def _require_full_sha256(value: str, label: str) -> str:
    h = (value or "").strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise RuntimeError(f"{label} must be a full 64-char SHA-256 hex digest, got {value!r}")
    if "…" in (value or "") or "..." in (value or ""):
        raise RuntimeError(f"{label} must not be truncated")
    return h


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return _require_full_sha256(h.hexdigest(), f"sha256({path.name})")


def _err(a: Vector, b: Vector) -> dict:
    d = b - a
    return {
        "front_x": round(float(d.x), 6),
        "side_y": round(float(d.y), 6),
        "top_z": round(float(d.z), 6),
        "euclidean_cm": round(float(d.length) * 100.0, 3),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser(description="Alpha3 frozen-parameter holdout eval")
    p.add_argument("--fbx", required=True, help="Path to holdout Meshy A-Pose FBX")
    p.add_argument("--label", default="holdout-meshy-apose", help="Holdout label for reports")
    return p.parse_args(argv)


def _enable_addon() -> None:
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def main() -> int:
    args = _parse_args(sys.argv)
    fbx_path = Path(args.fbx)
    if not fbx_path.exists():
        raise FileNotFoundError(fbx_path)

    sys.path.insert(0, str(ROOT))

    if not ALPHA3_LOCK.exists():
        raise RuntimeError("ALPHA3_LOCK.json missing")
    lock = json.loads(ALPHA3_LOCK.read_text(encoding="utf-8"))
    if not lock.get("frozen"):
        raise RuntimeError("Alpha3 must be frozen before holdout eval")

    locked_zip = _require_full_sha256(lock.get("sha256", ""), "ALPHA3_LOCK.sha256")
    locked_param = _require_full_sha256(lock.get("parameterHash", ""), "ALPHA3_LOCK.parameterHash")
    expected_zip = _require_full_sha256(ALPHA3_SHA, "ALPHA3_SHA constant")
    expected_param = _require_full_sha256(ALPHA3_PARAM_HASH, "ALPHA3_PARAM_HASH constant")
    if locked_zip != expected_zip or locked_param != expected_param:
        raise RuntimeError("ALPHA3_LOCK hashes do not match holdout constants")

    zip_sha = _sha256(ADDON_ZIP)
    if zip_sha != expected_zip:
        raise RuntimeError("Alpha3 ZIP hash changed — refuse holdout (parameters must stay frozen)")

    from nurion_character_landmarker.core.alpha3_parameters import ALPHA3_PARAMETER_HASH, ALPHA3_PARAMETERS, parameter_hash

    live_hash = _require_full_sha256(parameter_hash(ALPHA3_PARAMETERS), "live parameterHash")
    module_hash = _require_full_sha256(ALPHA3_PARAMETER_HASH, "ALPHA3_PARAMETER_HASH")
    if live_hash != expected_param or live_hash != module_hash:
        raise RuntimeError("Alpha3 parameter hash changed — refuse holdout retune")

    fbx_sha = _sha256(fbx_path)

    _write(
        REPORTS / "parameter-hash.json",
        {
            "schema": "NURION_HOLDOUT_PARAMETER_HASH",
            "sha256": live_hash,
            "sha256Length": 64,
            "frozenAlpha3PackageSha256": expected_zip,
            "frozenAlpha3ParameterHash": expected_param,
            "holdoutFbxSha256": fbx_sha,
            "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
            "note": "Frozen before holdout evaluation. No retune after seeing holdout results. Never truncate hashes.",
            "parameters": ALPHA3_PARAMETERS,
        },
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    _enable_addon()
    bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
    arms = sorted([o for o in bpy.data.objects if o.type == "ARMATURE"], key=lambda o: len(o.data.bones), reverse=True)
    if not meshes or not arms:
        reason = "MISSING_MESH" if not meshes else "MISSING_GT_ARMATURE"
        if not meshes and not arms:
            reason = "MISSING_MESH_AND_ARMATURE"
        prechecks = {
            "meshPresent": bool(meshes),
            "gtArmaturePresent": bool(arms),
            "meshCount": len(meshes),
            "armatureCount": len(arms),
            "meshVertexCounts": [len(o.data.vertices) for o in meshes[:5]],
            "armatureBoneCounts": [len(o.data.bones) for o in arms[:5]],
        }
        _write(REPORTS / "holdout-prechecks.json", {
            "schema": "NURION_HOLDOUT_PRECHECKS",
            "checks": prechecks,
            "blockedJoints": list(JOINTS_17),
            "reasonCode": reason,
        })
        _write(REPORTS / "asset-eligibility.json", {
            "schema": "NURION_ASSET_ELIGIBILITY",
            "assetEligible": False,
            "reasonCode": reason,
            "blockedJoints": list(JOINTS_17),
            "evaluationExcluded": list(JOINTS_17),
            "evaluationAllowed": False,
            "autoRigAllowed": False,
            "checks": {
                "meshPresent": bool(meshes),
                "gtArmaturePresent": bool(arms),
                "lateralComponentsPresent": False,
                "worldTransformUsable": False,
                "restPoseConsistent": False,
                "gtInsideMeshReachable": False,
            },
            "details": prechecks,
        })
        verdict = {
            "schema": "NURION_V0.2_HOLDOUT_VERDICT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": args.label,
            "fbx": str(fbx_path),
            "fbxSha256": fbx_sha,
            "alpha3PackageSha256": expected_zip,
            "parameterHash": live_hash,
            "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
            "holdoutPass": False,
            "failClass": "ASSET_INELIGIBLE",
            "reasonCode": reason,
            "prechecks": prechecks,
            "sealPolicy": (
                "Holdout FBX has no GT armature — quality eval cannot run. "
                "Provide a Meshy A-Pose FBX that includes mesh + biped/GT bones "
                "(e.g. withSkin / biped export). Do not SEAL v0.2."
            ),
            "witherRemains": "ASSET_GT_MISMATCH fixture (separate)",
            "v02Sealed": False,
            "note": "Not an algorithm FAIL. Alpha3 stays frozen FAIL on Wither; holdout waits for eligible asset.",
        }
        _write(OUT / "HOLDOUT_VERDICT.json", verdict)
        _write(
            OUT / "HOLDOUT_STATUS.json",
            {
                "schema": "NURION_HOLDOUT_STATUS",
                "status": "ASSET_INELIGIBLE_WAITING_FOR_BIPED",
                "v02Sealed": False,
                "witherFixture": "PASS",
                "assetEligibilityGate": "ACTIVE",
                "witherAutoRig": "DENY",
                "holdoutPass": False,
                "failClass": "ASSET_INELIGIBLE",
                "reasonCode": reason,
                "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
                "frozenAlpha3": {
                    "package": "NURION_Character_Landmarker_v0.2.0-alpha.3.zip",
                    "packageSha256": expected_zip,
                    "parameterHash": expected_param,
                    "packageSha256Length": 64,
                    "parameterHashLength": 64,
                },
                "lockedAsset": {
                    "label": args.label,
                    "fbxSha256": fbx_sha,
                    "fbxSha256Length": 64,
                },
                "pipeline": [
                    "FBX file SHA-256 (full 64-char) freeze",
                    "Asset Eligibility Gate",
                    "Alpha3 evaluation only if eligible",
                    "3× determinism",
                    "mean/max/per-joint errors",
                    "Holdout PASS or Algorithm FAIL",
                    "v0.2 SEAL review (not automatic)",
                ],
                "note": (
                    "Current holdout FBX is mesh-only (no GT armature). "
                    "Attach a biped/withSkin Meshy A-Pose FBX to continue."
                ),
            },
        )
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        return 3
    mesh, arm = meshes[0], arms[0]

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
    from nurion_character_landmarker.evaluation.asset_eligibility import evaluate_asset_eligibility
    from nurion_character_landmarker.evaluation.gt_bones import collect_gt_landmarks
    from nurion_character_landmarker.profiles.nurion_landmark_profile import (
        NurionCharacterProfile,
        measurements_payload,
        save_profile,
    )

    # Holdout must be evaluated in REST (no Rest/Pose mix).
    arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    view = build_world_mesh_view(mesh)
    eligibility = evaluate_asset_eligibility(mesh, arm, view=view)
    _write(REPORTS / "asset-eligibility.json", eligibility.to_dict())

    prechecks = {
        "lateralComponentsPresent": eligibility.checks.get("lateralComponentsPresent", False),
        "worldTransformUsable": eligibility.checks.get("worldTransformUsable", False),
        "restPoseConsistent": eligibility.checks.get("restPoseConsistent", False),
        "gtInsideMeshReachable": eligibility.checks.get("gtInsideMeshReachable", False),
        "assetEligible": eligibility.assetEligible,
    }
    _write(REPORTS / "holdout-prechecks.json", {
        "schema": "NURION_HOLDOUT_PRECHECKS",
        "checks": prechecks,
        "blockedJoints": eligibility.blockedJoints,
        "reasonCode": eligibility.reasonCode,
    })

    if not eligibility.evaluationAllowed:
        verdict = {
            "schema": "NURION_V0.2_HOLDOUT_VERDICT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": args.label,
            "fbx": str(fbx_path),
            "fbxSha256": fbx_sha,
            "alpha3PackageSha256": expected_zip,
            "parameterHash": live_hash,
            "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
            "holdoutPass": False,
            "failClass": "ASSET_INELIGIBLE",
            "reasonCode": eligibility.reasonCode,
            "eligibility": eligibility.to_dict(),
            "sealPolicy": "Holdout ineligible — do not SEAL v0.2. Fix asset or choose another holdout.",
            "witherRemains": "ASSET_GT_MISMATCH fixture (separate)",
            "v02Sealed": False,
        }
        _write(OUT / "HOLDOUT_VERDICT.json", verdict)
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        return 3

    # --- Quality evaluation with frozen Alpha3 generation (no GT in generation) ---
    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    estimated = estimate_body_landmarks(analysis, measurements)

    leak_fail = False
    try:
        with generation_scope("holdout_leak"):
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
            character_id=args.label,
            character_height=measurements.height.value,
            width=measurements.width.value,
            center=list(measurements.center),
            forward_axis=measurements.forward_axis,
            floor_z=measurements.floor_position.value,
            measurements=measurements_payload(measurements),
            landmarks=solve_coordinates(geom.landmarks),
        ),
        PROFILES / f"{args.label}.geometry-corrected.json",
    )

    gt = collect_gt_landmarks(arm, JOINTS_17)
    rows = []
    for name in JOINTS_17:
        if name not in geom.landmarks or name not in gt:
            continue
        e = _err(geom.landmarks[name].position, Vector(gt[name]["position"]))
        rows.append({"landmark": name, "errors": e, "source": geom.landmarks[name].source})
    eu = [r["errors"]["euclidean_cm"] for r in rows]
    mean_g = round(sum(eu) / len(eu), 3) if eu else None
    max_g = round(max(eu), 3) if eu else None
    outside = [n for n in JOINTS_17 if n in geom.landmarks and not point_inside_mesh(view, geom.landmarks[n].position)]
    swaps = geom.constraints.left_right_swaps

    gates = {
        "mean_lt_7": bool(mean_g is not None and mean_g < 7.0),
        "max_lt_15": bool(max_g is not None and max_g < 15.0),
        "lr_swap_zero": len(swaps) == 0,
        "outside_zero": len(outside) == 0,
        "gt_leak_zero": not leak_fail,
        "determinism_pass": determinism_pass,
        "parameter_hash_fixed": live_hash == expected_param,
        "asset_eligible": True,
    }
    holdout_pass = all(gates.values())

    _write(REPORTS / "17-joint-error-comparison.json", {
        "schema": "NURION_17_JOINT_ERROR_COMPARISON",
        "version": "0.2.0-alpha.3-holdout",
        "label": args.label,
        "summary": {"meanError_cm": mean_g, "maxError_cm": max_g, "mappedJoints": len(rows)},
        "joints": rows,
    })
    _write(REPORTS / "determinism-report.json", {
        "pass": determinism_pass,
        "hashes": hashes,
        "runs": 3,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
    })
    _write(REPORTS / "outside-mesh-validation.json", {"pass": len(outside) == 0, "outsideJoints": outside})
    _write(REPORTS / "left-right-validation.json", {"pass": len(swaps) == 0, "swaps": swaps})

    verdict = {
        "schema": "NURION_V0.2_HOLDOUT_VERDICT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx_path),
        "fbxSha256": fbx_sha,
        "alpha3PackageSha256": expected_zip,
        "parameterHash": live_hash,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "gates": gates,
        "holdoutPass": holdout_pass,
        "metrics": {"meanError_cm": mean_g, "maxError_cm": max_g},
        "eligibility": eligibility.to_dict(),
        "failClass": None if holdout_pass else "ALGORITHM_FAIL",
        "sealPolicy": (
            "Holdout PASS recorded separately from Wither ASSET_GT_MISMATCH. "
            "v0.2 SEAL still requires explicit review — not automatic."
            if holdout_pass
            else "Holdout FAIL with eligible asset → treat as algorithm FAIL; proceed to Alpha4. Do not SEAL v0.2."
        ),
        "witherRemains": "ASSET_GT_MISMATCH fixture (separate)",
        "v02Sealed": False,
    }
    _write(OUT / "HOLDOUT_VERDICT.json", verdict)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if holdout_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
