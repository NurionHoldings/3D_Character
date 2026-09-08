"""Pack NURION Character Landmarker v0.2.0-alpha.1 ZIP (never touches v0.1 package)."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
OUT_DIR = ROOT / "dist" / "v0.2"
ZIP_NAME = "NURION_Character_Landmarker_v0.2.0-alpha.1.zip"
V01_ZIP = ROOT / "dist" / "NURION_Character_Landmarker_v0.1.0.zip"
V01_SHA = "94585a4c8a0a0c055ffd51891e972b6e730de52eb11a262081fa57443ecb34a1"

SKIP_PARTS = {"__pycache__", ".git", ".DS_Store"}


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS or part.endswith(".pyc") for part in path.parts)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pack() -> Path:
    if V01_ZIP.exists():
        current = sha256_file(V01_ZIP)
        if current != V01_SHA:
            raise RuntimeError(f"v0.1 ZIP hash changed unexpectedly: {current}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ZIP_NAME
    if out.exists():
        out.unlink()

    init_text = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if '"version": (0, 2, 0)' not in init_text:
        raise RuntimeError("Addon version must be (0, 2, 0) for v0.2.0-alpha.1 pack")

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ADDON_DIR.rglob("*")):
            if not file_path.is_file() or should_skip(file_path.relative_to(ROOT)):
                continue
            arcname = Path("nurion_character_landmarker") / file_path.relative_to(ADDON_DIR)
            zf.write(file_path, arcname.as_posix())

    with zipfile.ZipFile(out, "r") as zf:
        names = zf.namelist()
    if "nurion_character_landmarker/__init__.py" not in names:
        raise RuntimeError("Invalid ZIP structure")
    if "nurion_character_landmarker/core/geometry_correction.py" not in names:
        raise RuntimeError("ZIP missing geometry_correction.py")

    digest = sha256_file(out)
    manifest = {
        "package": ZIP_NAME,
        "version": "0.2.0-alpha.1",
        "sha256": digest,
        "entries": len(names),
        "v01PackageUntouched": True,
        "v01Sha256": V01_SHA,
    }
    (OUT_DIR / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return out


if __name__ == "__main__":
    pack()
