"""
v0.6 Gate 4 — Body + Face + Eye bind.

Usage:
  blender --background --python tools/blender_v06_gate4_body_face_eye_bind.py -- \\
    --zip dist/v0.5/gate1/inbox/ai-aba.bow.zip --label ai-aba.bow \\
    --gate2-class LIMITED --gate3-action APPLY_LIMITED_MAPPING --lipsync-supported 0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.6" / "gate4"
GATE1_HASH = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
GATE2_HASH = "b5d3c4931d1ef65a64844483e51bb74d6edcfcb9f90de28abe1c47192c85df6e"
GATE3_HASH = "35daa4fce90b00c474abcd08b7c40e313d79bcf7c50710ce8f8120b645bf1604"
V03 = ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V04 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V05 = ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V03_SHA = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_SHA = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default="")
    p.add_argument("--fbx", default="")
    p.add_argument("--label", required=True)
    p.add_argument("--gate2-class", required=True, choices=["FULL", "LIMITED", "INELIGIBLE"])
    p.add_argument("--gate3-action", required=True)
    p.add_argument("--lipsync-supported", type=int, default=0)
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--empty-scene", action="store_true")
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


def _baseline_ok() -> bool:
    for path, expected in [(V03, V03_SHA), (V04, V04_SHA), (V05, V05_SHA)]:
        if not path.is_file() or _sha(path) != expected:
            return False
    return True


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    zip_sha = ""
    if args.empty_scene or (args.gate2_class == "INELIGIBLE" and not args.zip and not args.fbx):
        out_dir.mkdir(parents=True, exist_ok=True)
        fbx = out_dir / "_empty_control.NOIMPORT"
    elif args.zip:
        zpath = Path(args.zip)
        if not zpath.is_absolute():
            zpath = ROOT / zpath
        extract = out_dir / "_extract"
        if extract.exists():
            shutil.rmtree(extract)
        extract.mkdir(parents=True)
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(extract)
        sys.path.insert(0, str(ROOT))
        from nurion_v06_unified_runtime.gate2.diagnosis import pick_primary_fbx

        fbx = pick_primary_fbx(extract)
        if fbx is None:
            raise FileNotFoundError("no FBX")
        zip_sha = _sha(zpath)
    elif args.fbx:
        fbx = Path(args.fbx)
        if not fbx.is_absolute():
            fbx = ROOT / fbx
        if not fbx.exists():
            raise FileNotFoundError(fbx)
    else:
        raise SystemExit("provide --zip, --fbx, or --empty-scene")

    fbx_sha = _sha(fbx) if fbx.is_file() else ""
    baseline_hash_ok = _baseline_ok()

    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as g1_hash
    from nurion_v06_unified_runtime.gate2.parameters import parameter_hash as g2_hash
    from nurion_v06_unified_runtime.gate3.parameters import parameter_hash as g3_hash
    from nurion_v06_unified_runtime.gate4.bind import run_gate4_bind
    from nurion_v06_unified_runtime.gate4.parameters import GATE4_PARAMETERS, parameter_hash

    if g1_hash() != GATE1_HASH or g2_hash() != GATE2_HASH or g3_hash() != GATE3_HASH:
        raise RuntimeError("Gate1/2/3 parameter hash mismatch — DENY")

    def _clean_import():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if fbx.is_file() and not args.empty_scene:
            bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
        bpy.context.view_layer.update()

    result = run_gate4_bind(
        root=ROOT,
        fbx_path=fbx,
        label=args.label,
        gate2_classification=args.gate2_class,
        gate3_runtime_action=args.gate3_action,
        lipsync_supported=bool(args.lipsync_supported),
        zip_sha256=zip_sha,
        fbx_sha256=fbx_sha,
        baseline_hash_ok=baseline_hash_ok,
        runs=args.runs,
        clean_import_cb=_clean_import,
    )

    _write(out_dir / "GATE4_PROFILE.json", result.profile)
    _write(out_dir / "GATE4_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V06_GATE4_ASSET_STATUS",
        "gate": "4",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "BODY_FACE_EYE_BIND",
        "label": args.label,
        "gate2Classification": args.gate2_class,
        "gate3RuntimeAction": args.gate3_action,
        "bindVerdict": result.verdict,
        "runtimeAction": result.runtime_action,
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate1Locked": True,
        "gate2Locked": True,
        "gate3Locked": True,
        "zipSha256": zip_sha,
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": fbx_sha,
        "sourceMutation": result.source_mutation,
        "manualCorrection": result.manual_correction,
        "assetSpecificTuning": result.asset_specific_tuning,
        "lipsyncMode": result.validation.get("lipsyncMode"),
        "abstainReasons": result.validation.get("abstainReasons"),
        "gates": result.validation.get("gates"),
        "inheritedLimitationsFromV05": GATE4_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "production": "NO-GO",
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifacts": {"profile": "GATE4_PROFILE.json", "validation": "GATE4_VALIDATION.json"},
        "next": "GATE5_MOTION_PRESET",
    }
    _write(out_dir / "V06_GATE4_ASSET_STATUS.json", status)

    print(
        json.dumps(
            {
                "label": args.label,
                "bindVerdict": result.verdict,
                "runtimeAction": result.runtime_action,
                "lipsyncMode": status["lipsyncMode"],
                "sourceMutation": result.source_mutation,
                "manualCorrection": 0,
                "abstainReasons": status["abstainReasons"],
                "parameterHash": parameter_hash(),
                "out": str(out_dir).replace("\\", "/"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
