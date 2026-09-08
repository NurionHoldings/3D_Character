"""Pack NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip after Gate7A regression PASS."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_SRC = ROOT / "nurion_universal_eye_calibration"
ENGINE_SRC = ROOT / "nurion_universal_eye"
OUT_DIR = ROOT / "dist" / "v0.3" / "universal_eye" / "gate7a" / "package"
ZIP_NAME = "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
SKIP = {"__pycache__", ".git", ".DS_Store"}

LOCK_FILES = [
    ROOT / "dist/v0.3/universal_eye/gate2/GATE2_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate3/GATE3_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate4a/GATE4A_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate4b/GATE4B_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate5/GATE5_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate6/GATE6_BASELINE_LOCK.json",
    ROOT / "dist/v0.3/universal_eye/gate7a/GATE7A_BASELINE_LOCK.json",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".DS_Store"),
    )


def pack(*, validation_status: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUT_DIR / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    addon_root = staging / "nurion_universal_eye_calibration"
    _copy_tree(ADDON_SRC, addon_root)
    _copy_tree(ENGINE_SRC, addon_root / "nurion_universal_eye")

    locks_dir = addon_root / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    for lf in LOCK_FILES:
        if lf.exists():
            shutil.copy2(lf, locks_dir / lf.name)

    # Embed validation status + manifest into package
    (addon_root / "VALIDATION_STATUS.json").write_text(
        json.dumps(validation_status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    out = OUT_DIR / ZIP_NAME
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(addon_root.rglob("*")):
            if not fp.is_file():
                continue
            if any(p in SKIP or str(p).endswith(".pyc") for p in fp.relative_to(staging).parts):
                continue
            arc = fp.relative_to(staging).as_posix()
            zf.write(fp, arc)

    names = zipfile.ZipFile(out).namelist()
    required = [
        "nurion_universal_eye_calibration/__init__.py",
        "nurion_universal_eye_calibration/panel.py",
        "nurion_universal_eye_calibration/operators.py",
        "nurion_universal_eye_calibration/README.md",
        "nurion_universal_eye_calibration/VALIDATION_STATUS.json",
        "nurion_universal_eye_calibration/nurion_universal_eye/gate6/beauty_integration.py",
        "nurion_universal_eye_calibration/nurion_universal_eye/gate7a/integrated_regression.py",
    ]
    missing = [r for r in required if r not in names]
    if missing:
        raise RuntimeError(f"RC zip missing: {missing}")

    digest = sha256_file(out)
    manifest = {
        "schema": "NURION_UEC_PACKAGE_MANIFEST",
        "package": ZIP_NAME,
        "version": "0.3.0-rc.1",
        "sha256": digest,
        "sha256Length": 64,
        "entries": len(names),
        "releaseCandidate": True,
        "sealed": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "defaultPreset": "NATURAL",
        "selectablePresets": ["NATURAL", "LUMINOUS", "AI_PREMIUM"],
        "tiers": ["High", "Medium", "Low", "Fallback"],
        "includes": [
            "Gate1-6 runtime",
            "lock checks",
            "UI panel",
            "NATURAL default preset",
            "LUMINOUS/AI_PREMIUM selectable",
            "High/Medium/Low/Fallback tiers",
            "diagnostic/status export",
            "README",
            "Manifest",
            "Validation Status",
        ],
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "validationStatus": validation_status,
    }
    (addon_root / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    # Rebuild zip including MANIFEST
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(addon_root.rglob("*")):
            if not fp.is_file():
                continue
            if any(p in SKIP or str(p).endswith(".pyc") for p in fp.relative_to(staging).parts):
                continue
            zf.write(fp, fp.relative_to(staging).as_posix())
    digest = sha256_file(out)
    manifest["sha256"] = digest
    manifest["entries"] = len(zipfile.ZipFile(out).namelist())
    (OUT_DIR / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"package": str(out), "sha256": digest, "entries": manifest["entries"]}, indent=2))
    return out


if __name__ == "__main__":
    # Minimal status if run standalone
    pack(
        validation_status={
            "GATE7A": "UNKNOWN",
            "releaseCandidate": True,
            "sealed": False,
            "holdout": "WAITING",
        }
    )
