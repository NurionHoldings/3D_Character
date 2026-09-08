#!/usr/bin/env python3
"""Independent PRODUCT-01 proof — runnable from extracted audit ZIP."""

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
    if not (REPO / "fast_track" / "runtime").exists():
        raise SystemExit(f"missing runtime under {REPO}")
    env = os.environ.copy()
    env["NURION_REPO_ROOT"] = str(REPO)
    proof = REPO / "tools/run_product01_assembly_proof.py"
    proc = subprocess.run([sys.executable, str(proof)], cwd=str(REPO), env=env)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
