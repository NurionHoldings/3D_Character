"""CR04 audit path resolution."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_v2_cr04_roots(script_file: str | Path) -> dict[str, Path | str | bool]:
    here = Path(script_file).resolve()
    parent = here.parents[1]
    if parent.name == "repo" and (parent / "fast_track" / "v2_cr04").is_dir():
        repo_root = parent
        package_root = here.parents[2]
        mode = "EXTRACTED_AUDIT_ZIP"
        ev = package_root / "evidence"
        rep = package_root / "reports"
        sem = package_root / "semantic"
        derived = package_root / "derived"
        baseline = package_root / "assets" / "SECOND_ASSET_BASELINE.glb"
    else:
        repo_root = Path(os.environ.get("NURION_REPO_ROOT", str(parent)))
        package_root = repo_root / "fast_track" / "working" / "adaptation_engine_v2"
        mode = "MONOREPO"
        ev = package_root / "evidence"
        rep = package_root / "reports_cr04"
        sem = package_root / "semantic"
        derived = package_root / "derived_cr04"
        baseline = package_root / "assets_cr04" / "SECOND_ASSET_BASELINE.glb"

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
        "baseline": baseline,
        "extracted": mode == "EXTRACTED_AUDIT_ZIP",
    }
