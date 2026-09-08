#!/usr/bin/env python3
"""CR02-P06 — Idle_15 end-to-end real-asset proof seal (no new capability / no rewrite)."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

here = Path(__file__).resolve()
parent = here.parents[1]
if parent.name == "repo":
    sys.path.insert(0, str(parent))
else:
    sys.path.insert(0, str(Path(os.environ.get("NURION_REPO_ROOT", str(parent)))))

from fast_track.v2_cr02.audit_paths import resolve_v2_cr02_roots
from fast_track.v2_cr02.real_asset_proof import (
    P04_DERIVED_SHA,
    P05_CLASSIFICATION,
    P05_QUAL_DIGEST,
    seal_real_asset_proof,
)


def run_all(script_file: str | Path | None = None) -> dict:
    r = resolve_v2_cr02_roots(script_file or __file__)
    EV: Path = r["evidence"]
    REP: Path = r["reports"]
    DER: Path = r["derived"]
    IDLE15: Path = r["idle15"]
    EV.mkdir(parents=True, exist_ok=True)
    REP.mkdir(parents=True, exist_ok=True)

    p03 = DER / "Idle_15_P03_eye_blink.glb"
    p04 = DER / "Idle_15_P04_jaw_expression_talking.glb"
    p05_path = REP / "V2_CR02_P05_runtime_qualification_idle15.json"
    if not p05_path.is_file():
        # extracted package may place under reports/
        alt = Path(r["packageRoot"]) / "reports" / "V2_CR02_P05_runtime_qualification_idle15.json"
        if alt.is_file():
            p05_path = alt

    p05 = json.loads(p05_path.read_text(encoding="utf-8"))
    # Carry-forward check before seal
    if p05.get("classification") != P05_CLASSIFICATION:
        raise AssertionError("P05 classification must remain QUALIFIED_WITH_LIMITATIONS")
    if p05.get("qualificationDigest") != P05_QUAL_DIGEST:
        raise AssertionError("P05 qualificationDigest mismatch")

    seal = seal_real_asset_proof(
        idle15=IDLE15,
        p03_derived=p03,
        p04_derived=p04,
        p05_report=p05,
    )
    if seal["status"] != "READY_FOR_HUMAN_AUDIT":
        raise AssertionError(f"P06 seal failed: {seal.get('blockers')}")

    (REP / "V2_CR02_P06_real_asset_proof_seal.json").write_text(
        json.dumps(seal, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR02_gate_matrix.json").write_text(
        json.dumps({"gates": seal["gates"], "chain": seal["provenanceChain"]}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    receipt = {
        "receiptId": "NURION-V2-CR02_READY_FOR_HUMAN_AUDIT_R1",
        "stage": "CR02-P06",
        "status": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "CR02-G20": "HUMAN_FINAL_ONLY",
        "CR02-P07": "HUMAN_FINAL_ONLY",
        "changeRequestId": "V2-CR-02",
        "revision": "R1",
        "realAssetProofDigest": seal["realAssetProofDigest"],
        "finalCandidateSha256": P04_DERIVED_SHA,
        "runtimeQualification": P05_CLASSIFICATION,
        "limitationsCarriedForward": seal["limitations"],
        "v2Engine": "NOT OPEN",
        "CR01_REOPEN": "DENY",
        "agentMayNotPassG20": True,
    }
    (EV / "NURION-V2-CR02_READY_FOR_HUMAN_AUDIT_receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR02_P06_PASS_receipt.json").write_text(
        json.dumps(
            {
                "receiptId": "NURION-V2-CR02_P06_PASS_receipt",
                "stage": "CR02-P06",
                "status": "PASS",
                "agentCeiling": "READY_FOR_HUMAN_AUDIT",
                "passDeclaredByAgent": False,
                "realAssetProofDigest": seal["realAssetProofDigest"],
                "finalCandidateSha256": P04_DERIVED_SHA,
                "runtimeQualification": P05_CLASSIFICATION,
                "limitations": seal["limitations"],
                "next": "CR02-P07 / CR02-G20 HUMAN FINAL AUDIT",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return seal


def main() -> int:
    try:
        s = run_all(__file__)
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": s["status"],
                    "pass": "NOT_DECLARED",
                    "CR02-G20": "HUMAN_FINAL_ONLY",
                    "realAssetProofDigest": s["realAssetProofDigest"],
                    "finalCandidateSha256": s["finalCandidate"]["sha256"],
                    "runtimeQualification": s["runtimeQualification"],
                    "limitations": s["limitations"],
                    "v2Engine": "NOT OPEN",
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
