"""Build v0.5 RC.1 ZIP: runtime + integrated-candidate evidence only."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    ADDON_MODULE,
    GATE1_FROZEN,
    GATE2_FROZEN,
    GATE3_FROZEN,
    GATE4_FROZEN,
    GATE5_FROZEN,
    GATE6_FROZEN,
    GATE7_FROZEN,
    GATE8_FROZEN,
    GATE9_PARAMETERS,
    INHERITED_LIMITATIONS,
    PACKAGE_NAME,
    V04_GATE7_FROZEN,
    V04_RC1_SHA256,
    VERSION,
    parameter_hash,
)

SKIP_DIR = {"__pycache__", ".git", ".DS_Store"}
FORBIDDEN_SUFFIX = {".fbx", ".zip", ".wav", ".m4a", ".mp3", ".flac", ".aac", ".blend", ".png", ".jpg", ".jpeg"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_parameter_hash(module_file: Path):
    """Load parameter_hash() without importing package __init__ (avoids mathutils outside Blender)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(f"_nurion_param_{module_file.stem}", module_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {module_file}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.parameter_hash()


def verify_frozen_hashes(root: Path) -> Dict:
    root = Path(root)
    pairs = [
        ("gate1", root / "nurion_v05_body_motion/gate1/parameters.py", GATE1_FROZEN),
        ("gate2", root / "nurion_v05_body_motion/gate2/parameters.py", GATE2_FROZEN),
        ("gate3", root / "nurion_v05_body_motion/gate3/parameters.py", GATE3_FROZEN),
        ("gate4", root / "nurion_v05_body_motion/gate4/parameters.py", GATE4_FROZEN),
        ("gate5", root / "nurion_v05_body_motion/gate5/parameters.py", GATE5_FROZEN),
        ("gate6", root / "nurion_v05_body_motion/gate6/parameters.py", GATE6_FROZEN),
        ("gate7", root / "nurion_v05_body_motion/gate7/parameters.py", GATE7_FROZEN),
        ("gate8", root / "nurion_v05_body_motion/gate8/parameters.py", GATE8_FROZEN),
        ("v04Gate7", root / "nurion_v04_face_rig/gate7/parameters.py", V04_GATE7_FROZEN),
    ]
    checks = {}
    for name, path, expected in pairs:
        checks[name] = _load_parameter_hash(path) == expected
    rc1 = root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    checks["v04Rc1"] = rc1.exists() and sha256_file(rc1) == V04_RC1_SHA256
    return {"ok": all(checks.values()), "checks": checks}


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
        f'''bl_info = {{
    "name": "NURION Body Motion Retarget v0.5 RC.1",
    "author": "NURION",
    "version": (0, 5, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > NURION v0.5",
    "description": "Limited-domain body motion retarget + v0.4 face sync (RC.1, not sealed)",
    "category": "Animation",
}}

import sys
from pathlib import Path

_ADDON_DIR = Path(__file__).resolve().parent
if str(_ADDON_DIR) not in sys.path:
    sys.path.insert(0, str(_ADDON_DIR))


def register():
    pass


def unregister():
    pass
''',
        encoding="utf-8",
    )
    (addon_root / "README.md").write_text(
        "# NURION Body Motion Retarget v0.5.0-rc.1\n\n"
        "- Supported domain: **LIMITED**\n"
        "- SEALED: **FALSE** (RC only; Final Seal HOLD)\n"
        "- PRODUCTION: **NO-GO**\n"
        "- Inherited limitations:\n"
        "  - FOOT_SLIDE_RESIDUAL_11\n"
        "  - SHALLOW_SUSTAINED_CONTACT_ACCEPTED\n"
        "  - GATE3_REVERSE_FOREARM_MILD_PRESERVED\n"
        "- Excluded from package: original FBX/ZIP, test assets, gate intermediates, v0.4 RC ZIP\n"
        "- v0.4 face/eye stack: runtime modules only (v0.4 package remains SEALED / READ ONLY externally)\n"
        "- Fresh Holdout: WAITING (unused Meshy humanoid original ZIP)\n"
        "- Repack: DENY after SHA-256 freeze\n",
        encoding="utf-8",
    )


