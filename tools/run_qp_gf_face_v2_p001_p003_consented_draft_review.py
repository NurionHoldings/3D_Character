"""Geometry-First v2 P001–P003 Consented Human Draft Review Execute GO.

Independent per-participant judgments on the Gate 4 isolated adapter path.
Does not mutate frozen Identity Core, Gate 3 runner, or Gate 4 contract.
DENY: automatic similarity PASS, Gate 8 evidence, partial distribution, Production.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.gate4_contract import GATE4_CONTRACT, gate4_parameter_hash
from nurion_qp_geometry_face_v2.integration_adapter import (
    AdapterInput,
    GeometryFirstIntegrationAdapter,
    load_gate2_params,
)
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_DET, EXP_LM, MediaPipeLandmarkerBackend, sha256_file

# Reuse Gate3 runner consent helpers without invoking all-or-none execute.
from run_quick_profile_gate3_consented_human_review import (  # noqa: E402
    EXPECTED as G3_EXPECTED,
    consent_ok,
    operator_filter_reasons,
)

PARTICIPANTS = ("P001", "P002", "P003")
COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 P001-P003 Consented Human Draft Review Execute GO"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
EXP_G3_GF = "160662e0a954643883be1ae154817cffabf83fced2a429bce63f47ddbb936f5e"
CORE_SHA = "636372fc0886870d536c093c2ba8dcc001ec87f3c6cb9922518eaeffdf473816"
RUNNER_SHA = "13837c5e5b4a31e9efb10c83528703375df44f59ac15babb69207a57e22dbcc4"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
OUT = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4/execution"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def map_verdict(adapter_out: dict) -> str:
    v = adapter_out.get("verdict")
    if v == "GEOMETRY_FIRST_DRAFT_READY":
        return "DRAFT_READY"
    if v == "GEOMETRY_REVIEW_REQUIRED":
        return "REVIEW_REQUIRED"
    return "ABSTAIN_RECAPTURE"


def human_review_template(pid: str, judgment: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_HUMAN_DRAFT_REVIEW_TEMPLATE_V1",
        "anonymousParticipantId": pid,
        "geometryFirstJudgment": judgment,
        "selfEvaluation": {
            "completed": False,
            "faceShapeAndMajorProportions": None,
            "eyeBrowNoseMouthJawSignature": None,
            "naturalAsymmetryPreserved": None,
            "comment": None,
        },
        "internalVisualReview": {
            "completed": False,
            "identityLoss": None,
            "geometryPlausibility": None,
            "captureLimitationImpact": None,
            "comment": None,
        },
        "automaticSimilarityPass": "DENY",
        "automaticHumanLikenessPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "production": "NO-GO",
        "characterGeneration": "DENY",
        "blenderDraftAssembly": "DENY",
    }


def verify_baselines() -> dict:
    issues = []
    if gate4_parameter_hash() != EXP_G4:
        issues.append("GATE4_HASH_MISMATCH")
    if GATE4_CONTRACT["gate3OfficialParameterHash"] != EXP_G3_GF:
        issues.append("GATE4_GATE3_PIN_MISMATCH")
    if sha256_file(ROOT / "tools/nurion_quick_profile_core.py") != CORE_SHA:
        issues.append("QP_CORE_MUTATION")
    if sha256_file(ROOT / "tools/run_quick_profile_gate3_consented_human_review.py") != RUNNER_SHA:
        issues.append("QP_GATE3_RUNNER_MUTATION")
    g8 = read_json(ROOT / "dist/v0.7/canonical/gate8/V07_CCS_GATE8_OFFICIAL_FREEZE.json")
    if g8.get("parameterHash") != GATE8_HASH:
        issues.append("GATE8_MUTATION")
    g2 = read_json(ROOT / "dist/v0.7/product/quick_profile/gate2/V07_QP_GATE2_OFFICIAL_FREEZE.json")
    if g2.get("parameterHash") != G3_EXPECTED["gate2_parameter"]:
        issues.append("QP_GATE2_FREEZE_MISMATCH")
    g3p = read_json(ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_PARAMETERS.json")
    if g3p.get("parameterHash") != G3_EXPECTED["gate3_parameter"]:
        issues.append("QP_GATE3_PROTOCOL_MISMATCH")
    det, lm = MODELS / "blaze_face_short_range_float16_v1.tflite", MODELS / "face_landmarker_float16_v1.task"
    if sha256_file(det) != EXP_DET or sha256_file(lm) != EXP_LM:
        issues.append("MODEL_SHA_MISMATCH")
    import mediapipe as mp

    if mp.__version__ != "1.0.1":
        issues.append("MEDIAPIPE_VERSION_MISMATCH")
    return {"issues": issues, "gate4": EXP_G4, "mediapipe": getattr(mp, "__version__", None)}


def validate_participant(pid: str, pins: dict, precheck: dict) -> dict:
    folder = INTAKE / "packages" / pid
    face = folder / "face.png"
    inp = read_json(folder / "participant_input.json")
    consent = read_json(folder / "consent.json")
    reasons: list[str] = []
    if not face.is_file():
        reasons.append("FACE_MISSING")
        return {"participantId": pid, "reasons": reasons, "face": face, "input": inp, "consent": consent, "imageSha": None}
    got = sha256_file(face)
    if pins.get(pid) != got or inp.get("originalImageSha256") != got:
        reasons.append("PINNED_IMAGE_HASH_MISMATCH")
    if inp.get("anonymousParticipantId") != pid:
        reasons.append("PARTICIPANT_ID_MISMATCH")
    if inp.get("mutationAfterFix") != "DENY":
        reasons.append("INPUT_MUTATION_POLICY_MISSING")
    if not isinstance(inp.get("heightCm"), (int, float)) or not isinstance(inp.get("weightKg"), (int, float)):
        reasons.append("HEIGHT_WEIGHT_INVALID")
    reasons.extend(consent_ok(consent, pid))
    reasons.extend(operator_filter_reasons(precheck.get("packages", {}).get(pid, {})))
    # replacement consent continuity when pinEvent says superseded
    cont = folder / "CONSENT_CONTINUES_ON_REPLACEMENT.json"
    pin_detail = read_json(INTAKE / "V07_QP_GATE3_PINNED_SHA256_RECORD.json").get("detail", {}).get(pid, {})
    if pin_detail.get("pinEvent") == "SUPERSEDED_BY_FILTER_FREE_INPUT":
        if not cont.is_file():
            reasons.append("CONSENT_CONTINUES_ON_REPLACEMENT_MISSING")
        else:
            cdoc = read_json(cont)
            continues = any(
                cdoc.get(k) is True
                for k in (
                    "consentContinuesOnReplacementPhoto",
                    "consentContinuesOnReplacement",
                    "consentContinues",
                )
            )
            if not continues:
                reasons.append("CONSENT_CONTINUES_FALSE")
    retention = consent.get("retentionOrDeletionChoice")
    if retention not in ("DELETE_AFTER_REVIEW", "KEEP_FOR_DAYS"):
        reasons.append("RETENTION_CHOICE_INVALID")
    if consent.get("countsAsGate8ParticipantEvidence") != "DENY":
        reasons.append("GATE8_EVIDENCE_DENY_MISSING")
    return {
        "participantId": pid,
        "reasons": sorted(set(reasons)),
        "face": face,
        "input": inp,
        "consent": consent,
        "imageSha": got,
        "retentionOrDeletionChoice": retention,
        "bytes": face.stat().st_size,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = OUT / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    baseline = verify_baselines()
    if baseline["issues"]:
        abort = {
            "schema": "NURION_V07_QP_GF_FACE_V2_P001_P003_DRAFT_REVIEW_SAFE_ABORT_V1",
            "command": COMMAND,
            "verdict": "SAFE_ABORT",
            "reason": "BASELINE_REVERIFY_FAIL",
            "issues": baseline["issues"],
            "partialResultDistribution": "DENY",
            "countsAsGate8ParticipantEvidence": "DENY",
            "production": "NO-GO",
            "registeredAt": now,
        }
        write_json(run_dir / "V07_QP_GF_FACE_V2_P001_P003_DRAFT_REVIEW_SAFE_ABORT.json", abort)
        print(json.dumps(abort, indent=2, ensure_ascii=False))
        return 2

    pinned = read_json(INTAKE / "V07_QP_GATE3_PINNED_SHA256_RECORD.json")
    precheck = read_json(INTAKE / "V07_QP_GATE3_PACKAGE_PRECHECK.json")
    pins = pinned.get("pinnedSha256", {})
    packages = [validate_participant(pid, pins, precheck) for pid in PARTICIPANTS]
    hashes_before = {p["participantId"]: p["imageSha"] for p in packages}

    params = load_gate2_params(ROOT)
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    adapter = GeometryFirstIntegrationAdapter(backend)

    results = []
    for pkg in packages:
        pid = pkg["participantId"]
        entry: dict[str, Any] = {
            "participantId": pid,
            "pinnedSha256": pins.get(pid),
            "imageSha256": pkg["imageSha"],
            "bytes": pkg.get("bytes"),
            "consentStatus": pkg["consent"].get("status"),
            "retentionOrDeletionChoice": pkg.get("retentionOrDeletionChoice"),
            "packageValidationReasons": pkg["reasons"],
            "automaticSimilarityPass": "DENY",
            "countsAsGate8ParticipantEvidence": "DENY",
            "partialResultDistribution": "DENY",
            "characterGeneration": "DENY",
            "blenderDraftAssembly": "DENY",
            "production": "NO-GO",
            "identityCoreReplacement": "DENY",
        }
        if pkg["reasons"]:
            entry["judgment"] = "ABSTAIN_RECAPTURE"
            entry["abstainReasons"] = pkg["reasons"]
            entry["adapter"] = None
            entry["humanReview"] = "NOT_STARTED_PACKAGE_INVALID"
            results.append(entry)
            write_json(run_dir / "participants" / pid / "V07_QP_GF_FACE_V2_PARTICIPANT_JUDGMENT.json", entry)
            continue

        out = adapter.analyze(
            AdapterInput(
                pid,
                pkg["face"],
                float(pkg["input"]["heightCm"]),
                float(pkg["input"]["weightKg"]),
                pkg["input"].get("declaredPose", "FRONTAL"),
            ),
            params,
        )
        judgment = map_verdict(out)
        entry["judgment"] = judgment
        entry["adapterVerdict"] = out.get("verdict")
        entry["abstainReasons"] = out.get("abstainReasons", [])
        entry["heuristicExistenceGate"] = out.get("heuristicExistenceGate")
        entry["legacyHeuristicComparison"] = out.get("legacyHeuristicComparison")
        entry["geometryAnalysis"] = out.get("geometryAnalysis")
        entry["identityLayer"] = out.get("identityLayer")
        entry["bodyRecommendation"] = out.get("bodyRecommendation")
        entry["adapterFingerprintSha256"] = out.get("adapterFingerprintSha256")

        pdir = run_dir / "participants" / pid
        write_json(pdir / "V07_QP_GF_FACE_V2_ADAPTER_RESULT.json", out)

        if judgment in ("DRAFT_READY", "REVIEW_REQUIRED"):
            template = human_review_template(pid, judgment)
            write_json(pdir / "V07_QP_GF_FACE_V2_HUMAN_REVIEW.json", template)
            if out.get("identityLayer") is not None:
                recipe = {
                    "schema": "NURION_V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE_V1",
                    "participantId": pid,
                    "distribution": "DENY",
                    "characterGeneration": "DENY",
                    "blenderDraftAssembly": "DENY",
                    "identityLayer": out["identityLayer"],
                    "bodyRecommendation": out.get("bodyRecommendation"),
                    "geometryOutcome": (out.get("geometryAnalysis") or {}).get("outcome"),
                    "note": "INTERNAL_GEOMETRY_PREVIEW_ONLY_NOT_PRODUCT_DRAFT",
                }
                write_json(pdir / "V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE.json", recipe)
            entry["humanReview"] = "AWAITING_HUMAN_REVIEW"
            entry["internalDraftRecipe"] = "RECORDED_DISTRIBUTION_DENY"
        else:
            entry["humanReview"] = "NOT_STARTED_ABSTAIN"
            entry["internalDraftRecipe"] = "DENY"

        write_json(pdir / "V07_QP_GF_FACE_V2_PARTICIPANT_JUDGMENT.json", entry)
        results.append(entry)

    hashes_after = {pid: sha256_file(INTAKE / "packages" / pid / "face.png") for pid in PARTICIPANTS}
    mutation = 0 if hashes_after == hashes_before else 1

    summary = {r["participantId"]: r["judgment"] for r in results}
    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "gate4ParameterHash": EXP_G4,
        "gate3GeometryFirstParameterHash": EXP_G3_GF,
        "integrationMode": "ISOLATED_ADAPTER",
        "replaceFrozenIdentityCore": "DENY",
        "mutateGate3Runner": "DENY",
        "participantJudgments": summary,
        "participantResults": [
            {
                "participantId": r["participantId"],
                "judgment": r["judgment"],
                "imageSha256": r.get("imageSha256"),
                "abstainReasons": r.get("abstainReasons", []),
                "legacyHeuristicReasons": (r.get("legacyHeuristicComparison") or {}).get("reasons"),
                "geometryOutcome": None
                if r.get("geometryAnalysis") is None
                else r["geometryAnalysis"].get("outcome"),
                "humanReview": r.get("humanReview"),
            }
            for r in results
        ],
        "independentJudgments": True,
        "allOrNoneAbort": "DENY",
        "automaticSimilarityPass": "DENY",
        "automaticHumanLikenessPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "characterGeneration": "DENY",
        "blenderDraftAssembly": "DENY",
        "participantInputMutation": mutation,
        "baselineMutation": 0,
        "production": "NO-GO",
        "retentionDeletionState": "DELETE_AFTER_REVIEW_PENDING_HUMAN_REVIEW",
        "productLimitations": [],
    }
    # note P002 blur false-abstain risk if applicable
    for r in results:
        if r["participantId"] == "P002" and r["judgment"] == "ABSTAIN_RECAPTURE":
            if "SEVERE_BLUR_OR_OCCLUSION" in r.get("abstainReasons", []):
                receipt["productLimitations"].append(
                    {
                        "code": "LARGE_IMAGE_EDGE_VARIANCE_FALSE_ABSTAIN_RISK",
                        "participantId": "P002",
                        "note": "Adapter retained blur precheck fired; direct MediaPipe geometry may still succeed. Gate4 contract unchanged.",
                    }
                )
        if r.get("legacyHeuristicComparison") and "NO_DETECTABLE_FACE" in (
            r.get("legacyHeuristicComparison") or {}
        ).get("reasons", []):
            if r["judgment"] == "DRAFT_READY":
                receipt.setdefault("heuristicBypassEvidence", []).append(r["participantId"])

    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(run_dir / "V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json", receipt)
    write_json(OUT / "V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json", receipt)

    # Gate4 status update (baseline remains PASS/LOCKED)
    g4_status_path = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4/V07_QP_GF_FACE_V2_GATE4_STATUS.json"
    g4s = read_json(g4_status_path)
    g4s["updatedAt"] = now
    g4s["realParticipantUsage"] = 3
    g4s["lastDraftReviewExecute"] = {
        "runId": run_id,
        "judgments": summary,
        "production": "NO-GO",
        "gate8Evidence": "DENY",
    }
    g4s["next"] = "AWAIT_HUMAN_REVIEW_AND_OR_P002_CAPTURE_QUALITY_FOLLOWUP"
    write_json(g4_status_path, g4s)

    qp3_path = ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_STATUS.json"
    qp3 = read_json(qp3_path)
    qp3["updatedAt"] = now
    qp3["geometryFirstFaceAnalyzerV2P001P003DraftReview"] = {
        "verdict": "EXECUTED_INDEPENDENT_JUDGMENTS",
        "runId": run_id,
        "judgments": summary,
        "replaceFrozenIdentityCore": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "production": "NO-GO",
        "receipt": str(
            OUT / "V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json"
        ).replace(str(ROOT) + "\\", "").replace("\\", "/"),
    }
    qp3["parallelTracks"] = {
        "P001FilterFreeReplacement": "NOT_REQUIRED_FOR_GF_V2_PATH_CURRENT_PIN_USED",
        "geometryFirstFaceV2": "GATE4_PASS_LOCKED_DRAFT_REVIEW_EXECUTED",
        "humanDraftReview": "AWAITING_FOR_NON_ABSTAIN_PARTICIPANTS",
    }
    write_json(qp3_path, qp3)

    print(
        json.dumps(
            {
                "verdict": "EXECUTED_INDEPENDENT_JUDGMENTS",
                "judgments": summary,
                "runId": run_id,
                "production": "NO-GO",
                "gate8Evidence": "DENY",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
