#!/usr/bin/env python3
"""RAAT-02 — Real Asset Acceptance Test 02 (structurally different submitted GLB).

Purpose: map V1 real-asset support envelope. Engine V1 = CONSUME ONLY.
RAPT-01 opens only after a RELEASED candidate exists.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
RAAT = ROOT / "fast_track/working/raat02"
EV = RAAT / "evidence"
REP = RAAT / "reports"
DERIVED = RAAT / "derived"


def resolve_default_asset() -> Path:
    env = os.environ.get("NURION_RAAT02_ASSET")
    if env:
        return Path(env)
    matches = list((ROOT / "assets").rglob("free_cartoon_game_man_character_rigged.glb"))
    if matches:
        return matches[0]
    raise FileNotFoundError("RAAT-02 asset not found; set NURION_RAAT02_ASSET")


def main() -> int:
    asset = resolve_default_asset()
    character_id = os.environ.get("NURION_RAAT02_CHARACTER_ID", "raat02_cartoon_man")

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
            test_id="RAAT-02",
        )
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        raat_result = result["raatResult"]
        report_path = REP / f"RAAT02_report_{character_id}.json"
        result_path = EV / "NURION-RAAT-02_RESULT.json"
        receipt_path = EV / f"NURION-RAAT-02_{character_id}_acceptance_receipt.json"

        receipt = {
            "schema": "NURION_RAAT02_ACCEPTANCE_RECEIPT_V1",
            "testId": "RAAT-02",
            "characterId": character_id,
            "executedAtUtc": ts,
            "selectionRationale": (
                "Structurally different from RAAT-01 Meshy Idle_15 — CC_Base_* skeleton, "
                "no NURION_* source naming; avoids repeating identical Meshy spine ancestry blocker"
            ),
            "engineV1": result["engineV1"],
            "canonicalMutation": result["canonicalMutation"],
            "raatResult": raat_result,
            "fullReport": f"reports/RAAT02_report_{character_id}.json",
            "rapt01": "NOT OPENED — requires RELEASED candidate",
            "policy": "Consumer acceptance — Engine V1 CONSUME ONLY; support-envelope measurement",
        }

        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result_path.write_text(json.dumps(raat_result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        print(
            json.dumps(
                {
                    "ok": True,
                    "testId": "RAAT-02",
                    "characterId": character_id,
                    "sourceSha256": raat_result["sourceSha256"],
                    "pipelineStatus": raat_result["pipelineStatus"],
                    "firstStopStage": raat_result["firstStopStage"],
                    "automaticStagesPassed": raat_result["automaticStagesPassed"],
                    "manualReviewRequired": raat_result["manualReviewRequired"],
                    "releaseCandidateSha256": raat_result["releaseCandidateSha256"],
                    "raptEligible": raat_result["raptEligible"],
                    "result": str(result_path),
                    "report": str(report_path),
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
