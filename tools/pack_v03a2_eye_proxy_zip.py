"""Pack v0.3.0-alpha.2 Eye Proxy ZIP. Does not touch frozen Alpha1 ZIP."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
OUT_DIR = ROOT / "dist" / "v0.3" / "face" / "alpha2"
ZIP_NAME = "NURION_Character_Landmarker_v0.3.0-alpha.2.zip"
ALPHA1_ZIP = ROOT / "dist" / "v0.3" / "face" / "NURION_Character_Landmarker_v0.3.0-alpha.1.zip"
ALPHA1_SHA = "b50ce235bd0f93ec97be64cd803e16964c7b293f33b06b8fa0cd2b7e4b3f168f"
V02_SHA = "679190e443d5814c6f7a7c41dcc7a62a52a0b02a6697e7485358d6a8853b02b2"
V02_ZIP = ROOT / "dist" / "v0.2" / "final" / "NURION_Character_Landmarker_v0.2.0.zip"
SKIP = {"__pycache__", ".git", ".DS_Store"}

REQUIRED = [
    "nurion_character_landmarker/core/face/eye_proxy.py",
    "nurion_character_landmarker/core/face/procedural_eyeball.py",
    "nurion_character_landmarker/core/face/eye_proxy_pipeline.py",
    "nurion_character_landmarker/core/face/parameters_alpha2.py",
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _param_hash() -> str:
    import ast

    src = (ADDON_DIR / "core" / "face" / "parameters_alpha2.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    node = None
    for n in tree.body:
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == "FACE_ALPHA2_PARAMETERS":
                    node = n.value
    params = ast.literal_eval(node)
    return hashlib.sha256(json.dumps(params, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


ALPHA2_FROZEN_SHA = "1fcafa0fdc99cff4f0925fcc1744bee49d7d98b1072174e00e44d98f2f507530"
ALPHA2_FROZEN_PARAM = "1a1fc8ab52a43d29c738c579596395443fcb5c4db26c287d4b639ae1793a8605"
BASELINE_LOCK = OUT_DIR / "V0.3A2_BASELINE_LOCK.json"


def pack() -> Path:
    if ALPHA1_ZIP.exists() and sha256_file(ALPHA1_ZIP) != ALPHA1_SHA:
        raise RuntimeError("Frozen Alpha1 ZIP changed — refuse alpha.2 pack")
    if V02_ZIP.exists() and sha256_file(V02_ZIP) != V02_SHA:
        raise RuntimeError("v0.2 SEALED ZIP changed — refuse alpha.2 pack")
    if BASELINE_LOCK.exists():
        lock = json.loads(BASELINE_LOCK.read_text(encoding="utf-8"))
        if lock.get("frozen"):
            raise RuntimeError(
                "v0.3.0-alpha.2 baseline is frozen (WAITING_FOR_SURFACE_GT). "
                "Do not repack until surface GT evaluation completes."
            )
    init = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if "0.3.0-alpha.2" not in init and "v0.3.0-alpha.2" not in init:
        raise RuntimeError("bl_info must mention v0.3.0-alpha.2")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / ZIP_NAME
    if out.exists():
        if sha256_file(out) == ALPHA2_FROZEN_SHA:
            raise RuntimeError("alpha.2 ZIP is frozen — refuse overwrite")
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(ADDON_DIR.rglob("*")):
            if not fp.is_file():
                continue
            rel = fp.relative_to(ROOT)
            if any(p in SKIP or str(p).endswith(".pyc") for p in rel.parts):
                continue
            arc = Path("nurion_character_landmarker") / fp.relative_to(ADDON_DIR)
            zf.write(fp, arc.as_posix())
    names = zipfile.ZipFile(out).namelist()
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        raise RuntimeError(f"missing {missing}")
    digest = sha256_file(out)
    ph = _param_hash()
    manifest = {
        "package": ZIP_NAME,
        "version": "0.3.0-alpha.2",
        "track": "v0.3a-MESHY_EYE_PROXY",
        "sha256": digest,
        "parameterHash": ph,
        "sha256Length": 64,
        "parameterHashLength": 64,
        "entries": len(names),
        "alpha1FrozenUntouched": True,
        "alpha1Sha256": ALPHA1_SHA,
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
