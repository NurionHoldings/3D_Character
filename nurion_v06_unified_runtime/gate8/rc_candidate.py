"""v0.6 Gate 8 — RC candidate package (no auto-seal, production remains NO-GO)."""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETER_HASH_FROZEN,
    GATE6_PARAMETER_HASH_FROZEN,
    GATE7_PARAMETER_HASH_FROZEN,
    GATE8_PARAMETERS,
    RC_PACKAGE_NAME,
    V03_RC1_SHA256,
    V04_RC1_SHA256,
    V05_RC1_SHA256,
    parameter_hash,
)

SKIP_DIR = {"__pycache__", ".git", ".DS_Store"}
FORBIDDEN_SUFFIX = {".fbx", ".zip", ".wav", ".m4a", ".mp3", ".flac", ".aac", ".blend", ".png", ".jpg", ".jpeg", ".glb"}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_rc_candidate(
    *,
    root: Path,
    out_dir: Path,
    holdout_receipt: Dict,
    gate8_status: Dict,
) -> Dict:
    """Create RC.1 candidate ZIP from runtime package + evidence JSON only."""
    root = Path(root)
    out_dir = Path(out_dir)
    pkg_dir = out_dir / "package"
    staging = pkg_dir / "_staging" / "nurion_v06_unified_runtime"
    if pkg_dir.exists():
        shutil.rmtree(pkg_dir)
    staging.parent.mkdir(parents=True, exist_ok=True)

    src = root / "nurion_v06_unified_runtime"
    shutil.copytree(
        src,
        staging,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".DS_Store"),
    )

    evidence = pkg_dir / "_staging" / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "V06_GATE8_HOLDOUT_RECEIPT.json").write_text(
        json.dumps(holdout_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (evidence / "V06_GATE8_STATUS.json").write_text(
        json.dumps(gate8_status, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    manifest = {
        "schema": "NURION_V06_RC1_CANDIDATE_MANIFEST",
        "package": RC_PACKAGE_NAME,
        "version": "0.6.0-rc.1",
        "product": "NURION Unified Character Animation Runtime",
        "status": "RC_CANDIDATE",
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "gate1To7Frozen": True,
        "parameterHashes": {
            "gate1": GATE1_PARAMETER_HASH_FROZEN,
            "gate2": GATE2_PARAMETER_HASH_FROZEN,
            "gate3": GATE3_PARAMETER_HASH_FROZEN,
            "gate4": GATE4_PARAMETER_HASH_FROZEN,
            "gate5": GATE5_PARAMETER_HASH_FROZEN,
            "gate6": GATE6_PARAMETER_HASH_FROZEN,
            "gate7": GATE7_PARAMETER_HASH_FROZEN,
            "gate8": parameter_hash(),
        },
        "readonlyBaselines": {
            "v0.3": V03_RC1_SHA256,
            "v0.4": V04_RC1_SHA256,
            "v0.5": V05_RC1_SHA256,
        },
        "holdout": {
            "label": GATE8_PARAMETERS["holdoutLabel"],
            "zipSha256": GATE8_PARAMETERS["holdoutZipSha256"],
            "fbxSha256": GATE8_PARAMETERS["holdoutFbxSha256"],
            "animation": GATE8_PARAMETERS["holdoutAnimation"],
        },
        "inheritedLimitationsFromV05": GATE8_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "createdAt": now,
        "next": "FINAL_SEAL_REVIEW_SEPARATE_TRACK",
    }
    (pkg_dir / "_staging" / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (staging / "RC1_CANDIDATE_NOTICE.json").write_text(
        json.dumps(
            {
                "SEALED": False,
                "autoSeal": "DENY",
                "production": "NO-GO",
                "note": "RC candidate only — requires separate final seal review; no production advance.",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    zip_path = pkg_dir / RC_PACKAGE_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in (pkg_dir / "_staging").rglob("*"):
            if path.is_dir():
                continue
            if path.suffix.lower() in FORBIDDEN_SUFFIX:
                continue
            if any(part in SKIP_DIR for part in path.parts):
                continue
            arc = path.relative_to(pkg_dir / "_staging").as_posix()
            zf.write(path, arcname=f"nurion_v06_unified_runtime_rc1/{arc}")

    freeze = {
        "schema": "NURION_V06_RC1_CANDIDATE_FREEZE",
        "package": RC_PACKAGE_NAME,
        "packageSha256": sha256_file(zip_path),
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "gate8ParameterHash": parameter_hash(),
        "createdAt": now,
        "repack": "DENY_UNTIL_SEAL_REVIEW",
    }
    (pkg_dir / "RC1_CANDIDATE_FREEZE.json").write_text(
        json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (pkg_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return {
        "ok": True,
        "package": str(zip_path).replace("\\", "/"),
        "packageSha256": freeze["packageSha256"],
        "SEALED": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "freeze": str((pkg_dir / "RC1_CANDIDATE_FREEZE.json").as_posix()),
    }
