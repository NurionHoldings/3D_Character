#!/usr/bin/env python3
"""Build NURION-PRODUCT-06 release baseline artifact."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_release_baseline import BASELINE_PATH, build_and_hash


def main() -> int:
    result = build_and_hash()
    result.write(BASELINE_PATH)
    print(
        json.dumps(
            {
                "out": str(BASELINE_PATH),
                "runtimeId": result.baseline["runtimeId"],
                "canonicalSha256": result.sha256,
                "releaseId": result.baseline["releaseId"],
                "canonicalReleaseDigest": result.baseline["canonicalReleaseDigest"],
                "product06Pass": "NOT_DECLARED",
                "pipelineOverallPass": "NOT_DECLARED",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
