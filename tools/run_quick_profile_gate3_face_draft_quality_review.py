"""NURION Quick Profile Gate 3 — Internal Face Draft Quality Review GO.

Reviews face-draft quality axes. Auto similarity alone cannot PASS.
Synthetic fixture cannot claim self-likeness; human review remains REVIEW_REQUIRED.
Gate2 / CCS baselines read-only. Not Gate8 participant evidence. Production NO-GO.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.7" / "product" / "quick_profile" / "gate3"
GATE2_HASH = "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
GATE2_FREEZE = ROOT / "dist/v0.7/product/quick_profile/gate2/V07_QP_GATE2_OFFICIAL_FREEZE.json"
DRAFT_DIR = ROOT / "dist/v0.7/product/quick_profile/gate2/validation/dryrun/run1/eligible_frontal"
DRAFT_BLEND = DRAFT_DIR / "NURION_QuickProfile_DryRun_V1.blend"
DRAFT_RECIPE = ROOT / "dist/v0.7/product/quick_profile/gate2/validation/dryrun/run1/eligible_frontal_RECIPE.json"
DRAFT_RESULT = ROOT / "dist/v0.7/product/quick_profile/gate2/validation/dryrun/run1/eligible_frontal_PIPELINE_RESULT.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
INSPECT = ROOT / "tools" / "blender_quick_profile_gate3_face_inspect.py"
COMMAND = "NURION Quick Profile Single Image Pipeline Gate 3 Internal Face Draft Quality Review GO"

SEALED = [
    (ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend", "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"),
    (ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend", "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"),
]


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _param_hash(params: dict) -> str:
    raw = json.dumps(
        {k: v for k, v in params.items() if k != "parameterHash"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _evidence_count(folder: Path) -> int:
    if not folder.exists():
        return 0
    return len([p for p in folder.glob("*.json") if p.is_file() and not p.name.startswith("_")])


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    reviews_dir = OUT / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    (reviews_dir / "_README.txt").write_text(
        "Place completed human face-draft quality reviews here. "
        "Do not invent scores. Real human photos require consent, access control, and deletion records. "
        "These reviews are NOT Gate 8 participant evidence.\n",
        encoding="utf-8",
    )

    # Gate2 freeze pin
    freeze = json.loads(GATE2_FREEZE.read_text(encoding="utf-8"))
    if freeze.get("parameterHash") != GATE2_HASH or not freeze.get("LOCKED"):
        raise SystemExit("Gate2 freeze pin mismatch or not locked")

    for p, exp in SEALED:
        if _sha(p) != exp:
            raise SystemExit(f"Sealed baseline mutated: {p}")

    params_path = OUT / "V07_QP_GATE3_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    ph = _param_hash(params)
    params["parameterHash"] = ph
    _write(params_path, params)

    if not DRAFT_BLEND.exists() or not DRAFT_RECIPE.exists() or not DRAFT_RESULT.exists():
        raise SystemExit("Gate2 validated eligible draft artifacts missing")

    result = json.loads(DRAFT_RESULT.read_text(encoding="utf-8"))
    recipe = json.loads(DRAFT_RECIPE.read_text(encoding="utf-8"))

    caps_path = OUT / "_polished_caps.json"
    _write(caps_path, params["polishedCaps"])
    inspect_json = OUT / "V07_QP_GATE3_BLENDER_STRUCTURAL_INSPECT.json"
    proc = subprocess.run(
        [
            str(BLENDER),
            "--background",
            "--python",
            str(INSPECT),
            "--",
            "--draft-blend",
            str(DRAFT_BLEND),
            "--recipe-json",
            str(DRAFT_RECIPE),
            "--polished-caps-json",
            str(caps_path),
            "--out-json",
            str(inspect_json),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    (OUT / "blender_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (OUT / "blender_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        print(proc.stderr[-8000:] if proc.stderr else proc.stdout)
        return proc.returncode
    inspect = json.loads(inspect_json.read_text(encoding="utf-8"))

    axis_results = {}

    # Structural automated
    disc = result.get("disclosure") or {}
    disclosure_ok = disc == {
        "face": "SINGLE_IMAGE_IDENTITY_ESTIMATE",
        "body": "HEIGHT_WEIGHT_CANONICAL_RECOMMENDATION",
        "back": "UNOBSERVED_STANDARD_COMPLETION",
        "resultGrade": "QUICK_PROFILE_PREVIEW",
        "faceAuthentication": "OUT_OF_SCOPE",
        "claimFullRealBodyReconstruction": "DENY",
    } and bool(result.get("userFacingDisclosureKo"))
    axis_results["UNOBSERVABLE_PARTS_CLEAR_DISCLOSURE"] = {
        "status": "PASS" if disclosure_ok else "FAIL",
        "mode": "STRUCTURAL_AUTOMATED",
        "autoSimilarityUsed": False,
    }

    beau = recipe.get("beautificationValues") or {}
    polished_ok = inspect.get("polishedWithinCaps") and inspect.get("ageImpressionWithinCap")
    # gender/age shift proxy: AgeImpression within POLISHED cap; no ASPIRATIONAL
    gender_age_ok = polished_ok and recipe.get("beautificationMode") == "POLISHED"
    axis_results["NO_EXCESSIVE_BEAUTIFY_GENDER_AGE_SHIFT"] = {
        "status": "PASS" if gender_age_ok else "FAIL",
        "mode": "STRUCTURAL_AUTOMATED",
        "detail": {"mode": recipe.get("beautificationMode"), "beau": beau},
    }

    axis_results["OFF_FRONTAL_VIRTUAL_VIEW_COLLAPSE_DISTORTION"] = {
        "status": "PASS" if not inspect.get("offFrontalCollapseDetected") else "FAIL",
        "mode": "STRUCTURAL_AUTOMATED",
        "detail": inspect.get("offFrontalViews"),
    }

    axis_results["STANDARD_BODY_DOES_NOT_BLOCK_FACE_RECOGNITION"] = {
        "status": "PASS" if not inspect.get("standardBodyBlocksFaceProxy") else "REVIEW_REQUIRED",
        "mode": "STRUCTURAL_AUTOMATED",
        "detail": {"bodyHeadSize": inspect.get("bodyHeadSize"), "bmiIsBodyFatJudgment": "DENY"},
    }

    # Hairline axis present; glasses not in synthetic fixture → disclose REVIEW for real photos
    id_vals = recipe.get("identityValues") or {}
    hairline_ok = "ID_Hairline" in id_vals
    axis_results["SKIN_TONE_GLASSES_HAIRLINE"] = {
        "status": "PASS" if hairline_ok else "FAIL",
        "mode": "STRUCTURAL_AUTOMATED",
        "detail": {
            "hairlinePresent": hairline_ok,
            "glassesInSyntheticFixture": "NOT_PRESENT_DISCLOSED",
            "skinToneEstimate": "VIA_IMAGE_MEAN_RGB_ONLY",
        },
    }

    # Human self-likeness axes: cannot auto PASS (synthetic + autoSimilarity DENY)
    for axis in params["humanSelfLikenessAxes"]:
        axis_results[axis] = {
            "status": "REVIEW_REQUIRED",
            "mode": "HUMAN_REQUIRED",
            "reason": "SYNTHETIC_FIXTURE_AND_AUTO_SIMILARITY_ALONE_DENY",
            "autoSimilarityUsedAlone": "DENY",
        }

    structural_fail = any(
        axis_results[a]["status"] == "FAIL" for a in params["structuralAutomatedAxes"] if a in axis_results
    )
    human_reviews = [
        p for p in reviews_dir.glob("*.json") if p.is_file() and not p.name.startswith("_")
    ]
    human_collected = len(human_reviews) > 0

    if structural_fail:
        verdict = "FAIL"
    elif not human_collected:
        # Protocol/review complete structurally; self-likeness still required
        verdict = "REVIEW_REQUIRED"
    else:
        # Would adjudicate human forms; none expected now
        verdict = "REVIEW_REQUIRED"

    # Force-generate deny confirmation
    force_gen = params.get("forceGenerateOnQualityFail") == "DENY"

    ev_root = ROOT / "dist/v0.7/canonical/gate8/evidence"
    ev_counts = {
        sub: _evidence_count(ev_root / sub)
        for sub in ("consents", "self_eval", "acquaintance_eval", "stranger_eval", "revocation", "phase1_full_body_motion")
    }

    g8 = json.loads((ROOT / "dist/v0.7/canonical/gate8/V07_CCS_GATE8_OFFICIAL_BASELINE.json").read_text(encoding="utf-8"))
    g8_ok = g8.get("parameterHash") == GATE8_HASH

    now = datetime.now(timezone.utc).isoformat()
    report = {
        "schema": "NURION_V07_QP_GATE3_FACE_DRAFT_QUALITY_REVIEW_REPORT",
        "command": COMMAND,
        "sourceDraft": str(DRAFT_DIR.relative_to(ROOT)).replace("\\", "/"),
        "sourceSyntheticFixture": True,
        "syntheticFixtureSelfLikenessClaim": "DENY",
        "axisResults": axis_results,
        "structuralAutomatedVerdict": "FAIL" if structural_fail else "PASS",
        "humanSelfLikenessVerdict": "REVIEW_REQUIRED",
        "humanReviewFormsCollected": len(human_reviews),
        "autoSimilarityScoreAlonePass": "DENY",
        "bmiIsBodyFatOrMuscleJudgment": "DENY",
        "forceGenerateOnQualityFail": "DENY" if force_gen else "VIOLATION",
        "onQualityFailAllowed": params["onQualityFail"],
        "countsAsGate8ParticipantEvidence": "DENY",
        "gate8EvidenceDirCounts": ev_counts,
        "gate2ParameterHashPinned": GATE2_HASH,
        "gate2ReadOnly": True,
        "ccsBaselinesReadOnly": True,
        "gate8BaselineUnchanged": g8_ok,
        "blenderInspect": "V07_QP_GATE3_BLENDER_STRUCTURAL_INSPECT.json",
        "production": "NO-GO",
        "completedAt": now,
    }
    _write(OUT / "V07_QP_GATE3_FACE_DRAFT_QUALITY_REVIEW_REPORT.json", report)

    status = {
        "schema": "NURION_V07_QP_GATE3_STATUS",
        "track": "NURION Quick Profile Single Image Pipeline",
        "gate": 3,
        "command": COMMAND,
        "V07_QP_GATE3": verdict,
        "LOCKED": True,
        "lockMeaning": "FACE_DRAFT_QUALITY_REVIEW_PROTOCOL_LOCKED_SELF_LIKENESS_REVIEW_REQUIRED",
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "gate2ParameterHash": GATE2_HASH,
        "gate2Mutation": "DENY",
        "structuralAutomatedReview": "FAIL" if structural_fail else "PASS",
        "humanSelfLikenessReview": "REVIEW_REQUIRED",
        "productFaceQualityClaim": "DENY",
        "autoSimilarityScoreAlonePass": "DENY",
        "participantEvidenceCounting": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "bmiIsBodyFatOrMuscleJudgment": "DENY",
        "forceGenerateOnQualityFail": "DENY",
        "realHumanPhotoRequiresConsentAccessDeletion": True,
        "gate8BaselineMutation": "DENY",
        "gate8ParameterHash": GATE8_HASH,
        "production": "NO-GO",
        "next": "AWAIT_HUMAN_FACE_DRAFT_QUALITY_REVIEWS_OR_CONSENTED_REAL_PHOTO_INTAKE",
        "updatedAt": now,
    }
    _write(OUT / "V07_QP_GATE3_STATUS.json", status)

    freeze = {
        "schema": "NURION_V07_QP_GATE3_OFFICIAL_FREEZE",
        "V07_QP_GATE3": verdict,
        "LOCKED": True,
        "lockMeaning": "FACE_DRAFT_QUALITY_REVIEW_PROTOCOL_LOCKED_SELF_LIKENESS_REVIEW_REQUIRED",
        "parameterHash": ph,
        "gate2ParameterHash": GATE2_HASH,
        "structuralAutomatedReview": status["structuralAutomatedReview"],
        "humanSelfLikenessReview": "REVIEW_REQUIRED",
        "productFaceQualityClaim": "DENY",
        "participantEvidenceCounting": "DENY",
        "gate8BaselineMutation": "DENY",
        "production": "NO-GO",
        "lockedAt": now,
    }
    _write(OUT / "V07_QP_GATE3_OFFICIAL_FREEZE.json", freeze)

    op = {
        "schema": "NURION_V07_QP_GATE3_OFFICIAL_OPERATOR_CONFIRMATION",
        "confirmation": "OPERATOR_ISSUED_GATE3_INTERNAL_FACE_DRAFT_QUALITY_REVIEW_GO",
        "command": COMMAND,
        "confirmedAt": now,
        "V07_QP_GATE3": verdict,
        "LOCKED": True,
        "parameterHash": ph,
        "gate2ParameterHash": GATE2_HASH,
        "structuralAutomatedReview": status["structuralAutomatedReview"],
        "humanSelfLikenessReview": "REVIEW_REQUIRED",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }
    _write(OUT / "V07_QP_GATE3_OFFICIAL_OPERATOR_CONFIRMATION.json", op)

    protocol = """# QUICK PROFILE Gate 3 — Internal Face Draft Quality Review

