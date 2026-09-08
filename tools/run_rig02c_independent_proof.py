#!/usr/bin/env python3
"""
Independent RIG-02C proof entry — runnable from extracted audit ZIP.

Layout created by pack_rig02c_jake_adapter_proof_zip.py:

  <extract>/
    run_rig02c_independent_proof.py
    repo/   # NURION Character Landmarker root mirror
"""

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
    proof_path = REPO / "tools/run_rig02c_jake_adapter_proof.py"
    proc = subprocess.run([sys.executable, str(proof_path)], cwd=str(REPO), env=env)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
