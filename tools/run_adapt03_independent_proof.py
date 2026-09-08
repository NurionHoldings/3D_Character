#!/usr/bin/env python3
"""Independent ADAPT-03 proof runner for extracted audit ZIP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve()
proof = here.parent / "run_adapt03_face_adaptation_proof.py"
result = subprocess.run([sys.executable, str(proof)], check=False)
raise SystemExit(result.returncode)
