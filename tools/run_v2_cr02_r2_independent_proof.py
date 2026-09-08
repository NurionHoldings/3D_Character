#!/usr/bin/env python3
"""CR02-R2 independent proof — GLB morph POSITION measurement only (no report trust)."""

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
    package = here.parents[2]
    idle15 = package / "assets" / "Idle_15_withSkin_WORKING_BASELINE.glb"
    derived = package / "derived" / "Idle_15_R2_facial_deformation.glb"
    ev = package / "evidence"
    rep = package / "reports"
else:
    root = Path(os.environ.get("NURION_REPO_ROOT", str(parent)))
    sys.path.insert(0, str(root))
    idle15 = root / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
    derived = root / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_R2_facial_deformation.glb"
    ev = root / "fast_track/working/adaptation_engine_v2/evidence"
    rep = root / "fast_track/working/adaptation_engine_v2/reports_cr02"

from fast_track.v2_cr02.r2_independent_gates import run_independent_gates


def main() -> int:
    try:
        ev.mkdir(parents=True, exist_ok=True)
        rep.mkdir(parents=True, exist_ok=True)
        result = run_independent_gates(original=idle15, derived=derived)
        if result["status"] != "READY_FOR_HUMAN_AUDIT":
            raise AssertionError(f"independent gates blocked: {result.get('blockers')}")

        (rep / "V2_CR02_R2_independent_gate_matrix.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (ev / "NURION-V2-CR02_R2_READY_FOR_HUMAN_AUDIT_receipt.json").write_text(
            json.dumps(
                {
                    "receiptId": "NURION-V2-CR02_R2_READY_FOR_HUMAN_AUDIT_R1",
                    "revision": "R2",
                    "status": "READY_FOR_HUMAN_AUDIT",
                    "pass": "NOT_DECLARED",
                    "CR02-R2-G20": "HUMAN_FINAL_ONLY",
                    "independentProofDigest": result["independentProofDigest"],
                    "agentReportedProofDigest": result["agentReportedProofDigest"],
                    "agentReportedOnly": True,
                    "measurementPolicy": result["measurementPolicy"],
                    "thresholds": result["thresholds"],
                    "v2Engine": "NOT OPEN",
                    "r1Status": "HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED",
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "ok": True,
                    "status": result["status"],
                    "pass": "NOT_DECLARED",
                    "CR02-R2-G20": "HUMAN_FINAL_ONLY",
                    "independentProofDigest": result["independentProofDigest"],
                    "agentReportedProofDigest": result["agentReportedProofDigest"],
                    "agentReportedOnly": True,
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
