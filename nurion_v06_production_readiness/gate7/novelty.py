"""Novelty / eligibility for PR Gate 7 holdout ZIP."""

from __future__ import annotations

import hashlib
import re
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional, Tuple

from .parameters import (
    HOLDOUT_FBX_SHA256,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    USED_FBX_SHA256,
    USED_LABELS,
    USED_ZIP_SHA256,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _compact(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def extract_withskin_fbx(zip_path: Path, work_dir: Path) -> Tuple[Optional[Path], Dict]:
    work_dir = Path(work_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        fbxs = [n for n in names if n.lower().endswith(".fbx")]
        with_skin = [n for n in fbxs if "withskin" in _compact(n)]
        pick = with_skin[0] if with_skin else None
        if pick is None:
            return None, {
                "ok": False,
                "reason": "NO_WITHSKIN_FBX",
                "form": "INVALID",
                "fbxCount": len(fbxs),
            }
        zf.extractall(work_dir)
        fbx = work_dir / pick
        return fbx, {
            "ok": True,
            "fbxRel": pick.replace("\\", "/"),
            "fbxSha256": sha256_file(fbx),
            "withSkin": True,
            "form": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP",
            "zipEntries": len(names),
        }


def evaluate_holdout(*, zip_path: Path, label: str, expected_zip_sha: str, expected_fbx_sha: str) -> Dict:
    zip_path = Path(zip_path)
    reasons = []
    zip_sha = sha256_file(zip_path)
    if zip_sha != expected_zip_sha:
        reasons.append(f"ZIP_SHA_MISMATCH:{zip_sha}")
    if zip_sha in USED_ZIP_SHA256:
        reasons.append(f"USED_ZIP:{USED_ZIP_SHA256[zip_sha]}")

    label_c = _compact(label)
    for used in USED_LABELS:
        if _compact(used) in label_c or label_c in _compact(used):
            # exact holdout label MINIMALIST_TENNIS_OUT is fine
            if _compact(used) == label_c and used != "minimalist_tennis_out":
                reasons.append(f"USED_LABEL:{used}")

    # Block AILAWFRIEND / silver / lightning family names in path
    path_c = _compact(str(zip_path))
    for bad in ("ailawfriend", "silverstarlight", "lightningpilot", "aiaba", "aibaeby"):
        if bad in path_c and "wither" not in path_c and "minimalist" not in path_c:
            reasons.append(f"USED_FAMILY_PATH:{bad}")

    work = zip_path.parent / "_extract"
    fbx, meta = extract_withskin_fbx(zip_path, work)
    if not meta.get("ok") or fbx is None:
        return {
            "eligible": False,
            "verdict": "ASSET_INELIGIBLE",
            "reasons": reasons + [meta.get("reason") or "EXTRACT_FAIL"],
            "zipSha256": zip_sha,
            "extract": meta,
        }

    fbx_sha = meta["fbxSha256"]
    if fbx_sha != expected_fbx_sha:
        reasons.append(f"FBX_SHA_MISMATCH:{fbx_sha}")
    if fbx_sha in USED_FBX_SHA256:
        reasons.append(f"USED_FBX:{USED_FBX_SHA256[fbx_sha]}")

    # Must not be AILAWFRIEND sibling / tennis banned
    if "법률" in str(fbx) or "ailaw" in _compact(str(fbx)):
        reasons.append("AILAWFRIEND_FAMILY_DENY")

    eligible = len(reasons) == 0 and meta.get("form") == "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP"
    return {
        "eligible": eligible,
        "verdict": "ELIGIBLE" if eligible else "ASSET_INELIGIBLE",
        "reasons": reasons,
        "zipSha256": zip_sha,
        "fbxSha256": fbx_sha,
        "fbxPath": str(fbx).replace("\\", "/"),
        "label": label,
        "expectedZipSha256": expected_zip_sha,
        "expectedFbxSha256": expected_fbx_sha,
        "extract": meta,
        "matchesPinnedHoldout": zip_sha == HOLDOUT_ZIP_SHA256 and fbx_sha == HOLDOUT_FBX_SHA256 and label == HOLDOUT_LABEL,
    }
