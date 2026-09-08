"""
v0.5 Gate 10 — Fresh Holdout (ai-baeby / Lightning Pilot Formal Bow).

Usage:
  blender --background --python tools/blender_v05_gate10_fresh_holdout.py -- \\
    --zip "ai-baeby/aibaeby-bow.zip" --label ai-baeby --runs 3
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
DEFAULT_OUT = ROOT / "dist" / "v0.5" / "gate10"
DEFAULT_ZIP = ROOT / "ai-baeby" / "aibaeby-bow.zip"
EXPECTED_ZIP_SHA = "3703b784072e791b999c2332fb4fff951e4997560ee7f92b5b49fdc743b3d54a"
V05_RC1 = ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V05_RC1_SHA = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"
V04_RC1 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V04_RC1_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default=str(DEFAULT_ZIP))
    p.add_argument("--label", default="ai-baeby")
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


def _clean_import(model: Path) -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(model), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()


def main() -> int:
    args = _parse(sys.argv)
    zpath = Path(args.zip)
    if not zpath.is_absolute():
        zpath = ROOT / zpath
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    if not zpath.exists():
        raise FileNotFoundError(zpath)
    zip_sha = _sha(zpath)
    if zip_sha != EXPECTED_ZIP_SHA:
        raise RuntimeError(f"aibaeby-bow.zip SHA mismatch: {zip_sha} != {EXPECTED_ZIP_SHA}")
    if _sha(V05_RC1) != V05_RC1_SHA:
        raise RuntimeError("v0.5 RC.1 mutated — REPACK DENY")
    if _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("v0.4 RC.1 mutated — DENY")

    # Freeze receipt before run
    _write(
        out_dir / "HOLDOUT_ASSET_LOCK.json",
        {
            "schema": "NURION_V05_HOLDOUT_ASSET_LOCK",
            "label": args.label,
            "character": "ai-baeby",
            "meshyName": "Lightning_Pilot",
            "zip": str(zpath).replace("\\", "/"),
            "zipSha256": zip_sha,
            "animation": "Formal_Bow",
            "siblingZipMix": "DENY",
            "excludedSiblings": ["aibaeby-15.zip", "aibaeby-vendition.zip"],
            "v05Rc1Sha256": V05_RC1_SHA,
            "v05Rc1Repack": "DENY",
            "lockedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    sys.path.insert(0, str(ROOT))
    from nurion_v05_body_motion.gate10.holdout import run_gate10_holdout
    from nurion_v05_body_motion.gate10.parameters import INHERITED_LIMITATIONS, parameter_hash

    result = run_gate10_holdout(
        zip_path=zpath,
        root=ROOT,
        mesh_name=args.mesh,
        work_dir=out_dir / "_extract",
        runs=args.runs,
        clean_import_cb=_clean_import,
    )

    if _sha(zpath) != EXPECTED_ZIP_SHA or _sha(V05_RC1) != V05_RC1_SHA or _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("source/RC mutated during Gate10 — FAIL")

    seal_review = "HOLD"
    if result.verdict in ("HOLDOUT_PASS", "PASS_WITH_LIMITATIONS"):
        seal_review = "ELIGIBLE_FOR_FINAL_SEAL_REVIEW"

    _write(out_dir / "GATE10_HOLDOUT_REPORT.json", result.report)
    _write(out_dir / "GATE10_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V05_GATE10_STATUS",
        "gate": "10",
        "track": "v0.5 Body Motion Retarget & Rig Correction",
        "name": "FRESH_HOLDOUT",
        "V05_GATE10": result.verdict,
        "label": args.label,
        "character": "ai-baeby",
        "meshyName": "Lightning_Pilot",
        "animation": "Formal_Bow",
        "parameterHash": parameter_hash(),
        "zipSha256": zip_sha,
        "modelSha256": result.report.get("modelSha256"),
        "v05Rc1Sha256": V05_RC1_SHA,
        "v05Rc1Repack": "DENY",
        "v04Rc1Sha256": V04_RC1_SHA,
        "parameterTuning": 0,
        "manualCorrection": 0,
        "siblingZipMix": "DENY",
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
        "holdout": result.verdict,
        "finalSeal": "HOLD",
        "finalSealReview": seal_review,
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "limitations": result.validation.get("limitations"),
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "next": "FINAL_SEAL_REVIEW" if seal_review == "ELIGIBLE_FOR_FINAL_SEAL_REVIEW" else "HOLDOUT_FIX",
    }
    _write(out_dir / "V05_GATE10_STATUS.json", status)
    _write(DEFAULT_OUT / "V05_GATE10_LATEST.json", status)
    _write(
        DEFAULT_OUT / "GATE10_DECISION.json",
        {
            "schema": "NURION_V05_GATE10_DECISION",
            "verdict": result.verdict,
            "zipSha256": zip_sha,
            "v05Rc1Sha256": V05_RC1_SHA,
            "finalSealReview": seal_review,
            "inheritedLimitations": INHERITED_LIMITATIONS,
            "notes": result.notes,
            "decidedAt": datetime.now(timezone.utc).isoformat(),
        },
    )
    _write(
        ROOT / "dist/v0.5/STATUS.json",
        {
            "schema": "NURION_V0.5_STATUS",
            "track": "Body Motion Retarget & Rig Correction",
            "implementation": "GATE10_FRESH_HOLDOUT",
            "V05_GATE1": "PASS_WITH_LIMITATIONS",
            "V05_GATE2": "PASS_WITH_LIMITATIONS",
            "V05_GATE3": "PASS_WITH_LIMITATIONS",
            "V05_GATE4": "PASS_WITH_LIMITATIONS",
            "V05_GATE5": "PASS_WITH_LIMITATIONS",
            "V05_GATE6": "PASS_WITH_LIMITATIONS",
            "V05_GATE7": "PASS_WITH_LIMITATIONS",
            "V05_GATE8": "PASS_WITH_LIMITATIONS",
            "V05_GATE9": "PASS_WITH_LIMITATIONS",
            "V05_GATE10": result.verdict,
            "gate10ParameterHash": parameter_hash(),
            "holdoutAsset": "ai-baeby",
            "holdoutZipSha256": zip_sha,
            "rc1Sha256": V05_RC1_SHA,
            "repack": "DENY",
            "sealed": False,
            "SEALED": False,
            "v04": "SEALED_READONLY",
            "supportedDomain": "LIMITED",
            "production": "NO-GO",
            "inheritedLimitations": INHERITED_LIMITATIONS,
            "finalSealReview": seal_review,
            "next": status["next"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V05_GATE10": result.verdict,
                "parameterHash": parameter_hash(),
                "zipSha256": zip_sha,
                "modelSha256": result.report.get("modelSha256"),
                "v05Rc1Sha256": V05_RC1_SHA,
                "finalSealReview": seal_review,
                "fails": result.validation.get("fails"),
                "limitations": result.validation.get("limitations"),
                "bodyTypeDependency": result.report.get("bodyTypeDependency"),
                "next": status["next"],
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
