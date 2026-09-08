"""
v0.5 Gate 5 — Mesh Penetration (clone-only, mesh BVH).

Usage:
  blender --background --python tools/blender_v05_gate5_mesh_penetration.py -- \\
    --fbx PATH --label ai-aba.bow
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
DEFAULT_OUT = ROOT / "dist" / "v0.5" / "gate5"
DEFAULT_FBX = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
DEFAULT_ZIP = ROOT / "dist/v0.5/gate1/inbox/ai-aba.bow.zip"
V04_RC1 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V04_RC1_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
GATE1_HASH = "b8bc827a8b10bf82365e0dfa6971feaf0c834a0e82c23f8b9174bbe4503296bb"
GATE2_HASH = "3e1cf159061c5eaaae44000cb82d2116135d4b3af8fae84098ddb45edf1c257f"
GATE3_HASH = "15f0a44037b9b2c1b6c4aedc3917eaaf4f26a69e8084df03d6e8e9ac90df8c57"
GATE4_HASH = "837fd79115113aa316671552d7fd4027f1e873e984c6d5ebc35239fd66e357ca"
ZIP_SHA = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
FBX_SHA = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_FBX))
    p.add_argument("--zip", default=str(DEFAULT_ZIP))
    p.add_argument("--label", default="ai-aba.bow")
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
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()


def main() -> int:
    args = _parse(sys.argv)
    fbx = Path(args.fbx)
    zpath = Path(args.zip)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    if not fbx.is_absolute():
        fbx = ROOT / fbx
    if not zpath.is_absolute():
        zpath = ROOT / zpath

    if _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("v0.4 RC.1 mutated — DENY")
    if not fbx.exists():
        raise FileNotFoundError(fbx)
    fbx_sha = _sha(fbx)
    zip_sha = _sha(zpath) if zpath.exists() else ""
    if fbx_sha != FBX_SHA:
        raise RuntimeError(f"source FBX hash mismatch: {fbx_sha}")
    if zpath.exists() and zip_sha != ZIP_SHA:
        raise RuntimeError(f"source ZIP hash mismatch: {zip_sha}")

    sys.path.insert(0, str(ROOT))
    from nurion_v05_body_motion.gate1.parameters import parameter_hash as g1_hash
    from nurion_v05_body_motion.gate2.parameters import parameter_hash as g2_hash
    from nurion_v05_body_motion.gate3.parameters import parameter_hash as g3_hash
    from nurion_v05_body_motion.gate4.parameters import parameter_hash as g4_hash
    from nurion_v05_body_motion.gate5.penetration import run_gate5
    from nurion_v05_body_motion.gate5.parameters import parameter_hash

    if g1_hash() != GATE1_HASH:
        raise RuntimeError("Gate1 parameter hash changed — DENY")
    if g2_hash() != GATE2_HASH:
        raise RuntimeError("Gate2 parameter hash changed — DENY")
    if g3_hash() != GATE3_HASH:
        raise RuntimeError("Gate3 parameter hash changed — DENY")
    if g4_hash() != GATE4_HASH:
        raise RuntimeError("Gate4 parameter hash changed — DENY")

    result = run_gate5(
        fbx_path=fbx,
        mesh_name=args.mesh if args.mesh else "",
        runs=args.runs,
        clean_import_cb=lambda: _clean_import(fbx),
    )

    if _sha(fbx) != FBX_SHA or (zpath.exists() and _sha(zpath) != ZIP_SHA):
        raise RuntimeError("source asset mutated during Gate5 — FAIL")

    _write(out_dir / "GATE5_PROFILE.json", result.profile)
    _write(out_dir / "GATE5_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V05_GATE5_STATUS",
        "gate": "5",
        "track": "v0.5 Body Motion Retarget & Rig Correction",
        "name": "MESH_PENETRATION",
        "V05_GATE5": result.verdict,
        "label": args.label,
        "parameterHash": parameter_hash(),
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "zipSha256": zip_sha or ZIP_SHA,
        "fbxSha256": fbx_sha,
        "v04Sealed": True,
        "v04Rc1Sha256": V04_RC1_SHA,
        "v04Mutation": "DENY",
        "sourceZipFbxMutation": "DENY",
        "sourceActionMutation": "DENY",
        "correctionTarget": "CLONE_ONLY",
        "footSlideResidualGate4": 11,
        "footSlideFix": "DENY_VERIFY_NO_WORSEN",
        "rightForeArmReCorrect": "DENY",
        "production": "NO-GO",
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "limitations": result.validation.get("limitations"),
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {"profile": "GATE5_PROFILE.json", "validation": "GATE5_VALIDATION.json"},
        "next": (
            "GATE6_CLONE_SAFE_CORRECTION_CANDIDATE"
            if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS")
            else "GATE5_FIX"
        ),
    }
    _write(out_dir / "V05_GATE5_STATUS.json", status)
    _write(DEFAULT_OUT / "V05_GATE5_LATEST.json", status)
    _write(
        ROOT / "dist/v0.5/STATUS.json",
        {
            "schema": "NURION_V0.5_STATUS",
            "track": "Body Motion Retarget & Rig Correction",
            "implementation": "GATE5_MESH_PENETRATION",
            "V05_GATE1": "PASS_WITH_LIMITATIONS",
            "V05_GATE2": "PASS_WITH_LIMITATIONS",
            "V05_GATE3": "PASS_WITH_LIMITATIONS",
            "V05_GATE4": "PASS_WITH_LIMITATIONS",
            "V05_GATE5": result.verdict,
            "gate1ParameterHash": GATE1_HASH,
            "gate2ParameterHash": GATE2_HASH,
            "gate3ParameterHash": GATE3_HASH,
            "gate4ParameterHash": GATE4_HASH,
            "gate5ParameterHash": parameter_hash(),
            "footSlideResidualGate4": 11,
            "footSlideDisposition": "VERIFY_NO_WORSEN_IN_GATE5",
            "seedZip": "ai-aba.bow.zip",
            "v04": "SEALED_READONLY",
            "production": "NO-GO",
            "next": status["next"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V05_GATE5": result.verdict,
                "parameterHash": parameter_hash(),
                "gates": result.validation.get("gates"),
                "fails": result.validation.get("fails"),
                "limitations": result.validation.get("limitations"),
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
