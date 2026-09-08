"""
v0.5 Gate 1 — Formal Bow source motion & rig diagnosis.

Usage:
  blender --background --python tools/blender_v05_gate1_body_motion_diagnosis.py -- \\
    --zip dist/v0.5/gate1/inbox/ai-aba.bow.zip --label ai-aba.bow

v0.4 SEALED / READ ONLY — never mutate RC.1 or seal files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.5" / "gate1"
DEFAULT_ZIP = DEFAULT_OUT / "inbox" / "ai-aba.bow.zip"
V04_RC1 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V04_RC1_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--zip", default=str(DEFAULT_ZIP))
    p.add_argument("--label", default="ai-aba.bow")
    p.add_argument("--mesh", default="")
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


def _pick_fbx(extract_dir: Path) -> Path:
    fbxs = sorted(extract_dir.rglob("*.fbx")) + sorted(extract_dir.rglob("*.FBX"))
    if not fbxs:
        raise FileNotFoundError("no FBX in bow zip")

    def score(p: Path) -> tuple:
        n = p.name.lower()
        s = 0
        if "formal" in n and "bow" in n:
            s += 100
        if "withskin" in n or "with_skin" in n:
            s += 50
        return (-s, str(p).lower())

    return sorted(fbxs, key=score)[0]


def main() -> int:
    args = _parse(sys.argv)
    zpath = Path(args.zip)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not zpath.is_absolute():
        zpath = ROOT / zpath
    if not zpath.exists():
        raise FileNotFoundError(zpath)

    # v0.4 immutability check (read-only)
    if not V04_RC1.exists() or _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("v0.4 RC.1 missing or mutated — DENY")

    extract = out_dir / "_extract"
    if extract.exists():
        import shutil

        shutil.rmtree(extract)
    extract.mkdir(parents=True)
    with zipfile.ZipFile(zpath, "r") as zf:
        zf.extractall(extract)
    fbx = _pick_fbx(extract)
    zip_sha = _sha(zpath)
    fbx_sha = _sha(fbx)

    sys.path.insert(0, str(ROOT))
    from nurion_v05_body_motion.gate1.diagnosis import run_gate1
    from nurion_v05_body_motion.gate1.parameters import GATE1_PARAMETERS, parameter_hash

    def _clean_import():
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
        for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
            # keep animation; REST checked inside diagnosis
            pass
        bpy.context.view_layer.update()

    result = run_gate1(
        fbx_path=fbx,
        zip_sha256=zip_sha,
        mesh_name=args.mesh if args.mesh else "",
        runs=args.runs,
        clean_import_cb=_clean_import,
    )

    _write(out_dir / "GATE1_PROFILE.json", result.profile)
    _write(out_dir / "GATE1_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V05_GATE1_STATUS",
        "gate": "1",
        "track": "v0.5 Body Motion Retarget & Rig Correction",
        "name": "FORMAL_BOW_SOURCE_MOTION_RIG_DIAGNOSIS",
        "V05_GATE1": result.verdict,
        "label": args.label,
        "parameterHash": parameter_hash(),
        "zipSha256": zip_sha,
        "fbx": str(fbx).replace("\\", "/"),
        "fbxSha256": fbx_sha,
        "v04Sealed": True,
        "v04Rc1Sha256": V04_RC1_SHA,
        "v04Mutation": "DENY",
        "sourceCharacterMutation": "DENY",
        "correctionTarget": "CLONE_ONLY",
        "production": "NO-GO",
        "gates": result.validation.get("gates"),
        "hardFails": result.validation.get("hardFails"),
        "limitations": result.validation.get("limitations"),
        "notes": result.notes,
        "pipeline": GATE1_PARAMETERS["pipeline"],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": "GATE1_PROFILE.json",
            "validation": "GATE1_VALIDATION.json",
        },
        "next": "GATE2_BONE_AXIS_HIERARCHY_NORMALIZE" if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else "GATE1_FIX",
    }
    _write(out_dir / "V05_GATE1_STATUS.json", status)
    _write(DEFAULT_OUT / "V05_GATE1_LATEST.json", status)
    _write(
        ROOT / "dist/v0.5/STATUS.json",
        {
            "schema": "NURION_V0.5_STATUS",
            "track": "Body Motion Retarget & Rig Correction",
            "implementation": "GATE1_FORMAL_BOW_DIAGNOSIS",
            "V05_GATE1": result.verdict,
            "seedZip": "ai-aba.bow.zip",
            "seedZipSha256": zip_sha,
            "v04": "SEALED_READONLY",
            "v04Rc1Sha256": V04_RC1_SHA,
            "production": "NO-GO",
            "parameterHash": parameter_hash(),
            "next": status["next"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V05_GATE1": result.verdict,
                "parameterHash": parameter_hash(),
                "zipSha256": zip_sha,
                "fbxSha256": fbx_sha,
                "limitations": result.validation.get("limitations"),
                "hardFails": result.validation.get("hardFails"),
                "next": status["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
