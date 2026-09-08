"""Lock Alpha2 10-point surface GT with complete evaluation evidence hashes.

Records:
  - Original Tennis FBX SHA-256
  - Annotated .blend SHA-256
  - Surface GT JSON SHA-256
  - GT Export script SHA-256
  - Alpha2 ZIP + Parameter SHA-256

Usage:
  py -3 tools/make_face_surface_gt_lock.py \\
    dist/v0.3/face/alpha2/annotations/face-surface-gt.json \\
    --fbx "assets/.../Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx" \\
    --blend dist/v0.3/face/alpha2/annotations/tennis-surface-gt-edit.blend
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACE_KEYS = {
    "eye.inner.L", "eye.inner.R",
    "eye.outer.L", "eye.outer.R",
    "eyelid.upper.L", "eyelid.upper.R",
    "eyelid.lower.L", "eyelid.lower.R",
    "iris.visualCenter.L", "iris.visualCenter.R",
}
ALPHA2_ZIP_SHA = "1fcafa0fdc99cff4f0925fcc1744bee49d7d98b1072174e00e44d98f2f507530"
ALPHA2_PARAM = "1a1fc8ab52a43d29c738c579596395443fcb5c4db26c287d4b639ae1793a8605"
EXPECTED_TENNIS_FBX_SHA = "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d"
DEFAULT_TENNIS_FBX = (
    ROOT
    / "assets"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped"
    / "Meshy_AI_Monochrome_Tennis_Loo_biped_Animation_Walking_withSkin.fbx"
)
DEFAULT_BLEND = ROOT / "dist" / "v0.3" / "face" / "alpha2" / "annotations" / "tennis-surface-gt-edit.blend"
EXPORT_SCRIPT = ROOT / "tools" / "blender_export_surface_gt.py"
ALPHA2_ZIP = ROOT / "dist" / "v0.3" / "face" / "alpha2" / "NURION_Character_Landmarker_v0.3.0-alpha.2.zip"
REQUIRED_BIND = (
    "faceIndex",
    "triangleVertices",
    "barycentric",
    "uv",
    "positionWorld",
    "positionHeadLocal",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("gt_json", type=Path)
    p.add_argument("--fbx", type=Path, default=DEFAULT_TENNIS_FBX, help="Original Tennis FBX")
    p.add_argument("--blend", type=Path, default=DEFAULT_BLEND, help="Annotated .blend")
    p.add_argument("--allow-fbx-mismatch", action="store_true", help="Allow non-canonical Tennis FBX SHA")
    args = p.parse_args()

    gt = args.gt_json if args.gt_json.is_absolute() else ROOT / args.gt_json
    fbx = args.fbx if args.fbx.is_absolute() else ROOT / args.fbx
    blend = args.blend if args.blend.is_absolute() else ROOT / args.blend

    for path, label in ((gt, "gt_json"), (fbx, "fbx"), (blend, "blend"), (EXPORT_SCRIPT, "export_script"), (ALPHA2_ZIP, "alpha2_zip")):
        if not path.exists():
            raise SystemExit(f"Missing {label}: {path}")

    doc = json.loads(gt.read_text(encoding="utf-8"))
    annotated = []
    invalid = []
    for e in doc.get("landmarks", []):
        if e.get("name") not in SURFACE_KEYS or not e.get("annotated"):
            continue
        miss = [f for f in REQUIRED_BIND if e.get(f) is None]
        if e.get("predictionHidden") is not True:
            miss.append("predictionHidden!=true")
        if e.get("snapToPrediction") is not False:
            miss.append("snapToPrediction!=false")
        if miss:
            invalid.append({"name": e.get("name"), "fields": miss})
            continue
        annotated.append(e)

    if invalid:
        raise SystemExit(f"SURFACE_GT_INVALID binding fields: {json.dumps(invalid, ensure_ascii=False)}")
    if len(annotated) != 10:
        raise SystemExit(f"Need 10 annotated surface landmarks, found {len(annotated)}")

    gt_sha = sha256_file(gt)
    fbx_sha = sha256_file(fbx)
    blend_sha = sha256_file(blend)
    export_sha = sha256_file(EXPORT_SCRIPT)
    zip_sha = sha256_file(ALPHA2_ZIP)

    if zip_sha != ALPHA2_ZIP_SHA:
        raise SystemExit(f"Alpha2 ZIP hash mismatch: got {zip_sha}, expected {ALPHA2_ZIP_SHA}")
    if fbx_sha != EXPECTED_TENNIS_FBX_SHA and not args.allow_fbx_mismatch:
        raise SystemExit(
            f"Tennis FBX hash mismatch: got {fbx_sha}, expected {EXPECTED_TENNIS_FBX_SHA}. "
            "Pass --allow-fbx-mismatch only for intentional alternate assets."
        )

    lock = {
        "schema": "NURION_FACE_SURFACE_GT_LOCK",
        "version": "0.3.0-alpha.2",
        "gtFile": str(gt.relative_to(ROOT)).replace("\\", "/") if gt.is_relative_to(ROOT) else str(gt),
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "evidenceHashes": {
            "tennisFbxSha256": fbx_sha,
            "annotatedBlendSha256": blend_sha,
            "surfaceGtJsonSha256": gt_sha,
            "gtExportScriptSha256": export_sha,
            "alpha2ZipSha256": zip_sha,
            "alpha2ParameterHash": ALPHA2_PARAM,
        },
        "paths": {
            "tennisFbx": str(fbx.relative_to(ROOT)).replace("\\", "/") if fbx.is_relative_to(ROOT) else str(fbx),
            "annotatedBlend": str(blend.relative_to(ROOT)).replace("\\", "/") if blend.is_relative_to(ROOT) else str(blend),
            "gtExportScript": "tools/blender_export_surface_gt.py",
            "alpha2Zip": "dist/v0.3/face/alpha2/NURION_Character_Landmarker_v0.3.0-alpha.2.zip",
        },
        "sha256": gt_sha,
        "sha256Length": 64,
        "landmarkCount": len(annotated),
        "surfaceBoundCount": len(annotated),
        "coordinateSpaces": ["WORLD", "HEAD_LOCAL", "MESH_SURFACE", "UV"],
        "predictionHiddenDuringAnnotation": bool(doc.get("predictionHiddenDuringAnnotation", True)),
        "snapToPrediction": bool(doc.get("snapToPrediction", False)),
        "eyeballsHiddenDuringAnnotation": bool(doc.get("eyeballsHiddenDuringAnnotation", True)),
        "frozen": True,
        "alpha2FrozenUnchanged": True,
        "keys": sorted(SURFACE_KEYS),
        "note": (
            "Complete eval evidence lock. Do not edit GT/blend after lock without new version. "
            "iris.visualCenter is texture visual center on surface."
        ),
    }
    out = gt.with_name("face-surface-gt.lock.json") if gt.name.endswith("face-surface-gt.json") else gt.with_name(gt.stem + ".lock.json")
    out.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(lock, indent=2, ensure_ascii=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
