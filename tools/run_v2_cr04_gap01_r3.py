#!/usr/bin/env python3
"""CR04-GAP-01 R3 — asset-independent facial resolve on preserved Sporty pin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr04.audit_paths import resolve_v2_cr04_roots
from fast_track.v2_cr04.gap01_pipeline import run_gap01

APPROVED = "4a8467ad945d3c56d9222075c44ae4cc12e8df5edcd833d4091b046901b903f3"


def main() -> int:
    roots = resolve_v2_cr04_roots(__file__)
    sem = Path(roots["semantic"])
    track = json.loads(
        (sem / "NURION_ADAPTATION_ENGINE_V2_CR04_GAP01_TRACK_V1.json").read_text(encoding="utf-8")
    )
    spec = sem / "NURION_ADAPTATION_ENGINE_V2_CR04_GAP01_ASSET_INDEPENDENT_FACIAL_REGION_RESOLUTION_SPEC_R1.json"
    result = run_gap01(
        track=track,
        spec_path=spec,
        roots=roots,
        approved_gap01_digest=APPROVED,
    )
    print(json.dumps({k: result[k] for k in result if k != "report"}, indent=2, ensure_ascii=True))
    if result.get("status") == "READY_FOR_HUMAN_AUDIT":
        track["phase"] = "READY_FOR_HUMAN_AUDIT"
        track["pins"] = {
            "secondAssetSha256": result["report"]["secondAssetSha256"],
            "derivedSha256": result["derivedSha256"],
            "headJointLocalIndexResolved": result["headResolve"]["headJointLocalIndex"],
            "finalCandidateSemanticDigest": result["report"]["finalCandidateSemanticDigest"],
        }
        (sem / "NURION_ADAPTATION_ENGINE_V2_CR04_GAP01_TRACK_V1.json").write_text(
            json.dumps(track, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
