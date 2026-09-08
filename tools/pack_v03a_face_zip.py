"""Pack v0.3.0-alpha.1 Face ZIP into dist/v0.3/face/ without touching v0.2 sealed artifacts."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
OUT_DIR = ROOT / "dist" / "v0.3" / "face"
ZIP_NAME = "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
V02_FINAL = ROOT / "dist" / "v0.2" / "final" / "NURION_Character_Landmarker_v0.2.0.zip"
V02_SHA = "679190e443d5814c6f7a7c41dcc7a62a52a0b02a6697e7485358d6a8853b02b2"
SKIP = {"__pycache__", ".git", ".DS_Store"}

REQUIRED = [
    "nurion_character_landmarker/core/face/parameters.py",
    "nurion_character_landmarker/core/face/correct.py",
    "nurion_character_landmarker/core/face/geometry_detect.py",
    "nurion_character_landmarker/core/face/multiview.py",
    "nurion_character_landmarker/core/face/region.py",
    "nurion_character_landmarker/core/face/gt_schema.py",
    "nurion_character_landmarker/evaluation/face_gt.py",
    "nurion_character_landmarker/rig/face_guide_builder.py",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _face_param_hash() -> str:
    import ast

    src = (ADDON_DIR / "core" / "face" / "parameters.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    params_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "FACE_ALPHA1_PARAMETERS":
                    params_node = node.value
    if params_node is None:
        raise RuntimeError("FACE_ALPHA1_PARAMETERS missing")
    params = ast.literal_eval(params_node)
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


ALPHA1_FROZEN_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"
ALPHA1_FROZEN_PARAM = "2bd812ee4be5c63ce1053cfa5023305e2c9a41fe021b4ca01153f7ab3f799095"
BASELINE_LOCK = OUT_DIR / "V0.3A_BASELINE_LOCK.json"


def pack() -> Path:
    if V02_FINAL.exists() and sha256_file(V02_FINAL) != V02_SHA:
        raise RuntimeError("v0.2 SEALED ZIP hash changed — refuse v0.3a pack")

    if BASELINE_LOCK.exists():
        lock = json.loads(BASELINE_LOCK.read_text(encoding="utf-8"))
        if lock.get("frozen"):
            raise RuntimeError(
                "v0.3.0-alpha.1 baseline is frozen (WAITING_FOR_FACE_GT). "
                "Do not repack until face GT evaluation completes."
            )

    init_text = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if "0.3.0-alpha.1" not in init_text and "v0.3.0-alpha.1" not in init_text:
        raise RuntimeError("Addon description must mention v0.3.0-alpha.1")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ZIP_NAME
    if out.exists():
        if sha256_file(out) == ALPHA1_FROZEN_SHA:
            raise RuntimeError("alpha.1 ZIP is frozen — refuse overwrite")
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
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        raise RuntimeError(f"ZIP missing: {missing}")

    digest = sha256_file(out)
    param_hash = _face_param_hash()
    manifest = {
        "package": ZIP_NAME,
        "version": "0.3.0-alpha.1",
        "track": "v0.3a",
        "sha256": digest,
        "sha256Length": 64,
        "parameterHash": param_hash,
        "parameterHashLength": 64,
        "entries": len(names),
        "v02SealedUntouched": True,
        "v02SealedSha256": V02_SHA,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
    }
    (OUT_DIR / "package-manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    return out


if __name__ == "__main__":
    pack()
