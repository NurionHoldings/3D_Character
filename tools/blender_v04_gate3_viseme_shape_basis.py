"""
v0.4 Gate 3 — Viseme Shape Basis (clone-only diagnostic).

No audio, no automatic lip sync, no source rig application.

Usage:
  blender --background --python tools/blender_v04_gate3_viseme_shape_basis.py -- \\
    --fbx PATH --label tennis --role DEVELOPMENT
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

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate3"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_TENNIS))
    p.add_argument("--label", default="tennis")
    p.add_argument("--role", default="DEVELOPMENT", choices=["DEVELOPMENT", "CROSS_VALIDATION", "REFERENCE"])
    p.add_argument("--mesh", default="char1")
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    return p.parse_args(argv)


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _clean_import(fbx: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate3.integration import run_gate3
    from nurion_v04_face_rig.gate3.parameters import GATE3_PARAMETERS, parameter_hash

    result = run_gate3(
        root=ROOT,
        role=args.role,
        asset=args.label,
        mesh_name=args.mesh if args.mesh else "",
        runs=args.runs,
        clean_import_cb=lambda: _clean_import(fbx),
    )
    _write(out_dir / "GATE3_PROFILE.json", result.profile)
    _write(out_dir / "GATE3_VALIDATION.json", result.validation)
    status = {
        "schema": "NURION_V04_GATE3_STATUS",
        "gate": "3",
        "name": "VISEME_SHAPE_BASIS",
        "V04_GATE3": result.verdict,
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "notes": result.notes,
        "audioInput": "INACTIVE",
        "automaticLipSync": "HOLD",
        "sourceCharacterMutation": "DENY",
        "gate2ParameterHashRequired": GATE3_PARAMETERS["gate2ParameterHash"],
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": _sha(fbx),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {"profile": "GATE3_PROFILE.json", "validation": "GATE3_VALIDATION.json"},
    }
    _write(out_dir / "V04_GATE3_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE3_LATEST.json", status)
    print(
        json.dumps(
            {
                "V04_GATE3": result.verdict,
                "parameterHash": parameter_hash(),
                "gates": result.validation.get("gates"),
                "fails": result.validation.get("fails"),
                "notes": result.notes,
            },
            indent=2,
        )
    )
    return 0 if result.verdict == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
