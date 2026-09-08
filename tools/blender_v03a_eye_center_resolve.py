"""
Resolve eye.center.L/R GT from visible eyeball surface fit on an integrated face mesh.

Does NOT modify frozen Alpha1 ZIP/params. Evaluation-prep only.

Usage:
  blender --background --python tools/blender_v03a_eye_center_resolve.py -- --fbx PATH
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
OUT = ROOT / "dist" / "v0.3" / "face"
REPORTS = OUT / "reports"
ADDON_ZIP = OUT / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
ADDON_MODULE = "nurion_character_landmarker"
ALPHA1_ZIP_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"
ALPHA1_PARAM = "2bd812ee4be5c63ce1053cfa5023305e2c9a41fe021b4ca01153f7ab3f799095"

MIN_SAMPLES = 32
MAX_RESIDUAL_MM = 2.0
MAX_RADIUS_DIFF_RATIO = 0.15


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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
    p.add_argument("--label", default="tennis-eye-center-resolve")
    return p.parse_args(argv)


def _fit_sphere(points: List[Vector]) -> Tuple[Optional[Vector], float, float]:
    if len(points) < MIN_SAMPLES:
        return None, 0.0, float("inf")
    # Algebraic least-squares sphere fit: ||x||^2 + d·x + e = 0 → center=-d/2
    n = len(points)
    sx = sy = sz = sxx = syy = szz = sxy = sxz = syz = sxr = syr = szr = 0.0
    for p in points:
        x, y, z = float(p.x), float(p.y), float(p.z)
        r2 = x * x + y * y + z * z
        sx += x
        sy += y
        sz += z
        sxx += x * x
        syy += y * y
        szz += z * z
        sxy += x * y
        sxz += x * z
        syz += y * z
        sxr += x * r2
        syr += y * r2
        szr += z * r2
    # Solve 3x3 for d
    A = [
        [sxx, sxy, sxz],
        [sxy, syy, syz],
        [sxz, syz, szz],
    ]
    b = [-sxr, -syr, -szr]
    # Gauss elimination
    M = [A[i][:] + [b[i]] for i in range(3)]
    for i in range(3):
        piv = max(range(i, 3), key=lambda r: abs(M[r][i]))
        M[i], M[piv] = M[piv], M[i]
        if abs(M[i][i]) < 1e-12:
            # Fallback to centroid + mean radius
            c = sum(points, Vector((0, 0, 0))) / n
            rs = [(p - c).length for p in points]
            r = sum(rs) / n
            residual = math.sqrt(sum((x - r) ** 2 for x in rs) / n)
            return c, r, residual
        diag = M[i][i]
        for j in range(i, 4):
            M[i][j] /= diag
        for r in range(3):
            if r == i:
                continue
            f = M[r][i]
            for j in range(i, 4):
                M[r][j] -= f * M[i][j]
    d = Vector((M[0][3], M[1][3], M[2][3]))
    c = d * -0.5
    rs = [(p - c).length for p in points]
    r = sum(rs) / n
    residual = math.sqrt(sum((x - r) ** 2 for x in rs) / n)
    return c, r, residual


def _collect_eye_surface_candidates(
    worlds: List[Vector],
    frame,
    side: str,
) -> List[Vector]:
    """Isolate exposed eyeball-ish verts: eye-height band, lateral side, forward surface."""
    sign = 1.0 if side == "L" else -1.0
    h = frame.head_height
    band: List[Tuple[float, Vector]] = []
    for p in worlds:
        loc = frame.to_local(p)
        t = (loc.z / h) * 0.5 + 0.5
        if not (0.52 <= t <= 0.78):
            continue
        if loc.x * sign < h * 0.03:
            continue
        if abs(loc.x) > h * 0.28:
            continue
        if loc.y < -h * 0.02:
            continue
        band.append((float(loc.y), p))
    if len(band) < MIN_SAMPLES:
        return []
    band.sort(key=lambda t: t[0], reverse=True)
    # Take forward percentile, then keep a compact lateral cluster (exclude eyelids that are more peripheral).
    top_n = max(MIN_SAMPLES, len(band) // 6)
    forward = band[:top_n]
    xs = sorted(frame.to_local(p).x for _, p in forward)
    med_x = xs[len(xs) // 2]
    # Tight cluster around median x / z of forward set
    zs = sorted(frame.to_local(p).z for _, p in forward)
    med_z = zs[len(zs) // 2]
    cluster: List[Vector] = []
    for _, p in forward:
        loc = frame.to_local(p)
        if abs(loc.x - med_x) > h * 0.035:
            continue
        if abs(loc.z - med_z) > h * 0.03:
            continue
        cluster.append(p)
    if len(cluster) < MIN_SAMPLES:
        # Relax slightly
        cluster = [p for _, p in forward if abs(frame.to_local(p).x - med_x) <= h * 0.05]
    # Prefer points that form a bulging cap: keep those with local y near max.
    if cluster:
        ys = [frame.to_local(p).y for p in cluster]
        y_cut = sorted(ys)[int(len(ys) * 0.35)]
        cluster = [p for p in cluster if frame.to_local(p).y >= y_cut]
    return cluster


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    if not fbx.exists():
        raise FileNotFoundError(fbx)
    if not ADDON_ZIP.exists() or _sha(ADDON_ZIP) != ALPHA1_ZIP_SHA:
        raise RuntimeError("Frozen Alpha1 ZIP missing or hash mismatch")

    sys.path.insert(0, str(ROOT))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted(
        [o for o in bpy.data.objects if o.type == "MESH"],
        key=lambda o: len(o.data.vertices),
        reverse=True,
    )
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    if not meshes:
        raise RuntimeError("No mesh")
    mesh = meshes[0]
    if arms:
        arms[0].data.pose_position = "REST"
        bpy.context.view_layer.update()

    import importlib
    import nurion_character_landmarker

    importlib.reload(nurion_character_landmarker)
    from nurion_character_landmarker.core.character_analyzer import analyze_character
    from nurion_character_landmarker.core.face.region import evaluate_face_region
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import (
        build_world_mesh_view,
        point_inside_or_on_mesh,
    )

    analysis = analyze_character(mesh)
    measurements = measure_character(analysis)
    body = estimate_body_landmarks(analysis, measurements)
    view = build_world_mesh_view(mesh)
    region = evaluate_face_region(
        mesh, view=view, body=body, forward_axis=measurements.forward_axis
    )
    if not region.eligible or region.headFrame is None:
        report = {
            "schema": "NURION_EYE_CENTER_RESOLUTION",
            "EYE_CENTER_RESOLUTION": "FAIL",
            "reasonCode": "FACE_ASSET_INELIGIBLE",
            "ThirteenPointGtEligibility": "FAIL",
            "alpha1QualityPass": "DENY",
        }
        _write(REPORTS / "eye-center-resolution.json", report)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 3

    frame = region.headFrame
    evidence: Dict[str, dict] = {}
    centers: Dict[str, Vector] = {}
    radii: Dict[str, float] = {}

    for side in ("L", "R"):
        name = f"eye.center.{side}"
        samples = _collect_eye_surface_candidates(region.faceVertexWorld, frame, side)
        center, radius, residual = _fit_sphere(samples)
        residual_mm = residual * 1000.0 if math.isfinite(residual) else float("inf")
        radius_mm = radius * 1000.0
        inside = bool(center is not None and point_inside_or_on_mesh(view, center))
        # Reject near-zero / huge radii (texture-flat or whole-head fit)
        radius_ok = frame.head_height * 0.015 <= radius <= frame.head_height * 0.12
        accepted = (
            center is not None
            and len(samples) >= MIN_SAMPLES
            and residual_mm <= MAX_RESIDUAL_MM
            and inside
            and radius_ok
        )
        row = {
            "landmark": name,
            "gtMethod": "VISIBLE_EYEBALL_SURFACE_FIT",
            "sampleCount": len(samples),
            "fitResidualMm": None if not math.isfinite(residual_mm) else round(residual_mm, 3),
            "radiusMm": round(radius_mm, 3) if center is not None else None,
            "centerWorld": [round(float(x), 6) for x in center] if center is not None else None,
            "centerHeadLocal": [round(float(x), 6) for x in frame.to_local(center)]
            if center is not None
            else None,
            "centerInsideHead": inside,
            "radiusPlausible": radius_ok,
            "accepted": accepted,
        }
        evidence[name] = row
        if accepted and center is not None:
            centers[name] = center
            radii[name] = radius

    lr_swap = 0
    if "eye.center.L" in centers and "eye.center.R" in centers:
        lx = frame.to_local(centers["eye.center.L"]).x
        rx = frame.to_local(centers["eye.center.R"]).x
        if lx < rx:
            lr_swap = 1
    radius_ratio_ok = True
    if len(radii) == 2:
        ra, rb = radii["eye.center.L"], radii["eye.center.R"]
        avg = 0.5 * (ra + rb)
        radius_ratio_ok = abs(ra - rb) / max(avg, 1e-9) <= MAX_RADIUS_DIFF_RATIO

    both_accepted = (
        evidence["eye.center.L"]["accepted"]
        and evidence["eye.center.R"]["accepted"]
        and lr_swap == 0
        and radius_ratio_ok
    )

    pending_note = None
    if both_accepted:
        resolution = "PASS"
        reason = "EYE_CENTER_RESOLVED"
        thirteen = "PASS"
        alpha1_quality = "ALLOWED_AFTER_GT_LOCK"
        next_step = (
            "EYE_CENTER_RESOLUTION = PASS → annotate remaining 11 GT points manually "
            "(use fitted eye centers for eye.center.L/R) → Export GT → make_face_gt_lock.py → Alpha1 eval"
        )
    else:
        resolution = "FAIL"
        reason = "EYE_CENTER_NOT_RESOLVABLE"
        thirteen = "FAIL"
        alpha1_quality = "DENY"
        next_step = (
            "EYE_CENTER_RESOLUTION = FAIL → optional 11-point diagnostic only on this asset; "
            "obtain a character with resolvable eyeball geometry (preferably separate eyeball meshes). "
            "Official Alpha1 quality gate remains deferred."
        )

    evidence_payload = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    evidence_sha = _sha_text(evidence_payload)

    # Candidate GT snippet for eye centers only (not a full 13-point GT lock).
    eye_gt_candidates = {
        "schema": "NURION_FACE_EYE_CENTER_GT_CANDIDATES",
        "gtMethod": "VISIBLE_EYEBALL_SURFACE_FIT",
        "accepted": both_accepted,
        "landmarks": {
            k: {
                "positionWorld": evidence[k]["centerWorld"],
                "positionHeadLocal": evidence[k]["centerHeadLocal"],
                "evidence": evidence[k],
            }
            for k in ("eye.center.L", "eye.center.R")
            if evidence[k]["accepted"]
        },
    }
    _write(REPORTS / "eye-center-gt-candidates.json", eye_gt_candidates)

    report = {
        "schema": "NURION_EYE_CENTER_RESOLUTION",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx),
        "fbxSha256": _sha(fbx),
        "FACE_ASSET_ELIGIBILITY": "ELIGIBLE",
        "EYE_CENTER_RESOLUTION": resolution,
        "ThirteenPointGtEligibility": thirteen,
        "ThirteenPointGtEligibilityPending": pending_note,
        "reasonCode": reason,
        "alpha1QualityPass": alpha1_quality,
        "gates": {
            "sampleCount_ge_32": all(evidence[k]["sampleCount"] >= MIN_SAMPLES for k in evidence),
            "residual_le_2_0_mm": all(
                evidence[k]["fitResidualMm"] is not None and evidence[k]["fitResidualMm"] <= MAX_RESIDUAL_MM
                for k in evidence
            ),
            "radiusDiff_le_15pct": radius_ratio_ok,
            "centerInsideHead": all(evidence[k]["centerInsideHead"] for k in evidence),
            "lrSwap_zero": lr_swap == 0,
        },
        "evidence": evidence,
        "evidenceSha256": evidence_sha,
        "evidenceSha256Length": 64,
        "lrSwap": lr_swap,
        "alpha1Frozen": {
            "packageSha256": ALPHA1_ZIP_SHA,
            "parameterHash": ALPHA1_PARAM,
            "untouched": True,
        },
        "diagnosticNote": (
            "If FAIL: remaining 11 landmarks may be annotated for diagnosis only; "
            "do not treat as official Alpha1 gate PASS."
        ),
        "next": next_step,
    }
    _write(REPORTS / "eye-center-resolution.json", report)
    _write(
        OUT / "EYE_CENTER_RESOLUTION_VERDICT.json",
        {
            "schema": "NURION_EYE_CENTER_RESOLUTION_VERDICT",
            "FACE_ASSET_ELIGIBILITY": "ELIGIBLE",
            "EYE_CENTER_RESOLUTION": resolution,
            "ThirteenPointGtEligibility": report["ThirteenPointGtEligibility"],
            "reasonCode": reason,
            "alpha1QualityPass": alpha1_quality,
            "evidenceSha256": evidence_sha,
            "fbxSha256": report["fbxSha256"],
            "report": "reports/eye-center-resolution.json",
        },
    )
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if both_accepted else 4


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
