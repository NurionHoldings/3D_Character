#!/usr/bin/env python3
"""CR02-P04 — Jaw/Expression/TALKING ONLY; preserve P03 Eye/Blink (regression)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.v2_cr02.augmentation_plan import build_augmentation_plan
from fast_track.v2_cr02.capability_gap import CR01_DIGEST, IDLE15_SHA, inspect_capability_gap
from fast_track.v2_cr02.jaw_expression_talking import P04_AUTHORIZED, P04_PRESERVE, run_p04_jaw_expression_talking

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
P03_DERIVED = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_P03_eye_blink.glb"
P04_DERIVED = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_P04_jaw_expression_talking.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"

P02_PLAN_DIGEST = "857438ca4948ee53d61d71d4ae012ae4b0a7d4df1ae10a41e102282b94fdc170"
P03_DERIVED_SHA = "a0f3b76c12b1055170f1330bda402be6c6073783c182fd92bfffea6ddbfa5fc7"
P03_SEMANTIC = "8dca89f8061fa05539eb06e670ceb813bb269dc97b357d0f53b35235b9772b04"
P03_FUNC = "b107fa0c72ec206230d11631af6903720306a146e95c146bc1fe85f1c915720a"
P01_GAP = "fb7ba2dfd0471482e9ad44f881e44306550fb39138bb2cf010d3dabd2ef727ab"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)

        gap = inspect_capability_gap(IDLE15)
        plan = build_augmentation_plan(gap)
        if plan["augmentationPlanDigest"] != P02_PLAN_DIGEST:
            raise AssertionError("P02 plan digest mismatch")

        p03_receipt = {
            "derivedAssetSha256": P03_DERIVED_SHA,
            "p03DerivedSemanticDigest": P03_SEMANTIC,
            "functionalEvidenceDigest": P03_FUNC,
            "gapInspectionDigest": P01_GAP,
            "augmentationPlanDigest": P02_PLAN_DIGEST,
        }

        result = run_p04_jaw_expression_talking(
            P03_DERIVED,
            P04_DERIVED,
            original_source_path=IDLE15,
            plan=plan,
            p03_receipt=p03_receipt,
            cr01_digest=CR01_DIGEST,
            original_source_sha=IDLE15_SHA,
        )
        if result["status"] != "PASS":
            raise AssertionError(f"P04 blocked: {result.get('blockers')}")

        def _ok(c: bool, m: str) -> None:
            if not c:
                raise AssertionError(m)

        _ok(result["p03Regression"]["status"] == "PASS", "P03 regression failed")
        for cap in P04_PRESERVE:
            _ok(result["p03Regression"]["functional"][cap]["functionalTest"] == "PASS", f"regression {cap}")
        for cap in P04_AUTHORIZED:
            _ok(result["functionalEvidence"][cap]["functionalTest"] == "PASS", f"{cap} fail")

        fe = result["functionalEvidence"]
        _ok(fe["independence"]["jawEqualsTalking"] is False, "Jaw must ≠ TALKING")
        _ok(fe["TALKING"]["changingMouthStates"] is True, "TALKING needs changing states")
        _ok(fe["TALKING"]["staticOpenPose"] is False, "static open forbidden")
        _ok(fe["Expression"]["distinctDeformations"] is True, "expressions not distinct")
        _ok(result["safety"]["globalAutoWeight"] == "DENY", "global weight")
        _ok(result["originalSourcePreservation"]["immutable"], "source mutated")

        (REP / "V2_CR02_P04_jaw_expression_talking_idle15.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_P04_PASS_receipt",
            "stage": "CR02-P04",
            "status": "PASS",
            "changeRequestId": "V2-CR-02",
            "revision": "R1",
            "scope": sorted(P04_AUTHORIZED),
            "p03Preserved": sorted(P04_PRESERVE),
            "p03Regression": "PASS",
            "inputP03Sha256": P03_DERIVED_SHA,
            "p03DerivedSemanticDigest": P03_SEMANTIC,
            "derivedAssetSha256": result["derivedArtifact"]["derivedAssetSha256"],
            "derivedPath": str(P04_DERIVED),
            "functionalEvidenceDigest": result["functionalEvidenceDigest"],
            "p04DerivedSemanticDigest": result["p04DerivedSemanticDigest"],
            "p04ResultDigest": result["p04ResultDigest"],
            "originalSourceImmutable": True,
            "idle15Sha256": IDLE15_SHA,
            "v2Engine": "NOT OPEN",
            "CR01_REOPEN": "DENY",
            "next": "CR02-P05 BODY+FACE Coexistence / Runtime Qualification",
        }
        (EV / "NURION-V2-CR02_P04_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
