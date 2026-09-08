"""Pack NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip (Gate9)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nurion_v05_body_motion.gate9.packaging import pack_rc1, sha256_file  # noqa: E402
from nurion_v05_body_motion.gate9.parameters import INHERITED_LIMITATIONS, VERSION  # noqa: E402


def main() -> int:
    status = {
        "schema": "NURION_V05_RC1_VALIDATION_STATUS",
        "version": VERSION,
        "releaseCandidate": True,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "SEALED": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "repack": "DENY",
        "parameterTuning": 0,
        "manualCorrection": 0,
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "gate1to8ParameterChange": 0,
        "packedAt": datetime.now(timezone.utc).isoformat(),
        "note": "RC.1 only — do not seal. Fresh Holdout required next.",
    }
    path, manifest = pack_rc1(root=ROOT, validation_status=status)
    print(json.dumps({"package": str(path), "sha256": sha256_file(path), "manifest": manifest}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
