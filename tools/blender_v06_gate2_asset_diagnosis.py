"""
v0.6 Gate 2 — automatic asset diagnosis (FULL / LIMITED / INELIGIBLE).

Usage:
  blender --background --python tools/blender_v06_gate2_asset_diagnosis.py -- \\
    --zip dist/v0.5/gate1/inbox/ai-aba.bow.zip --label ai-aba.bow

  blender --background --python tools/blender_v06_gate2_asset_diagnosis.py -- \\
    --fbx path/to/file.fbx --label sample

Gate 1 contract is frozen. Source FBX/ZIP are not mutated.
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
DEFAULT_OUT = ROOT / "dist" / "v0.6" / "gate2"
GATE1_HASH = "19a7ae9aae86437c79139b5ccc777e9bd22dcc874c21a13694509feaf06e1676"
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
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--sibling-zip-mix", action="store_true")
    p.add_argument(
        "--empty-scene",
        action="store_true",
        help="Diagnose empty scene as INELIGIBLE control (no FBX import)",
    )
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
    checks = [(V03, V03_SHA), (V04, V04_SHA), (V05, V05_SHA)]
    for path, expected in checks:
        if not path.is_file() or _sha(path) != expected:
            return False
    return True


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    zip_sha = ""
    fbx: Path | None = None
    if args.empty_scene:
        out_dir.mkdir(parents=True, exist_ok=True)
        # Sentinel path only — import callback skips load; file is never created.
        fbx = out_dir / "_empty_control.NOIMPORT"
    elif args.zip:
        zpath = Path(args.zip)
        if not zpath.is_absolute():
            zpath = ROOT / zpath
        if not zpath.exists():
            raise FileNotFoundError(zpath)
        extract = out_dir / "_extract"
        if extract.exists():
            shutil.rmtree(extract)
        extract.mkdir(parents=True)
        with zipfile.ZipFile(zpath, "r") as zf:
            zf.extractall(extract)
        sys.path.insert(0, str(ROOT))
        from nurion_v06_unified_runtime.gate2.diagnosis import pick_primary_fbx

        picked = pick_primary_fbx(extract)
        if picked is None:
            raise FileNotFoundError("no FBX in zip")
        fbx = picked
        zip_sha = _sha(zpath)
    elif args.fbx:
        fbx = Path(args.fbx)
        if not fbx.is_absolute():
            fbx = ROOT / fbx
        if not fbx.exists():
            raise FileNotFoundError(fbx)
    else:
        raise SystemExit("provide --zip or --fbx")

    assert fbx is not None
    fbx_sha = _sha(fbx) if (fbx.exists() and not args.empty_scene) else ""
    baseline_hash_ok = _baseline_ok()

    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate1.parameters import parameter_hash as g1_hash
    from nurion_v06_unified_runtime.gate2.diagnosis import run_gate2_diagnosis
    from nurion_v06_unified_runtime.gate2.parameters import GATE2_PARAMETERS, parameter_hash

    if g1_hash() != GATE1_HASH:
        raise RuntimeError("Gate1 parameter hash mismatch — DENY mutation")

    def _clean_import():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if not args.empty_scene:
            bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
        bpy.context.view_layer.update()

    result = run_gate2_diagnosis(
        fbx_path=fbx,
        label=args.label,
        zip_sha256=zip_sha,
        fbx_sha256=fbx_sha,
        sibling_zip_mix=bool(args.sibling_zip_mix),
        baseline_hash_ok=baseline_hash_ok,
        runs=args.runs,
        clean_import_cb=_clean_import,
    )

    _write(out_dir / "GATE2_PROFILE.json", result.profile)
    _write(out_dir / "GATE2_CLASSIFICATION.json", result.classification)

    status = {
        "schema": "NURION_V06_GATE2_ASSET_STATUS",
        "gate": "2",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "AUTO_ASSET_DIAGNOSIS",
        "label": args.label,
        "assetClassification": result.classification.get("classification"),
        "runtimeAction": result.classification.get("runtimeAction"),
        "diagnosisVerdict": result.verdict,
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE1_HASH,
        "gate1Locked": True,
        "zipSha256": zip_sha,
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": fbx_sha,
        "baselineHashOk": baseline_hash_ok,
        "sourceMutation": 0,
        "production": "NO-GO",
        "pathStatus": result.classification.get("pathStatus"),
        "abstainReasons": result.classification.get("abstainReasons"),
        "inheritedLimitationsFromV05": GATE2_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "determinism": result.classification.get("determinism"),
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "artifacts": {
            "profile": "GATE2_PROFILE.json",
            "classification": "GATE2_CLASSIFICATION.json",
        },
        "next": "GATE3_UNIFIED_BONE_MAPPING",
    }
    _write(out_dir / "V06_GATE2_ASSET_STATUS.json", status)

    print(
        json.dumps(
            {
                "label": args.label,
                "classification": status["assetClassification"],
                "runtimeAction": status["runtimeAction"],
                "diagnosisVerdict": result.verdict,
                "parameterHash": parameter_hash(),
                "abstainReasons": status["abstainReasons"],
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
