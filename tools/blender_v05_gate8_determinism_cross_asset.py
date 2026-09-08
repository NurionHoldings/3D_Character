"""
v0.5 Gate 8 — Determinism (8A) + Cross-Asset (8B).

Usage:
  blender --background --python tools/blender_v05_gate8_determinism_cross_asset.py -- \\
    --stage both --runs 3
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
DEFAULT_OUT = ROOT / "dist" / "v0.5" / "gate8"
DEFAULT_SEED_FBX = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
DEFAULT_SEED_ZIP = ROOT / "dist/v0.5/gate1/inbox/ai-aba.bow.zip"
V04_RC1 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V04_RC1_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
SEED_ZIP_SHA = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"

DEFAULT_CROSS = {
    "hyerie": ROOT / "hyerie_15.fbx",
    "captain": Path(r"D:\gaonsejong\assets\captain_character\captain_15.fbx"),
    "tennis": (
        ROOT
        / "assets/Meshy_AI_Monochrome_Tennis_Loo_biped/Meshy_AI_Monochrome_Tennis_Loo_biped"
        / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
    ),
}


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--stage", default="both", choices=["8a", "8b", "both"])
    p.add_argument("--fbx", default=str(DEFAULT_SEED_FBX))
    p.add_argument("--zip", default=str(DEFAULT_SEED_ZIP))
    p.add_argument("--label", default="ai-aba.bow")
    p.add_argument("--mesh", default="char1")
    p.add_argument("--hyerie-fbx", default=str(DEFAULT_CROSS["hyerie"]))
    p.add_argument("--captain-fbx", default=str(DEFAULT_CROSS["captain"]))
    p.add_argument("--tennis-fbx", default=str(DEFAULT_CROSS["tennis"]))
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
    out_root = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    if not out_root.is_absolute():
        out_root = ROOT / out_root

    seed_fbx = Path(args.fbx)
    seed_zip = Path(args.zip)
    if not seed_fbx.is_absolute():
        seed_fbx = ROOT / seed_fbx
    if not seed_zip.is_absolute():
        seed_zip = ROOT / seed_zip

    if _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("v0.4 RC.1 mutated — DENY")
    if args.stage in ("8a", "both"):
        if not seed_fbx.exists():
            raise FileNotFoundError(seed_fbx)
        if _sha(seed_fbx) != SEED_FBX_SHA:
            raise RuntimeError(f"seed FBX hash mismatch: {_sha(seed_fbx)}")
        if seed_zip.exists() and _sha(seed_zip) != SEED_ZIP_SHA:
            raise RuntimeError(f"seed ZIP hash mismatch: {_sha(seed_zip)}")

    sys.path.insert(0, str(ROOT))
    from nurion_v05_body_motion.gate8.cross_asset import combine_gate8_verdict, run_gate8b
    from nurion_v05_body_motion.gate8.parameters import parameter_hash
    from nurion_v05_body_motion.gate8.regression import run_gate8a

    verdict_8a = "SKIP"
    verdict_8b = "SKIP"
    result_8a = None
    result_8b = None

    if args.stage in ("8a", "both"):
        result_8a = run_gate8a(
            fbx_path=seed_fbx,
            mesh_name=args.mesh,
            runs=args.runs,
            clean_import_cb=lambda: _clean_import(seed_fbx),
            root=ROOT,
        )
        verdict_8a = result_8a.verdict
        a_dir = out_root / "8a" / args.label
        _write(a_dir / "GATE8A_REGRESSION_REPORT.json", result_8a.report)
        _write(a_dir / "GATE8A_VALIDATION.json", result_8a.validation)
        _write(
            a_dir / "V05_GATE8A_STATUS.json",
            {
                "schema": "NURION_V05_GATE8A_STATUS",
                "gate": "8A",
                "name": "FULL_DETERMINISM_REGRESSION",
                "V05_GATE8A": result_8a.verdict,
                "parameterHash": parameter_hash(),
                "gates": result_8a.validation.get("gates"),
                "fails": result_8a.validation.get("fails"),
                "limitations": result_8a.validation.get("limitations"),
                "intermediateOutputReuse": "DENY",
                "supportedDomain": "LIMITED",
                "production": "NO-GO",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "next": "GATE8B_CROSS_ASSET",
            },
        )
        if _sha(seed_fbx) != SEED_FBX_SHA or _sha(V04_RC1) != V04_RC1_SHA:
            raise RuntimeError("source/seal mutated during Gate8A — FAIL")

    if args.stage in ("8b", "both"):
        paths = {
            "hyerie": Path(args.hyerie_fbx),
            "captain": Path(args.captain_fbx),
            "tennis": Path(args.tennis_fbx),
        }
        result_8b = run_gate8b(
            asset_paths=paths,
            mesh_names={"hyerie": "char1", "captain": "char1", "tennis": "char1"},
            runs=args.runs,
            clean_import_factory=lambda fbx: (lambda f=fbx: _clean_import(f)),
            root=ROOT,
        )
        verdict_8b = result_8b.verdict
        b_dir = out_root / "8b"
        _write(b_dir / "GATE8B_CROSS_ASSET_REPORT.json", result_8b.report)
        _write(b_dir / "GATE8B_VALIDATION.json", result_8b.validation)
        _write(
            b_dir / "V05_GATE8B_STATUS.json",
            {
                "schema": "NURION_V05_GATE8B_STATUS",
                "gate": "8B",
                "name": "CROSS_ASSET_VALIDATION",
                "V05_GATE8B": result_8b.verdict,
                "parameterHash": parameter_hash(),
                "gates": result_8b.validation.get("gates"),
                "fails": result_8b.validation.get("fails"),
                "limitations": result_8b.validation.get("limitations"),
                "parameterTuning": 0,
                "manualCorrection": 0,
                "supportedDomain": "LIMITED",
                "production": "NO-GO",
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "next": "RC_CANDIDATE_PACKAGING",
            },
        )
        if _sha(V04_RC1) != V04_RC1_SHA:
            raise RuntimeError("v0.4 RC.1 mutated during Gate8B — FAIL")

    if args.stage == "8a":
        overall = verdict_8a
    elif args.stage == "8b":
        overall = verdict_8b
    else:
        overall = combine_gate8_verdict(verdict_8a, verdict_8b)

    status = {
        "schema": "NURION_V05_GATE8_STATUS",
        "gate": "8",
        "track": "v0.5 Body Motion Retarget & Rig Correction",
        "name": "DETERMINISM_CROSS_ASSET",
        "V05_GATE8": overall,
        "V05_GATE8A": verdict_8a,
        "V05_GATE8B": verdict_8b,
        "parameterHash": parameter_hash(),
        "intermediateOutputReuse": "DENY",
        "parameterTuning": 0,
        "manualCorrection": 0,
        "v04Sealed": True,
        "v04Mutation": "DENY",
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "inheritedLimitations": [
            "FOOT_SLIDE_RESIDUAL_11",
            "SHALLOW_SUSTAINED_CONTACT_ACCEPTED",
            "GATE3_REVERSE_FOREARM_MILD_PRESERVED",
        ],
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "next": (
            "RC_CANDIDATE_PACKAGING"
            if overall in ("PASS", "PASS_WITH_LIMITATIONS", "CROSS_ASSET_LIMITED")
            else "GATE8_FIX"
        ),
    }
    if result_8a is not None:
        status["gate8aFails"] = result_8a.validation.get("fails")
        status["gate8aLimitations"] = result_8a.validation.get("limitations")
    if result_8b is not None:
        status["gate8bFails"] = result_8b.validation.get("fails")
        status["gate8bLimitations"] = result_8b.validation.get("limitations")
        status["crossAssets"] = {
            a["label"]: {"verdict": a["verdict"], "fails": a.get("fails"), "slides": (a.get("bodyTypeDependency") or {}).get("slidesFinal")}
            for a in result_8b.report.get("assets") or []
        }

    _write(out_root / "V05_GATE8_STATUS.json", status)
    _write(DEFAULT_OUT / "V05_GATE8_LATEST.json", status)
    _write(
        ROOT / "dist/v0.5/STATUS.json",
        {
            "schema": "NURION_V0.5_STATUS",
            "track": "Body Motion Retarget & Rig Correction",
            "implementation": "GATE8_DETERMINISM_CROSS_ASSET",
            "V05_GATE1": "PASS_WITH_LIMITATIONS",
            "V05_GATE2": "PASS_WITH_LIMITATIONS",
            "V05_GATE3": "PASS_WITH_LIMITATIONS",
            "V05_GATE4": "PASS_WITH_LIMITATIONS",
            "V05_GATE5": "PASS_WITH_LIMITATIONS",
            "V05_GATE6": "PASS_WITH_LIMITATIONS",
            "V05_GATE7": "PASS_WITH_LIMITATIONS",
            "V05_GATE8": overall,
            "V05_GATE8A": verdict_8a,
            "V05_GATE8B": verdict_8b,
            "gate8ParameterHash": parameter_hash(),
            "v04": "SEALED_READONLY",
            "supportedDomain": "LIMITED",
            "production": "NO-GO",
            "next": status["next"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V05_GATE8": overall,
                "V05_GATE8A": verdict_8a,
                "V05_GATE8B": verdict_8b,
                "parameterHash": parameter_hash(),
                "gate8aFails": status.get("gate8aFails"),
                "gate8bFails": status.get("gate8bFails"),
                "crossAssets": status.get("crossAssets"),
                "next": status["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if overall in ("PASS", "PASS_WITH_LIMITATIONS", "CROSS_ASSET_LIMITED") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
