"""V2-CR-01 audit path resolution — monorepo or extracted self-contained ZIP."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def resolve_v2_cr01_roots(script_file: str | Path) -> dict[str, Path | str | bool]:
    """
    Extracted audit ZIP layout:
      <package>/repo/tools/<script>.py
      <package>/fixtures/
      <package>/assets/Idle_15_withSkin_WORKING_BASELINE.glb
      <package>/evidence|reports|semantic/

    Monorepo layout:
      <repo>/tools/<script>.py
      <repo>/fast_track/v2_cr01/fixtures
      <repo>/fast_track/working/meshy_silver_starlight/baseline/Idle_15...
    """
    here = Path(script_file).resolve()
    parent = here.parents[1]
    if parent.name == "repo" and (parent / "fast_track" / "v2_cr01").is_dir():
        repo_root = parent
        package_root = here.parents[2]
        mode = "EXTRACTED_AUDIT_ZIP"
        fix = package_root / "fixtures"
        ev = package_root / "evidence"
        rep = package_root / "reports"
        sem = package_root / "semantic"
        idle15 = package_root / "assets" / "Idle_15_withSkin_WORKING_BASELINE.glb"
    else:
        repo_root = Path(os.environ.get("NURION_REPO_ROOT", str(parent)))
        package_root = repo_root / "fast_track" / "working" / "adaptation_engine_v2"
        mode = "MONOREPO"
        fix = repo_root / "fast_track" / "v2_cr01" / "fixtures"
        ev = package_root / "evidence"
        rep = package_root / "reports_cr01"
        sem = package_root / "semantic"
        idle15 = (
            repo_root
            / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
        )

    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    return {
        "mode": mode,
        "repoRoot": repo_root,
        "packageRoot": package_root,
        "fixtures": fix,
        "evidence": ev,
        "reports": rep,
        "semantic": sem,
        "idle15": idle15,
        "extracted": mode == "EXTRACTED_AUDIT_ZIP",
    }
