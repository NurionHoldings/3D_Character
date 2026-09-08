#!/usr/bin/env python3
"""Build NURION-PRODUCT-02 motion library artifact."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_motion_library import LIBRARY_PATH, build_and_hash


def main() -> int:
    result = build_and_hash()
    result.write(LIBRARY_PATH)
    print(
        json.dumps(
            {
                "out": str(LIBRARY_PATH),
                "libraryId": result.library["libraryId"],
                "motions": [m["motionId"] for m in result.library["motions"]],
                "canonicalSha256": result.sha256,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
