"""Smoke-test Alpha2 Eye Proxy + Procedural Eyeball on a Meshy-like FBX."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.3" / "face" / "alpha2"
REPORTS = OUT / "reports"
ADDON_ZIP = OUT / "NURION_Character_Landmarker_v0.3.0-alpha.2.zip"
ADDON_MODULE = "nurion_character_landmarker"
ALPHA1_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"


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
    p.add_argument("--label", default="eye-proxy-smoke")
    return p.parse_args(argv)


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    if not ADDON_ZIP.exists():
        raise FileNotFoundError(ADDON_ZIP)
    a1 = ROOT / "dist" / "v0.3" / "face" / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
    if a1.exists() and _sha(a1) != ALPHA1_SHA:
        raise RuntimeError("Alpha1 ZIP mutated")

    sys.path.insert(0, str(ROOT))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
    bpy.ops.preferences.addon_install(filepath=str(ADDON_ZIP), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)

    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
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
    from nurion_character_landmarker.core.face.keys import ALPHA2_DERIVED_EYE_CENTER_KEYS, ALPHA2_EYE_SURFACE_KEYS
    from nurion_character_landmarker.core.face.parameters_alpha2 import (
        FACE_ALPHA2_PARAMETER_HASH,
        FACE_ALPHA2_PARAMETERS,
        parameter_hash,
    )
    from nurion_character_landmarker.core.landmark_engine import estimate_body_landmarks
    from nurion_character_landmarker.core.measurement_engine import measure_character
    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view, point_inside_or_on_mesh

    live = parameter_hash(FACE_ALPHA2_PARAMETERS)
    if live != FACE_ALPHA2_PARAMETER_HASH:
        raise RuntimeError("Alpha2 parameter hash mismatch")

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
        payload = serialize_landmarks_for_hash(last.landmarks, ALPHA2_EYE_SURFACE_KEYS + ALPHA2_DERIVED_EYE_CENTER_KEYS)
        hashes.append(hashlib.sha256(payload.encode()).hexdigest())
    determinism = len(set(hashes)) == 1

    centers_ok = len(last.proxy.centers) == 2
    inside = all(point_inside_or_on_mesh(view, last.proxy.centers[k].position) for k in last.proxy.centers)
    radii = list(last.proxy.radii.values())
    radius_diff = 0.0
    if len(radii) == 2:
        avg = 0.5 * (radii[0] + radii[1])
        radius_diff = abs(radii[0] - radii[1]) / max(avg, 1e-9)
    lr_swap = 0
    if centers_ok:
        fr = last.region.headFrame
        lx = fr.to_local(last.proxy.centers["eye.center.L"].position).x
        rx = fr.to_local(last.proxy.centers["eye.center.R"].position).x
        if lx < rx:
            lr_swap = 1

    eyeballs = [o for o in bpy.data.objects if o.name.startswith("NURION_Eyeball")]
    report = {
        "schema": "NURION_V0.3A2_EYE_PROXY_SMOKE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "fbx": str(fbx),
        "fbxSha256": _sha(fbx),
        "parameterHash": live,
        "packageSha256": _sha(ADDON_ZIP),
        "alpha1FrozenSha256": ALPHA1_SHA,
        "smokePass": bool(centers_ok and inside and lr_swap == 0 and determinism and len(eyeballs) == 2 and radius_diff <= 0.10),
        "gates": {
            "bothCenters": centers_ok,
            "centersInsideHead": inside,
            "lrSwapZero": lr_swap == 0,
            "radiusDiffLe10pct": radius_diff <= 0.10,
            "determinism3x": determinism,
            "eyeballObjectsCreated": len(eyeballs) == 2,
        },
        "metrics": {
            "surfaceLandmarks": len(last.proxy.surface),
            "radiusDiff": round(radius_diff, 6),
            "radiiMm": {k: round(v * 1000.0, 3) for k, v in last.proxy.radii.items()},
            "eyeballs": [o.name for o in eyeballs],
        },
        "determinismHashes": hashes,
        "pipeline": last.to_dict(),
        "note": "Alpha2 smoke for Meshy Eye Proxy. Surface GT quality gates require manual annotation separately.",
    }
    _write(REPORTS / f"{args.label}-eye-proxy-smoke.json", report)
    _write(OUT / "ALPHA2_SMOKE_VERDICT.json", report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["smokePass"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
