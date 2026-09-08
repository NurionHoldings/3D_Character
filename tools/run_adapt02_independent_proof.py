#!/usr/bin/env python3
"""Independent ADAPT-02 proof — stdlib + packaged adaptation only."""

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
    from tools.run_adapt02_inspection_proof import run_all

    summary = run_all()
    print(
        json.dumps(
            {
                "independentRunner": True,
                "revision": "R2",
                "executionMode": summary.get("executionMode"),
                "agentStatus": summary["agentStatus"],
                "adapt02Pass": "NOT_DECLARED",
                "AD2-G20": "HUMAN_FINAL_ONLY",
                "automatedGatePassCount": summary["automatedGatePassCount"],
                "nurionV1Mutation": summary["nurionV1Mutation"],
                "adapt01Mutation": summary["adapt01Mutation"],
                "adapt03": "NOT_STARTED",
                "noProductRuntimeImport": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary["automatedGatePassCount"] == 19 else 1


if __name__ == "__main__":
    raise SystemExit(main())
