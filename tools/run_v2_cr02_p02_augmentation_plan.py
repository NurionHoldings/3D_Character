#!/usr/bin/env python3
"""CR02-P02 — FACE attachment / augmentation plan seal (no weight apply, no derived GLB)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.inspector import sha256_file
from fast_track.v2_cr02.augmentation_plan import build_augmentation_plan
from fast_track.v2_cr02.capability_gap import CR01_DIGEST, IDLE15_SHA, inspect_capability_gap

IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"
P01_GAP_DIGEST = "fb7ba2dfd0471482e9ad44f881e44306550fb39138bb2cf010d3dabd2ef727ab"


def main() -> int:
    try:
        EV.mkdir(parents=True, exist_ok=True)
        REP.mkdir(parents=True, exist_ok=True)

        before = IDLE15.read_bytes()
        before_sha = sha256_file(IDLE15)

        gap = inspect_capability_gap(IDLE15)
        if gap["status"] != "PASS":
            raise AssertionError(f"P01 gap blocked: {gap.get('blockers')}")
        if gap["gapInspectionDigest"] != P01_GAP_DIGEST:
            raise AssertionError(
                f"gap digest drift: {gap['gapInspectionDigest']} != {P01_GAP_DIGEST}"
            )

        plan = build_augmentation_plan(gap)
        if plan["status"] != "PASS":
            raise AssertionError(f"P02 plan blocked: {plan.get('blockers')}")

        # P02 must not mutate source or create derived artifact
        after = IDLE15.read_bytes()
        after_sha = sha256_file(IDLE15)
        if before != after or before_sha != after_sha or after_sha != IDLE15_SHA:
            raise AssertionError("SOURCE MUTATION DETECTED AT P02")

        caps = plan["capabilityPlan"]
        for name in ("Eye_L", "Eye_R", "Blink_L", "Blink_R", "Jaw_Mouth", "Expression", "TALKING"):
            if name not in caps:
                raise AssertionError(f"missing capability plan: {name}")
            if caps[name].get("weightApplyAtP02") != "DENY":
                raise AssertionError(f"{name} must deny weight apply at P02")
            if caps[name].get("status") != "PLANNED":
                raise AssertionError(f"{name} expected PLANNED got {caps[name].get('status')}")

        if caps["Eye_L"]["capability"] == caps["Eye_R"]["capability"]:
            raise AssertionError("Eye_L must be distinct from Eye_R")
        if caps["TALKING"]["consumes"] != ["Jaw_Mouth"]:
            raise AssertionError("TALKING must consume Jaw_Mouth without being equal")
        if plan["safety"]["jawMouthEqualsTalking"] != "DENY":
            raise AssertionError("Jaw≠Talking safety missing")
        if plan["attachment"]["interface"] != "NURION_head → FACE_Rig_Root":
            raise AssertionError("attachment interface mismatch")
        if plan["input"]["cr01SemanticAdapterDigest"] != CR01_DIGEST:
            raise AssertionError("CR01 digest pin failed")

        # Determinism
        plan2 = build_augmentation_plan(gap)
        if plan["augmentationPlanDigest"] != plan2["augmentationPlanDigest"]:
            raise AssertionError("nondeterministic augmentationPlanDigest")

        (REP / "V2_CR02_P02_augmentation_plan_idle15.json").write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        receipt = {
            "receiptId": "NURION-V2-CR02_P02_PASS_receipt",
            "stage": "CR02-P02",
            "status": "PASS",
            "changeRequestId": "V2-CR-02",
            "revision": "R1",
            "planOnly": True,
            "weightApply": "DENY",
            "derivedArtifact": "NONE",
            "sourceImmutable": True,
            "idle15Sha256": IDLE15_SHA,
            "cr01Digest": CR01_DIGEST,
            "gapInspectionDigest": P01_GAP_DIGEST,
            "augmentationPlanDigest": plan["augmentationPlanDigest"],
            "attachment": plan["attachment"]["interface"],
            "resolvedHead": plan["attachment"]["resolvedHeadSourceBone"],
            "capabilitiesPlanned": sorted(caps.keys()),
            "v2Engine": "NOT OPEN",
            "CR01_REOPEN": "DENY",
            "next": "CR02-P03 Eye/Blink Augmentation — first derived character",
        }
        (EV / "NURION-V2-CR02_P02_PASS_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(json.dumps({"ok": True, **receipt}, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
