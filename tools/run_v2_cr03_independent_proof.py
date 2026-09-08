#!/usr/bin/env python3
"""Independent CR03 proof — GLB-measured; do not trust report PASS."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr03.audit_paths import resolve_v2_cr03_roots
from fast_track.v2_cr03.independent_gates import run_cr03_independent_gates


def main() -> int:
    roots = resolve_v2_cr03_roots(__file__)
    sem = Path(roots["semantic"])
    rep = Path(roots["reports"])
    der = Path(roots["derived"])
    track = json.loads(
        (sem / "NURION_ADAPTATION_ENGINE_V2_CR03_TRACK_V1.json").read_text(encoding="utf-8")
    )
    spec = sem / "NURION_ADAPTATION_ENGINE_V2_CR03_MORPH_WEIGHT_RUNTIME_TALKING_SEQUENCE_SPEC_R1.json"
    matrix = run_cr03_independent_gates(
        input_glb=Path(roots["cr02Derived"]),
        derived_glb=der / "Idle_15_CR03_talking_weights.glb",
        track=track,
        spec_path=spec,
    )
    out = rep / "V2_CR03_independent_gate_matrix.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(matrix, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": matrix["status"], "blockers": matrix.get("blockers")}, indent=2))
    return 0 if matrix["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
