"""Aggregate v0.6 Gate 3 bone-mapping asset results."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nurion_v06_unified_runtime.gate3.parameters import (
    GATE1_PARAMETER_HASH_FROZEN,
    GATE2_PARAMETER_HASH_FROZEN,
    GATE3_PARAMETERS,
    parameter_hash,
)


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    gate3 = ROOT / "dist" / "v0.6" / "gate3"
    assets = []
    for p in sorted(gate3.glob("*/V06_GATE3_ASSET_STATUS.json")):
        assets.append(json.loads(p.read_text(encoding="utf-8")))
    if not assets:
        print("no assets", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ph = parameter_hash()
    actions = {a["label"]: a.get("runtimeAction") for a in assets}
    verdicts = {a["label"]: a.get("mappingVerdict") for a in assets}
    mut = sum(int(a.get("sourceMutation") or 0) for a in assets)
    manual = sum(int(a.get("manualMappingCount") or 0) for a in assets)
    tune = sum(int(a.get("assetSpecificTuningCount") or 0) for a in assets)
    hard = []
    if mut:
        hard.append("SOURCE_MUTATION_NONZERO")
    if manual:
        hard.append("MANUAL_MAPPING_NONZERO")
    if tune:
        hard.append("ASSET_TUNING_NONZERO")
    if any(a.get("gate1ParameterHash") != GATE1_PARAMETER_HASH_FROZEN for a in assets):
        hard.append("GATE1_HASH_DRIFT")
    if any(a.get("gate2ParameterHash") != GATE2_PARAMETER_HASH_FROZEN for a in assets):
        hard.append("GATE2_HASH_DRIFT")

    ok = all(v in ("PASS", "PASS_WITH_LIMITATIONS") for v in verdicts.values()) and not hard
    track_verdict = "PASS_WITH_LIMITATIONS" if ok else "FAIL"
    if ok and all(a.get("runtimeAction") == "APPLY_LIMITED_MAPPING" and not a.get("abstainReasons") for a in assets):
        track_verdict = "PASS"

    receipt = {
        "schema": "NURION_V06_GATE3_RECEIPT",
        "gate": "3",
        "name": "UNIFIED_BONE_MAPPING",
        "V06_GATE3": track_verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "gate2Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": mut,
        "manualMappingTotal": manual,
        "assetSpecificTuningTotal": tune,
        "inheritedLimitationsFromV05": GATE3_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "assets": [
            {
                "label": a["label"],
                "gate2Classification": a.get("gate2Classification"),
                "mappingVerdict": a.get("mappingVerdict"),
                "runtimeAction": a.get("runtimeAction"),
                "bodyCoreOk": a.get("bodyCoreOk"),
                "mappingSufficient": a.get("mappingSufficient"),
                "abstainReasons": a.get("abstainReasons"),
                "sourceMutation": a.get("sourceMutation"),
                "manualMappingCount": a.get("manualMappingCount"),
            }
            for a in assets
        ],
        "hardFails": hard,
        "updatedAt": now,
        "next": "GATE4_BODY_FACE_EYE_BIND",
    }
    status = {
        "schema": "NURION_V06_GATE3_STATUS",
        "gate": "3",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "UNIFIED_BONE_MAPPING",
        "V06_GATE3": track_verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "gate2Locked": True,
        "production": "NO-GO",
        "runtimeActions": actions,
        "sourceMutationTotal": mut,
        "manualMappingTotal": manual,
        "inheritedLimitationsFromV05": GATE3_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": hard,
        "updatedAt": now,
        "artifacts": {"receipt": "V06_GATE3_RECEIPT.json", "parameters": "V06_GATE3_PARAMETERS.json"},
        "next": "GATE4_BODY_FACE_EYE_BIND",
    }
    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE3",
        "status": "IN_PROGRESS",
        "V06_GATE1": "PASS",
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "V06_GATE2": "PASS_WITH_LIMITATIONS",
        "gate2ParameterHash": GATE2_PARAMETER_HASH_FROZEN,
        "gate2Locked": True,
        "V06_GATE3": track_verdict,
        "gate3ParameterHash": ph,
        "production": "NO-GO",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE3_PARAMETERS["inheritedLimitationsFromV05"],
        "next": "GATE4_BODY_FACE_EYE_BIND",
        "updatedAt": now,
    }

    _write(gate3 / "V06_GATE3_PARAMETERS.json", GATE3_PARAMETERS)
    _write(gate3 / "V06_GATE3_RECEIPT.json", receipt)
    _write(gate3 / "V06_GATE3_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)
    print(json.dumps({"V06_GATE3": track_verdict, "parameterHash": ph, "runtimeActions": actions}, indent=2))
    return 0 if track_verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
