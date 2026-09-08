#!/usr/bin/env python3
"""Independent V2-CR-01 proof runner for extracted Human Audit ZIP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve()
proof = here.parent / "run_v2_cr01_prototype_proof.py"
result = subprocess.run([sys.executable, str(proof)], check=False)
raise SystemExit(result.returncode)
