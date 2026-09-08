#!/usr/bin/env python3
"""Independent ADAPT-01 proof — stdlib + packaged adaptation only. Exit 0 on G01–G15."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

here = Path(__file__).resolve()
parent = here.parents[1]
if parent.name == "repo":
    sys.path.insert(0, str(parent))
else:
    sys.path.insert(0, str(Path(os.environ.get("NURION_REPO_ROOT", str(parent)))))


def main() -> int:
    from tools.run_adapt01_inspection_proof import run_all

    summary = run_all()
    out = {
        "independentRunner": True,
        "revision": "R1",
        "exitPolicy": "0 iff automated AD1-G01..G15 PASS",
        "executionMode": summary.get("executionMode"),
        "agentStatus": summary["agentStatus"],
        "productPass": "NOT_DECLARED",
        "adapt01Pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "AD1-G16": "HUMAN_FINAL_ONLY",
        "automatedGatePassCount": summary["automatedGatePassCount"],
        "nurionV1Mutation": summary["nurionV1Mutation"]["mutation"],
        "adapt02": "NOT_STARTED",
        "noProductRuntimeImport": True,
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    return 0 if summary["automatedGatePassCount"] == 15 else 1


if __name__ == "__main__":
    raise SystemExit(main())
