#!/usr/bin/env python3
"""CR02-R2 — Actual facial deformation proof (measured vertex N→A→N)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.v2_cr02.capability_gap import IDLE15_SHA
from fast_track.v2_cr02.facial_deformation import VERTEX_DELTA_THRESHOLD, run_r2_deformation_proof

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
DERIVED = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_R2_facial_deformation.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)
        result = run_r2_deformation_proof(IDLE15, DERIVED)
        if result["status"] != "PASS":
            raise AssertionError(f"R2 deformation blocked: {result.get('blockers')}")

        def _ok(c: bool, m: str) -> None:
            if not c:
                raise AssertionError(m)

        _ok(result["sourcePreservation"]["sha256"] == IDLE15_SHA, "source sha")
        _ok(result["sourcePreservation"]["immutable"], "source mutated")
        for cap in ("Blink_L", "Blink_R", "Jaw_Mouth"):
            _ok(result["functionalEvidence"][cap]["functionalTest"] == "PASS", cap)
            _ok(result["functionalEvidence"][cap]["maxActivateDelta"] > VERTEX_DELTA_THRESHOLD, f"{cap} delta")
            _ok(result["functionalEvidence"][cap]["measurement"] == "INDEPENDENT_VERTEX_POSITION", f"{cap} measure")
        _ok(result["expressionDistinct"], "expr distinct")
        _ok(result["talkingVisemesDistinct"], "talk distinct")
        for name, row in result["fileMorphMeasurements"].items():
            _ok(row["pass"], f"file morph {name}")

        (REP / "V2_CR02_R2_facial_deformation_idle15.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_R2_DEFORMATION_PROOF_PASS_receipt",
            "revision": "R2",
            "changeRequestId": "V2-CR-02",
            "status": "PASS",
            "mechanism": "MORPH_TARGET_INJECTION",
            "r1Blocker": "AUXILIARY_CONTROL_METADATA_WITHOUT_ACTUAL_FACIAL_DEFORMATION",
            "r1BlockerAddressed": True,
            "derivedAssetSha256": result["derived"]["derivedSha256"],
            "derivedPath": str(DERIVED),
            "morphCount": result["derived"]["morphCount"],
            "r2DeformationProofDigest": result["r2DeformationProofDigest"],
            "measurement": "INDEPENDENT_VERTEX_POSITION",
            "jsonOnlyTraces": "DENY",
            "v2Engine": "NOT OPEN",
            "CR01_REOPEN": "DENY",
            "next": "CR02-R2 Human Audit ZIP when READY_FOR_HUMAN_AUDIT package assembled",
        }
        (EV / "NURION-V2-CR02_R2_DEFORMATION_PROOF_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
