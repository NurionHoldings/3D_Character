"""Pack nurion_character_landmarker into an installable Blender add-on ZIP."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
DIST_DIR = ROOT / "dist"
ZIP_NAME = "NURION_Character_Landmarker_v0.1.0.zip"

SKIP_PARTS = {"__pycache__", ".git", ".DS_Store"}

REQUIRED_IN_ZIP = [
    "nurion_character_landmarker/__init__.py",
    "nurion_character_landmarker/examples/nurion-character-profile.json",
    "nurion_character_landmarker/reports/practical-smoke-report.json",
    "nurion_character_landmarker/reports/VALIDATION_STATUS.json",
]


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS or part.endswith(".pyc") for part in path.parts)


def _sync_root_example() -> None:
    """Keep repo-root examples/ mirrored into the installable package."""
    src = ROOT / "examples" / "nurion-character-profile.json"
    dst = ADDON_DIR / "examples" / "nurion-character-profile.json"
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _assert_bl_info_blender() -> None:
    init_text = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if '"blender": (5, 0, 0)' not in init_text and "'blender': (5, 0, 0)" not in init_text:
        raise RuntimeError('bl_info["blender"] must be (5, 0, 0) for the Blender 5.0.1 baseline')


def pack() -> Path:
    _sync_root_example()
    _assert_bl_info_blender()

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    out = DIST_DIR / ZIP_NAME
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ADDON_DIR.rglob("*")):
            if not file_path.is_file() or should_skip(file_path.relative_to(ROOT)):
                continue
            arcname = Path("nurion_character_landmarker") / file_path.relative_to(ADDON_DIR)
            zf.write(file_path, arcname.as_posix())

    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()

    missing = [item for item in REQUIRED_IN_ZIP if item not in names]
    if missing:
        raise RuntimeError("ZIP missing required entries: " + ", ".join(missing))

    # Mirror report into dist/ for external package review.
    report_src = ADDON_DIR / "reports" / "practical-smoke-report.json"
    shutil.copy2(report_src, DIST_DIR / "practical-smoke-report.json")
    shutil.copy2(ADDON_DIR / "reports" / "VALIDATION_STATUS.json", DIST_DIR / "VALIDATION_STATUS.json")

    manifest = {
        "zip": ZIP_NAME,
        "entries": len(names),
        "requiredPresent": REQUIRED_IN_ZIP,
        "sealStatus": "CANDIDATE_NOT_SEALED",
        "bl_info_blender": [5, 0, 0],
    }
    (DIST_DIR / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Created: {out}")
    print(f"Entries: {len(names)}")
    for item in REQUIRED_IN_ZIP:
        print(f"  OK {item}")
    return out


if __name__ == "__main__":
    pack()
