#!/usr/bin/env python3
"""CR03-P01 Runtime Talking Contract / Morph Binding Inspection."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr03.audit_paths import resolve_v2_cr03_roots
from fast_track.v2_cr03.p01_morph_binding import inspect_morph_binding, write_report


def main() -> int:
    roots = resolve_v2_cr03_roots(__file__)
    pkg = Path(roots["packageRoot"])
    sem = Path(roots["semantic"])
    ev = Path(roots["evidence"])
    rep = Path(roots["reports"])
    rep.mkdir(parents=True, exist_ok=True)

    track_path = sem / "NURION_ADAPTATION_ENGINE_V2_CR03_TRACK_V1.json"
    spec_path = (
        sem / "NURION_ADAPTATION_ENGINE_V2_CR03_MORPH_WEIGHT_RUNTIME_TALKING_SEQUENCE_SPEC_R1.json"
    )
    track = json.loads(track_path.read_text(encoding="utf-8"))
    input_glb = Path(roots["cr02Derived"])

    report = inspect_morph_binding(
        input_glb=input_glb,
        track=track,
        spec_path=spec_path,
    )
    report_path = rep / "V2_CR03_P01_morph_binding_idle15.json"
    report_sha = write_report(report, report_path)

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = {
        "receiptId": "NURION-V2-CR03_P01_PASS" if report["status"] == "PASS" else "NURION-V2-CR03_P01_BLOCKED",
        "changeRequestId": "V2-CR-03",
        "stage": "CR03-P01",
        "status": report["status"],
        "declaredAtUtc": utc,
        "approvedSpecDigest": track["humanSpecGate"]["approvedSpecDigest"],
        "inputSha256": report["input"]["sha256"],
        "morphIndexMap": report.get("morphIndexMap"),
        "reportPath": str(report_path.relative_to(pkg)).replace("\\", "/"),
        "reportSha256": report_sha,
        "agentCeiling": "READY_FOR_HUMAN_AUDIT",
        "note": "P01 binding only — not temporal talking PASS; Gate infra ≠ technical PASS",
        "next": report.get("next"),
    }
    receipt_name = (
        "NURION-V2-CR03_P01_PASS_receipt.json"
        if report["status"] == "PASS"
        else "NURION-V2-CR03_P01_BLOCKED_receipt.json"
    )
    receipt_path = ev / receipt_name
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Advance stage markers on track if PASS (authority remains GRANTED)
    if report["status"] == "PASS":
        track["stages"]["CR03-P01"] = "PASS"
        track["stages"]["CR03-P02"] = "AUTHORIZED"
        track["updatedAtUtc"] = utc
        track["next"] = "CR03-P02 Morph-Weight Animation Injection"
        track_path.write_text(json.dumps(track, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"status": report["status"], "report": str(report_path), "receipt": str(receipt_path)}, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
