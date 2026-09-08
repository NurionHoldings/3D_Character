"""
v0.4 Gate 5B — Automatic Lip Sync Rendering.

Consumes frozen Gate5A timelines (no timestamp reinterpretation).
Gate4 coarticulation + Gate3 viseme axes on Gate2 clone candidate only.

Usage:
  blender --background --python tools/blender_v04_gate5b_auto_lip_sync.py -- \\
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
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate5b"
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
    p.add_argument("--gate5a-dir", default="")
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
    g5a = Path(args.gate5a_dir) if args.gate5a_dir else ROOT / "dist" / "v0.4" / "gate5a" / args.label
    if not g5a.is_absolute():
        g5a = ROOT / g5a
    if not fbx.exists():
        raise FileNotFoundError(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate5b.integration import run_gate5b
    from nurion_v04_face_rig.gate5b.parameters import GATE5B_PARAMETERS, parameter_hash

    result = run_gate5b(
        root=ROOT,
        role=args.role,
        asset=args.label,
        mesh_name=args.mesh if args.mesh else "",
        gate5a_dir=g5a,
        runs=args.runs,
        clean_import_cb=lambda: _clean_import(fbx),
    )

    _write(out_dir / "GATE5B_PROFILE.json", result.profile)
    _write(out_dir / "GATE5B_VALIDATION.json", result.validation)
    _write(out_dir / "GATE5B_EVIDENCE.json", result.evidence)

    status = {
        "schema": "NURION_V04_GATE5B_STATUS",
        "gate": "5B",
        "name": "AUTOMATIC_LIP_SYNC_RENDERING",
        "V04_GATE5B": result.verdict,
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "gate4ParameterHash": GATE5B_PARAMETERS["gate4ParameterHash"],
        "gate5aParameterHash": GATE5B_PARAMETERS["gate5aParameterHash"],
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "notes": result.notes,
        "asr": "INACTIVE",
        "microphone": "INACTIVE",
        "realTimeLipSync": "HOLD",
        "fullExpression": "HOLD",
        "sourceCharacterMutation": "DENY",
        "gate1to5aMutation": "DENY",
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": _sha(fbx),
        "gate5aDir": str(g5a).replace("\\", "/"),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": "GATE5B_PROFILE.json",
            "validation": "GATE5B_VALIDATION.json",
            "evidence": "GATE5B_EVIDENCE.json",
        },
    }
    _write(out_dir / "V04_GATE5B_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE5B_LATEST.json", status)

    if result.verdict == "PASS" and args.role == "DEVELOPMENT" and args.label == "tennis":
        freeze = {
            "schema": "NURION_V04_GATE5B_PARAM_TEMP_FREEZE",
            "status": "TEMP_FROZEN_AFTER_TENNIS_DEV_PASS",
            "parameterHash": parameter_hash(),
            "parameterChange": "DENY_UNTIL_CV_COMPLETE",
            "tennis": "PASS",
            "gate4ParameterHash": GATE5B_PARAMETERS["gate4ParameterHash"],
            "gate5aParameterHash": GATE5B_PARAMETERS["gate5aParameterHash"],
            "combinedLockCandidate": {
                "gate5a": GATE5B_PARAMETERS["gate5aParameterHash"],
                "gate5b": parameter_hash(),
            },
            "asr": "INACTIVE",
            "microphone": "INACTIVE",
            "realTimeLipSync": "HOLD",
            "next": "CAPTAIN_CROSS_VALIDATION",
            "frozenAt": datetime.now(timezone.utc).isoformat(),
        }
        _write(DEFAULT_OUT / "GATE5B_PARAM_TEMP_FREEZE.json", freeze)
        _write(
            DEFAULT_OUT / "GATE5_COMBINED_LOCK_CANDIDATE.json",
            {
                "schema": "NURION_V04_GATE5_COMBINED_LOCK_CANDIDATE",
                "status": "CANDIDATE_AFTER_TENNIS_5B_PASS",
                "gate5aParameterHash": GATE5B_PARAMETERS["gate5aParameterHash"],
                "gate5bParameterHash": parameter_hash(),
                "gate4ParameterHash": GATE5B_PARAMETERS["gate4ParameterHash"],
                "awaiting": ["CAPTAIN_CV", "HYERIE_REFERENCE"],
                "createdAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    print(
        json.dumps(
            {
                "V04_GATE5B": result.verdict,
                "parameterHash": parameter_hash(),
                "gates": result.validation.get("gates"),
                "fails": result.validation.get("fails"),
                "notes": result.notes,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
