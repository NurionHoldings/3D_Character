"""
v0.4 Gate 8C — Fresh Holdout Validation.

Usage:
  blender --background --python tools/blender_v04_gate8c_fresh_holdout.py -- \\
    --zip PATH/TO/meshy_original.zip [--label holdout1] [--mesh ""]

Rules:
  RC.1 REPACK = DENY
  PARAMETER TUNING = 0
  MANUAL CORRECTION = 0
  CORE14 TIMELINE CHANGE = DENY
  SOURCE CHARACTER MUTATION = 0
  Tennis / Captain / hyerie / AILAWFRIEND = ineligible
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
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate8c"
DEFAULT_TIMELINES = ROOT / "dist" / "v0.4" / "gate6" / "human_gate4_timelines"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", required=True, help="Unused Meshy humanoid original ZIP (FBX+textures)")
    p.add_argument("--label", default="holdout")
    p.add_argument("--mesh", default="")
    p.add_argument("--out-dir", default="")
    p.add_argument("--timelines-dir", default=str(DEFAULT_TIMELINES))
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
    tdir = Path(args.timelines_dir)
    if not tdir.is_absolute():
        tdir = ROOT / tdir
    if not zpath.exists():
        raise FileNotFoundError(zpath)

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate8c.holdout_validation import run_fresh_holdout
    from nurion_v04_face_rig.gate8c.parameters import GATE8C_PARAMETERS, RC1_SHA256, parameter_hash

    work = out_dir / "_extract"
    result = run_fresh_holdout(
        zip_path=zpath,
        root=ROOT,
        mesh_name=args.mesh,
        work_dir=work,
        timelines_dir=tdir,
        clean_import_cb=_clean_import,
        runs=args.runs,
    )
    report = result.to_report()
    report["label"] = args.label
    report["createdAt"] = datetime.now(timezone.utc).isoformat()

    seal_review = "HOLD"
    if result.verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"):
        seal_review = "ELIGIBLE_FOR_FINAL_SEAL_REVIEW"

    status = {
        "schema": "NURION_V04_GATE8C_STATUS",
        "gate": "8C",
        "name": "FRESH_HOLDOUT_VALIDATION",
        "V04_GATE8C": result.verdict,
        "label": args.label,
        "parameterHash": parameter_hash(),
        "rc1Sha256": RC1_SHA256,
        "rc1Repack": "DENY",
        "zipSha256": report.get("zipSha256"),
        "modelSha256": report.get("modelSha256"),
        "manualCorrection": 0,
        "parameterTuning": 0,
        "core14TimelineChange": "DENY",
        "retryAfterEdit": "DENY",
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "sealed": False,
        "holdout": report.get("holdout"),
        "finalSeal": "HOLD",
        "finalSealReview": seal_review,
        "pipeline": GATE8C_PARAMETERS["pipeline"],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {"report": _rel(out_dir / "GATE8C_HOLDOUT_REPORT.json")},
        "next": (
            "FINAL_SEAL_REVIEW"
            if seal_review == "ELIGIBLE_FOR_FINAL_SEAL_REVIEW"
            else ("SUBMIT_NEW_HOLDOUT_ASSET" if result.verdict == "ASSET_INELIGIBLE" else "HOLD")
        ),
    }

    _write(out_dir / "GATE8C_HOLDOUT_REPORT.json", report)
    _write(out_dir / "V04_GATE8C_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE8C_LATEST.json", status)
    _write(
        DEFAULT_OUT / "GATE8C_DECISION.json",
        {
            "schema": "NURION_V04_GATE8C_DECISION",
            "verdict": result.verdict,
            "rc1Sha256": RC1_SHA256,
            "finalSeal": "HOLD",
            "finalSealReview": seal_review,
            "notes": result.notes,
            "decidedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V04_GATE8C": result.verdict,
                "rc1Sha256": RC1_SHA256,
                "zipSha256": report.get("zipSha256"),
                "modelSha256": report.get("modelSha256"),
                "finalSealReview": seal_review,
                "notes": result.notes,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
