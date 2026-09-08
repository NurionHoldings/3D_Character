"""
Stage hyerie Holdout evaluation ZIP (path remap only — no byte edits).

Geometry/Rig = hyerie_15(1).fbx
Material     = Meshy texture ZIP Base Color → Animation_Idle_15_withSkin.fbm/texture_0.png

Usage:
  py -3 tools/stage_hyerie_holdout.py --fbx PATH/hyerie_15(1).fbx --texture-zip PATH/…_texture_fbx.zip
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.3" / "universal_eye" / "gate7b" / "hyerie_holdout_staging"

EXPECTED_FBX = "62b466495050ba2058398b7ebc5106c548ae76eab4df39ceb3e7d2f817d2973c"
EXPECTED_TEX_ZIP = "2f92d6b3dec96c4f940d8642e749ea52e661b11e6f770a7cf8aad424ba5a5949"
EXPECTED_BASECOLOR = "2c5b978689a4442d9138ff35b75f08d2bec9f41c17b5206a71593d45f3f4cc61"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def find_base_color(zf: zipfile.ZipFile) -> tuple[str, bytes]:
    # Prefer exact expected hash; else name heuristics
    candidates = []
    for name in zf.namelist():
        if name.endswith("/") or not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        data = zf.read(name)
        digest = sha256_bytes(data)
        low = name.lower().replace("\\", "/")
        score = 0
        if digest == EXPECTED_BASECOLOR:
            score += 1000
        if "basecolor" in low or "base_color" in low or "base colour" in low:
            score += 100
        if "albedo" in low or "diffuse" in low:
            score += 50
        candidates.append((score, name, data, digest))
    if not candidates:
        raise RuntimeError("No texture images in ZIP")
    candidates.sort(key=lambda x: (-x[0], x[1]))
    score, name, data, digest = candidates[0]
    if digest != EXPECTED_BASECOLOR:
        raise RuntimeError(f"Base Color SHA mismatch: {digest} != {EXPECTED_BASECOLOR} (picked {name})")
    return name, data


def stage(*, fbx: Path, texture_zip: Path, out_dir: Path) -> Path:
    fbx = Path(fbx)
    texture_zip = Path(texture_zip)
    out_dir = Path(out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    staging = out_dir / "hyerie_holdout"
    fbm = staging / "Animation_Idle_15_withSkin.fbm"
    fbm.mkdir(parents=True, exist_ok=True)

    fbx_sha = sha256_file(fbx)
    zip_sha = sha256_file(texture_zip)
    if fbx_sha != EXPECTED_FBX:
        raise RuntimeError(f"FBX SHA mismatch: {fbx_sha}")
    if zip_sha != EXPECTED_TEX_ZIP:
        raise RuntimeError(f"Texture ZIP SHA mismatch: {zip_sha}")

    dest_fbx = staging / "hyerie_15.fbx"
    shutil.copyfile(fbx, dest_fbx)
    if sha256_file(dest_fbx) != fbx_sha:
        raise RuntimeError("FBX copy altered bytes")

    with zipfile.ZipFile(texture_zip, "r") as zf:
        src_name, png_bytes = find_base_color(zf)
    dest_png = fbm / "texture_0.png"
    dest_png.write_bytes(png_bytes)
    png_sha = sha256_file(dest_png)
    if png_sha != EXPECTED_BASECOLOR:
        raise RuntimeError("PNG write altered bytes")

    receipt = {
        "schema": "NURION_GATE7B_PATH_REMAP_RECEIPT",
        "characterId": "hyerie",
        "operation": "PATH_REMAP_ONLY",
        "byteEdit": False,
        "manualGeometryCorrection": 0,
        "parameterTuning": 0,
        "geometryRig": {
            "sourceFile": fbx.name,
            "stagedAs": "hyerie_15.fbx",
            "sha256": fbx_sha,
        },
        "material": {
            "sourceZip": texture_zip.name,
            "sourceZipSha256": zip_sha,
            "sourceEntry": src_name,
            "sourceEntrySha256": png_sha,
            "stagedAs": "Animation_Idle_15_withSkin.fbm/texture_0.png",
            "stagedSha256": png_sha,
            "identityCopy": png_sha == EXPECTED_BASECOLOR,
        },
        "ailawfriendSeparated": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    (staging / "PATH_REMAP_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "PATH_REMAP_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    eval_zip = out_dir / "hyerie_holdout_eval.zip"
    if eval_zip.exists():
        eval_zip.unlink()
    with zipfile.ZipFile(eval_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(staging.rglob("*")):
            if fp.is_file():
                zf.write(fp, fp.relative_to(staging).as_posix())

    manifest = {
        "schema": "NURION_GATE7B_STAGED_EVAL_ZIP",
        "evalZip": str(eval_zip).replace("\\", "/"),
        "evalZipSha256": sha256_file(eval_zip),
        "receipt": receipt,
        "structure": [
            "hyerie_15.fbx",
            "Animation_Idle_15_withSkin.fbm/texture_0.png",
            "PATH_REMAP_RECEIPT.json",
        ],
        "submission": "COMPLETE_FOR_STAGING",
        "gate7b": "READY_TO_RUN",
        "sealed": False,
    }
    (out_dir / "STAGING_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"evalZip": str(eval_zip), "evalZipSha256": manifest["evalZipSha256"]}, indent=2))
    return eval_zip


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fbx", required=True)
    p.add_argument("--texture-zip", required=True)
    p.add_argument("--out-dir", default=str(OUT))
    args = p.parse_args()
    stage(fbx=Path(args.fbx), texture_zip=Path(args.texture_zip), out_dir=Path(args.out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
