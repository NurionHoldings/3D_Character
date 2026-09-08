"""
v0.4 Gate 7 — Limited Facial Performance Integration.

Combines v0.3 Eye/Gaze/Blink (read-only) + v0.4 expression states +
Gate5A.2/Gate6 frozen timelines + Gate5B lip sync + Conflict Coordinator.
Clone candidate only. ASR / mic / real-time = INACTIVE.

Usage:
  blender --background --python tools/blender_v04_gate7_limited_facial.py -- \\
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
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate7"
DEFAULT_TENNIS = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)
DEFAULT_TIMELINES = ROOT / "dist" / "v0.4" / "gate6" / "human_gate4_timelines"


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
    p.add_argument("--timelines-dir", default="")
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
    tdir = Path(args.timelines_dir) if args.timelines_dir else DEFAULT_TIMELINES
    if not tdir.is_absolute():
        tdir = ROOT / tdir
    if not fbx.exists():
        raise FileNotFoundError(fbx)
    if not tdir.exists():
        raise FileNotFoundError(tdir)

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate7.integration import run_gate7
    from nurion_v04_face_rig.gate7.parameters import GATE7_PARAMETERS, parameter_hash

    result = run_gate7(
        root=ROOT,
        role=args.role,
        asset=args.label,
        mesh_name=args.mesh if args.mesh else "",
        timelines_dir=tdir,
        runs=args.runs,
        clean_import_cb=lambda: _clean_import(fbx),
    )

    _write(out_dir / "GATE7_PROFILE.json", result.profile)
    _write(out_dir / "GATE7_VALIDATION.json", result.validation)
    _write(out_dir / "GATE7_EVIDENCE.json", result.evidence)

    status = {
        "schema": "NURION_V04_GATE7_STATUS",
        "gate": "7",
        "name": "LIMITED_FACIAL_PERFORMANCE_INTEGRATION",
        "V04_GATE7": result.verdict,
        "mode": "LIMITED_INTEGRATION",
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "gate6ParameterHash": GATE7_PARAMETERS["gate6ParameterHash"],
        "gate5bParameterHash": GATE7_PARAMETERS["gate5bParameterHash"],
        "gate5a2ParameterHash": GATE7_PARAMETERS["gate5a2ParameterHash"],
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "notes": result.notes,
        "asr": "INACTIVE",
        "microphone": "INACTIVE",
        "realTime": "INACTIVE",
        "fullUnrestricted": "HOLD",
        "parameterTuning": "DENY",
        "sourceCharacterMutation": "DENY",
        "gate1to6Mutation": "DENY",
        "v03Mutation": "DENY",
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": _sha(fbx),
        "timelinesDir": str(tdir).replace("\\", "/"),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": "GATE7_PROFILE.json",
            "validation": "GATE7_VALIDATION.json",
            "evidence": "GATE7_EVIDENCE.json",
        },
        "next": "CAPTAIN_CROSS_VALIDATION" if result.verdict == "PASS" else "TENNIS_DEV_FIX",
    }
    _write(out_dir / "V04_GATE7_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE7_LATEST.json", status)

    if result.verdict == "PASS" and args.role == "DEVELOPMENT" and args.label == "tennis":
        freeze = {
            "schema": "NURION_V04_GATE7_PARAM_TEMP_FREEZE",
            "status": "TEMP_FROZEN_AFTER_TENNIS_DEV_PASS",
            "parameterHash": parameter_hash(),
            "parameterChange": "DENY_UNTIL_CV_COMPLETE",
            "tennis": "PASS",
            "mode": "LIMITED_INTEGRATION",
            "gate6ParameterHash": GATE7_PARAMETERS["gate6ParameterHash"],
            "gate5bParameterHash": GATE7_PARAMETERS["gate5bParameterHash"],
            "gate5a2ParameterHash": GATE7_PARAMETERS["gate5a2ParameterHash"],
            "fullUnrestricted": "HOLD",
            "asr": "INACTIVE",
            "microphone": "INACTIVE",
            "realTime": "INACTIVE",
            "next": "CAPTAIN_CROSS_VALIDATION",
            "frozenAt": datetime.now(timezone.utc).isoformat(),
        }
        _write(DEFAULT_OUT / "GATE7_PARAM_TEMP_FREEZE.json", freeze)

    print(
        json.dumps(
            {
                "V04_GATE7": result.verdict,
                "mode": "LIMITED_INTEGRATION",
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
