#!/usr/bin/env python3
"""RAAT-01 — Real Asset End-to-End Acceptance Test (Engine V1 CONSUME ONLY)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

DEFAULT_ASSET = (
    ROOT
    / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
)
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
RAAT = ROOT / "fast_track/working/raat01"
EV = RAAT / "evidence"
REP = RAAT / "reports"
DERIVED = RAAT / "derived"


def main() -> int:
    asset = Path(os.environ.get("NURION_RAAT01_ASSET", str(DEFAULT_ASSET)))
    character_id = os.environ.get("NURION_RAAT01_CHARACTER_ID", "raat01_idle15")

    if not asset.is_file():
        print(json.dumps({"ok": False, "error": f"asset not found: {asset}"}, indent=2))
        return 1

    from fast_track.raat01.consumer_pipeline import run_raat_pipeline

    EV.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    try:
        result = run_raat_pipeline(
            asset,
            character_id=character_id,
            semantic_dir=SEM,
            derived_dir=DERIVED,
        )
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = REP / f"RAAT01_report_{character_id}.json"
        receipt_path = EV / f"NURION-RAAT-01_{character_id}_acceptance_receipt.json"

        # Slim receipt without full nested reports
        receipt = {
            "schema": "NURION_RAAT01_ACCEPTANCE_RECEIPT_V1",
            "testId": "RAAT-01",
            "characterId": character_id,
            "executedAtUtc": ts,
            "sourceAssetSha256": result["sourceAsset"]["sha256"],
            "engineV1": result["engineV1"],
            "canonicalMutation": result["canonicalMutation"],
            "pipelineStatus": result["pipelineStatus"],
            "firstStopStage": result["firstStopStage"],
            "stages": {
                k: {
                    "status": v["status"],
                    "classification": v.get("classification"),
                    "blockerCount": len(v.get("blockers") or []),
                    "manualReviewCount": len(v.get("manualReviewItems") or []),
                }
                for k, v in result["stages"].items()
            },
            "preservation": result["preservation"],
            "fullReport": f"reports/RAAT01_report_{character_id}.json",
            "policy": "Consumer acceptance — does not modify Engine V1 authority",
        }

        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "ok": True,
                    "testId": "RAAT-01",
                    "characterId": character_id,
                    "sourceAssetSha256": result["sourceAsset"]["sha256"],
                    "pipelineStatus": result["pipelineStatus"],
                    "firstStopStage": result["firstStopStage"],
                    "stages": receipt["stages"],
                    "report": str(report_path),
                    "receipt": str(receipt_path),
                },
                indent=2,
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
