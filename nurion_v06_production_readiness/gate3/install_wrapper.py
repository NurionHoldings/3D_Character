"""Build Blender-installable wrapper from sealed RC.1 without mutating RC.1."""

from __future__ import annotations

import hashlib
import shutil
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

from .parameters import ADDON_MODULE, RC1_SHA256


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


ADDON_INIT = '''bl_info = {
    "name": "NURION Unified Character Animation Runtime v0.6 RC.1",
    "author": "NURION",
    "version": (0, 6, 0),
    "blender": (5, 0, 0),
    "location": "View3D > Sidebar > NURION",
    "description": "Limited-domain unified runtime (SEALED_WITH_LIMITATIONS). Production NO-GO.",
    "category": "Animation",
}

from . import gate6 as _gate6


def register():
    _gate6.register()


def unregister():
    _gate6.unregister()
'''


def build_install_wrapper(*, rc1_zip: Path, out_dir: Path) -> Dict:
    """Extract sealed RC.1 runtime package and emit installable addon ZIP + folder."""
    rc1_zip = Path(rc1_zip)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    actual = sha256_file(rc1_zip)
    if actual != RC1_SHA256:
        return {"ok": False, "reason": "RC1_SHA_MISMATCH", "actual": actual}

    extract = out_dir / "_rc1_extract"
    if extract.exists():
        shutil.rmtree(extract)
    extract.mkdir(parents=True)
    with zipfile.ZipFile(rc1_zip) as zf:
        bad = zf.testzip()
        if bad is not None:
            return {"ok": False, "reason": "RC1_ZIP_CORRUPT", "bad": bad}
        zf.extractall(extract)

    # Sealed layout: nurion_v06_unified_runtime_rc1/nurion_v06_unified_runtime/...
    src_pkg = extract / "nurion_v06_unified_runtime_rc1" / "nurion_v06_unified_runtime"
    if not src_pkg.is_dir():
        # fallback: find package dir
        hits = list(extract.rglob("gate6/operators.py"))
        if not hits:
            return {"ok": False, "reason": "RUNTIME_PACKAGE_MISSING"}
        src_pkg = hits[0].parents[1]

    addon_root = out_dir / ADDON_MODULE
    if addon_root.exists():
        shutil.rmtree(addon_root)
    shutil.copytree(src_pkg, addon_root)

    # Record sealed member hashes (pre-shim) for gate modules
    sealed_hashes = {}
    for p in sorted(src_pkg.rglob("*.py")):
        rel = p.relative_to(src_pkg).as_posix()
        sealed_hashes[rel] = sha256_file(p)

    # Inject bl_info shim (install wrapper only — does not alter RC.1 ZIP)
    (addon_root / "__init__.py").write_text(ADDON_INIT, encoding="utf-8")

    # Verify non-init sealed modules unchanged vs extract
    drift = []
    for rel, expected in sealed_hashes.items():
        if rel == "__init__.py":
            continue
        cur = addon_root / rel
        if not cur.is_file() or sha256_file(cur) != expected:
            drift.append(rel)
    if drift:
        return {"ok": False, "reason": "WRAPPER_MEMBER_DRIFT", "drift": drift[:20]}

    wrapper_zip = out_dir / f"{ADDON_MODULE}_from_rc1_install_wrapper.zip"
    if wrapper_zip.exists():
        wrapper_zip.unlink()
    with zipfile.ZipFile(wrapper_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in addon_root.rglob("*"):
            if path.is_dir():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            arc = f"{ADDON_MODULE}/{path.relative_to(addon_root).as_posix()}"
            zf.write(path, arcname=arc)

    return {
        "ok": True,
        "rc1Sha256": actual,
        "addonDir": str(addon_root).replace("\\", "/"),
        "wrapperZip": str(wrapper_zip).replace("\\", "/"),
        "wrapperSha256": sha256_file(wrapper_zip),
        "sealedModuleCount": len(sealed_hashes),
        "initShimInjected": True,
        "rc1Repack": "DENY",
    }
