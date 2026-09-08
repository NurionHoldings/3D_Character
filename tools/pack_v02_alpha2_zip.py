"""Pack v0.2.0-alpha.2 ZIP without modifying alpha.1 or v0.1 artifacts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
OUT_DIR = ROOT / "dist" / "v0.2"
ZIP_NAME = "NURION_Character_Landmarker_v0.2.0-alpha.2.zip"
ALPHA1_ZIP = OUT_DIR / "NURION_Character_Landmarker_v0.2.0-alpha.1.zip"
ALPHA1_SHA = "915bb5be9894086bdd344463a2fab27c74b4ad2ef016439ed4ca0e1b8be0dc01"
ALPHA2_LOCK = OUT_DIR / "alpha2" / "ALPHA2_LOCK.json"
ALPHA2_SHA = "357677285373514bc5ed6e7fa9c765b26651b59b0515df63c53a1a4b6d44a2d8"
V01_ZIP = ROOT / "dist" / "NURION_Character_Landmarker_v0.1.0.zip"
V01_SHA = "94585a4c8a0a0c055ffd51891e972b6e730de52eb11a262081fa57443ecb34a1"
SKIP = {"__pycache__", ".git", ".DS_Store"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def pack() -> Path:
    if ALPHA2_LOCK.exists():
        lock = json.loads(ALPHA2_LOCK.read_text(encoding="utf-8"))
        if lock.get("frozen"):
            raise RuntimeError(
                "alpha.2 is frozen (ALPHA2_LOCK.json). Do not repack; ship a new version path."
            )
    if ALPHA1_ZIP.exists() and sha256_file(ALPHA1_ZIP) != ALPHA1_SHA:
        raise RuntimeError("alpha.1 ZIP hash changed — refuse to pack alpha.2")
    if V01_ZIP.exists() and sha256_file(V01_ZIP) != V01_SHA:
        raise RuntimeError("v0.1 ZIP hash changed — refuse to pack alpha.2")

    init_text = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if "alpha.2" not in init_text:
        raise RuntimeError("Addon description must mention alpha.2")

    out = OUT_DIR / ZIP_NAME
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if sha256_file(out) == ALPHA2_SHA:
            raise RuntimeError("alpha.2 ZIP is locked — refuse overwrite")
        out.unlink()

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ADDON_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(ROOT)
            if any(p in SKIP or str(p).endswith(".pyc") for p in rel.parts):
                continue
            arc = Path("nurion_character_landmarker") / file_path.relative_to(ADDON_DIR)
            zf.write(file_path, arc.as_posix())

    names = zipfile.ZipFile(out).namelist()
    required = [
        "nurion_character_landmarker/core/joint_specific/wrist.py",
        "nurion_character_landmarker/core/joint_specific/shoulder.py",
        "nurion_character_landmarker/core/joint_specific/pelvis_hip.py",
        "nurion_character_landmarker/core/candidate_scoring.py",
    ]
    missing = [r for r in required if r not in names]
    if missing:
        raise RuntimeError(f"ZIP missing: {missing}")

    digest = sha256_file(out)
    manifest = {
        "package": ZIP_NAME,
        "version": "0.2.0-alpha.2",
        "sha256": digest,
        "entries": len(names),
        "alpha1Untouched": True,
        "alpha1Sha256": ALPHA1_SHA,
        "v01Untouched": True,
        "v01Sha256": V01_SHA,
    }
    (OUT_DIR / "alpha2" / "package-manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "alpha2" / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return out


if __name__ == "__main__":
    pack()
