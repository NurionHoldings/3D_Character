"""NURION Quick Profile Single Image Pipeline Gate 2 GO.

Implements pipeline + internal dry-run. Separated from Gate 8 participant evidence.
Sealed CCS baselines are verified unchanged (mutation 0).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from nurion_quick_profile_core import (  # noqa: E402
    InputBundle,
    run_pipeline,
    sha256_file,
    sha256_obj,
    write_fixture_images,
)

BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_quick_profile_gate2_assemble.py"
OUT = ROOT / "dist" / "v0.7" / "product" / "quick_profile" / "gate2"
GATE1_HASH = "fdc57d1a276cd51fe58d8f65f0f8246cdf5ba88fdc233e0dbfc9b96c15e798d1"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
GATE5_BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
GATE5_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
GATE1_BLEND = ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend"
GATE1_BLEND_SHA = "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"
GATE4_BLEND = ROOT / "dist/v0.7/canonical/gate4/run3/NURION_CanonicalIdentityBeautification_V1.blend"
GATE4_BLEND_SHA = "72b8b2a6ff9708f6d3890de88d95fe670403e238f4514f55cd4c14a621ed502f"
COMMAND = "NURION Quick Profile Single Image Pipeline Gate 2 GO"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _param_hash(params: dict) -> str:
    raw = json.dumps(
        {k: v for k, v in params.items() if k != "parameterHash"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures_dir = OUT / "fixtures"
    dryrun_dir = OUT / "dryrun"
    dryrun_dir.mkdir(parents=True, exist_ok=True)

    # sealed baseline mutation 0
    for p, exp, label in (
        (GATE1_BLEND, GATE1_BLEND_SHA, "CCS_Gate1"),
        (GATE4_BLEND, GATE4_BLEND_SHA, "CCS_Gate4"),
        (GATE5_BLEND, GATE5_SHA, "CCS_Gate5"),
    ):
        got = sha256_file(p)
        if got != exp:
            raise SystemExit(f"{label} sealed blend mutated: {got}")

    params_path = OUT / "V07_QP_GATE2_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    if params.get("gate1ParameterHash") != GATE1_HASH:
        raise SystemExit("Gate1 parameter hash pin mismatch")
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(params_path, params)

    # inherit Gate1 contracts for analyzer ranges
    g1 = json.loads(
        (ROOT / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json").read_text(encoding="utf-8")
    )
    pipeline_params = {
        "inputContract": g1["inputContract"],
        "photoQualityCriteria": g1["photoQualityCriteria"],
        "exaggerationBan": g1["exaggerationBan"],
    }

    paths = write_fixture_images(fixtures_dir)
    cases = [
        InputBundle("eligible_frontal", str(paths["eligible_frontal"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_blur", str(paths["abstain_blur"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_noface", str(paths["abstain_noface"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_height_out_of_range", str(paths["eligible_frontal"]), 90.0, 65.0, "FRONTAL"),
    ]

    run_reports = []
    for run_id in (1, 2, 3):
        run_dir = dryrun_dir / f"run{run_id}"
        run_dir.mkdir(parents=True, exist_ok=True)
        case_results = []
        for bundle in cases:
            result = run_pipeline(bundle, pipeline_params)
            case_path = run_dir / f"{bundle.caseId}_PIPELINE_RESULT.json"
            _write(case_path, result)
            if result["verdict"] == "QUICK_PROFILE_DRAFT_READY":
                recipe_path = run_dir / f"{bundle.caseId}_RECIPE.json"
                _write(recipe_path, result["recipe"])
                cmd = [
                    str(BLENDER),
                    "--background",
                    "--python",
                    str(SCRIPT),
                    "--",
                    "--gate5-blend",
                    str(GATE5_BLEND),
                    "--expected-gate5-sha256",
                    GATE5_SHA,
                    "--recipe-json",
                    str(recipe_path),
                    "--out-dir",
                    str(dryrun_dir),
                    "--run-id",
                    str(run_id),
                    "--case-id",
                    bundle.caseId,
                ]
                proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
                (run_dir / f"{bundle.caseId}_blender_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
                (run_dir / f"{bundle.caseId}_blender_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
                if proc.returncode != 0:
                    print(proc.stderr[-8000:] if proc.stderr else proc.stdout)
                    return proc.returncode
                assemble = json.loads(
                    (run_dir / bundle.caseId / "V07_QP_GATE2_ASSEMBLE_REPORT.json").read_text(encoding="utf-8")
                )
                result["assembleFingerprintSha256"] = assemble["assembleFingerprintSha256"]
                result["outputBlendSha256"] = assemble["outputBlendSha256"]
                _write(case_path, result)
            case_results.append(
                {
                    "caseId": bundle.caseId,
                    "verdict": result["verdict"],
                    "pipelineFingerprintSha256": result.get("pipelineFingerprintSha256"),
                    "assembleFingerprintSha256": result.get("assembleFingerprintSha256"),
                    "abstainReasons": result.get("abstainReasons", []),
                }
            )

        run_fp = sha256_obj(case_results)
        report = {
            "schema": "NURION_V07_QP_GATE2_RUN_REPORT",
            "runId": run_id,
            "cases": case_results,
            "runFingerprintSha256": run_fp,
            "countsAsGate8ParticipantEvidence": "DENY",
            "production": "NO-GO",
        }
        _write(run_dir / "V07_QP_GATE2_RUN_REPORT.json", report)
        run_reports.append(report)

    fps = [r["runFingerprintSha256"] for r in run_reports]
    assemble_fps = []
    for r in run_reports:
        for c in r["cases"]:
            if c.get("assembleFingerprintSha256"):
                assemble_fps.append(c["assembleFingerprintSha256"])
    determinism = len(set(fps)) == 1 and (not assemble_fps or len(set(assemble_fps)) == 1)

    # re-verify sealed baselines after runs
    sealed_ok = all(
        sha256_file(p) == exp
        for p, exp in (
            (GATE1_BLEND, GATE1_BLEND_SHA),
            (GATE4_BLEND, GATE4_BLEND_SHA),
            (GATE5_BLEND, GATE5_SHA),
        )
    )

    r1 = run_reports[0]
    by_id = {c["caseId"]: c for c in r1["cases"]}
    fails: list[str] = []
    if by_id["eligible_frontal"]["verdict"] != "QUICK_PROFILE_DRAFT_READY":
        fails.append("ELIGIBLE_CASE_NOT_READY")
    for aid in ("abstain_blur", "abstain_noface", "abstain_height_out_of_range"):
        if by_id[aid]["verdict"] != "ABSTAIN":
            fails.append(f"EXPECTED_ABSTAIN_FAIL:{aid}")
    if not determinism:
        fails.append("DETERMINISM_FAIL")
    if not sealed_ok:
        fails.append("SEALED_BASELINE_MUTATION")
    if params["participantEvidenceCounting"] != "DENY":
        fails.append("EVIDENCE_COUNTING_NOT_DENIED")
    if params["arkaonCharacterGenerationIntervention"] != "DENY":
        fails.append("ARKAON_INTERVENTION_NOT_DENIED")

    verdict = "PASS" if not fails else "FAIL"
    now = datetime.now(timezone.utc).isoformat()

    status = {
        "schema": "NURION_V07_QP_GATE2_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate": 2,
        "command": COMMAND,
        "V07_QP_GATE2": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "determinism": determinism,
        "determinismRuns": 3,
        "runFingerprintSha256": fps[0] if fps else None,
        "assembleFingerprintSha256": assemble_fps[0] if assemble_fps else None,
        "sealedBaselineMutation": "PASS_ZERO" if sealed_ok else "FAIL",
        "pipelineImplementation": "COMPLETE_INTERNAL_DRY_RUN",
        "participantEvidenceCounting": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "gate8OfficialState": "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION",
        "talkingProfileMix": "DENY",
        "arkaonCharacterGenerationIntervention": "DENY",
        "arkaonGenerationRigWeightIntervention": "DENY",
        "arkaonPostQuickPresetBinding": "BOUND_IN_DRY_RUN_RECIPE",
        "fails": fails,
        "production": "NO-GO",
        "next": "AWAIT_OPERATOR_CONFIRM_THEN_PHASE1_DRAFT_USE_OR_GATE3",
        "updatedAt": now,
    }
    _write(OUT / "V07_QP_GATE2_STATUS.json", status)

    freeze = {
        "schema": "NURION_V07_QP_GATE2_OFFICIAL_FREEZE",
        "V07_QP_GATE2": verdict,
        "LOCKED": verdict == "PASS",
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "runFingerprintSha256": fps[0] if fps else None,
        "assembleFingerprintSha256": assemble_fps[0] if assemble_fps else None,
        "participantEvidenceCounting": "DENY",
        "gate8BaselineMutation": "DENY",
        "production": "NO-GO",
        "lockedAt": now,
    }
    _write(OUT / "V07_QP_GATE2_OFFICIAL_FREEZE.json", freeze)

    receipt = {
        "schema": "NURION_V07_QP_GATE2_DRY_RUN_RECEIPT",
        "command": COMMAND,
        "V07_QP_GATE2": verdict,
        "parameterHash": ph,
        "stagesCompleted": params["pipelineStages"],
        "dryRunCases": [c["caseId"] for c in r1["cases"]],
        "caseVerdicts": {c["caseId"]: c["verdict"] for c in r1["cases"]},
        "determinism": determinism,
        "sealedBaselineMutationZero": sealed_ok,
        "countsAsGate8ParticipantEvidence": "DENY",
        "fails": fails,
        "completedAt": now,
        "artifacts": {
            "fixtures": "fixtures/",
            "dryrun": "dryrun/",
            "status": "V07_QP_GATE2_STATUS.json",
        },
        "production": "NO-GO",
    }
    _write(OUT / "V07_QP_GATE2_DRY_RUN_RECEIPT.json", receipt)

    track = {
        "schema": "NURION_V07_QUICK_PROFILE_PIPELINE_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate1Lock": "INPUT_OUTPUT_ABSTAIN_CONTRACT_LOCKED",
        "gate2": verdict,
        "gate2ParameterHash": ph,
        "pipelineImplementation": "COMPLETE_INTERNAL_DRY_RUN" if verdict == "PASS" else "FAIL",
        "internalDryRun": "COMPLETE" if verdict == "PASS" else "FAIL",
        "participantEvidenceCounting": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "gate8OfficialState": "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION",
        "production": "NO-GO",
        "nextCommand": None if verdict == "PASS" else "REPAIR_QUICK_PROFILE_GATE2",
        "updatedAt": now,
    }
    _write(OUT.parent / "V07_QUICK_PROFILE_PIPELINE_STATUS.json", track)

    print(
        json.dumps(
            {
                "V07_QP_GATE2": verdict,
                "parameterHash": ph,
                "determinism": determinism,
                "fails": fails,
            },
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
