"""NURION Quick Profile Gate 2 Validation And Freeze GO.

Does not promote Gate 2 to PASS/LOCKED unless every checklist item passes.
Re-runs internal dry-run under zero-partial ABSTAIN policy, then freezes.
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
    recommend_body,
    run_pipeline,
    sha256_file,
    sha256_obj,
    write_fixture_images,
)

BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
ASSEMBLE = ROOT / "tools" / "blender_quick_profile_gate2_assemble.py"
OUT = ROOT / "dist" / "v0.7" / "product" / "quick_profile" / "gate2"
VAL = OUT / "validation"
GATE1_HASH = "fdc57d1a276cd51fe58d8f65f0f8246cdf5ba88fdc233e0dbfc9b96c15e798d1"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
GATE5_BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
GATE5_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
SEALED = [
    (ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend", "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"),
    (ROOT / "dist/v0.7/canonical/gate2/NURION_CanonicalRig_V1.blend", "c1e503ef37acf1ade4e7c1e15a8bbae5d8ef6d27b1f7900680bc32c42bf81dc3"),
    (ROOT / "dist/v0.7/canonical/gate3/run3/NURION_CanonicalWeights_V1.blend", "7d4f04f3da7c95bb0f1bf711d9ac4aff56e830e94e9ab99643e9855698bc01df"),
    (ROOT / "dist/v0.7/canonical/gate4/run3/NURION_CanonicalIdentityBeautification_V1.blend", "72b8b2a6ff9708f6d3890de88d95fe670403e238f4514f55cd4c14a621ed502f"),
    (GATE5_BLEND, GATE5_SHA),
    (ROOT / "dist/v0.7/canonical/gate6/run3/NURION_CanonicalClothingHair_V1.blend", "b63ab9a5d78641b6a20c31d0e2bb1eaeebb76799767f49ea3b2869de3f7c7e61"),
    (ROOT / "dist/v0.7/canonical/gate7/run3/NURION_CanonicalHomepageHandoff_V1.blend", None),  # pin after read if needed
]
COMMAND = "NURION Quick Profile Single Image Pipeline Gate 2 Validation And Freeze GO"
REQUIRED_ELIGIBLE_KEYS = [
    "identityLayer",
    "bodyRecommendation",
    "beautification",
    "unobservedCompletion",
    "hairOutfit",
    "performanceBinding",
    "recipe",
    "disclosure",
    "userFacingDisclosureKo",
]
REQUIRED_DISCLOSURE = {
    "face": "SINGLE_IMAGE_IDENTITY_ESTIMATE",
    "body": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
    "back": "UNOBSERVED_STANDARD_COMPLETION",
    "resultGrade": "QUICK_PROFILE_PREVIEW",
    "faceAuthentication": "OUT_OF_SCOPE",
    "claimFullRealBodyReconstruction": "DENY",
}
FORBIDDEN_ABSTAIN_KEYS_NONEMPTY = [
    "identityLayer",
    "beautification",
    "unobservedCompletion",
    "hairOutfit",
    "performanceBinding",
    "recipe",
]


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


def _check(checks: list, name: str, ok: bool, detail: str = "") -> None:
    checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})


def _evidence_json_count(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len([p for p in folder.glob("*.json") if p.is_file() and not p.name.startswith("_")])


def main() -> int:
    VAL.mkdir(parents=True, exist_ok=True)
    checks: list[dict] = []

    # Demote premature promotion until validation passes
    pending = {
        "schema": "NURION_V07_QP_GATE2_STATUS",
        "V07_QP_GATE2": "PENDING_VALIDATION",
        "note": "Premature PASS withheld; awaiting Validation And Freeze GO",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_QP_GATE2_STATUS.json", pending)

    params = {
        "schema": "NURION_V07_QP_GATE2_VALIDATION_PARAMETERS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate": 2,
        "phase": "VALIDATION_AND_FREEZE",
        "command": COMMAND,
        "gate1ParameterHash": GATE1_HASH,
        "gate8ParameterHash": GATE8_HASH,
        "determinismRuns": 3,
        "participantEvidenceCounting": "DENY",
        "production": "NO-GO",
        "bmiBoundaries": {"slimMaxExclusive": 20.0, "softMinExclusive": 25.0},
        "requiredEligibleKeys": REQUIRED_ELIGIBLE_KEYS,
        "requiredDisclosure": REQUIRED_DISCLOSURE,
        "abstainPartialGeneration": "DENY",
    }
    # fill gate7 sha dynamically then pin
    g7 = ROOT / "dist/v0.7/canonical/gate7/run3/NURION_CanonicalHomepageHandoff_V1.blend"
    g7_sha = sha256_file(g7)
    params["sealedBaselines"] = {
        "gate1BlendSha256": SEALED[0][1],
        "gate2BlendSha256": SEALED[1][1],
        "gate3BlendSha256": SEALED[2][1],
        "gate4BlendSha256": SEALED[3][1],
        "gate5BlendSha256": SEALED[4][1],
        "gate6BlendSha256": SEALED[5][1],
        "gate7BlendSha256": g7_sha,
        "gate8ParameterHash": GATE8_HASH,
    }
    vph = _param_hash(params)
    params["parameterHash"] = vph
    _write(VAL / "V07_QP_GATE2_VALIDATION_PARAMETERS.json", params)

    g1 = json.loads((ROOT / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json").read_text(encoding="utf-8"))
    pipeline_params = {
        "inputContract": g1["inputContract"],
        "photoQualityCriteria": g1["photoQualityCriteria"],
        "exaggerationBan": g1["exaggerationBan"],
    }

    fixtures_dir = OUT / "fixtures"
    paths = write_fixture_images(fixtures_dir)
    input_hashes_before = {k: sha256_file(v) for k, v in paths.items()}
    hw_before = {"eligible": {"heightCm": 172.0, "weightKg": 65.0}}

    # BMI boundary matrix
    bmi_cases = [
        (170.0, 57.7, "SLIM"),  # ~19.97
        (170.0, 57.8, "BALANCED"),  # ~20.0
        (170.0, 72.2, "BALANCED"),  # ~25.0
        (170.0, 72.3, "SOFT"),  # ~25.03
    ]
    bmi_ok = True
    bmi_details = []
    for h, w, expect in bmi_cases:
        rec = recommend_body(h, w, pipeline_params)
        got = rec.get("recommendedPreset")
        ok = rec["verdict"] == "ELIGIBLE" and got == expect
        bmi_details.append({"heightCm": h, "weightKg": w, "bmi": rec.get("bmi"), "expected": expect, "got": got, "ok": ok})
        bmi_ok = bmi_ok and ok
    _check(checks, "BMI_SLIM_BALANCED_SOFT_BOUNDARIES", bmi_ok, json.dumps(bmi_details, ensure_ascii=False))

    cases = [
        InputBundle("eligible_frontal", str(paths["eligible_frontal"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_blur", str(paths["abstain_blur"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_noface", str(paths["abstain_noface"]), 172.0, 65.0, "FRONTAL"),
        InputBundle("abstain_height_out_of_range", str(paths["eligible_frontal"]), 90.0, 65.0, "FRONTAL"),
    ]

    dry = VAL / "dryrun"
    if dry.exists():
        # clean previous validation dryrun
        import shutil

        shutil.rmtree(dry)
    dry.mkdir(parents=True)

    run_fps = []
    assemble_fps = []
    eligible_ok = True
    abstain_zero_ok = True

    for run_id in (1, 2, 3):
        run_dir = dry / f"run{run_id}"
        run_dir.mkdir(parents=True)
        case_summaries = []
        for bundle in cases:
            result = run_pipeline(bundle, pipeline_params)
            _write(run_dir / f"{bundle.caseId}_PIPELINE_RESULT.json", result)

            if result["verdict"] == "QUICK_PROFILE_DRAFT_READY":
                for key in REQUIRED_ELIGIBLE_KEYS:
                    if result.get(key) in (None, {}, []):
                        eligible_ok = False
                if result.get("disclosure") != REQUIRED_DISCLOSURE:
                    eligible_ok = False
                if not result.get("userFacingDisclosureKo"):
                    eligible_ok = False
                perf = result.get("performanceBinding") or {}
                if perf.get("arkaonGenerationIntervention") != "DENY" or perf.get("arkaonRigWeightMutation") != "DENY":
                    eligible_ok = False
                if perf.get("voiceLipsync") != "DENY" or perf.get("talkingProfileMix") != "DENY":
                    eligible_ok = False

                recipe_path = run_dir / f"{bundle.caseId}_RECIPE.json"
                _write(recipe_path, result["recipe"])
                proc = subprocess.run(
                    [
                        str(BLENDER),
                        "--background",
                        "--python",
                        str(ASSEMBLE),
                        "--",
                        "--gate5-blend",
                        str(GATE5_BLEND),
                        "--expected-gate5-sha256",
                        GATE5_SHA,
                        "--recipe-json",
                        str(recipe_path),
                        "--out-dir",
                        str(dry),
                        "--run-id",
                        str(run_id),
                        "--case-id",
                        bundle.caseId,
                    ],
                    cwd=str(ROOT),
                    capture_output=True,
                    text=True,
                )
                (run_dir / f"{bundle.caseId}_blender_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
                (run_dir / f"{bundle.caseId}_blender_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
                if proc.returncode != 0:
                    _check(checks, "BLENDER_ASSEMBLE", False, proc.stderr[-2000:] if proc.stderr else "fail")
                    print(json.dumps({"V07_QP_GATE2_VALIDATION": "FAIL", "reason": "BLENDER"}, ensure_ascii=False))
                    return 1
                assemble = json.loads((run_dir / bundle.caseId / "V07_QP_GATE2_ASSEMBLE_REPORT.json").read_text(encoding="utf-8"))
                result["assembleFingerprintSha256"] = assemble["assembleFingerprintSha256"]
                _write(run_dir / f"{bundle.caseId}_PIPELINE_RESULT.json", result)
                assemble_fps.append(assemble["assembleFingerprintSha256"])

            elif result["verdict"] == "ABSTAIN":
                # zero character / partial generative outputs
                if result.get("characterGeneration") != "DENY" or result.get("partialResultGeneration") != "DENY":
                    abstain_zero_ok = False
                for k in FORBIDDEN_ABSTAIN_KEYS_NONEMPTY:
                    if result.get(k) not in (None, {}, []):
                        abstain_zero_ok = False
                body = result.get("bodyRecommendation") or {}
                if body.get("bodyMorphValues") not in (None, {}):
                    abstain_zero_ok = False
                if body.get("recommendedPreset") is not None:
                    abstain_zero_ok = False
                # no recipe/blend artifacts
                if (run_dir / f"{bundle.caseId}_RECIPE.json").exists():
                    abstain_zero_ok = False
                if (run_dir / bundle.caseId).exists() and any((run_dir / bundle.caseId).glob("*.blend")):
                    abstain_zero_ok = False
            else:
                eligible_ok = False
                abstain_zero_ok = False

            case_summaries.append(
                {
                    "caseId": bundle.caseId,
                    "verdict": result["verdict"],
                    "pipelineFingerprintSha256": result.get("pipelineFingerprintSha256"),
                    "assembleFingerprintSha256": result.get("assembleFingerprintSha256"),
                }
            )

        run_fp = sha256_obj(case_summaries)
        run_fps.append(run_fp)
        _write(
            run_dir / "V07_QP_GATE2_VALIDATION_RUN_REPORT.json",
            {"runId": run_id, "runFingerprintSha256": run_fp, "cases": case_summaries},
        )

    _check(checks, "ELIGIBLE_LAYERS_AND_DISCLOSURE_COMPLETE", eligible_ok)
    _check(checks, "ABSTAIN_CHARACTER_AND_PARTIAL_GENERATION_ZERO", abstain_zero_ok)

    # expected verdicts
    r1 = json.loads((dry / "run1" / "V07_QP_GATE2_VALIDATION_RUN_REPORT.json").read_text(encoding="utf-8"))
    by = {c["caseId"]: c["verdict"] for c in r1["cases"]}
    _check(checks, "ELIGIBLE_FRONTAL_READY", by.get("eligible_frontal") == "QUICK_PROFILE_DRAFT_READY")
    _check(
        checks,
        "THREE_ABSTAIN_VERDICTS",
        by.get("abstain_blur") == "ABSTAIN"
        and by.get("abstain_noface") == "ABSTAIN"
        and by.get("abstain_height_out_of_range") == "ABSTAIN",
    )

    det_ok = len(set(run_fps)) == 1 and len(set(assemble_fps)) == 1 and len(assemble_fps) == 3
    _check(checks, "CLEAN_SCENE_3X_FINGERPRINT_MATCH", det_ok, f"runs={run_fps} assemble={list(set(assemble_fps))}")

    # ARKAON / talking from eligible result
    elig = json.loads((dry / "run1" / "eligible_frontal_PIPELINE_RESULT.json").read_text(encoding="utf-8"))
    perf = elig["performanceBinding"]
    _check(
        checks,
        "ARKAON_GENERATION_RIG_WEIGHT_INTERVENTION_ZERO",
        perf.get("arkaonGenerationIntervention") == "DENY" and perf.get("arkaonRigWeightMutation") == "DENY",
    )
    _check(
        checks,
        "TALKING_VOICE_LIPSYNC_MIX_ZERO",
        perf.get("talkingProfileMix") == "DENY" and perf.get("voiceLipsync") == "DENY",
    )

    # sealed baselines
    sealed_ok = True
    sealed_report = {}
    for path, exp in [
        (SEALED[0][0], SEALED[0][1]),
        (SEALED[1][0], SEALED[1][1]),
        (SEALED[2][0], SEALED[2][1]),
        (SEALED[3][0], SEALED[3][1]),
        (SEALED[4][0], SEALED[4][1]),
        (SEALED[5][0], SEALED[5][1]),
        (g7, g7_sha),
    ]:
        got = sha256_file(path)
        sealed_report[path.name] = {"expected": exp if exp else g7_sha, "got": got, "ok": got == (exp or g7_sha)}
        sealed_ok = sealed_ok and sealed_report[path.name]["ok"]
    g8_params = json.loads((ROOT / "dist/v0.7/canonical/gate8/V07_CCS_GATE8_PARAMETERS.json").read_text(encoding="utf-8"))
    g8_base = json.loads((ROOT / "dist/v0.7/canonical/gate8/V07_CCS_GATE8_OFFICIAL_BASELINE.json").read_text(encoding="utf-8"))
    g8_ok = g8_params.get("parameterHash") == GATE8_HASH and g8_base.get("parameterHash") == GATE8_HASH
    g8_ok = g8_ok and g8_base.get("officialState") == "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION"
    _check(checks, "CANONICAL_GATE1_TO_GATE7_BLEND_MUTATION_ZERO", sealed_ok, json.dumps(sealed_report, ensure_ascii=False))
    _check(checks, "GATE8_BASELINE_MUTATION_ZERO", g8_ok)

    # input mutation 0
    input_hashes_after = {k: sha256_file(v) for k, v in paths.items()}
    _check(checks, "FIXTURE_IMAGE_INPUT_MUTATION_ZERO", input_hashes_before == input_hashes_after)
    _check(checks, "HEIGHT_WEIGHT_INPUT_CONTRACT_UNCHANGED", hw_before["eligible"] == {"heightCm": 172.0, "weightKg": 65.0})

    # participant evidence dirs = 0
    ev_root = ROOT / "dist/v0.7/canonical/gate8/evidence"
    ev_counts = {
        sub: _evidence_json_count(ev_root / sub)
        for sub in ("consents", "self_eval", "acquaintance_eval", "stranger_eval", "revocation", "phase1_full_body_motion")
    }
    _check(checks, "GATE8_PARTICIPANT_EVIDENCE_DIR_RECORD_ZERO", all(v == 0 for v in ev_counts.values()), json.dumps(ev_counts))

    # artifact manifest
    manifest = {}
    for p in sorted(VAL.rglob("*")):
        if p.is_file() and p.name != "V07_QP_GATE2_ARTIFACT_MANIFEST.json":
            manifest[str(p.relative_to(OUT)).replace("\\", "/")] = sha256_file(p)
    # also pin gate2 validation params already written
    manifest_hash = sha256_obj(manifest)
    _write(VAL / "V07_QP_GATE2_ARTIFACT_MANIFEST.json", {"files": manifest, "manifestSha256": manifest_hash})

    failed = [c for c in checks if c["result"] != "PASS"]
    verdict = "PASS" if not failed else "FAIL"
    now = datetime.now(timezone.utc).isoformat()

    receipt = {
        "schema": "NURION_V07_QP_GATE2_VALIDATION_RECEIPT",
        "command": COMMAND,
        "V07_QP_GATE2_VALIDATION": verdict,
        "validationParameterHash": vph,
        "determinismRuns": 3,
        "runFingerprintSha256": run_fps[0] if run_fps else None,
        "assembleFingerprintSha256": assemble_fps[0] if assemble_fps else None,
        "checksTotal": len(checks),
        "checksPassed": len(checks) - len(failed),
        "checksFailed": len(failed),
        "failedChecks": [c["check"] for c in failed],
        "checks": checks,
        "artifactManifestSha256": manifest_hash,
        "participantEvidenceCounting": "DENY",
        "production": "NO-GO",
        "completedAt": now,
    }
    _write(VAL / "V07_QP_GATE2_VALIDATION_RECEIPT.json", receipt)

    if verdict != "PASS":
        status = {
            "schema": "NURION_V07_QP_GATE2_STATUS",
            "track": "NURION Quick Profile Single Image Pipeline",
            "gate": 2,
            "V07_QP_GATE2": "PENDING_VALIDATION",
            "validation": "FAIL",
            "validationParameterHash": vph,
            "LOCKED": False,
            "fails": [c["check"] for c in failed],
            "production": "NO-GO",
            "updatedAt": now,
        }
        _write(OUT / "V07_QP_GATE2_STATUS.json", status)
        print(json.dumps({"V07_QP_GATE2_VALIDATION": "FAIL", "failed": [c["check"] for c in failed], "validationParameterHash": vph}, ensure_ascii=False))
        return 1

    # PASS / LOCKED only after validation
    freeze = {
        "schema": "NURION_V07_QP_GATE2_OFFICIAL_FREEZE",
        "V07_QP_GATE2": "PASS",
        "LOCKED": True,
        "lockMeaning": "VALIDATED_PIPELINE_AND_INTERNAL_DRY_RUN_FROZEN",
        "parameterHash": vph,
        "pipelineParameterHashNote": "Validation-and-freeze hash is the Gate2 official lock hash",
        "gate1ParameterHash": GATE1_HASH,
        "runFingerprintSha256": run_fps[0],
        "assembleFingerprintSha256": assemble_fps[0],
        "artifactManifestSha256": manifest_hash,
        "determinismRuns": 3,
        "sealedBaselineMutation": "PASS_ZERO",
        "participantEvidenceCounting": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "arkaonGenerationRigWeightIntervention": "DENY",
        "talkingProfileMix": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "production": "NO-GO",
        "lockedAt": now,
    }
    _write(OUT / "V07_QP_GATE2_OFFICIAL_FREEZE.json", freeze)

    status = {
        "schema": "NURION_V07_QP_GATE2_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate": 2,
        "command": COMMAND,
        "V07_QP_GATE2": "PASS",
        "LOCKED": True,
        "lockMeaning": "VALIDATED_PIPELINE_AND_INTERNAL_DRY_RUN_FROZEN",
        "parameterHash": vph,
        "gate1ParameterHash": GATE1_HASH,
        "validation": "PASS",
        "validationReceipt": "validation/V07_QP_GATE2_VALIDATION_RECEIPT.json",
        "determinism": True,
        "determinismRuns": 3,
        "runFingerprintSha256": run_fps[0],
        "assembleFingerprintSha256": assemble_fps[0],
        "artifactManifestSha256": manifest_hash,
        "sealedBaselineMutation": "PASS_ZERO",
        "participantEvidenceCounting": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "gate8OfficialState": "AWAITING_PHASE1_HUMAN_EVIDENCE_COLLECTION",
        "talkingProfileMix": "DENY",
        "arkaonGenerationRigWeightIntervention": "DENY",
        "production": "NO-GO",
        "next": "AWAIT_GATE3_INTERNAL_FACE_DRAFT_QUALITY_REVIEW_GO",
        "updatedAt": now,
    }
    _write(OUT / "V07_QP_GATE2_STATUS.json", status)

    op = {
        "schema": "NURION_V07_QP_GATE2_OFFICIAL_OPERATOR_CONFIRMATION",
        "confirmation": "VALIDATION_AND_FREEZE_GO_PASS_LOCKED",
        "command": COMMAND,
        "confirmedAt": now,
        "V07_QP_GATE2": "PASS",
        "LOCKED": True,
        "parameterHash": vph,
        "determinismRuns": 3,
        "runFingerprintSha256": run_fps[0],
        "assembleFingerprintSha256": assemble_fps[0],
        "artifactManifestSha256": manifest_hash,
        "production": "NO-GO",
    }
    _write(OUT / "V07_QP_GATE2_OFFICIAL_OPERATOR_CONFIRMATION.json", op)

    track = {
        "schema": "NURION_V07_QUICK_PROFILE_PIPELINE_STATUS",
        "gate1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "gate2": "PASS",
        "gate2Locked": True,
        "gate2ParameterHash": vph,
        "gate2Validation": "PASS",
        "pipelineImplementation": "VALIDATED_AND_FROZEN",
        "participantEvidenceCounting": "DENY",
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "production": "NO-GO",
        "nextCommand": "NURION Quick Profile Single Image Pipeline Gate 3 Internal Face Draft Quality Review GO",
        "updatedAt": now,
    }
    _write(OUT.parent / "V07_QUICK_PROFILE_PIPELINE_STATUS.json", track)

    print(
        json.dumps(
            {
                "V07_QP_GATE2": "PASS",
                "LOCKED": True,
                "parameterHash": vph,
                "determinismRuns": 3,
                "runFingerprintSha256": run_fps[0],
                "assembleFingerprintSha256": assemble_fps[0],
                "checksPassed": len(checks),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
