#!/usr/bin/env python3
"""Independent PRODUCT-05 proof entry."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE / "repo"
if not (REPO / "fast_track" / "runtime").exists():
    REPO = HERE.parent if (HERE.parent / "fast_track").exists() else HERE


def main() -> int:
    env = os.environ.copy()
    env["NURION_REPO_ROOT"] = str(REPO)
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools/run_product05_behavior_runtime_proof.py")],
        cwd=str(REPO),
        env=env,
    )
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