Gate 2 / Canonical 기준선: **읽기 전용**  
Production: **NO-GO**  
Gate 8 참가자 증거 산정: **DENY**  
자동 유사도만으로 PASS: **DENY**  
BMI → 체지방·근육량 판정 확대: **DENY**  
품질 실패 시 강제 생성: **DENY** → `REVIEW_REQUIRED` 또는 `ABSTAIN`  
실사 사진: 별도 동의·접근통제·삭제 기록 필요
"""
    (OUT / "V07_QP_GATE3_PROTOCOL.md").write_text(protocol, encoding="utf-8")

    track_path = OUT.parent / "V07_QUICK_PROFILE_PIPELINE_STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.exists() else {}
    track.update(
        {
            "schema": "NURION_V07_QUICK_PROFILE_PIPELINE_STATUS",
            "gate2": "PASS",
            "gate2Locked": True,
            "gate2ParameterHash": GATE2_HASH,
            "gate3": verdict,
            "gate3Locked": True,
            "gate3ParameterHash": ph,
            "gate3StructuralAutomatedReview": status["structuralAutomatedReview"],
            "gate3HumanSelfLikenessReview": "REVIEW_REQUIRED",
            "participantEvidenceCounting": "DENY",
            "production": "NO-GO",
            "nextCommand": "AWAIT_HUMAN_FACE_DRAFT_QUALITY_REVIEWS",
            "updatedAt": now,
        }
    )
    _write(track_path, track)

    print(
        json.dumps(
            {
                "V07_QP_GATE3": verdict,
                "LOCKED": True,
                "parameterHash": ph,
                "structuralAutomatedReview": status["structuralAutomatedReview"],
                "humanSelfLikenessReview": "REVIEW_REQUIRED",
                "productFaceQualityClaim": "DENY",
            },
            ensure_ascii=False,
        )
    )
    return 0 if not structural_fail else 1


if __name__ == "__main__":
    raise SystemExit(main())
