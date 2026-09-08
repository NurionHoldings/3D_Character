"""Aggregate v0.6 Gate 5 motion-preset results."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nurion_v06_unified_runtime.gate5.parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETER_HASH_FROZEN,
    GATE4_PARAMETER_HASH_FROZEN,
    GATE5_PARAMETERS,
    parameter_hash,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    gate5 = ROOT / "dist" / "v0.6" / "gate5"
    assets = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(gate5.glob("*/V06_GATE5_ASSET_STATUS.json"))]
    if not assets:
        print("no assets", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ph = parameter_hash()
    actions = {a["label"]: a.get("runtimeAction") for a in assets}
    verdicts = {a["label"]: a.get("presetVerdict") for a in assets}
    mut = sum(int(a.get("sourceMutation") or 0) for a in assets)
    manual = sum(int(a.get("manualCorrection") or 0) for a in assets)
    hard = []
    if mut:
        hard.append("SOURCE_MUTATION_NONZERO")
    if manual:
        hard.append("MANUAL_CORRECTION_NONZERO")
    if any(a.get("gate4ParameterHash") != GATE4_PARAMETER_HASH_FROZEN for a in assets):
        hard.append("GATE4_HASH_DRIFT")

    ok = all(v in ("PASS", "PASS_WITH_LIMITATIONS") for v in verdicts.values()) and not hard
    track_verdict = "PASS_WITH_LIMITATIONS" if ok else "FAIL"

    receipt = {
        "schema": "NURION_V06_GATE5_RECEIPT",
        "gate": "5",
        "name": "MOTION_PRESET",
        "V06_GATE5": track_verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
        "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
        "gate4Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": mut,
        "manualCorrectionTotal": manual,
        "inheritedLimitationsFromV05": GATE5_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "assets": [
            {
                "label": a["label"],
                "presetVerdict": a.get("presetVerdict"),
                "runtimeAction": a.get("runtimeAction"),
                "availablePresets": a.get("availablePresets"),
                "unavailablePresets": a.get("unavailablePresets"),
                "lipsyncMode": a.get("lipsyncMode"),
                "abstainReasons": a.get("abstainReasons"),
            }
            for a in assets
        ],
        "hardFails": hard,
        "updatedAt": now,
        "next": "GATE6_BLENDER_OPERATOR_WORKFLOW",
    }
    status = {
        "schema": "NURION_V06_GATE5_STATUS",
        "gate": "5",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "MOTION_PRESET",
        "V06_GATE5": track_verdict,
        "parameterHash": ph,
        "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
        "gate4Locked": True,
        "production": "NO-GO",
        "runtimeActions": actions,
        "sourceMutationTotal": mut,
        "inheritedLimitationsFromV05": GATE5_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": hard,
        "updatedAt": now,
        "artifacts": {"receipt": "V06_GATE5_RECEIPT.json", "parameters": "V06_GATE5_PARAMETERS.json"},
        "next": "GATE6_BLENDER_OPERATOR_WORKFLOW",
    }
    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE5",
        "status": "IN_PROGRESS",
        "V06_GATE1": "PASS",
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "V06_GATE2": "PASS_WITH_LIMITATIONS",
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate2Locked": True,
        "V06_GATE3": "PASS_WITH_LIMITATIONS",
        "gate3ParameterHash": GATE3_PARAMETER_HASH_FROZEN,
        "gate3Locked": True,
        "V06_GATE4": "PASS_WITH_LIMITATIONS",
        "gate4ParameterHash": GATE4_PARAMETER_HASH_FROZEN,
        "gate4Locked": True,
        "V06_GATE5": track_verdict,
        "gate5ParameterHash": ph,
        "production": "NO-GO",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE5_PARAMETERS["inheritedLimitationsFromV05"],
        "next": "GATE6_BLENDER_OPERATOR_WORKFLOW",
        "updatedAt": now,
    }

    _write(gate5 / "V06_GATE5_PARAMETERS.json", GATE5_PARAMETERS)
    _write(gate5 / "V06_GATE5_RECEIPT.json", receipt)
    _write(gate5 / "V06_GATE5_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)
    print(json.dumps({"V06_GATE5": track_verdict, "parameterHash": ph, "runtimeActions": actions}, indent=2))
    return 0 if track_verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
