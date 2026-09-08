"""Aggregate v0.6 Gate 2 multi-asset diagnosis into track status."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nurion_v06_unified_runtime.gate2.parameters import GATE1_PARAMETER_HASH_FROZEN, GATE2_PARAMETERS, parameter_hash


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    gate2 = ROOT / "dist" / "v0.6" / "gate2"
    assets = []
    for status_path in sorted(gate2.glob("*/V06_GATE2_ASSET_STATUS.json")):
        doc = json.loads(status_path.read_text(encoding="utf-8"))
        assets.append(doc)

    if not assets:
        print("no asset statuses found", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    ph = parameter_hash()
    classes = {a["label"]: a.get("assetClassification") for a in assets}
    diagnoses = {a["label"]: a.get("diagnosisVerdict") for a in assets}
    mut = sum(int(a.get("sourceMutation") or 0) for a in assets)
    det_fail = [a["label"] for a in assets if a.get("determinism") != "PASS"]
    hard = []
    if mut != 0:
        hard.append("SOURCE_MUTATION_NONZERO")
    if det_fail:
        hard.append("DETERMINISM_FAIL")
    if any(a.get("gate1ParameterHash") != GATE1_PARAMETER_HASH_FROZEN for a in assets):
        hard.append("GATE1_HASH_DRIFT")

    # Gate 2 track verdict: PASS if all asset diagnoses succeeded (incl. INELIGIBLE ABSTAIN)
    asset_diag_ok = all(v in ("PASS", "PASS_WITH_LIMITATIONS") for v in diagnoses.values())
    verdict = "PASS" if asset_diag_ok and not hard else "FAIL"
    if verdict == "PASS" and any(c == "LIMITED" for c in classes.values()):
        verdict = "PASS_WITH_LIMITATIONS"

    receipt = {
        "schema": "NURION_V06_GATE2_RECEIPT",
        "gate": "2",
        "name": "AUTO_ASSET_DIAGNOSIS",
        "V06_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "production": "NO-GO",
        "sourceMutationTotal": mut,
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE2_PARAMETERS["inheritedLimitationsFromV05"],
        "assets": [
            {
                "label": a["label"],
                "classification": a.get("assetClassification"),
                "runtimeAction": a.get("runtimeAction"),
                "diagnosisVerdict": a.get("diagnosisVerdict"),
                "abstainReasons": a.get("abstainReasons"),
                "pathStatus": a.get("pathStatus"),
                "zipSha256": a.get("zipSha256"),
                "fbxSha256": a.get("fbxSha256"),
            }
            for a in assets
        ],
        "hardFails": hard,
        "updatedAt": now,
        "next": "GATE3_UNIFIED_BONE_MAPPING",
    }

    status = {
        "schema": "NURION_V06_GATE2_STATUS",
        "gate": "2",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "AUTO_ASSET_DIAGNOSIS",
        "V06_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "production": "NO-GO",
        "classifications": classes,
        "sourceMutationTotal": mut,
        "inheritedLimitationsFromV05": GATE2_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "hardFails": hard,
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_GATE2_RECEIPT.json",
            "parameters": "V06_GATE2_PARAMETERS.json",
        },
        "next": "GATE3_UNIFIED_BONE_MAPPING",
    }

    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE2",
        "status": "IN_PROGRESS",
        "V06_GATE1": "PASS",
        "gate1ParameterHash": GATE1_PARAMETER_HASH_FROZEN,
        "gate1Locked": True,
        "V06_GATE2": verdict,
        "gate2ParameterHash": ph,
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE2_PARAMETERS["inheritedLimitationsFromV05"],
        "gate2Classifications": classes,
        "next": "GATE3_UNIFIED_BONE_MAPPING",
        "updatedAt": now,
    }

    _write(gate2 / "V06_GATE2_PARAMETERS.json", GATE2_PARAMETERS)
    _write(gate2 / "V06_GATE2_RECEIPT.json", receipt)
    _write(gate2 / "V06_GATE2_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)

    print(json.dumps({"V06_GATE2": verdict, "parameterHash": ph, "classifications": classes}, indent=2, ensure_ascii=False))
    return 0 if verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
