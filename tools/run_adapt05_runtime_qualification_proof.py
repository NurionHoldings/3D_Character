#!/usr/bin/env python3
"""ADAPT-05 proof — AD5-G01…G19 automated. AD5-G20 HUMAN ONLY."""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

here = Path(__file__).resolve()
parent = here.parents[1]
if parent.name == "repo":
    sys.path.insert(0, str(parent))
else:
    sys.path.insert(0, str(Path(os.environ.get("NURION_REPO_ROOT", str(parent)))))

from fast_track.adaptation.audit_paths import resolve_adapt01_roots
from fast_track.adaptation.authoritative_runtime_qualification_binding import (
    ADAPT04_PASS_AUDIT_ZIP_SHA256,
    ADAPT04_PASS_RECEIPT_SHA256,
    verify_runtime_qualification_binding,
)
from fast_track.adaptation.inspector import sha256_file
from fast_track.adaptation.runtime_qualification import (
    CANONICAL_QUALIFIED_CHARACTER_ID,
    compute_qualification_report_digest,
    load_runtime_binding,
    qualify_from_glb,
)


def _roots():
    r = resolve_adapt01_roots(__file__)
    pkg = Path(r["packageRoot"])
    if r["extracted"]:
        fix = pkg / "fixtures"
        rep = pkg / "reports"
        derived = pkg / "derived"
    else:
        repo = Path(r["repoRoot"])
        fix = repo / "fast_track/adaptation/fixtures_adapt05"
        rep = pkg / "reports_adapt05"
        derived = pkg / "derived_adapt05"
    ev = Path(r["evidence"])
    sem = Path(r["semantic"])
    adapt_pkg = pkg if r["extracted"] else Path(r["repoRoot"]) / "fast_track/working/adaptation_engine_v1"
    return {
        **r,
        "fixtures": fix,
        "reports": rep,
        "derived": derived,
        "evidence": ev,
        "semantic": sem,
        "runtimeBinding": sem / "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1.json",
        "augBinding": sem / "NURION_ADAPT04_REQUIREMENT_BINDING_V1.json",
        "faceBinding": sem / "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json",
        "adapt02Binding": sem / "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
        "contract": sem / "NURION_ADAPT05_RUNTIME_QUALIFICATION_CONTRACT_V1.json",
        "provenance": adapt_pkg / "evidence/NURION-ADAPT-05_UPSTREAM_PROVENANCE_RECEIPT.json",
        "adapt04Pass": adapt_pkg / "evidence/NURION-ADAPT-04_PASS_receipt.json",
        "adapt03Pass": adapt_pkg / "evidence/NURION-ADAPT-03_PASS_receipt.json",
        "adapt02Pass": adapt_pkg / "evidence/NURION-ADAPT-02_PASS_receipt.json",
        "adapt01Pass": adapt_pkg / "evidence/NURION-ADAPT-01_PASS_receipt.json",
        "adapt04Provenance": adapt_pkg / "evidence/NURION-ADAPT-04_UPSTREAM_PROVENANCE_RECEIPT.json",
        "adapt03Provenance": adapt_pkg / "evidence/NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json",
    }


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _write(ev: Path, name: str, obj: object) -> None:
    ev.mkdir(parents=True, exist_ok=True)
    (ev / name).write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_all() -> dict:
    r = _roots()
    FIX: Path = r["fixtures"]
    REP: Path = r["reports"]
    DERIVED: Path = r["derived"]
    EV: Path = r["evidence"]
    REPO: Path = r["repoRoot"]
    EXTRACTED = bool(r["extracted"])
    REP.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)
    FIX.mkdir(parents=True, exist_ok=True)

    os.environ["NURION_ADAPT05_FIXTURE_DIR"] = str(FIX)
    os.environ["NURION_ADAPT05_REPO_ROOT"] = str(REPO)
    os.environ["NURION_ADAPT04_FIXTURE_DIR"] = str(FIX)  # glbs colocated after build
    os.environ["NURION_ADAPT04_REPO_ROOT"] = str(REPO)
    from tools.build_adapt05_fixtures import main as build_fix

    build_fix()

    binding = load_runtime_binding(r["runtimeBinding"])
    auth_verify = verify_runtime_qualification_binding(
        binding,
        repo_root=REPO if not EXTRACTED else None,
        provenance_path=r["provenance"],
        adapt01_pass_path=r["adapt01Pass"],
        adapt02_pass_path=r["adapt02Pass"],
        adapt03_pass_path=r["adapt03Pass"],
        adapt04_pass_path=r["adapt04Pass"],
    )
    _ok(auth_verify["status"] == "PASS", f"binding blocked: {auth_verify.get('blockers')}")

    def run_asset(name: str, force: dict | None = None, cid: str | None = None):
        sub = DERIVED / (cid or name)
        sub.mkdir(parents=True, exist_ok=True)
        return qualify_from_glb(
            FIX / name,
            r["adapt02Binding"],
            r["faceBinding"],
            r["augBinding"],
            r["runtimeBinding"],
            sub,
            character_id=cid or name,
            force_flags=force,
        )

    gates: dict[str, dict] = {}

    # G01 Authoritative Runtime Input Identity
    _ok(r["runtimeBinding"].is_file(), "runtime binding")
    _ok(r["contract"].is_file(), "contract")
    _ok(r["provenance"].is_file(), "provenance")
    gates["AD5-G01"] = {
        "status": "PASS",
        "runtimeBindingSha256": sha256_file(r["runtimeBinding"]),
        "adapt04PassZipPin": ADAPT04_PASS_AUDIT_ZIP_SHA256,
        "adapt04PassReceiptSha256": ADAPT04_PASS_RECEIPT_SHA256,
        "verifyMode": auth_verify["mode"],
        "verifyChecks": auth_verify["checks"],
    }

    # Primary AUTHORITATIVE qualified candidate (exactly one)
    _, _, _, a04_q, q_full = run_asset(
        "body_minimal_face.glb", cid=CANONICAL_QUALIFIED_CHARACTER_ID
    )
    _ok(q_full["finalClassification"] == "QUALIFIED", "canonical must be QUALIFIED")
    canonical_digest = q_full["qualificationReportDigest"]
    canonical_runtime = q_full["runtimeCompatibilityDigest"]
    canonical_handoff = q_full["adapt06HandoffDigest"]
    canonical_candidate = q_full["candidateIdentity"]["derivedArtifactSha256"]
    _ok(canonical_digest == compute_qualification_report_digest(q_full), "digest recomputable")
    _ok(
        (q_full.get("adapt06Handoff") or {}).get("qualificationReportDigest") == canonical_digest,
        "handoff must pin qualificationReportDigest",
    )

    # Non-authoritative fixture evidence (digests MUST NOT be treated as canonical)
    _, _, _, a04_na, q_na = run_asset("body_minimal_face.glb", force={"noAugmentationRequired": True}, cid="fixture_no_aug")
    _, _, _, a04_meshy, q_meshy = run_asset("meshy_style.glb", cid="fixture_meshy")

    auth_report = {
        "schema": "NURION_ADAPT05_CANONICAL_QUALIFICATION_REPORT_V1",
        "authorityRole": "AUTHORITATIVE",
        "characterId": CANONICAL_QUALIFIED_CHARACTER_ID,
        "adapt05": q_full,
    }
    (REP / "ADAPT05_report_canonical_qualified.json").write_text(
        json.dumps(auth_report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    for label, report, role in (
        ("fixture_no_aug", q_na, "NON_AUTHORITATIVE_FIXTURE_EVIDENCE"),
        ("fixture_meshy", q_meshy, "NON_AUTHORITATIVE_FIXTURE_EVIDENCE"),
    ):
        (REP / f"ADAPT05_report_{label}.json").write_text(
            json.dumps(
                {
                    "schema": "NURION_ADAPT05_FIXTURE_QUALIFICATION_REPORT_V1",
                    "authorityRole": role,
                    "canonicalQualificationReportDigest": canonical_digest,
                    "note": "Fixture digest is NOT the stage authority seal",
                    "adapt05": report,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    # G02 ADAPT-04 PASS / Candidate Provenance
    _ok(r["adapt04Pass"].is_file(), "adapt04 pass")
    _ok(sha256_file(r["adapt04Pass"]) == ADAPT04_PASS_RECEIPT_SHA256, "adapt04 pass sha")
    _ok(q_full.get("sourceIdentity", {}).get("adapt04Classification") in ("AUGMENTED", "NO_AUGMENTATION_REQUIRED"), "a04 class")
    _, _, _, _, q_prov = run_asset("body_minimal_face.glb", force={"adapt04ProvenanceMismatch": True}, cid="prov_bad")
    _ok(q_prov["finalClassification"] == "BLOCKED", "prov mismatch")
    gates["AD5-G02"] = {"status": "PASS", "adapt04PassIntegrity": "VERIFIED"}

    # G03 Exact Candidate Identity Binding
    id1 = q_full["candidateIdentity"]
    _ok(id1.get("sourceAssetSha256"), "source sha")
    _ok(id1.get("derivedArtifactSha256") or q_na["candidateIdentity"].get("sourceAssetSha256"), "derived/source")
    _, _, _, _, q_sha = run_asset("body_minimal_face.glb", force={"candidateShaMismatch": True}, cid="sha_bad")
    _ok(q_sha["finalClassification"] == "BLOCKED", "sha mismatch")
    gates["AD5-G03"] = {"status": "PASS", "candidateIdentity": id1}

    # G04 Structural
    _ok(q_full["structuralQualification"]["status"] == "PASS", "structural")
    _, _, _, _, q_mal = run_asset("body_minimal_face.glb", force={"malformedCandidate": True}, cid="mal")
    _ok(q_mal["finalClassification"] == "BLOCKED", "malformed")
    gates["AD5-G04"] = {"status": "PASS"}

    # G05 BODY
    _ok(q_full["bodyQualification"]["status"] == "PASS", "body")
    _, _, _, _, q_body = run_asset("body_minimal_face.glb", force={"bodyHierarchyMismatch": True}, cid="body_bad")
    _ok(q_body["finalClassification"] == "BLOCKED", "body hierarchy")
    gates["AD5-G05"] = {"status": "PASS"}

    # G06 Root/Pelvis
    _ok(q_full["bodyQualification"]["invariants"]["NURION_root_neq_NURION_pelvis"] is True, "root≠pelvis")
    _, _, _, _, q_rp = run_asset("body_minimal_face.glb", force={"rootPelvisViolation": True}, cid="rp")
    _ok(q_rp["finalClassification"] == "BLOCKED", "rp")
    gates["AD5-G06"] = {"status": "PASS"}

    # G07 FACE/BODY Attachment
    _ok(q_full["faceAttachmentQualification"]["status"] == "PASS", "attach")
    _, _, _, _, q_att = run_asset("body_minimal_face.glb", force={"faceAttachmentMismatch": True}, cid="att")
    _ok(q_att["finalClassification"] == "BLOCKED", "att")
    _, _, _, _, q_comp = run_asset("body_minimal_face.glb", force={"competingFaceRoot": True}, cid="comp")
    _ok(q_comp["finalClassification"] == "BLOCKED", "competing root")
    gates["AD5-G07"] = {"status": "PASS", "soleAttachment": "NURION_head → FACE_Rig_Root"}

    # G08 FACE Semantic
    _ok(q_full["faceQualification"]["status"] == "PASS", "face")
    _, _, _, _, q_expr = run_asset(
        "expression_mapping_required.glb", force={"missingRequiredExpression": True}, cid="expr_bad"
    )
    _ok(q_expr["finalClassification"] == "BLOCKED", "missing expr")
    gates["AD5-G08"] = {"status": "PASS"}

    # G09 Eye
    _ok(q_full["eyeQualification"]["status"] == "PASS", "eye")
    _, _, _, _, q_eye = run_asset("body_minimal_face.glb", force={"leftRightEyeInversion": True}, cid="eye_inv")
    _ok(q_eye["finalClassification"] == "BLOCKED", "eye inv")
    _, _, _, _, q_blink = run_asset("body_minimal_face.glb", force={"missingBlink": True}, cid="blink_miss")
    _ok(q_blink["finalClassification"] == "BLOCKED", "blink miss")
    gates["AD5-G09"] = {"status": "PASS", "eyeCalibration": "PRESERVE"}

    # G10 Expression
    _ok(q_full["expressionQualification"]["status"] == "PASS", "expression")
    gates["AD5-G10"] = {"status": "PASS"}

    # G11 Jaw/Mouth
    _ok(q_full["jawMouthQualification"]["status"] == "PASS", "jaw")
    _, _, _, _, q_jaw = run_asset("talking_augmentation_required.glb", force={"missingJawMouth": True}, cid="jaw")
    _ok(q_jaw["finalClassification"] == "BLOCKED", "jaw miss")
    gates["AD5-G11"] = {"status": "PASS"}

    # G12 TALKING
    _ok(q_full["talkingQualification"]["status"] == "PASS", "talking")
    _, _, _, _, q_talk = run_asset(
        "talking_augmentation_required.glb", force={"talkingIncompatible": True}, cid="talk_bad"
    )
    _ok(q_talk["finalClassification"] == "BLOCKED", "talking blocked")
    gates["AD5-G12"] = {
        "status": "PASS",
        "talkingClassification": q_full["talkingQualification"].get("talkingClassification"),
    }

    # G13 Motion
    _ok(q_full["motionCompatibility"]["status"] == "PASS", "motion")
    _, _, _, _, q_mot = run_asset("body_minimal_face.glb", force={"canonicalMotionIncompatible": True}, cid="mot")
    _ok(q_mot["finalClassification"] == "BLOCKED", "motion bad")
    gates["AD5-G13"] = {"status": "PASS"}

    # G14 Co-play
    _ok(q_full["faceBodyCoPlay"]["status"] == "PASS", "coplay")
    _, _, _, _, q_cp = run_asset("body_minimal_face.glb", force={"faceBodyCoplayFailure": True}, cid="coplay")
    _ok(q_cp["finalClassification"] == "BLOCKED", "coplay fail")
    gates["AD5-G14"] = {"status": "PASS"}

    # G15 Runtime State / Behavior
    _ok(q_full["runtimeStateCompatibility"]["status"] == "PASS", "state")
    _ok(q_full["behaviorRuntimeCompatibility"]["status"] == "PASS", "behavior")
    _, _, _, _, q_st = run_asset("body_minimal_face.glb", force={"runtimeStateIncompatible": True}, cid="state")
    _ok(q_st["finalClassification"] == "BLOCKED", "state bad")
    _, _, _, _, q_bh = run_asset("body_minimal_face.glb", force={"behaviorMappingIncompatible": True}, cid="beh")
    _ok(q_bh["finalClassification"] == "BLOCKED", "behavior bad")
    gates["AD5-G15"] = {"status": "PASS"}

    # G16 Product Release
    _ok(q_full["productReleaseCompatibility"]["status"] == "PASS", "product")
    gates["AD5-G16"] = {"status": "PASS", "nurionV1Modify": "DENY"}

    # G17 Classification / Fail-Closed
    _ok(q_full["finalClassification"] == "QUALIFIED", f"expected QUALIFIED got {q_full['finalClassification']}")
    _ok(q_na["finalClassification"] in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"), "no-aug qualify")
    _, _, _, _, q_mr = run_asset("body_minimal_face.glb", force={"manualReviewRequired": True}, cid="mr")
    _ok(q_mr["finalClassification"] == "MANUAL_REVIEW_REQUIRED", "manual review")
    _, _, _, _, q_up = run_asset("body_minimal_face.glb", force={"upstreamPinMismatch": True}, cid="up")
    _ok(q_up["finalClassification"] == "BLOCKED", "upstream pin")
    _, _, _, _, q_mut = run_asset("body_minimal_face.glb", force={"unauthorizedCandidateMutation": True}, cid="mut")
    _ok(q_mut["finalClassification"] == "BLOCKED", "mutation attempt")
    gates["AD5-G17"] = {
        "status": "PASS",
        "qualifiedSample": q_full["finalClassification"],
        "failClosedVerified": True,
    }

    # G18 Preservation
    v1_none = {
        "nurionV1Mutation": "NONE",
        "product01to06Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "adapt03Mutation": "NONE",
        "adapt04Mutation": "NONE",
        "faceAuthorityMutation": "NONE",
        "bodyCanonicalMutation": "NONE",
        "sourceOriginalMutation": "NONE",
        "candidateMutationDuringAdapt05": "NONE",
        "adapt06Implementation": "NOT_STARTED",
    }
    for k, v in v1_none.items():
        _ok(q_full["preservation"].get(k) == v, f"preservation {k}")
    src = FIX / "body_minimal_face.glb"
    before = src.read_bytes()
    run_asset("body_minimal_face.glb", cid="preserve")
    _ok(src.read_bytes() == before, "source mutated")
    gates["AD5-G18"] = {"status": "PASS", **v1_none}

    # G19 Determinism / Independent — MUST seal the SAME canonical digests
    _, _, _, _, d1 = run_asset("body_minimal_face.glb", cid=CANONICAL_QUALIFIED_CHARACTER_ID)
    _, _, _, _, d2 = run_asset("body_minimal_face.glb", cid=CANONICAL_QUALIFIED_CHARACTER_ID)
    _ok(d1["qualificationReportDigest"] == d2["qualificationReportDigest"], "report det")
    _ok(d1["runtimeCompatibilityDigest"] == d2["runtimeCompatibilityDigest"], "runtime det")
    _ok(d1["adapt06HandoffDigest"] == d2["adapt06HandoffDigest"], "handoff det")
    _ok(d1["qualificationReportDigest"] == canonical_digest, "G19 digest == canonical seal")
    _ok(d1["runtimeCompatibilityDigest"] == canonical_runtime, "G19 runtime == canonical seal")
    _ok(d1["adapt06HandoffDigest"] == canonical_handoff, "G19 handoff == canonical seal")
    _ok(
        d1["candidateIdentity"]["derivedArtifactSha256"] == canonical_candidate,
        "G19 candidate == canonical seal",
    )
    gates["AD5-G19"] = {
        "status": "PASS",
        "executionMode": r["mode"],
        "authorityRole": "AUTHORITATIVE_CANONICAL_SEAL",
        "characterId": CANONICAL_QUALIFIED_CHARACTER_ID,
        "candidateSha256": canonical_candidate,
        "qualificationReportDigest": canonical_digest,
        "runtimeCompatibilityDigest": canonical_runtime,
        "adapt06HandoffDigest": canonical_handoff,
        "determinismVerified": True,
        "fixtureDigestsNonAuthoritative": True,
    }

    gates["AD5-G20"] = {"status": "HUMAN_FINAL_ONLY", "agentMayNotPass": True}

    critical = [
        "AD5-G01",
        "AD5-G02",
        "AD5-G03",
        "AD5-G05",
        "AD5-G06",
        "AD5-G07",
        "AD5-G08",
        "AD5-G09",
        "AD5-G12",
        "AD5-G13",
        "AD5-G14",
        "AD5-G15",
        "AD5-G17",
        "AD5-G18",
        "AD5-G19",
    ]
    for g in critical:
        _ok(gates[g]["status"] == "PASS", f"{g} not PASS")

    automated = [f"AD5-G{i:02d}" for i in range(1, 20)]
    for g in automated:
        _ok(gates[g]["status"] == "PASS", f"{g} failed")

    summary = {
        "schema": "NURION_ADAPT05_PROOF_RECEIPT_V1",
        "revision": "R2",
        "stage": "ADAPT-05",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "executionMode": r["mode"],
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "ADAPT-05_CLOSED_PASS": "DENY_AGENT",
        "ADAPT-06": "LOCKED BY PREDECESSOR",
        "humanPassAuthority": "RESERVED",
        "AD5-G20": "HUMAN_FINAL_ONLY",
        "r1Blocker": "qualificationReportDigest inconsistency across proof receipt / G19 / fixture reports",
        "r2Fix": "Single AUTHORITATIVE canonical qualified candidate seal; fixture digests marked NON_AUTHORITATIVE",
        "automatedGatePassCount": 19,
        "automatedGateTotal": 19,
        "gates": gates,
        "criticalGates": {g: "PASS" for g in critical},
        "canonicalSeal": {
            "characterId": CANONICAL_QUALIFIED_CHARACTER_ID,
            "candidateSha256": canonical_candidate,
            "qualificationReportDigest": canonical_digest,
            "runtimeCompatibilityDigest": canonical_runtime,
            "adapt06HandoffDigest": canonical_handoff,
            "authoritativeReport": "reports/ADAPT05_report_canonical_qualified.json",
        },
        "candidateSha256": canonical_candidate,
        "qualificationReportDigest": canonical_digest,
        "runtimeCompatibilityDigest": canonical_runtime,
        "adapt06HandoffDigest": canonical_handoff,
        "candidateSha": canonical_candidate,
        "adapt04PassReceiptSha256": ADAPT04_PASS_RECEIPT_SHA256,
        "classificationSamples": {
            "canonicalQualified": q_full["finalClassification"],
            "fixtureNoAugmentation": q_na["finalClassification"],
            "fixtureMeshy": q_meshy["finalClassification"],
            "manualReview": q_mr["finalClassification"],
            "blockedSha": q_sha["finalClassification"],
        },
        "fixtureEvidenceNote": "ADAPT05_report_fixture_*.json digests are NON_AUTHORITATIVE_FIXTURE_EVIDENCE",
        **v1_none,
    }
    _ok(summary["qualificationReportDigest"] == gates["AD5-G19"]["qualificationReportDigest"], "seal sync G19")
    _ok(summary["adapt06HandoffDigest"] == gates["AD5-G19"]["adapt06HandoffDigest"], "seal sync handoff")

    seal = {
        "schema": "NURION_ADAPT05_CANONICAL_QUALIFICATION_SEAL_V1",
        "revision": "R2",
        "authorityRole": "AUTHORITATIVE",
        "characterId": CANONICAL_QUALIFIED_CHARACTER_ID,
        "candidateSha256": canonical_candidate,
        "qualificationReportDigest": canonical_digest,
        "runtimeCompatibilityDigest": canonical_runtime,
        "adapt06HandoffDigest": canonical_handoff,
        "bindings": {
            "proofReceipt": "evidence/NURION-ADAPT-05_runtime_qualification_proof_receipt.json",
            "gateMatrixG19": "evidence/NURION-ADAPT-05_gate_matrix.json",
            "authoritativeReport": "reports/ADAPT05_report_canonical_qualified.json",
            "adapt06HandoffField": "adapt05.adapt06Handoff.qualificationReportDigest",
        },
        "policy": "Exactly one canonical qualification authority per audit package",
    }
    _write(EV, "NURION-ADAPT-05_CANONICAL_QUALIFICATION_SEAL.json", seal)
    _write(EV, "NURION-ADAPT-05_runtime_qualification_proof_receipt.json", summary)
    _write(EV, "NURION-ADAPT-05_gate_matrix.json", {"gates": gates, "critical": summary["criticalGates"], "canonicalSeal": seal})
    _write(EV, "NURION-ADAPT-05_mutation_none.json", v1_none)
    _write(
        EV,
        "NURION-ADAPT-05_READY_FOR_HUMAN_AUDIT_receipt.json",
        {
            "receiptId": "NURION-ADAPT-05_READY_FOR_HUMAN_AUDIT_R2",
            "revision": "R2",
            "status": "READY_FOR_HUMAN_AUDIT",
            "AD5-G20": "HUMAN_FINAL_ONLY",
            "ADAPT-06": "LOCKED BY PREDECESSOR",
            "pass": "NOT_DECLARED",
            "r1HumanAudit": "BLOCKED — qualificationReportDigest inconsistency",
            "r2Fix": "Canonical qualification seal",
            "qualificationReportDigest": canonical_digest,
            "candidateSha256": canonical_candidate,
            "adapt06HandoffDigest": canonical_handoff,
            "runtimeCompatibilityDigest": canonical_runtime,
        },
    )
    return summary


def main() -> int:
    try:
        s = run_all()
        print(
            json.dumps(
                {
                    "ok": True,
                    "revision": "R2",
                    "executionMode": s["executionMode"],
                    "agentStatus": s["agentStatus"],
                    "automatedGates": f"{s['automatedGatePassCount']}/19 PASS",
                    "AD5-G20": "HUMAN_FINAL_ONLY",
                    "pass": "NOT_DECLARED",
                },
                indent=2,
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
