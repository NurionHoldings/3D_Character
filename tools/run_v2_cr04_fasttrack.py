#!/usr/bin/env python3
"""CR04 P01–P06 fail-closed fast-track (second Meshy asset generalization)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr04.audit_paths import resolve_v2_cr04_roots
from fast_track.v2_cr04.fasttrack import run_fasttrack


def main() -> int:
    roots = resolve_v2_cr04_roots(__file__)
    sem = Path(roots["semantic"])
    track_path = sem / "NURION_ADAPTATION_ENGINE_V2_CR04_TRACK_V1.json"
    spec_path = (
        sem / "NURION_ADAPTATION_ENGINE_V2_CR04_SECOND_REAL_MESHY_ASSET_GENERALIZATION_SPEC_R1.json"
    )
    track = json.loads(track_path.read_text(encoding="utf-8"))

    # Require pin before run
    if (track.get("secondAsset") or {}).get("status") != "PINNED":
        # allow if pin receipt exists and update track
        pin = Path(roots["evidence"]) / "NURION-V2-CR04_SECOND_ASSET_PIN_receipt.json"
        if not pin.is_file():
            print(json.dumps({"status": "BLOCKED", "reason": "secondAsset NOT_PINNED"}))
            return 1
        pin_doc = json.loads(pin.read_text(encoding="utf-8"))
        track["secondAsset"] = {
            "status": "PINNED",
            "sha256": pin_doc["secondAsset"]["sha256"],
            "path": pin_doc["secondAsset"]["workspaceBaseline"],
            "characterFamily": pin_doc["secondAsset"]["characterFamily"],
        }
        track["phase"] = "IMPLEMENTATION"
        track["stages"]["CR04-P01"] = "AUTHORIZED"

    result = run_fasttrack(track=track, spec_path=spec_path, roots=roots)
    print(json.dumps(result, indent=2, ensure_ascii=True))

    if result.get("status") == "READY_FOR_HUMAN_AUDIT":
        track["phase"] = "READY_FOR_HUMAN_AUDIT"
        track["stages"] = {
            "CR04-P01": "PASS",
            "CR04-P02": "PASS",
            "CR04-P03": "PASS",
            "CR04-P04": "PASS",
            "CR04-P05": "PASS",
            "CR04-P06": "PASS",
            "CR04-P07": "HUMAN_FINAL_ONLY",
        }
        track["pins"] = {
            "secondAssetSha256": result["secondAssetSha256"],
            "derivedSha256": result["derivedSha256"],
            "finalCandidateSemanticDigest": result["finalCandidateSemanticDigest"],
            "runtimeProofDigest": result["runtimeProofDigest"],
            "approvedSpecDigest": track["humanSpecGate"]["approvedSpecDigest"],
        }
        track["next"] = "CR04-P07 / G20 Human Final — Agent PASS deny"
        track_path.write_text(json.dumps(track, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
