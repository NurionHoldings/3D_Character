#!/usr/bin/env python3
"""Build NURION-PRODUCT-04 entrance state artifact."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_entrance_state import STATE_PATH, build_and_hash


def main() -> int:
    result = build_and_hash()
    result.write(STATE_PATH)
    print(
        json.dumps(
            {
                "out": str(STATE_PATH),
                "runtimeId": result.state["runtimeId"],
                "canonicalSha256": result.sha256,
                "product04Pass": "NOT_DECLARED",
                "currentState": result.state["currentState"],
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
