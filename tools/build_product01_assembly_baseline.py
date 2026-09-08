#!/usr/bin/env python3
"""Build NURION-PRODUCT-01 MJN character assembly baseline artifact."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_character_assembly import build_mjn_assembly_baseline

OUT = (
    ROOT
    / "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
)


def main() -> int:
    asm = build_mjn_assembly_baseline(idle_frame_index=2)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(asm.to_json_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "out": str(OUT),
                "assemblyId": asm.assembly_id,
                "coreBones": len(asm.core_bones),
                "unitScale": asm.unit_scale,
                "assetSha256": asm.asset_sha256,
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
