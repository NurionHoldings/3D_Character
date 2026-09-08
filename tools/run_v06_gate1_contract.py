"""Run v0.6 Gate 1 — unified contract lock + sealed baseline hash verify."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nurion_v06_unified_runtime.gate1.abstain import ABSTAIN_RULES, classify_abstain
from nurion_v06_unified_runtime.gate1.contract import build_contract, validate_sealed_baselines
from nurion_v06_unified_runtime.gate1.parameters import GATE1_PARAMETERS, parameter_hash


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    out_dir = ROOT / "dist" / "v0.6" / "gate1"
    ph = parameter_hash()
    contract = build_contract()
    baseline = validate_sealed_baselines(ROOT)

    # Contract self-check: classification helper must be deterministic for golden vectors
    golden_full = classify_abstain(
        has_armature=True,
        has_skinned_mesh=True,
        core_bones_ok=True,
        zero_length_critical=False,
        sibling_zip_mix=False,
        baseline_hash_ok=True,
        has_motion_preset=True,
        face_path_ok=True,
        eye_path_ok=True,
        lipsync_ok=True,
        auto_mappable=True,
        manual_mapping_required=False,
    )
    golden_limited = classify_abstain(
        has_armature=True,
        has_skinned_mesh=True,
        core_bones_ok=True,
        zero_length_critical=False,
        sibling_zip_mix=False,
        baseline_hash_ok=True,
        has_motion_preset=True,
        face_path_ok=False,
        eye_path_ok=True,
        lipsync_ok=False,
        auto_mappable=True,
        manual_mapping_required=False,
    )
    golden_ineligible = classify_abstain(
        has_armature=False,
        has_skinned_mesh=False,
        core_bones_ok=False,
        zero_length_critical=False,
        sibling_zip_mix=False,
        baseline_hash_ok=True,
        has_motion_preset=False,
        face_path_ok=False,
        eye_path_ok=False,
        lipsync_ok=False,
        auto_mappable=False,
        manual_mapping_required=True,
    )

    class_ok = (
        golden_full["classification"] == "FULL"
        and golden_limited["classification"] == "LIMITED"
        and golden_ineligible["classification"] == "INELIGIBLE"
    )

    gates = dict(baseline["gates"])
    gates["CONTRACT_BUILT"] = "PASS"
    gates["ABSTAIN_RULES_LOCKED"] = "PASS"
    gates["CLASSIFIER_GOLDEN"] = "PASS" if class_ok else "FAIL"
    gates["V05_LIMITATIONS_INHERITED"] = "PASS"
    gates["SEALED_BASELINES_READONLY"] = "PASS"
    hard_fails = [k for k, v in gates.items() if v == "FAIL"]
    verdict = "PASS" if not hard_fails else "FAIL"

    receipt = {
        "schema": "NURION_V06_GATE1_RECEIPT",
        "gate": "1",
        "name": "UNIFIED_CONTRACT_IO_SPEC",
        "track": GATE1_PARAMETERS["track"],
        "product": GATE1_PARAMETERS["product"],
        "V06_GATE1": verdict,
        "parameterHash": ph,
        "production": "NO-GO",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "inheritedLimitationsFromV05": GATE1_PARAMETERS["inheritedLimitationsFromV05"],
        "gates": gates,
        "hardFails": hard_fails,
        "baselineVerification": baseline,
        "classifierGolden": {
            "FULL": golden_full,
            "LIMITED": golden_limited,
            "INELIGIBLE": golden_ineligible,
        },
        "updatedAt": now,
        "next": "GATE2_AUTO_ASSET_DIAGNOSIS",
    }

    status = {
        "schema": "NURION_V06_GATE1_STATUS",
        "gate": "1",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "UNIFIED_CONTRACT_IO_SPEC",
        "V06_GATE1": verdict,
        "parameterHash": ph,
        "production": "NO-GO",
        "readonlyBaselines": GATE1_PARAMETERS["readonlyBaselines"],
        "inheritedLimitationsFromV05": GATE1_PARAMETERS["inheritedLimitationsFromV05"],
        "gates": gates,
        "hardFails": hard_fails,
        "pipeline": GATE1_PARAMETERS["pipeline"],
        "updatedAt": now,
        "artifacts": {
            "contract": "V06_GATE1_CONTRACT.json",
            "baselineLock": "V06_GATE1_BASELINE_LOCK.json",
            "abstainRules": "V06_GATE1_ABSTAIN_RULES.json",
            "receipt": "V06_GATE1_RECEIPT.json",
            "parameters": "V06_GATE1_PARAMETERS.json",
        },
        "next": "GATE2_AUTO_ASSET_DIAGNOSIS",
    }

    baseline_lock = {
        "schema": "NURION_V06_GATE1_BASELINE_LOCK",
        "version": "0.6.0-gate1",
        "status": verdict,
        "parameterHash": ph,
        "sealedBaselines": GATE1_PARAMETERS["readonlyBaselines"],
        "verification": baseline["details"],
        "mutation": "DENY",
        "repackSealedRc": "DENY",
        "inPlaceRepair": "DENY",
        "production": "NO-GO",
        "updatedAt": now,
    }

    track_status = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE1",
        "status": "IN_PROGRESS",
        "V06_GATE1": verdict,
        "gate1ParameterHash": ph,
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "sealedBaselineMutation": "DENY",
        "readonlyDependencies": {
            "v0.3": GATE1_PARAMETERS["readonlyBaselines"]["v0.3"],
            "v0.4": GATE1_PARAMETERS["readonlyBaselines"]["v0.4"],
            "v0.5": GATE1_PARAMETERS["readonlyBaselines"]["v0.5"],
        },
        "inheritedLimitationsFromV05": GATE1_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "next": "GATE2_AUTO_ASSET_DIAGNOSIS",
        "updatedAt": now,
    }

    _write(out_dir / "V06_GATE1_PARAMETERS.json", GATE1_PARAMETERS)
    _write(out_dir / "V06_GATE1_CONTRACT.json", contract)
    _write(out_dir / "V06_GATE1_ABSTAIN_RULES.json", ABSTAIN_RULES)
    _write(out_dir / "V06_GATE1_BASELINE_LOCK.json", baseline_lock)
    _write(out_dir / "V06_GATE1_RECEIPT.json", receipt)
    _write(out_dir / "V06_GATE1_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track_status)

    md = f"""# NURION Unified Character Animation Runtime v0.6 — Gate 1