def _copy_reports(root: Path, reports: Path) -> List[str]:
    reports.mkdir(parents=True, exist_ok=True)
    copied = []
    for rel in (
        "dist/v0.5/STATUS.json",
        "dist/v0.5/gate6/ai-aba.bow/GATE6_PROFILE.json",
        "dist/v0.5/gate6/ai-aba.bow/V05_GATE6_STATUS.json",
        "dist/v0.5/gate7/ai-aba.bow/GATE7_PROFILE.json",
        "dist/v0.5/gate7/ai-aba.bow/V05_GATE7_STATUS.json",
        "dist/v0.5/gate8/V05_GATE8_STATUS.json",
        "dist/v0.5/gate8/8a/ai-aba.bow/GATE8A_REGRESSION_REPORT.json",
        "dist/v0.5/gate8/8b/GATE8B_CROSS_ASSET_REPORT.json",
    ):
        src = root / rel
        if not src.exists():
            continue
        dst = reports / src.name
        # Avoid name collisions
        if dst.exists():
            dst = reports / f"{src.parent.name}_{src.name}"
        shutil.copy2(src, dst)
        copied.append(dst.name)
    return copied


def pack_rc1(
    *,
    root: Path,
    out_dir: Optional[Path] = None,
    validation_status: Optional[Dict] = None,
) -> Tuple[Path, Dict]:
    """Package runtime + candidate evidence. Never include FBX/test assets/v0.4 zip."""
    root = Path(root)
    out_dir = Path(out_dir) if out_dir else root / "dist" / "v0.5" / "gate9" / "package"
    out_dir.mkdir(parents=True, exist_ok=True)

    frozen = verify_frozen_hashes(root)
    if not frozen["ok"]:
        raise RuntimeError(f"Gate1–8 frozen hash verification failed: {frozen['checks']}")

    staging = out_dir / "_staging"
    if staging.exists():
        shutil.rmtree(staging)
    addon_root = staging / ADDON_MODULE
    addon_root.mkdir(parents=True)
    _write_addon_init(addon_root)

    # Runtime code only
    _copy_tree(root / "nurion_v05_body_motion", addon_root / "nurion_v05_body_motion")
    _copy_tree(root / "nurion_v04_face_rig", addon_root / "nurion_v04_face_rig")
    _copy_tree(root / "nurion_universal_eye", addon_root / "nurion_universal_eye")

    # Primary timeline RO copy (not human audio / not full test suite)
    t_src = root / "dist/v0.4/gate6/human_gate4_timelines/word_확인.json"
    if not t_src.exists():
        raise FileNotFoundError(t_src)
    t_dst = addon_root / "dist/v0.4/gate6/human_gate4_timelines"
    t_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(t_src, t_dst / "word_확인.json")

    locks = addon_root / "locks"
    locks.mkdir(parents=True, exist_ok=True)
    lock_doc = {
        "schema": "NURION_V05_RC1_BASELINE_LOCK",
        "version": VERSION,
        "parameterHashes": {
            "gate1": GATE1_FROZEN,
            "gate2": GATE2_FROZEN,
            "gate3": GATE3_FROZEN,
            "gate4": GATE4_FROZEN,
            "gate5": GATE5_FROZEN,
            "gate6": GATE6_FROZEN,
            "gate7": GATE7_FROZEN,
            "gate8": GATE8_FROZEN,
            "gate9": parameter_hash(),
            "v04Gate7": V04_GATE7_FROZEN,
        },
        "v04Rc1Sha256": V04_RC1_SHA256,
        "seedZipSha256": GATE9_PARAMETERS["seedZipSha256"],
        "seedFbxSha256": GATE9_PARAMETERS["seedFbxSha256"],
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "repack": "DENY",
        "candidateAction": "NURION_BodyMotionCandidateAction",
        "primaryTimeline": "word_확인",
    }
    (locks / "V05_RC1_BASELINE_LOCK.json").write_text(
        json.dumps(lock_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    reports = addon_root / "reports"
    copied_reports = _copy_reports(root, reports)
    # Integrated candidate digest (no mesh/FBX)
    g6 = root / "dist/v0.5/gate6/ai-aba.bow/GATE6_PROFILE.json"
    g7 = root / "dist/v0.5/gate7/ai-aba.bow/GATE7_PROFILE.json"
    candidate = {
        "schema": "NURION_V05_INTEGRATED_CANDIDATE_RECORD",
        "bodyAction": "NURION_BodyMotionCandidateAction",
        "seedLabel": "ai-aba.bow",
        "primaryTimeline": "word_확인",
        "gate6ProfileSha256": sha256_file(g6) if g6.exists() else "",
        "gate7ProfileSha256": sha256_file(g7) if g7.exists() else "",
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "note": "Rebuild candidate from external Formal Bow FBX; FBX not packaged.",
    }
    (reports / "INTEGRATED_CANDIDATE_RECORD.json").write_text(
        json.dumps(candidate, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if validation_status is None:
        validation_status = {
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
            "frozenHashes": frozen,
            "packedAt": datetime.now(timezone.utc).isoformat(),
        }
    validation_status = {
        **validation_status,
        "inheritedLimitations": list(INHERITED_LIMITATIONS),
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
    }
    (addon_root / "VALIDATION_STATUS.json").write_text(
        json.dumps(validation_status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (addon_root / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(
            {
                "schema": "NURION_V05_RC_PACKAGE_MANIFEST",
                "package": PACKAGE_NAME,
                "version": VERSION,
                "addonModule": ADDON_MODULE,
                "supportedDomain": "LIMITED",
                "production": "NO-GO",
                "sealed": False,
                "inheritedLimitations": INHERITED_LIMITATIONS,
                "includes": [
                    "nurion_v05_body_motion",
                    "nurion_v04_face_rig (runtime)",
                    "nurion_universal_eye (runtime)",
                    "word_확인 timeline RO",
                    "integrated candidate reports",
                ],
                "excludes": [
                    "original FBX",
                    "seed ZIP",
                    "test assets (hyerie/captain/tennis)",
                    "gate intermediate rebuild caches",
                    "v0.4 RC ZIP package",
                    "human audio",
                ],
                "repack": "DENY",
                "reports": copied_reports + ["INTEGRATED_CANDIDATE_RECORD.json"],
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    out = out_dir / PACKAGE_NAME
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for fp in sorted(addon_root.rglob("*")):
            if not fp.is_file():
                continue
            rel_parts = fp.relative_to(staging).parts
            if any(p in SKIP_DIR or str(p).endswith(".pyc") for p in rel_parts):
                continue
            if fp.suffix.lower() in FORBIDDEN_SUFFIX:
                raise RuntimeError(f"forbidden artifact staged for package: {fp}")
            # hard deny nested v0.4 RC zip if somehow present
            if fp.name.endswith("-rc.1.zip") or "NURION_Native_Face_Rig" in fp.name:
                raise RuntimeError(f"v0.4 package leak: {fp}")
            zf.write(fp, fp.relative_to(staging).as_posix())

    names = zipfile.ZipFile(out).namelist()
    required = [
        f"{ADDON_MODULE}/__init__.py",
        f"{ADDON_MODULE}/README.md",
        f"{ADDON_MODULE}/VALIDATION_STATUS.json",
        f"{ADDON_MODULE}/PACKAGE_MANIFEST.json",
        f"{ADDON_MODULE}/nurion_v05_body_motion/gate8/parameters.py",
        f"{ADDON_MODULE}/nurion_v05_body_motion/gate7/sync.py",
        f"{ADDON_MODULE}/nurion_v04_face_rig/gate7/integration.py",
        f"{ADDON_MODULE}/nurion_universal_eye/gate6/beauty_integration.py",
        f"{ADDON_MODULE}/dist/v0.4/gate6/human_gate4_timelines/word_확인.json",
        f"{ADDON_MODULE}/locks/V05_RC1_BASELINE_LOCK.json",
        f"{ADDON_MODULE}/reports/INTEGRATED_CANDIDATE_RECORD.json",
    ]
    missing = [r for r in required if r not in names]
    if missing:
        raise RuntimeError(f"RC zip missing: {missing}")
    leaks = [
        n
        for n in names
        if n.lower().endswith((".fbx", ".wav", ".m4a", ".mp3"))
        or "NURION_Native_Face_Rig_LipSync" in n
        or n.lower().endswith("ai-aba.bow.zip")
    ]
    if leaks:
        raise RuntimeError(f"excluded artifacts leaked into package: {leaks}")

    digest = sha256_file(out)
    manifest = {
        "schema": "NURION_V05_RC_PACKAGE_MANIFEST",
        "package": PACKAGE_NAME,
        "packagePath": str(out.relative_to(root)).replace("\\", "/"),
        "version": VERSION,
        "sha256": digest,
        "sha256Length": 64,
        "entries": len(names),
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
        "gate9ParameterHash": parameter_hash(),
        "gate8ParameterHash": GATE8_FROZEN,
        "excludeOriginalFbx": True,
        "excludeV04Package": True,
        "excludeTestAssets": True,
        "excludeIntermediateOutputs": True,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "PACKAGE_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "VALIDATION_STATUS.json").write_text(
        json.dumps(validation_status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return out, manifest
