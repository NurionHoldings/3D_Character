"""V2-IRG audit path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_v2_irg_roots(script_file: str | Path) -> dict:
    here = Path(script_file).resolve()
    parent = here.parents[1]
    if parent.name == "repo" and (parent / "fast_track" / "v2_irg").is_dir():
        repo_root = parent
        package_root = here.parents[2]
        mode = "EXTRACTED_AUDIT_ZIP"
        ev = package_root / "evidence"
        rep = package_root / "reports"
        sem = package_root / "semantic"
        derived = package_root / "derived"
        assets = package_root / "assets"
    else:
        repo_root = Path(os.environ.get("NURION_REPO_ROOT", str(parent)))
        package_root = repo_root / "fast_track" / "working" / "adaptation_engine_v2"
        mode = "MONOREPO"
        ev = package_root / "evidence"
        rep = package_root / "reports_irg"
        sem = package_root / "semantic"
        derived = package_root / "derived_irg"
        assets = package_root / "assets_irg"

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    return {
        "mode": mode,
        "repoRoot": repo_root,
        "packageRoot": package_root,
        "evidence": ev,
        "reports": rep,
        "semantic": sem,
        "derived": derived,
        "assets": assets,
        "extracted": mode == "EXTRACTED_AUDIT_ZIP",
    }
