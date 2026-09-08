"""
v0.3a Face Alpha1 evaluation harness.

- Never mutates v0.2 SEALED artifacts.
- Face GT is evaluation-only (leak_guard enforced).
- Writes reports under dist/v0.3/face/.

Usage:
  blender --background --python tools/blender_v03a_face_eval.py -- \\
    --fbx PATH [--gt PATH] [--label LABEL]
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
OUT = ROOT / "dist" / "v0.3" / "face"
REPORTS = OUT / "reports"
PROFILES = OUT / "profiles"
ANNOTATIONS = OUT / "annotations"
ADDON_ZIP = OUT / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
ADDON_MODULE = "nurion_character_landmarker"
V02_SHA = "679190e443d5814c6f7a7c41dcc7a62a52a0b02a6697e7485358d6a8853b02b2"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--gt", default="", help="Optional face-ground-truth.json")
    p.add_argument("--label", default="face-alpha1")
    return p.parse_args(argv)


def _enable_addon() -> None:
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    if not ADDON_ZIP.exists():
        raise FileNotFoundError(ADDON_ZIP)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    v02 = ROOT / "dist" / "v0.2" / "final" / "NURION_Character_Landmarker_v0.2.0.zip"
    if v02.exists() and _sha(v02) != V02_SHA:
        raise RuntimeError("v0.2 SEALED ZIP mutated — abort face eval")

    from nurion_character_landmarker.core.face.parameters import (
        FACE_ALPHA1_PARAMETER_HASH,
        FACE_ALPHA1_PARAMETERS,
        parameter_hash,
    )

    live = parameter_hash(FACE_ALPHA1_PARAMETERS)
    if live != FACE_ALPHA1_PARAMETER_HASH or len(live) != 64:
        raise RuntimeError("Face Alpha1 parameter hash invalid")

    _write(
        REPORTS / "parameter-hash.json",
        {
            "schema": "NURION_FACE_PARAMETER_HASH",
            "version": "0.3.0-alpha.1",
            "sha256": live,
            "sha256Length": 64,
            "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
            "parameters": FACE_ALPHA1_PARAMETERS,
            "v02SealedSha256": V02_SHA,
        },
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    _enable_addon()
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
    if not meshes:
        raise RuntimeError("No mesh in FBX")
    mesh = meshes[0]

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.determinism import serialize_landmarks_for_hash
    from nurion_character_landmarker.core.face.correct import correct_face_landmarks
    from nurion_character_landmarker.core.face.keys import ALPHA1_CORE_KEYS
    from nurion_character_landmarker.core.face.spaces import entries_from_landmarks
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.leak_guard import generation_scope, reset_gt_access_log
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view, point_inside_mesh
    from nurion_character_landmarker.evaluation.face_gt import collect_face_gt_landmarks, face_gt_vector_map
    from nurion_character_landmarker.profiles.nurion_landmark_profile import (
        NurionCharacterProfile,
        measurements_payload,
        save_profile,
    )

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    body = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)

    # Leak probe: GT must not be readable inside generation.
    gt_path = Path(args.gt) if args.gt else ANNOTATIONS / "face-ground-truth.json"
    leak_fail = False
    if gt_path.exists():
        try:
            with generation_scope("face_leak_probe"):
                collect_face_gt_landmarks(gt_path)
            leak_fail = True
        except Exception as exc:
            if type(exc).__name__ != "GroundTruthLeakError":
                raise

    reset_gt_access_log()
    result = correct_face_landmarks(
        mesh,
        view=view,
        body=body,
        forward_axis=measurements.forward_axis,
        core_only=True,
    )
    _write(REPORTS / "face-eligibility-report.json", result.region.to_dict())

    if not result.region.eligible:
        verdict = {
            "schema": "NURION_V0.3A_FACE_ALPHA1_VERDICT",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "label": args.label,
            "fbx": str(fbx),
            "fbxSha256": _sha(fbx),
            "parameterHash": live,
            "alphaPass": False,
            "failClass": "FACE_ASSET_INELIGIBLE",
            "reasonCode": result.region.reasonCode,
            "v02SealedSha256": V02_SHA,
        }
        _write(OUT / "ALPHA1_VERDICT.json", verdict)
        print(json.dumps(verdict, indent=2, ensure_ascii=False))
        return 3

    # Determinism 3x
    hashes = []
    for _ in range(3):
        run = correct_face_landmarks(
            mesh, view=view, body=body, forward_axis=measurements.forward_axis, core_only=True
        )
        hashes.append(
            hashlib.sha256(
                serialize_landmarks_for_hash(run.landmarks, ALPHA1_CORE_KEYS).encode()
            ).hexdigest()
        )
    determinism_pass = len(set(hashes)) == 1
    _write(
        REPORTS / "face-determinism-report.json",
        {"pass": determinism_pass, "hashes": hashes, "runs": 3, "hashPolicy": "FULL_64_CHAR_HEX_ONLY"},
    )

    frame = result.region.headFrame
    est_entries = entries_from_landmarks(result.landmarks, frame) if frame else []
    # Estimated profile = pre-final naming; geometry-corrected is the FACE_GEOMETRY_CORRECTED set.
    save_profile(
        NurionCharacterProfile(
            character_id=args.label,
            character_height=measurements.height.value,
            width=measurements.width.value,
            center=list(measurements.center),
            forward_axis=measurements.forward_axis,
            floor_z=measurements.floor_position.value,
            measurements=measurements_payload(measurements),
            landmarks=est_entries,
        ),
        PROFILES / "face.geometry-corrected.json",
    )
    _write(PROFILES / "face.estimated.json", {"schema": "NURION_FACE_ESTIMATED", "landmarks": est_entries})

    conf_rows = [
        {
            "name": n,
            "confidence": result.landmarks[n].confidence,
            "reviewRequired": result.landmarks[n].review_required,
            "source": result.landmarks[n].source,
            "evidence": result.landmarks[n].evidence,
        }
        for n in ALPHA1_CORE_KEYS
        if n in result.landmarks
    ]
    _write(
        REPORTS / "face-confidence-report.json",
        {"schema": "NURION_FACE_CONFIDENCE", "joints": conf_rows},
    )

    outside = [
        n
        for n in ALPHA1_CORE_KEYS
        if n in result.landmarks and not point_inside_mesh(view, result.landmarks[n].position)
    ]
    detection_rate = len([k for k in ALPHA1_CORE_KEYS if k in result.landmarks]) / len(ALPHA1_CORE_KEYS)

    gt_available = gt_path.exists() and bool(json.loads(gt_path.read_text(encoding="utf-8")).get("annotatedCount", 0))
    rows = []
    mean_g = max_g = None
    head_h = float(frame.head_height) if frame else max(measurements.height.value * 0.22, 1e-4)
    if gt_available:
        reset_gt_access_log()
        gt = face_gt_vector_map(gt_path, ALPHA1_CORE_KEYS)
        for name in ALPHA1_CORE_KEYS:
            if name not in result.landmarks or name not in gt:
                continue
            d = gt[name] - result.landmarks[name].position
            eu_cm = float(d.length) * 100.0
            rows.append(
                {
                    "landmark": name,
                    "euclidean_cm": round(eu_cm, 3),
                    "euclidean_headHeight": round(float(d.length) / head_h, 6),
                    "delta": [round(float(d.x), 6), round(float(d.y), 6), round(float(d.z), 6)],
                }
            )
        if rows:
            eu = [r["euclidean_cm"] for r in rows]
            mean_g = round(sum(eu) / len(eu), 3)
            max_g = round(max(eu), 3)

    _write(
        REPORTS / "face-landmark-error-report.json",
        {
            "schema": "NURION_FACE_LANDMARK_ERROR",
            "gtAvailable": gt_available,
            "gtPath": str(gt_path) if gt_available else None,
            "summary": {"meanError_cm": mean_g, "maxError_cm": max_g, "mappedJoints": len(rows)},
            "headHeight_m": round(head_h, 6),
            "joints": rows,
            "detectionSuccessRate": round(detection_rate, 4),
            "missing": result.missing,
        },
    )
    _write(
        REPORTS / "face-gt-leak-report.json",
        {"pass": not leak_fail, "leakFail": leak_fail, "gtPathExists": gt_path.exists()},
    )

    gates = FACE_ALPHA1_PARAMETERS["gatesAlpha1"]
    per = {r["landmark"]: r["euclidean_cm"] for r in rows}
    quality_checked = gt_available and mean_g is not None
    gate_results = {
        "detection_100": detection_rate >= float(gates["detectionSuccessRate"]),
        "mean_lt_2": bool(quality_checked and mean_g < float(gates["meanErrorCm"])),
        "max_lt_4": bool(quality_checked and max_g < float(gates["maxErrorCm"])),
        "eye_center_L_lt_1_5": bool(per.get("eye.center.L", 999) < float(gates["eyeCenterCm"])) if quality_checked else False,
        "eye_center_R_lt_1_5": bool(per.get("eye.center.R", 999) < float(gates["eyeCenterCm"])) if quality_checked else False,
        "nose_tip_lt_2": bool(per.get("nose.tip", 999) < float(gates["noseTipCm"])) if quality_checked else False,
        "mouth_center_lt_2": bool(per.get("mouth.center", 999) < float(gates["mouthCenterCm"])) if quality_checked else False,
        "chin_lt_2_5": bool(per.get("chin", 999) < float(gates["chinCm"])) if quality_checked else False,
        "lr_swap_zero": len(result.lr_swaps) == 0,
        "outside_zero": len(outside) == 0,
        "gt_leak_zero": not leak_fail,
        "determinism_pass": determinism_pass,
        "parameter_hash_fixed": True,
    }
    alpha_pass = all(gate_results.values()) if quality_checked else False

    verdict = {
        "schema": "NURION_V0.3A_FACE_ALPHA1_VERDICT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx),
        "fbxSha256": _sha(fbx),
        "parameterHash": live,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "alphaPass": alpha_pass,
        "qualityChecked": quality_checked,
        "failClass": None
        if alpha_pass
        else ("WAITING_FOR_FACE_GT" if not quality_checked else "FACE_ALPHA1_GATE_FAIL"),
        "gates": gate_results,
        "metrics": {
            "meanError_cm": mean_g,
            "maxError_cm": max_g,
            "detectionSuccessRate": round(detection_rate, 4),
            "detectedCore": len(result.landmarks),
            "outside": outside,
            "lrSwaps": result.lr_swaps,
        },
        "v02SealedSha256": V02_SHA,
        "note": (
            "Direction-validation Alpha1 gates. Final v0.3a targets are stricter. "
            "Without annotated face GT, quality gates remain unchecked."
        ),
    }
    _write(OUT / "ALPHA1_VERDICT.json", verdict)
    print(json.dumps(verdict, indent=2, ensure_ascii=False))
    return 0 if alpha_pass else (4 if not quality_checked else 2)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
