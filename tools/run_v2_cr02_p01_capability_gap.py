#!/usr/bin/env python3
"""CR02-P01 Capability Gap Inspection proof — Idle_15 first proof asset."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.v2_cr02.capability_gap import CR01_DIGEST, IDLE15_SHA, inspect_capability_gap

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)
        report = inspect_capability_gap(IDLE15)
        if report["status"] != "PASS":
            raise AssertionError(f"P01 blocked: {report.get('blockers')}")
        if report["sourceIdentity"]["sha256"] != IDLE15_SHA:
            raise AssertionError("Idle_15 SHA mismatch")
        if not report["cr01Consume"]["digestMatch"]:
            raise AssertionError("CR01 digest mismatch")
        if report["capabilityInventory"]["blendshapes"]["count"] != 0:
            raise AssertionError("expected blendshapeCount=0 for Idle_15 product surface")
        required = set(report["augmentationRequired"])
        for cap in ("FACE_Rig_Root", "Eye", "Blink", "Jaw_Mouth", "Expression", "TALKING"):
            if cap not in required:
                raise AssertionError(f"expected augmentation required for {cap}")

        (REP / "V2_CR02_P01_capability_gap_idle15.json").write_text(
            json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_P01_PASS_receipt",
            "stage": "CR02-P01",
            "status": "PASS",
            "changeRequestId": "V2-CR-02",
            "revision": "R1",
            "idle15Sha256": IDLE15_SHA,
            "cr01Digest": CR01_DIGEST,
            "gapInspectionDigest": report["gapInspectionDigest"],
            "augmentationRequired": report["augmentationRequired"],
            "blendshapeCount": 0,
            "sourceImmutable": report["sourcePreservation"]["bytesUnchanged"],
            "v2Engine": "NOT OPEN",
            "CR01_REOPEN": "DENY",
            "next": "CR02-P02 FACE Attachment / Augmentation Plan",
        }
        (EV / "NURION-V2-CR02_P01_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
