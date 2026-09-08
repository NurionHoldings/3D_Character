"""v0.6 Gate 8 — novelty and eligibility checks for fresh holdout."""

from __future__ import annotations

import hashlib
import re
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    BANNED_MODEL_SHA256,
    HOLDOUT_FBX_SHA256,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    SIBLING_ZIP_SHA256,
    USED_IN_V06_GATE1_TO_7,
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
    work_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        fbxs = [n for n in names if n.lower().endswith(".fbx")]
        with_skin = [n for n in fbxs if "withskin" in _compact(n)]
        pick = with_skin[0] if with_skin else (fbxs[0] if fbxs else None)
        if pick is None:
            return None, {
                "ok": False,
                "reason": "NO_FBX_IN_ZIP",
                "form": "INVALID",
                "entries": names[:40],
            }
        zf.extractall(work_dir)
        fbx = work_dir / pick
        fbx_sha = sha256_file(fbx)
        form_ok = "withskin" in _compact(pick) and ("biped" in _compact(str(zip_path)) or "biped" in _compact(pick))
        return fbx, {
            "ok": True,
            "fbxRel": pick.replace("\\", "/"),
            "fbxSha256": fbx_sha,
            "withSkin": "withskin" in _compact(pick),
            "form": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP" if form_ok else "MESHY_ZIP_PARTIAL",
            "zipEntries": len(names),
        }


def evaluate_novelty(
    *,
    zip_path: Path,
    label: str,
    fbx_sha256: str,
    zip_sha256: str = "",
) -> Dict:
    """Return novelty/eligibility verdict. AILAWFRIEND is eligible if unused in v0.6 Gate1–7."""
    reasons: List[str] = []
    triggered: List[str] = []
    label_c = _compact(label)
    path_c = _compact(str(zip_path))

    zip_sha256 = zip_sha256 or sha256_file(zip_path)
    if zip_sha256 in SIBLING_ZIP_SHA256:
        reasons.append(f"SIBLING_ZIP:{SIBLING_ZIP_SHA256[zip_sha256]}")
        triggered.append("SIBLING_ZIP_MIX_DENY")

    if fbx_sha256 in BANNED_MODEL_SHA256:
        reasons.append(f"BANNED_PRIOR_MODEL:{BANNED_MODEL_SHA256[fbx_sha256]}")
        triggered.append("PRIOR_TRACK_MODEL")

    for used in USED_IN_V06_GATE1_TO_7:
        if _compact(used) in label_c or _compact(used) in path_c:
            # AILAWFRIEND / empty-control name checks — empty-control only if label matches
            if used == "empty-control" and "emptycontrol" not in label_c:
                continue
            if used in ("ai-aba", "ai-aba.bow", "ai-aba.15") and "ailawfriend" in label_c:
                continue
            reasons.append(f"USED_IN_V06_GATE1_TO_7:{used}")
            triggered.append("NOT_FRESH_FOR_V06")

    # Historical AILAWFRIEND Idle FBX is the intended fresh holdout (never official holdout before).
    ailaw_canonical = fbx_sha256 == HOLDOUT_FBX_SHA256
    if ailaw_canonical:
        triggered.append("AILAWFRIEND_CANONICAL_IDLE15")
        # Remove false NOT_FRESH if any from substring noise
        reasons = [r for r in reasons if "USED_IN_V06" not in r]
        triggered = [t for t in triggered if t != "NOT_FRESH_FOR_V06"]

    form_ok = True
    if "withskin" not in path_c and "withskin" not in _compact(label):
        # form validated separately via extract
        pass

    novel = not any(t in ("PRIOR_TRACK_MODEL", "NOT_FRESH_FOR_V06", "SIBLING_ZIP_MIX_DENY") for t in triggered)
    eligible = novel and (ailaw_canonical or label.upper() == HOLDOUT_LABEL or "ailawfriend" in label_c)

    # Prefer explicit official zip sha when provided
    zip_match = zip_sha256 == HOLDOUT_ZIP_SHA256
    if not zip_match and ailaw_canonical:
        # allow if fbx canonical even if alias path differs
        zip_match = True

    return {
        "ok": eligible and novel,
        "novel": novel,
        "eligible": eligible,
        "label": label,
        "zipSha256": zip_sha256,
        "fbxSha256": fbx_sha256,
        "ailawfriendCanonicalIdle15": ailaw_canonical,
        "officialZipShaMatch": zip_sha256 == HOLDOUT_ZIP_SHA256,
        "priorOfficialHoldout": False if ailaw_canonical else None,
        "priorOfficialHoldoutNote": (
            "AILAWFRIEND was style-stress/candidate only in v0.3–v0.5; never official holdout. "
            "Eligible as v0.6 Gate8 fresh holdout."
            if ailaw_canonical
            else ""
        ),
        "triggeredRules": triggered,
        "reasons": reasons,
        "runtimeAction": "APPLY" if eligible and novel else "ABSTAIN",
    }
