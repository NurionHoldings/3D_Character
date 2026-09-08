"""
v0.5 Gate 9 — RC Packaging & Reinstall Smoke.

Usage:
  blender --background --python tools/blender_v05_gate9_rc_reinstall_smoke.py -- \\
    --runs 3
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.5" / "gate9"
DEFAULT_FBX = (
    ROOT
    / "dist/v0.5/gate1/ai-aba.bow/_extract/Meshy_AI_Silver_Starlight_Sent_biped"
    / "Meshy_AI_Silver_Starlight_Sent_biped_Animation_Formal_Bow_withSkin.fbx"
)
DEFAULT_ZIP_SEED = ROOT / "dist/v0.5/gate1/inbox/ai-aba.bow.zip"
V04_RC1 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V04_RC1_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
SEED_ZIP_SHA = "5452791b581b359b512f4f35ce90f3dadf2307dda07b2736c0f5b7b20e9f4309"
SEED_FBX_SHA = "247bf90331b657de2b266091aa5f776964f55263106de20fdc878024598e395f"


def _parse(argv):
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", default=str(DEFAULT_FBX))
    p.add_argument("--seed-zip", default=str(DEFAULT_ZIP_SEED))
    p.add_argument("--mesh", default="char1")
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--skip-pack", action="store_true")
    p.add_argument("--package", default="")
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


def main() -> int:
    args = _parse(sys.argv)
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    fbx = Path(args.fbx)
    seed_zip = Path(args.seed_zip)
    if not fbx.is_absolute():
        fbx = ROOT / fbx
    if not seed_zip.is_absolute():
        seed_zip = ROOT / seed_zip

    if _sha(V04_RC1) != V04_RC1_SHA:
        raise RuntimeError("v0.4 RC.1 mutated — DENY")
    if _sha(fbx) != SEED_FBX_SHA:
        raise RuntimeError(f"seed FBX hash mismatch: {_sha(fbx)}")
    if seed_zip.exists() and _sha(seed_zip) != SEED_ZIP_SHA:
        raise RuntimeError(f"seed ZIP hash mismatch: {_sha(seed_zip)}")

    sys.path.insert(0, str(ROOT))
    from nurion_v05_body_motion.gate9.packaging import pack_rc1
    from nurion_v05_body_motion.gate9.parameters import (
        INHERITED_LIMITATIONS,
        PACKAGE_NAME,
        VERSION,
        parameter_hash,
    )
    from nurion_v05_body_motion.gate9.reinstall_smoke import run_gate9_reinstall_smoke

    pkg_dir = out_dir / "package"
    if args.package:
        zip_path = Path(args.package)
        if not zip_path.is_absolute():
            zip_path = ROOT / zip_path
        if not zip_path.exists():
            raise FileNotFoundError(zip_path)
        # still refresh validation sidecar if packing skipped
        manifest_path = pkg_dir / "PACKAGE_MANIFEST.json"
        if not args.skip_pack and not zip_path.exists():
            pass
    else:
        validation_pre = {
            "schema": "NURION_V05_RC1_VALIDATION_STATUS",
            "version": VERSION,
            "releaseCandidate": True,
            "supportedDomain": "LIMITED",
            "production": "NO-GO",
            "sealed": False,
            "SEALED": False,
            "holdout": "WAITING",
            "finalSeal": "HOLD",
            "repack": "DENY",
            "parameterTuning": 0,
            "manualCorrection": 0,
            "inheritedLimitations": INHERITED_LIMITATIONS,
            "gate1to8ParameterChange": 0,
            "packedAt": datetime.now(timezone.utc).isoformat(),
        }
        zip_path, _manifest = pack_rc1(root=ROOT, out_dir=pkg_dir, validation_status=validation_pre)

    pkg_sha = _sha(zip_path)
    result = run_gate9_reinstall_smoke(
        zip_path=zip_path,
        fbx_path=fbx,
        workspace_root=ROOT,
        mesh_name=args.mesh,
        runs=args.runs,
    )

    if _sha(V04_RC1) != V04_RC1_SHA or _sha(fbx) != SEED_FBX_SHA or _sha(zip_path) != pkg_sha:
        raise RuntimeError("source/seal/RC zip mutated during Gate9 — FAIL")

    # Freeze RC baseline (sealed=false, repack deny)
    freeze = {
        "schema": "NURION_V05_RC1_BASELINE_FREEZE",
        "package": PACKAGE_NAME,
        "packagePath": str(zip_path.relative_to(ROOT)).replace("\\", "/"),
        "sha256": pkg_sha,
        "sha256Length": 64,
        "status": "FROZEN_RC_NOT_SEALED",
        "repack": "DENY",
        "parameterTuning": "DENY",
        "manualCorrection": "DENY",
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "reinstallSmoke": result.verdict,
        "gate9ParameterHash": parameter_hash(),
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "note": "RC.1 frozen for Fresh Holdout. Do not repack. Do not seal. Submit unused Meshy Rigged+WithSkin original ZIP.",
        "frozenAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(pkg_dir / "RC1_BASELINE_FREEZE.json", freeze)
    _write(out_dir / "GATE9_REINSTALL_SMOKE_REPORT.json", result.report)
    _write(out_dir / "GATE9_VALIDATION.json", result.validation)

    # Update package VALIDATION_STATUS with smoke outcome (sidecar only — do NOT repack ZIP)
    val_path = pkg_dir / "VALIDATION_STATUS.json"
    validation_doc = {
        "schema": "NURION_V05_RC1_VALIDATION_STATUS",
        "version": VERSION,
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "repack": "DENY",
        "packageSha256": pkg_sha,
        "reinstallSmoke": result.verdict,
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "parameterTuning": 0,
        "manualCorrection": 0,
        "gate1to8ParameterChange": 0,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "next": "FRESH_HOLDOUT",
    }
    _write(val_path, validation_doc)
    # Refresh manifest sha (must match frozen zip; do not rewrite zip)
    man_path = pkg_dir / "PACKAGE_MANIFEST.json"
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        man["sha256"] = pkg_sha
        man["sealed"] = False
        man["SEALED"] = False
        man["inheritedLimitations"] = INHERITED_LIMITATIONS
        man["reinstallSmoke"] = result.verdict
        _write(man_path, man)

    status = {
        "schema": "NURION_V05_GATE9_STATUS",
        "gate": "9",
        "track": "v0.5 Body Motion Retarget & Rig Correction",
        "name": "RC_PACKAGING_REINSTALL_SMOKE",
        "V05_GATE9": result.verdict,
        "parameterHash": parameter_hash(),
        "package": PACKAGE_NAME,
        "packageSha256": pkg_sha,
        "repack": "DENY",
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "limitations": result.validation.get("limitations"),
        "notes": result.notes,
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "next": "FRESH_HOLDOUT" if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else "GATE9_FIX",
    }
    _write(out_dir / "V05_GATE9_STATUS.json", status)
    _write(DEFAULT_OUT / "V05_GATE9_LATEST.json", status)
    _write(
        ROOT / "dist/v0.5/STATUS.json",
        {
            "schema": "NURION_V0.5_STATUS",
            "track": "Body Motion Retarget & Rig Correction",
            "implementation": "GATE9_RC_PACKAGING_REINSTALL_SMOKE",
            "V05_GATE1": "PASS_WITH_LIMITATIONS",
            "V05_GATE2": "PASS_WITH_LIMITATIONS",
            "V05_GATE3": "PASS_WITH_LIMITATIONS",
            "V05_GATE4": "PASS_WITH_LIMITATIONS",
            "V05_GATE5": "PASS_WITH_LIMITATIONS",
            "V05_GATE6": "PASS_WITH_LIMITATIONS",
            "V05_GATE7": "PASS_WITH_LIMITATIONS",
            "V05_GATE8": "PASS_WITH_LIMITATIONS",
            "V05_GATE9": result.verdict,
            "gate9ParameterHash": parameter_hash(),
            "rc1Package": PACKAGE_NAME,
            "rc1Sha256": pkg_sha,
            "repack": "DENY",
            "sealed": False,
            "SEALED": False,
            "v04": "SEALED_READONLY",
            "supportedDomain": "LIMITED",
            "production": "NO-GO",
            "inheritedLimitations": INHERITED_LIMITATIONS,
            "next": status["next"],
            "updatedAt": datetime.now(timezone.utc).isoformat(),
        },
    )

    print(
        json.dumps(
            {
                "V05_GATE9": result.verdict,
                "parameterHash": parameter_hash(),
                "package": PACKAGE_NAME,
                "packageSha256": pkg_sha,
                "sealed": False,
                "supportedDomain": "LIMITED",
                "production": "NO-GO",
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
