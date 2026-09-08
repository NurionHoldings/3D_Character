#!/usr/bin/env python3
"""CR02-P03 — Eye/Blink augmentation ONLY (first derived character)."""

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
from fast_track.v2_cr02.eye_blink_augmentation import P03_AUTHORIZED, P03_FORBIDDEN, run_p03_eye_blink_augmentation

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
DERIVED = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_P03_eye_blink.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"

P01_GAP_DIGEST = "fb7ba2dfd0471482e9ad44f881e44306550fb39138bb2cf010d3dabd2ef727ab"
P02_PLAN_DIGEST = "857438ca4948ee53d61d71d4ae012ae4b0a7d4df1ae10a41e102282b94fdc170"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)

        gap = inspect_capability_gap(IDLE15)
        if gap["gapInspectionDigest"] != P01_GAP_DIGEST:
            raise AssertionError("P01 gap digest mismatch")
        plan = build_augmentation_plan(gap)
        if plan["augmentationPlanDigest"] != P02_PLAN_DIGEST:
            raise AssertionError("P02 plan digest mismatch")

        result = run_p03_eye_blink_augmentation(
            IDLE15,
            DERIVED,
            plan=plan,
            gap_report=gap,
            cr01_digest=CR01_DIGEST,
        )
        if result["status"] != "PASS":
            raise AssertionError(f"P03 blocked: {result.get('blockers')}")

        _ok = lambda c, m: (_ for _ in ()).throw(AssertionError(m)) if not c else None
        _ok(result["sourcePreservation"]["immutable"], "source not immutable")
        _ok(result["derivedArtifact"]["derivedAssetSha256"], "missing derived sha")
        _ok(result["attachment"]["status"] == "VALID", "attachment invalid")
        _ok(result["attachment"]["interface"] == "NURION_head → FACE_Rig_Root", "interface")
        _ok(result["safety"]["globalAutoWeight"] == "DENY", "global weight")
        _ok(result["provenance"]["bodyWeightChanges"] == "NONE", "body weight changes")

        fe = result["functionalEvidence"]
        for cap in P03_AUTHORIZED:
            _ok(fe[cap]["functionalTest"] == "PASS", f"{cap} functional fail")
            _ok(len(fe[cap]["trace"]) == 3, f"{cap} trace must be 3-state")
        _ok(fe["crossContamination"]["status"] == "PASS", "cross contamination")
        _ok(fe["dualBlink"]["bothClosed"], "dual blink")

        # Eye ≠ Blink: eye activation must not equal blink closure metric
        _ok("rotation" in fe["Eye_L"]["trace"][1], "Eye_L uses rotation not eyelid")
        _ok("eyelidClosure" in fe["Blink_L"]["trace"][1], "Blink_L uses eyelid not gaze")

        forbidden_nodes = [n for n in (result["provenance"].get("affectedNodes") or []) if any(f in n for f in ("JAW", "EXPR", "TALK", "VISEME"))]
        _ok(not forbidden_nodes, f"P03 forbidden nodes: {forbidden_nodes}")

        (REP / "V2_CR02_P03_eye_blink_idle15.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_P03_PASS_receipt",
            "stage": "CR02-P03",
            "status": "PASS",
            "changeRequestId": "V2-CR-02",
            "revision": "R1",
            "scope": sorted(P03_AUTHORIZED),
            "forbiddenNotApplied": sorted(P03_FORBIDDEN),
            "sourceImmutable": True,
            "idle15Sha256": IDLE15_SHA,
            "cr01Digest": CR01_DIGEST,
            "gapInspectionDigest": P01_GAP_DIGEST,
            "augmentationPlanDigest": P02_PLAN_DIGEST,
            "derivedAssetSha256": result["derivedArtifact"]["derivedAssetSha256"],
            "derivedPath": str(DERIVED),
            "faceRigRootIdentity": result["provenance"]["faceRigRootIdentity"],
            "functionalEvidenceDigest": result["functionalEvidenceDigest"],
            "p03DerivedSemanticDigest": result["p03DerivedSemanticDigest"],
            "p03ResultDigest": result["p03ResultDigest"],
            "v2Engine": "NOT OPEN",
            "CR01_REOPEN": "DENY",
            "next": "CR02-P04 Jaw/Expression/TALKING Augmentation",
        }
        (EV / "NURION-V2-CR02_P03_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
