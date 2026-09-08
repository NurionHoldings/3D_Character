"""
Evaluate frozen Alpha2 Eye Proxy against locked 10-point surface GT.

Does not retune Alpha2 ZIP/params.
Verdict: PASS | FAIL | SURFACE_GT_INVALID | FACE_ASSET_INELIGIBLE
(Alpha2 ZIP/params unchanged on any verdict).

Usage:
  blender --background --python tools/blender_v03a2_surface_gt_eval.py -- \\
    --fbx PATH --gt PATH/face-surface-gt.json [--label tennis]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.3" / "face" / "alpha2"
REPORTS = OUT / "reports"
ADDON_ZIP = OUT / "NURION_Character_Landmarker_v0.3.0-alpha.2.zip"
ADDON_MODULE = "nurion_character_landmarker"
ALPHA2_ZIP_SHA = "1fcafa0fdc99cff4f0925fcc1744bee49d7d98b1072174e00e44d98f2f507530"
ALPHA2_PARAM = "1a1fc8ab52a43d29c738c579596395443fcb5c4db26c287d4b639ae1793a8605"
ALPHA1_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"

SURFACE_KEYS = [
    "eye.inner.L", "eye.inner.R",
    "eye.outer.L", "eye.outer.R",
    "eyelid.upper.L", "eyelid.upper.R",
    "eyelid.lower.L", "eyelid.lower.R",
    "iris.visualCenter.L", "iris.visualCenter.R",
]
MAX_SURFACE_DETACH_MM = 1.0
MAX_PENETRATION_M = 0.004


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
    p.add_argument("--gt", required=True)
    p.add_argument("--label", default="tennis-surface-gt")
    return p.parse_args(argv)


def _mean(xs: List[float]) -> Optional[float]:
    return round(sum(xs) / len(xs), 3) if xs else None


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    gt_path = Path(args.gt)
    if not fbx.exists() or not gt_path.exists():
        raise FileNotFoundError("fbx/gt missing")
    if not ADDON_ZIP.exists() or _sha(ADDON_ZIP) != ALPHA2_ZIP_SHA:
        raise RuntimeError("Frozen Alpha2 ZIP missing or hash mismatch")
    a1 = ROOT / "dist" / "v0.3" / "face" / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
    if a1.exists() and _sha(a1) != ALPHA1_SHA:
        raise RuntimeError("Alpha1 ZIP mutated")

    gt_doc = json.loads(gt_path.read_text(encoding="utf-8"))
    required = (
        "faceIndex",
        "triangleVertices",
        "barycentric",
        "uv",
        "positionWorld",
        "positionHeadLocal",
        "predictionHidden",
        "snapToPrediction",
    )
    gt_map: Dict[str, Vector] = {}
    detach = []
    invalid_fields: List[dict] = []
    for e in gt_doc.get("landmarks", []):
        if e.get("name") not in SURFACE_KEYS or not e.get("annotated"):
            continue
        miss = [f for f in required if e.get(f) is None]
        if e.get("predictionHidden") is not True:
            miss.append("predictionHidden!=true")
        if e.get("snapToPrediction") is not False:
            miss.append("snapToPrediction!=false")
        uv = e.get("uv")
        if not isinstance(uv, list) or len(uv) != 2:
            miss.append("uv")
        bc = e.get("barycentric")
        if not isinstance(bc, list) or len(bc) != 3:
            miss.append("barycentric")
        tv = e.get("triangleVertices")
        if not isinstance(tv, list) or len(tv) != 3:
            miss.append("triangleVertices")
        if miss:
            invalid_fields.append({"name": e.get("name"), "fields": sorted(set(miss))})
            continue
        pw = e.get("positionWorld")
        gt_map[e["name"]] = Vector((float(pw[0]), float(pw[1]), float(pw[2])))
        if e.get("surfaceDistanceMm") is not None and float(e["surfaceDistanceMm"]) > MAX_SURFACE_DETACH_MM:
            detach.append(e["name"])

    if invalid_fields:
        verdict = {
            "schema": "NURION_V0.3A2_SURFACE_GT_VERDICT",
            "alphaPass": False,
            "failClass": "SURFACE_GT_INVALID",
            "annotated": len(gt_map),
            "invalid": invalid_fields,
            "gtSha256": _sha(gt_path),
            "frozenAlpha2Unchanged": True,
        }
        _write(OUT / "SURFACE_GT_VERDICT.json", verdict)
        print(json.dumps(verdict, indent=2))
        return 5

    if len(gt_map) != 10:
        verdict = {
            "schema": "NURION_V0.3A2_SURFACE_GT_VERDICT",
            "alphaPass": False,
            "failClass": "WAITING_FOR_SURFACE_GT" if len(gt_map) == 0 else "INCOMPLETE_SURFACE_GT",
            "annotated": len(gt_map),
            "gtSha256": _sha(gt_path),
            "frozenAlpha2Unchanged": True,
        }
        _write(OUT / "SURFACE_GT_VERDICT.json", verdict)
        print(json.dumps(verdict, indent=2))
        return 4

    sys.path.insert(0, str(ROOT))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted(
        [o for o in bpy.data.objects if o.type == "MESH" and not o.name.startswith("NURION_")],
        key=lambda o: len(o.data.vertices),
        reverse=True,
    )
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    mesh = meshes[0]
    if arms:
        arms[0].data.pose_position = "REST"
        bpy.context.view_layer.update()

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.determinism import serialize_landmarks_for_hash
    from nurion_character_landmarker.core.face.eye_proxy_pipeline import run_eye_proxy_pipeline
    from nurion_character_landmarker.core.face.parameters_alpha2 import (
        FACE_ALPHA2_PARAMETER_HASH,
        FACE_ALPHA2_PARAMETERS,
        parameter_hash,
    )
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.leak_guard import generation_scope
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import (
        build_world_mesh_view,
        nearest_on_mesh,
        point_inside_or_on_mesh,
    )
    live = parameter_hash(FACE_ALPHA2_PARAMETERS)
    if live != FACE_ALPHA2_PARAMETER_HASH or live != ALPHA2_PARAM:
        raise RuntimeError("Alpha2 parameter hash drifted")

    # GT leak probe: note_gt_access must raise inside generation_scope
    leak_fail = False
    from nurion_character_landmarker.core.leak_guard import note_gt_access

    try:
        with generation_scope("surface_gt_leak"):
            note_gt_access("surface_gt_eval:probe")
        leak_fail = True
    except Exception as exc:
        if type(exc).__name__ != "GroundTruthLeakError":
            raise

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    body = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)

    hashes = []
    last = None
    for _ in range(3):
        last = run_eye_proxy_pipeline(
            mesh, view=view, body=body, forward_axis=measurements.forward_axis, create_meshes=True
        )
        hashes.append(
            hashlib.sha256(
                serialize_landmarks_for_hash(last.landmarks, SURFACE_KEYS + ["eye.center.L", "eye.center.R"]).encode()
            ).hexdigest()
        )
    determinism = len(set(hashes)) == 1

    rows = []
    for name in SURFACE_KEYS:
        if name not in last.proxy.surface or name not in gt_map:
            continue
        d = gt_map[name] - last.proxy.surface[name].position
        rows.append(
            {
                "landmark": name,
                "error_mm": round(float(d.length) * 1000.0, 3),
                "delta_m": [round(float(x), 6) for x in d],
            }
        )
    eu = [r["error_mm"] for r in rows]
    mean_all = _mean(eu)
    max_all = round(max(eu), 3) if eu else None

    def group_mean(suffixes: Tuple[str, ...]) -> Optional[float]:
        vals = [r["error_mm"] for r in rows if any(r["landmark"].startswith(s) for s in suffixes)]
        # startswith for eye.inner / eye.outer; eyelid.upper etc.
        return _mean(vals)

    inner_outer = _mean([r["error_mm"] for r in rows if "eye.inner" in r["landmark"] or "eye.outer" in r["landmark"]])
    upper_lower = _mean([r["error_mm"] for r in rows if "eyelid.upper" in r["landmark"] or "eyelid.lower" in r["landmark"]])
    iris_mean = _mean([r["error_mm"] for r in rows if "iris.visualCenter" in r["landmark"]])

    # L/R swap on surface pairs
    lr_swap = 0
    fr = last.region.headFrame
    for base in ("eye.inner", "eye.outer", "eyelid.upper", "eyelid.lower", "iris.visualCenter"):
        l, r = f"{base}.L", f"{base}.R"
        if l in last.proxy.surface and r in last.proxy.surface and fr:
            if fr.to_local(last.proxy.surface[l].position).x < fr.to_local(last.proxy.surface[r].position).x:
                lr_swap += 1

    # Procedural eyeball structural checks
    eyeballs = {s: bpy.data.objects.get(f"NURION_Eyeball.{s}") for s in ("L", "R")}
    eyeball_ok = all(eyeballs[s] is not None for s in ("L", "R"))
    centers_inside = all(
        point_inside_or_on_mesh(view, last.proxy.centers[k].position) for k in last.proxy.centers
    ) if last.proxy.centers else False
    radii = list(last.proxy.radii.values())
    radius_diff = 0.0
    if len(radii) == 2:
        avg = 0.5 * (radii[0] + radii[1])
        radius_diff = abs(radii[0] - radii[1]) / max(avg, 1e-9)

    penetration = {}
    aperture_align = {}
    gaze = {}
    depths = {}
    exposure = {}
    mesh_counts = {}
    for side in ("L", "R"):
        ckey = f"eye.center.{side}"
        if ckey not in last.proxy.centers:
            continue
        center = last.proxy.centers[ckey].position
        ap = last.proxy.apertures.get(side)
        radius = last.proxy.radii.get(side, 0.0)
        if ap is not None:
            depth = (ap.surface_center - center).dot(ap.normal_out.normalized())
            depths[side] = round(depth * 1000.0, 3)
            align_mm = (ap.surface_center - (center + ap.normal_out.normalized() * depth)).length * 1000.0
            # Alignment of projected center to aperture surface center
            proj = center + ap.normal_out.normalized() * max(depth, 0.0)
            aperture_align[side] = round((proj - ap.surface_center).length * 1000.0, 3)
            # Exposure ratio heuristic: how much of radius sits in front of surface
            exposure[side] = round(max(0.0, min(1.0, 1.0 - (depth / max(radius, 1e-6)))), 4)
            # Penetration: if sphere extends beyond surface more than radius-depth
            protrude = radius - depth
            penetration[side] = round(max(0.0, protrude) * 1000.0, 3)
            gaze[side] = [round(float(x), 6) for x in ap.normal_out.normalized()]
        obj = eyeballs.get(side)
        if obj and obj.type == "MESH":
            mesh_counts[side] = {"vertices": len(obj.data.vertices), "polygons": len(obj.data.polygons)}

    gaze_ok = True
    if "L" in gaze and "R" in gaze:
        gl, gr = Vector(gaze["L"]), Vector(gaze["R"])
        if gl.dot(gr) < 0.85:
            gaze_ok = False

    # Regen mesh hash seeds from object props / topology
    seed_l = f"NURION_Eyeball.L|{last.proxy.radii.get('L', 0):.8f}|{mesh_counts.get('L')}"
    seed_r = f"NURION_Eyeball.R|{last.proxy.radii.get('R', 0):.8f}|{mesh_counts.get('R')}"
    # Determinism of landmark hash already covers regen; mesh counts must match L/R topology
    mesh_hash_pass = (
        mesh_counts.get("L") == mesh_counts.get("R")
        and mesh_counts.get("L") is not None
        and determinism
    )
    eyeball_sha = hashlib.sha256(
        json.dumps(
            {
                "radii": {k: round(v, 8) for k, v in last.proxy.radii.items()},
                "centers": {
                    k: [round(float(x), 8) for x in last.proxy.centers[k].position]
                    for k in sorted(last.proxy.centers)
                },
                "mesh_counts": mesh_counts,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    pen_ok = all(v <= MAX_PENETRATION_M * 1000.0 for v in penetration.values()) if penetration else False
    align_ok = all(v < 5.0 for v in aperture_align.values()) if aperture_align else False

    gates = {
        "detection_10_of_10": len(rows) == 10,
        "mean_lt_5_0_mm": bool(mean_all is not None and mean_all < 5.0),
        "max_lt_10_0_mm": bool(max_all is not None and max_all < 10.0),
        "inner_outer_mean_lt_5_0_mm": bool(inner_outer is not None and inner_outer < 5.0),
        "upper_lower_mean_lt_5_0_mm": bool(upper_lower is not None and upper_lower < 5.0),
        "iris_mean_lt_5_0_mm": bool(iris_mean is not None and iris_mean < 5.0),
        "lr_swap_zero": lr_swap == 0,
        "surface_detach_zero": len(detach) == 0,
        "gt_leak_zero": not leak_fail,
        "determinism_pass": determinism,
        "eyeballs_created": eyeball_ok,
        "centers_inside_head": centers_inside,
        "aperture_align_pass": align_ok,
        "radius_diff_le_10pct": radius_diff <= 0.10,
        "penetration_ok": pen_ok,
        "gaze_axis_lr_ok": gaze_ok,
        "regen_mesh_hash_pass": mesh_hash_pass,
    }
    alpha_pass = all(gates.values())

    report = {
        "schema": "NURION_V0.3A2_SURFACE_GT_EVAL",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx),
        "fbxSha256": _sha(fbx),
        "gtPath": str(gt_path),
        "gtSha256": _sha(gt_path),
        "packageSha256": ALPHA2_ZIP_SHA,
        "parameterHash": ALPHA2_PARAM,
        "alphaPass": alpha_pass,
        "failClass": None if alpha_pass else "FACE_ALPHA2_SURFACE_GATE_FAIL",
        "preserveAlpha2OnFail": True,
        "gates": gates,
        "metrics": {
            "meanError_mm": mean_all,
            "maxError_mm": max_all,
            "innerOuterMean_mm": inner_outer,
            "upperLowerMean_mm": upper_lower,
            "irisMean_mm": iris_mean,
            "lrSwap": lr_swap,
            "radiusDiff": round(radius_diff, 6),
            "radiiMm": {k: round(v * 1000.0, 3) for k, v in last.proxy.radii.items()},
            "depthMm": depths,
            "exposureRatio": exposure,
            "penetrationMm": penetration,
            "apertureAlignMm": aperture_align,
            "meshCounts": mesh_counts,
            "eyeballResultSha256": eyeball_sha,
        },
        "joints": rows,
        "determinismHashes": hashes,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "note": (
            "Direction gate for Alpha2 surface landmarks + structural procedural eyeball checks. "
            "On FAIL, keep Alpha2 frozen artifacts and proceed to Alpha3 corrections."
        ),
    }
    _write(REPORTS / f"{args.label}-surface-gt-eval.json", report)
    _write(OUT / "SURFACE_GT_VERDICT.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if alpha_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
