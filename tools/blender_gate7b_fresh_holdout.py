"""
Gate 7B — Fresh Holdout Validation.

Usage:
  blender --background --python tools/blender_gate7b_fresh_holdout.py -- \\
    --zip PATH/TO/meshy_original.zip [--label holdout1] [--mesh ""]

Rules:
  MANUAL CORRECTION = 0
  PARAMETER TUNING = 0
  RETRY AFTER EDIT = DENY
  RC.1 package must remain SHA-frozen (no repack).
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate7b"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, help="Unused Meshy humanoid original ZIP")
    p.add_argument("--label", default="holdout")
    p.add_argument("--mesh", default="")
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    return p.parse_args(argv)


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _clean_import(model: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    suffix = model.suffix.lower()
    if suffix == ".fbx":
        bpy.ops.import_scene.fbx(filepath=str(model), automatic_bone_orientation=True, use_anim=False)
    elif suffix == ".glb":
        bpy.ops.import_scene.gltf(filepath=str(model))
    else:
        raise RuntimeError(f"Unsupported model format: {model}")
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()


def main() -> int:
    args = _parse(sys.argv)
    zpath = Path(args.zip)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not zpath.exists():
        raise FileNotFoundError(zpath)

    sys.path.insert(0, str(ROOT))
    from nurion_universal_eye.gate7b.holdout_validation import run_fresh_holdout
    from nurion_universal_eye.gate7b.parameters import GATE7B_PARAMETERS, RC1_SHA256, parameter_hash

    work = out_dir / "_extract"
    result = run_fresh_holdout(
        zip_path=zpath,
        root=ROOT,
        mesh_name=args.mesh,
        work_dir=work,
        clean_import_cb=_clean_import,
        runs=args.runs,
    )
    report = result.to_report()
    report["label"] = args.label
    report["createdAt"] = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_GATE7B_STATUS",
        "gate": "7B",
        "name": "FRESH_HOLDOUT_VALIDATION",
        "GATE7B": report["verdict"],
        "label": args.label,
        "parameterHash": parameter_hash(),
        "rc1Sha256": RC1_SHA256,
        "zipSha256": report.get("zipSha256"),
        "modelSha256": report.get("modelSha256"),
        "manualCorrection": 0,
        "parameterTuning": 0,
        "retryAfterEdit": "DENY",
        "releaseCandidate": True,
        "sealed": False,
        "holdout": report.get("holdout"),
        "finalSeal": "HOLD",
        "requiredGateParams": GATE7B_PARAMETERS["requiredGateParams"],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "report": _rel(out_dir / "GATE7B_HOLDOUT_REPORT.json"),
        },
    }

    _write(out_dir / "GATE7B_HOLDOUT_REPORT.json", report)
    _write(out_dir / "GATE7B_STATUS.json", status)
    _write(DEFAULT_OUT / "GATE7B_LATEST.json", status)

    print(
        json.dumps(
            {
                "GATE7B": report["verdict"],
                "rc1Sha256": RC1_SHA256,
                "parameterHash": parameter_hash(),
                "notes": report.get("notes"),
            },
            indent=2,
        )
    )
    if report["verdict"] == "HOLDOUT_PASS":
        return 0
    if report["verdict"] == "ASSET_INELIGIBLE":
        return 3
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
