"""NURION Quick Profile Gate 3 Consented Human Draft Review Intake GO.

Sets up Gate8-separated internal review intake. Does not invent participants.
If fewer than 3 consented real-photo packages are ready, keeps Gate3 REVIEW_REQUIRED / NO-GO.
Does not expand to Gate8 evidence or product quality approval.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.7" / "product" / "quick_profile" / "gate3"
INTAKE = OUT / "intake"
GATE3_HASH = "cde535402d8a92b50371bed8fefb82efabbb15c9ce2da64081855dd6a98f81bd"
GATE2_HASH = "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3"
GATE8_HASH = "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697"
COMMAND = "NURION Quick Profile Gate 3 Consented Human Draft Review Intake GO"
ALLOWED = {
    "INTERNAL_FACE_DRAFT_REVIEW_PASS",
    "PASS_WITH_LIMITATIONS",
    "REVIEW_REQUIRED",
    "ABSTAIN",
}


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


def _json_files(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.json") if p.is_file() and not p.name.startswith("_"))


def _valid_consent(doc: dict) -> bool:
    need_true = [
        "adultConfirmed",
        "photoUseConsentInternalDraftReviewOnly",
        "heightWeightUseConsent",
        "characterLikenessConsentInternalOnly",
        "understandsNotGate8Evidence",
        "understandsNotProductQualityApproval",
        "retentionUnderstood",
        "deletionUnderstood",
        "accessControlAcknowledged",
        "signatureOrEquivalent",
    ]
    if not doc.get("anonymousParticipantId") or not doc.get("consentTimestampUtc"):
        return False
    return all(doc.get(k) is True for k in need_true)


def _valid_manifest(doc: dict) -> bool:
    if doc.get("status") == "NOT_COLLECTED":
        return False
    req = [
        "anonymousParticipantId",
        "originalImageRelativePath",
        "originalImageSha256",
        "heightCm",
        "weightKg",
        "consentFile",
        "inputFixedAtUtc",
    ]
    if any(not doc.get(k) for k in req):
        return False
    # verify image hash if file exists
    img = INTAKE / doc["originalImageRelativePath"]
    if not img.is_file():
        return False
    h = hashlib.sha256()
    with img.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest() == doc["originalImageSha256"]


def main() -> int:
    for sub in (
        "consents",
        "inputs",
        "photos",
        "drafts",
        "self_eval",
        "internal_visual_review",
        "retention_deletion",
        "receipts",
    ):
        d = INTAKE / sub
        d.mkdir(parents=True, exist_ok=True)
        readme = d / "_README.txt"
        if not readme.exists():
            readme.write_text(
                f"Gate3 consented human draft review — {sub}. "
                "Adults only. Gate8 evidence DENY. Do not invent participants or scores.\n",
                encoding="utf-8",
            )

    params_path = INTAKE / "V07_QP_GATE3_INTAKE_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    if params.get("gate3ProtocolParameterHash") != GATE3_HASH:
        raise SystemExit("Gate3 protocol hash pin mismatch")
    iph = _param_hash(params)
    params["parameterHash"] = iph
    _write(params_path, params)

    consents = _json_files(INTAKE / "consents")
    manifests = _json_files(INTAKE / "inputs")
    self_evals = _json_files(INTAKE / "self_eval")
    visuals = _json_files(INTAKE / "internal_visual_review")
    retentions = _json_files(INTAKE / "retention_deletion")

    valid_consents = []
    for p in consents:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if _valid_consent(doc):
            valid_consents.append(doc)

    valid_manifests = []
    for p in manifests:
        doc = json.loads(p.read_text(encoding="utf-8"))
        if _valid_manifest(doc):
            valid_manifests.append(doc)

    # pair by anonymousParticipantId
    consent_ids = {c["anonymousParticipantId"] for c in valid_consents}
    manifest_ids = {m["anonymousParticipantId"] for m in valid_manifests}
    ready_ids = sorted(consent_ids & manifest_ids)

    min_n = int(params["minConsentedAdultParticipants"])
    ready_count = len(ready_ids)
    real_inputs_present = ready_count > 0
    enough_for_review_attempt = ready_count >= min_n

    # Do not invent drafts/reviews when inputs absent
    draft_packages = _json_files(INTAKE / "drafts")
    review_receipts = _json_files(INTAKE / "receipts")

    missing = []
    if ready_count < min_n:
        missing.append(f"CONSENTED_ADULT_PACKAGES_LT_{min_n}")
    if ready_count == 0:
        missing.append("NO_REAL_PHOTO_INPUTS")
    if enough_for_review_attempt:
        # check companion artifacts per id
        self_ids = {
            json.loads(p.read_text(encoding="utf-8")).get("anonymousParticipantId")
            for p in self_evals
            if json.loads(p.read_text(encoding="utf-8")).get("status") != "NOT_COLLECTED"
        }
        vis_ids = {
            json.loads(p.read_text(encoding="utf-8")).get("anonymousParticipantId")
            for p in visuals
            if json.loads(p.read_text(encoding="utf-8")).get("status") != "NOT_COLLECTED"
        }
        ret_ids = {
            json.loads(p.read_text(encoding="utf-8")).get("anonymousParticipantId")
            for p in retentions
            if json.loads(p.read_text(encoding="utf-8")).get("status") != "NOT_COLLECTED"
        }
        for pid in ready_ids:
            if pid not in self_ids:
                missing.append(f"SELF_EVAL_MISSING:{pid}")
            if pid not in vis_ids:
                missing.append(f"INTERNAL_VISUAL_MISSING:{pid}")
            if pid not in ret_ids:
                missing.append(f"RETENTION_DELETION_MISSING:{pid}")
        if not draft_packages:
            missing.append("GATE2_QUICK_DRAFTS_NOT_GENERATED")
        if not review_receipts:
            missing.append("GATE3_REVIEW_RECEIPT_ABSENT")

    # Intake phase verdict
    if not real_inputs_present:
        intake_verdict = "REVIEW_REQUIRED"
        intake_state = "AWAITING_CONSENTED_REAL_PHOTO_PACKAGES"
    elif not enough_for_review_attempt:
        intake_verdict = "REVIEW_REQUIRED"
        intake_state = "PARTIAL_INTAKE_BELOW_MINIMUM"
    elif missing:
        intake_verdict = "REVIEW_REQUIRED"
        intake_state = "INTAKE_PRESENT_REVIEWS_INCOMPLETE"
    else:
        # Aggregate only explicit overall fields; still pipeline-improvement only
        overalls = []
        for p in visuals:
            doc = json.loads(p.read_text(encoding="utf-8"))
            if doc.get("overall") in ALLOWED:
                overalls.append(doc["overall"])
        if any(o == "ABSTAIN" for o in overalls):
            intake_verdict = "ABSTAIN"
        elif any(o == "REVIEW_REQUIRED" for o in overalls) or not overalls:
            intake_verdict = "REVIEW_REQUIRED"
        elif all(o == "INTERNAL_FACE_DRAFT_REVIEW_PASS" for o in overalls):
            intake_verdict = "INTERNAL_FACE_DRAFT_REVIEW_PASS"
        else:
            intake_verdict = "PASS_WITH_LIMITATIONS"
        intake_state = "INTERNAL_REVIEW_COMPLETE_PIPELINE_IMPROVEMENT_ONLY"

    now = datetime.now(timezone.utc).isoformat()

    # Keep Gate3 official status REVIEW_REQUIRED when no complete internal review pass
    gate3_keep = "REVIEW_REQUIRED"
    if intake_verdict in ("INTERNAL_FACE_DRAFT_REVIEW_PASS", "PASS_WITH_LIMITATIONS") and enough_for_review_attempt and not missing:
        # Gate3 protocol remains locked; humanSelfLikeness may upgrade only for internal track
        gate3_keep = "REVIEW_REQUIRED"  # product face claim still denied; internal track separate
        # Actually user said results only for pipeline improvement - Gate3 official can stay REVIEW_REQUIRED
        # unless we record internalIntakeVerdict separately. Keep official Gate3 as REVIEW_REQUIRED
        # until product-facing claim allowed - user: don't expand to product quality approval.
        gate3_keep = "REVIEW_REQUIRED"

    scan = {
        "schema": "NURION_V07_QP_GATE3_INTAKE_SCAN_RECEIPT",
        "command": COMMAND,
        "intakeParameterHash": iph,
        "gate3ProtocolParameterHash": GATE3_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "validConsentCount": len(valid_consents),
        "validManifestCount": len(valid_manifests),
        "readyAnonymousParticipantIds": ready_ids,
        "readyPackageCount": ready_count,
        "minRequired": min_n,
        "selfEvalFiles": len(self_evals),
        "internalVisualReviewFiles": len(visuals),
        "retentionDeletionFiles": len(retentions),
        "draftPackageFiles": len(draft_packages),
        "reviewReceiptFiles": len(review_receipts),
        "missing": missing,
        "intakeVerdict": intake_verdict,
        "intakeState": intake_state,
        "usageRestriction": params["usageRestriction"],
        "countsAsGate8ParticipantEvidence": "DENY",
        "includeInGate8ParticipantCount": "DENY",
        "expandToProductQualityApproval": "DENY",
        "expandToActualSimilarityClaim": "DENY",
        "inventedParticipants": "DENY",
        "production": "NO-GO",
        "scannedAt": now,
    }
    _write(INTAKE / "V07_QP_GATE3_INTAKE_SCAN_RECEIPT.json", scan)

    # Gate3-dedicated intake receipt (even when awaiting)
    receipt = {
        "schema": "NURION_V07_QP_GATE3_CONSENTED_HUMAN_DRAFT_REVIEW_INTAKE_RECEIPT",
        "command": COMMAND,
        "intakeParameterHash": iph,
        "V07_QP_GATE3": gate3_keep,
        "LOCKED": True,
        "internalIntakeVerdict": intake_verdict,
        "allowedVerdicts": sorted(ALLOWED),
        "intakeState": intake_state,
        "readyPackageCount": ready_count,
        "minRequired": min_n,
        "gate2FrozenPipelineReady": True,
        "blindModesPlanned": ["NATURAL", "POLISHED"],
        "nextHumanWork": [
            "COLLECT_3_CONSENTED_ADULT_PHOTO_HEIGHT_WEIGHT_PACKAGES",
            "FIX_SHA256_AND_ANONYMOUS_PARTICIPANT_ID",
            "GENERATE_QUICK_DRAFTS_VIA_GATE2_FROZEN_PIPELINE",
            "BLIND_NATURAL_VS_POLISHED",
            "WRITE_SELF_EVAL_AND_INTERNAL_VISUAL_REVIEW",
            "RECORD_EXCESSIVE_BEAUTIFY_IDENTITY_LOSS_VIEW_COLLAPSE",
            "VERIFY_RETENTION_AND_DELETION",
            "ISSUE_PER_PARTICIPANT_GATE3_REVIEW_RECEIPT",
        ]
        if ready_count < min_n
        else [
            "COMPLETE_MISSING_REVIEWS_AND_DELETION_VERIFICATION",
            "ISSUE_GATE3_INTERNAL_REVIEW_RECEIPTS",
        ],
        "countsAsGate8ParticipantEvidence": "DENY",
        "pipelineImprovementDecisionOnly": True,
        "production": "NO-GO",
        "issuedAt": now,
    }
    _write(INTAKE / "receipts" / "V07_QP_GATE3_INTAKE_RECEIPT.json", receipt)

    # Update Gate3 status: keep REVIEW_REQUIRED / NO-GO when inputs absent
    status_path = OUT / "V07_QP_GATE3_STATUS.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status.update(
        {
            "V07_QP_GATE3": gate3_keep,
            "LOCKED": True,
            "humanSelfLikenessReview": "REVIEW_REQUIRED",
            "productFaceQualityClaim": "DENY",
            "consentedHumanDraftReviewIntake": {
                "command": COMMAND,
                "intakeParameterHash": iph,
                "intakeState": intake_state,
                "internalIntakeVerdict": intake_verdict,
                "readyPackageCount": ready_count,
                "minRequired": min_n,
                "scanReceipt": "intake/V07_QP_GATE3_INTAKE_SCAN_RECEIPT.json",
                "intakeReceipt": "intake/receipts/V07_QP_GATE3_INTAKE_RECEIPT.json",
                "countsAsGate8ParticipantEvidence": "DENY",
            },
            "countsAsGate8ParticipantEvidence": "DENY",
            "production": "NO-GO",
            "next": "AWAIT_CONSENTED_ADULT_INTAKE_PACKAGES_GE_3"
            if ready_count < min_n
            else "AWAIT_COMPLETE_INTERNAL_REVIEWS_AND_RECEIPTS",
            "updatedAt": now,
        }
    )
    _write(status_path, status)

    # freeze remains REVIEW_REQUIRED
    freeze_path = OUT / "V07_QP_GATE3_OFFICIAL_FREEZE.json"
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    freeze.update(
        {
            "V07_QP_GATE3": gate3_keep,
            "LOCKED": True,
            "humanSelfLikenessReview": "REVIEW_REQUIRED",
            "intakeParameterHash": iph,
            "intakeState": intake_state,
            "production": "NO-GO",
            "intakeRegisteredAt": now,
        }
    )
    _write(freeze_path, freeze)

    track_path = OUT.parent / "V07_QUICK_PROFILE_PIPELINE_STATUS.json"
    track = json.loads(track_path.read_text(encoding="utf-8")) if track_path.exists() else {}
    track.update(
        {
            "gate3": gate3_keep,
            "gate3Locked": True,
            "gate3ParameterHash": GATE3_HASH,
            "gate3IntakeParameterHash": iph,
            "gate3IntakeState": intake_state,
            "gate3InternalIntakeVerdict": intake_verdict,
            "participantEvidenceCounting": "DENY",
            "production": "NO-GO",
            "nextCommand": "AWAIT_CONSENTED_ADULT_INTAKE_PACKAGES_GE_3"
            if ready_count < min_n
            else "COMPLETE_GATE3_INTERNAL_DRAFT_REVIEWS",
            "updatedAt": now,
        }
    )
    _write(track_path, track)

    print(
        json.dumps(
            {
                "command": COMMAND,
                "V07_QP_GATE3": gate3_keep,
                "intakeState": intake_state,
                "internalIntakeVerdict": intake_verdict,
                "readyPackageCount": ready_count,
                "intakeParameterHash": iph,
                "production": "NO-GO",
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
