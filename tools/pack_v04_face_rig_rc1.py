"""Pack NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip after Gate8A PASS."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "dist" / "v0.4" / "gate8b" / "package"
ZIP_NAME = "NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
ADDON_NAME = "nurion_native_face_rig_lipsync"
SKIP = {"__pycache__", ".git", ".DS_Store"}

LOCK_FILES = [
    ROOT / "dist/v0.4/gate4/GATE4_BASELINE_LOCK.json",
    ROOT / "dist/v0.4/gate5b/GATE5_BASELINE_LOCK.json",
    ROOT / "dist/v0.4/gate6/GATE6_BASELINE_LOCK.json",
    ROOT / "dist/v0.4/gate6/GATE6_SUPPORTED_DOMAIN_REVIEW.json",
    ROOT / "dist/v0.4/gate7/GATE7_BASELINE_LOCK.json",
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


def _write_addon_init(addon_root: Path) -> None:
    (addon_root / "__init__.py").write_text(
        '''bl_info = {
    "name": "NURION Native Face Rig & Lip Sync v0.4 RC.1",
    "author": "NURION",
    "version": (0, 4, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > NURION v0.4",
    "description": "Limited-domain native face rig + offline lip sync (RC.1)",
    "category": "Animation",
}

import importlib
import sys
from pathlib import Path

_ADDON_DIR = Path(__file__).resolve().parent
if str(_ADDON_DIR) not in sys.path:
    sys.path.insert(0, str(_ADDON_DIR))


def register():
    # Engine modules are imported on demand by operators/tools.
    pass


def unregister():
    pass
''',
        encoding="utf-8",
    )
    (addon_root / "README.md").write_text(
        "# NURION Native Face Rig & Lip Sync v0.4.0-rc.1\n\n"
        "- Supported domain: LIMITED (Gate6 PASS_WITH_LIMITATIONS)\n"
        "- Human speech: offline WAV + transcript only\n"
        "- ASR / Microphone / Real-time: INACTIVE\n"
        "- Full unrestricted performance: HOLD\n"
        "- Human audio originals are NOT included; hashes/reports only\n"
        "- Holdout: WAITING (Tennis/Captain/hyerie excluded)\n"
        "- Final SEAL: HOLD\n",
        encoding="utf-8",
    )


def pack(*, validation_status: dict) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    staging = OUT_DIR / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    addon_root = staging / ADDON_NAME
    addon_root.mkdir(parents=True)
    _write_addon_init(addon_root)

    _copy_tree(ROOT / "nurion_v04_face_rig", addon_root / "nurion_v04_face_rig")
    _copy_tree(ROOT / "nurion_universal_eye", addon_root / "nurion_universal_eye")

    locks_dir = addon_root / "locks"
    locks_dir.mkdir(parents=True, exist_ok=True)
    for lf in LOCK_FILES:
        if lf.exists():
            shutil.copy2(lf, locks_dir / lf.name)

    # Reports / hashes only — never pack human WAV inbox
    reports = addon_root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    for rel in (
        "dist/v0.4/gate6/GATE6_DECISION.json",
        "dist/v0.4/gate6/HUMAN_SPEECH_MANIFEST.json",
        "dist/v0.4/gate8a/GATE8A_CROSS_ASSET_DECISION.json",
        "dist/v0.4/STATUS.json",
    ):
        src = ROOT / rel
        if src.exists():
            # scrub absolute local audio paths from manifest copy
            if src.name == "HUMAN_SPEECH_MANIFEST.json":
                doc = json.loads(src.read_text(encoding="utf-8"))
                for it in doc.get("items") or []:
                    it["audio"] = f"EXCLUDED/{Path(it.get('audio') or it.get('id')).name}"
                    it["audioPresentInPackage"] = False
                (reports / src.name).write_text(
                    json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
            else:
                shutil.copy2(src, reports / src.name)

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
            # hard deny audio
            if fp.suffix.lower() in {".wav", ".m4a", ".mp3", ".flac", ".aac"}:
                continue
            zf.write(fp, fp.relative_to(staging).as_posix())

    names = zipfile.ZipFile(out).namelist()
    required = [
        f"{ADDON_NAME}/__init__.py",
        f"{ADDON_NAME}/README.md",
        f"{ADDON_NAME}/VALIDATION_STATUS.json",
        f"{ADDON_NAME}/nurion_v04_face_rig/gate7/integration.py",
        f"{ADDON_NAME}/nurion_v04_face_rig/gate8a/regression.py",
        f"{ADDON_NAME}/nurion_universal_eye/gate6/beauty_integration.py",
    ]
    missing = [r for r in required if r not in names]
    if missing:
        raise RuntimeError(f"RC zip missing: {missing}")
    audio_leaks = [n for n in names if n.lower().endswith((".wav", ".m4a", ".mp3"))]
    if audio_leaks:
        raise RuntimeError(f"human audio leaked into package: {audio_leaks}")

    digest = sha256_file(out)
    manifest = {
        "schema": "NURION_V04_RC_PACKAGE_MANIFEST",
        "package": ZIP_NAME,
        "version": "0.4.0-rc.1",
        "sha256": digest,
        "sha256Length": 64,
        "entries": len(names),
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "humanSpeech": "PASS_WITH_LIMITATIONS",
        "sealed": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "excludeHumanAudio": True,
        "holdoutExcludedAssets": ["tennis", "captain", "hyerie"],
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    (OUT_DIR / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (OUT_DIR / "VALIDATION_STATUS.json").write_text(
        json.dumps(validation_status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out


if __name__ == "__main__":
    status = {
        "schema": "NURION_V04_RC1_VALIDATION_STATUS",
        "version": "0.4.0-rc.1",
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "humanSpeech": "PASS_WITH_LIMITATIONS",
        "sealed": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "gate8a": "PASS_REQUIRED",
        "packedAt": datetime.now(timezone.utc).isoformat(),
    }
    path = pack(validation_status=status)
    print(json.dumps({"package": str(path), "sha256": sha256_file(path)}, indent=2))
