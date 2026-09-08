"""Host-side ZIP / package / input security checks for PR Gate 5."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

from .parameters import GATE5_PARAMETERS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_zip_security(zip_path: Path) -> Dict:
    """Path traversal, symlink-like entries, duplicates, absolute paths."""
    zip_path = Path(zip_path)
    names: List[str] = []
    traversal = []
    absolute = []
    symlinks = []
    duplicates = []
    with zipfile.ZipFile(zip_path) as zf:
        bad = zf.testzip()
        infos = zf.infolist()
        for info in infos:
            name = info.filename.replace("\\", "/")
            names.append(name)
            # Path traversal
            if ".." in Path(name).parts or name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                traversal.append(name)
            if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
                absolute.append(name)
            # Symlink / external link flags (Unix)
            is_symlink = (info.external_attr >> 16) & 0o170000 == 0o120000
            if is_symlink or stat.S_ISLNK(info.external_attr >> 16):
                symlinks.append(name)
            # Also create_system / reserved bits sometimes used
            if info.external_attr & 0xA0000000:
                # high bits sometimes mark links on some tools — record conservatively
                if name not in symlinks and ("/" in name and name.endswith("/")) is False:
                    pass
        counts = Counter(names)
        duplicates = sorted([n for n, c in counts.items() if c > 1])
        return {
            "path": str(zip_path).replace("\\", "/"),
            "sha256": sha256_file(zip_path),
            "entryCount": len(names),
            "corruptMember": bad,
            "pathTraversal": traversal,
            "absolutePaths": absolute,
            "symlinks": symlinks,
            "duplicateEntries": duplicates,
            "ok": bad is None and not traversal and not absolute and not symlinks and not duplicates,
        }


def inventory_scripts(addon_dir: Path) -> Dict:
    """List .py / potential auto-exec / driver-related modules in install tree."""
    addon_dir = Path(addon_dir)
    py_files = sorted(str(p.relative_to(addon_dir)).replace("\\", "/") for p in addon_dir.rglob("*.py"))
    driver_hits = []
    autoexec_hits = []
    for p in addon_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(addon_dir)).replace("\\", "/")
        if "driver" in text.lower() or "bpy.app.driver" in text:
            driver_hits.append(rel)
        if "register_handler" in text or "load_post" in text or "persistent" in text:
            autoexec_hits.append(rel)
    return {
        "pythonModuleCount": len(py_files),
        "pythonModules": py_files,
        "driverRelatedModules": sorted(set(driver_hits)),
        "handlerAutoexecModules": sorted(set(autoexec_hits)),
    }


def scan_code_side_effects(addon_dir: Path) -> Dict:
    """Detect network / env access patterns in packaged Python."""
    addon_dir = Path(addon_dir)
    net_hits: List[str] = []
    env_hits: List[str] = []
    net_tokens = GATE5_PARAMETERS["networkImportTokens"]
    env_tokens = GATE5_PARAMETERS["envAccessTokens"]
    for p in addon_dir.rglob("*.py"):
        text = p.read_text(encoding="utf-8", errors="replace")
        rel = str(p.relative_to(addon_dir)).replace("\\", "/")
        for tok in net_tokens:
            if tok in text:
                net_hits.append(f"{rel}:{tok}")
        for tok in env_tokens:
            if tok in text:
                env_hits.append(f"{rel}:{tok}")
    return {
        "networkHits": sorted(set(net_hits)),
        "envHits": sorted(set(env_hits)),
        "networkOk": len(net_hits) == 0,
        "envOk": len(env_hits) == 0,
    }


def scan_export_artifact_paths(path: Path) -> Dict:
    """Scan export for sensitive filesystem paths (path-like strings only; avoid binary false positives)."""
    path = Path(path)
    if not path.is_file():
        return {"ok": False, "reason": "MISSING", "hits": []}
    data = path.read_bytes()[: min(path.stat().st_size, 8 * 1024 * 1024)]
    text = data.decode("utf-8", errors="ignore")
    # Extract path-like candidates only (not raw binary substrings like ".aws" in GLB/BLEND payloads)
    candidates = re.findall(
        r"(?:[A-Za-z]:[\\/][^\x00-\x1f\"']{2,240})|(?:/(?:Users|home|tmp|var|etc|root)[^\x00-\x1f\"']{0,240})",
        text,
    )
    # Also collect Blender packed // relative paths that look absolute after join — skip pure //
    hits = []
    patterns = GATE5_PARAMETERS.get("sensitivePathPatterns") or []
    for cand in candidates:
        for pat in patterns:
            if re.search(pat, cand):
                hits.append(f"{pat} @ {cand[:120]}")
    return {
        "ok": len(hits) == 0,
        "path": str(path).replace("\\", "/"),
        "candidateCount": len(candidates),
        "hits": sorted(set(hits))[:20],
    }


def prepare_bad_inputs(probe_dir: Path) -> Dict[str, Path]:
    """Create wrong-extension / corrupt / oversize probe files (no auto-fix of product)."""
    probe_dir = Path(probe_dir)
    probe_dir.mkdir(parents=True, exist_ok=True)
    wrong = probe_dir / "not_a_character.txt"
    wrong.write_text("not-an-fbx\n", encoding="utf-8")
    corrupt = probe_dir / "corrupt_character.fbx"
    corrupt.write_bytes(b"FBX\x00CORRUPT_PROBE_" + os.urandom(64))
    # Oversize marker file: create sparse-ish by seeking (Windows supports sparse-ish via truncate)
    oversize = probe_dir / "oversize_character.fbx"
    max_mb = int(GATE5_PARAMETERS["maxInputMb"])
    target = (max_mb + 1) * 1024 * 1024
    with oversize.open("wb") as f:
        f.write(b"FBX_OVERSIZE_PROBE\n")
        f.seek(target - 1)
        f.write(b"\0")
    return {"wrongExt": wrong, "corrupt": corrupt, "oversize": oversize}
