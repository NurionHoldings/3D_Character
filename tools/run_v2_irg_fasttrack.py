#!/usr/bin/env python3
"""V2-IRG-01 FAST-TRACK runner — P01…P05 (+ P06 via packer)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_irg.audit_paths import resolve_v2_irg_roots
from fast_track.v2_irg.fasttrack import run_fasttrack


def main() -> int:
    roots = resolve_v2_irg_roots(__file__)
    sem = Path(roots["semantic"])
    track = json.loads((sem / "NURION_ADAPTATION_ENGINE_V2_IRG_TRACK_V1.json").read_text(encoding="utf-8"))
    spec = sem / "NURION_ADAPTATION_ENGINE_V2_INTEGRATION_RELEASE_GATE_SPEC_R1.json"
    result = run_fasttrack(track=track, spec_path=spec, roots=roots)
    summary = {
        "status": result.get("status"),
        "stoppedAt": result.get("stoppedAt"),
        "blockers": result.get("blockers"),
        "digests": (result.get("report") or {}).get("digests") or (result.get("ready") or {}),
        "engineV2": "NOT_OPEN",
    }
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    if result.get("status") == "READY_FOR_HUMAN_AUDIT":
        track["phase"] = "READY_FOR_HUMAN_AUDIT"
        track["status"] = "OPEN_PROTOTYPE"
        track["pins"] = summary.get("digests")
        (sem / "NURION_ADAPTATION_ENGINE_V2_IRG_TRACK_V1.json").write_text(
            json.dumps(track, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
