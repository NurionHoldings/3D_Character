#!/usr/bin/env python3
"""CR02-P05 — BODY + FACE runtime coexistence / qualification ONLY (read-only)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.v2_cr02.capability_gap import IDLE15_SHA
from fast_track.v2_cr02.runtime_coexistence import (
    BODY_MOTIONS,
    P04_INPUT_SHA,
    run_p05_runtime_qualification,
)

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
P04_DERIVED = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_P04_jaw_expression_talking.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"

P03_SEMANTIC = "8dca89f8061fa05539eb06e670ceb813bb269dc97b357d0f53b35235b9772b04"
P04_SEMANTIC = "2405040cbf0bcb63f8cf7491fd2ce39a70c178bc1cb997a6a5bd203faf936fe5"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)

        p04_receipt = {
            "derivedAssetSha256": P04_INPUT_SHA,
            "p04DerivedSemanticDigest": P04_SEMANTIC,
        }

        result = run_p05_runtime_qualification(
            P04_DERIVED,
            original_source_path=IDLE15,
            p04_receipt=p04_receipt,
            p03_semantic_digest=P03_SEMANTIC,
            original_source_sha=IDLE15_SHA,
        )

        if result["status"] != "PASS":
            raise AssertionError(f"P05 blocked: {result.get('classification')} {result.get('blockers')}")

        def _ok(c: bool, m: str) -> None:
            if not c:
                raise AssertionError(m)

        _ok(result["classification"] in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"), "not qualified")
        _ok(result["policy"]["autoRepair"] == "DENY", "auto repair")
        _ok(result["p04InputPreservation"]["immutable"], "P04 mutated")
        _ok(result["originalSourcePreservation"]["immutable"], "source mutated")
        _ok(result["contamination"]["bodyFromFace"] == "NONE", "body contamination")
        _ok(result["contamination"]["faceDetachDuringBodyMotion"] == "NONE", "face detach")
        _ok(result["neutralRestoration"] == "PASS", "neutral restoration")
        _ok(result["interfaceStability"]["status"] == "PASS", "interface")

        for motion in BODY_MOTIONS:
            _ok(result["bodyMotion"][motion]["status"] == "PASS", f"body motion {motion}")
        for key, row in result["talkingWhileMoving"].items():
            _ok(row["status"] == "PASS", f"talking while moving {key}")

        (REP / "V2_CR02_P05_runtime_qualification_idle15.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_P05_PASS_receipt",
            "stage": "CR02-P05",
            "status": "PASS",
            "classification": result["classification"],
            "changeRequestId": "V2-CR-02",
            "revision": "R1",
            "inputP04Sha256": P04_INPUT_SHA,
            "p04DerivedSemanticDigest": P04_SEMANTIC,
            "qualificationDigest": result["qualificationDigest"],
            "bodyMotionsVerified": list(BODY_MOTIONS),
            "talkingWhileMoving": list(result["talkingWhileMoving"].keys()),
            "limitations": result.get("limitations") or [],
            "originalSourceImmutable": True,
            "p04InputImmutable": True,
            "v2Engine": "NOT OPEN",
            "next": "CR02-P06 Real-Asset End-to-End Proof Package",
        }
        (EV / "NURION-V2-CR02_P05_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
