#!/usr/bin/env python3
"""Independent ADAPT-05 proof runner for extracted audit ZIP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve()
proof = here.parent / "run_adapt05_runtime_qualification_proof.py"
result = subprocess.run([sys.executable, str(proof)], check=False)
raise SystemExit(result.returncode)