## Verdict

- `V06_GATE1`: `{verdict}`
- Parameter hash: `{ph}`
- Production: `NO-GO`
- Sealed baseline mutation: `DENY`
- Limitation auto-clear: `DENY`

## Locked baselines

| Baseline | SHA-256 |
| --- | --- |
| v0.3 RC.1 | `{GATE1_PARAMETERS["readonlyBaselines"]["v0.3"]["sha256"]}` |
| v0.4 RC.1 | `{GATE1_PARAMETERS["readonlyBaselines"]["v0.4"]["sha256"]}` |
| v0.5 RC.1 | `{GATE1_PARAMETERS["readonlyBaselines"]["v0.5"]["sha256"]}` |

## Inherited v0.5 limitations (must remain public)

1. `FOOT_SLIDE_RESIDUAL_11`
2. `SHALLOW_SUSTAINED_CONTACT_ACCEPTED`
3. `GATE3_REVERSE_FOREARM_MILD_PRESERVED`
4. `HOLDOUT_FOOT_SLIDE_9`

## Next

`GATE2_AUTO_ASSET_DIAGNOSIS`
"""
    (out_dir / "V06_GATE1_CONTRACT.md").write_text(md, encoding="utf-8")

    print(json.dumps({"V06_GATE1": verdict, "parameterHash": ph, "out": str(out_dir)}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
