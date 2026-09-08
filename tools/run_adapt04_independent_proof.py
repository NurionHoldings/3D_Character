#!/usr/bin/env python3
"""Independent ADAPT-04 proof runner for extracted audit ZIP."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

here = Path(__file__).resolve()
proof = here.parent / "run_adapt04_augmentation_proof.py"
result = subprocess.run([sys.executable, str(proof)], check=False)
raise SystemExit(result.returncode)
