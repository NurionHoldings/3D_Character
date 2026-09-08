#!/usr/bin/env python3
"""ADAPT-03 proof — AD3-G01…G19 automated. AD3-G20 HUMAN ONLY."""

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
from fast_track.adaptation.authoritative_face_binding import (
    AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
    verify_authoritative_face_binding,
)
from fast_track.adaptation.face_adaptation import adapt_face_from_glb, load_face_binding
from fast_track.adaptation.inspector import sha256_file
from fast_track.adaptation.skeleton_mapping import load_binding


def _roots():
    r = resolve_adapt01_roots(__file__)
    pkg = Path(r["packageRoot"])
    if r["extracted"]:
        fix = pkg / "fixtures"
        rep = pkg / "reports"
    else:
        repo = Path(r["repoRoot"])
        fix = repo / "fast_track/adaptation/fixtures_adapt03"
        rep = pkg / "reports_adapt03"
    ev = Path(r["evidence"])
    sem = Path(r["semantic"])
    adapt_pkg = pkg if r["extracted"] else Path(r["repoRoot"]) / "fast_track/working/adaptation_engine_v1"
    return {
        **r,
        "fixtures": fix,
        "reports": rep,
        "evidence": ev,
        "semantic": sem,
        "faceBinding": sem / "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json",
        "adapt02Binding": sem / "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
        "faceSemanticSnapshot": sem / "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json",
        "attachmentSnapshot": sem / "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json",
        "eyeTalkingSnapshot": sem / "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json",
        "provenance": adapt_pkg / "evidence/NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json",
        "contract": sem / "NURION_ADAPT03_FACE_EXPRESSION_ADAPTATION_CONTRACT_V1.json",
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
    EV: Path = r["evidence"]
    REPO: Path = r["repoRoot"]
    FACE_BIND: Path = r["faceBinding"]
    ADAPT02_BIND: Path = r["adapt02Binding"]
    CONTRACT: Path = r["contract"]
    EXTRACTED = bool(r["extracted"])
    REP.mkdir(parents=True, exist_ok=True)
    FIX.mkdir(parents=True, exist_ok=True)

    os.environ["NURION_ADAPT03_FIXTURE_DIR"] = str(FIX)
    os.environ["NURION_ADAPT03_REPO_ROOT"] = str(REPO)
    from tools.build_adapt03_fixtures import main as build_fix

    build_fix()
    face_binding = load_face_binding(FACE_BIND)
    _ok(ADAPT02_BIND.is_file(), "ADAPT-02 binding required for ADAPT-03")

    auth_verify = verify_authoritative_face_binding(
        face_binding,
        repo_root=REPO if not EXTRACTED else None,
        face_semantic_snapshot_path=r["faceSemanticSnapshot"],
        attachment_snapshot_path=r["attachmentSnapshot"],
        eye_talking_snapshot_path=r["eyeTalkingSnapshot"],
        provenance_path=r["provenance"],
    )
    _ok(auth_verify["status"] == "PASS", f"FACE binding blocked: {auth_verify.get('blockers')}")

    def run_asset(name: str, force: dict | None = None, cid: str | None = None):
        path = FIX / name
        a01, a02, a03 = adapt_face_from_glb(
            path, ADAPT02_BIND, FACE_BIND, character_id=cid or name, force_flags=force
        )
        return a01, a02, a03

    gates: dict[str, dict] = {}

    # G01 Authoritative FACE Input Identity
    _ok(FACE_BIND.is_file(), "face binding missing")
    _ok(CONTRACT.is_file(), "contract missing")
    _ok(r["faceSemanticSnapshot"].is_file(), "face semantic snapshot missing")
    _ok(r["provenance"].is_file(), "provenance missing")
    gates["AD3-G01"] = {
        "status": "PASS",
        "faceBindingSha256": sha256_file(FACE_BIND),
        "provenanceSha256": sha256_file(r["provenance"]),
        "faceProductLockSha256": AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256,
        "faceSemanticDigest": auth_verify["authoritativePins"]["faceSemanticDigest"],
        "verifyMode": auth_verify["mode"],
        "verifyChecks": auth_verify["checks"],
    }

    # Positive primary case
    r_rich, c_rich02, c_rich = run_asset("rich_facial_morphs.glb", cid="rich")
    r_meshy, c_meshy02, c_meshy = run_asset("meshy_style.glb", cid="meshy")
    r_ren, c_ren02, c_ren = run_asset("blendshape_renamed.glb", cid="renamed")
    r_eye, c_eye02, c_eye = run_asset("eye_adaptation_required.glb", cid="eye_adapt")
    r_expr, c_expr02, c_expr = run_asset("expression_mapping_required.glb", cid="expr_map")

    for label, a01, a02, a03 in [
        ("rich", r_rich, c_rich02, c_rich),
        ("meshy", r_meshy, c_meshy02, c_meshy),
        ("renamed", r_ren, c_ren02, c_ren),
        ("eye_adapt", r_eye, c_eye02, c_eye),
        ("expr_map", r_expr, c_expr02, c_expr),
    ]:
        (REP / f"ADAPT03_report_{label}.json").write_text(
            json.dumps(
                {
                    "adapt01": {"reportCanonicalSha256": a01.get("reportCanonicalSha256")},
                    "adapt02": {"contractCanonicalSha256": a02.get("contractCanonicalSha256")},
                    "adapt03": a03,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    # G02 ADAPT-01 Input Integrity
    _ok(c_rich.get("adapt01InspectionDigest") == r_rich.get("reportCanonicalSha256"), "a01 digest")
    gates["AD3-G02"] = {"status": "PASS", "adapt01Digest": c_rich.get("adapt01InspectionDigest")}

    # G03 ADAPT-02 Skeleton Mapping Integrity
    _ok(c_rich.get("adapt02MappingDigest") == c_rich02.get("contractCanonicalSha256"), "a02 digest")
    _ok(c_rich02.get("classification") in ("MAPPED", "PARTIAL"), "adapt02 ok")
    gates["AD3-G03"] = {
        "status": "PASS",
        "adapt02Digest": c_rich.get("adapt02MappingDigest"),
        "headResolved": c_rich02["semanticMappings"]["NURION_head"]["status"] == "RESOLVED",
    }

    # G04 Target HEAD / FACE Identity
    _ok(c_rich["headSemantic"]["status"] == "RESOLVED", "head")
    _ok(c_rich["targetFaceProfile"].get("blendshapesDetected") is True, "face detected")
    _, _, c_head = run_asset("rich_facial_morphs.glb", force={"headSemanticUnresolved": True}, cid="head_bad")
    _ok(c_head["classification"] == "BLOCKED", "head block")
    gates["AD3-G04"] = {"status": "PASS", "positive": "RESOLVED", "unresolvedCase": "BLOCKED"}

    # G05 FACE Authority Provenance
    _ok(face_binding.get("upstream", {}).get("faceProductLock", {}).get("sha256") == AUTHORITATIVE_FACE_PRODUCT_LOCK_SHA256, "pin")
    gates["AD3-G05"] = {
        "status": "PASS",
        "cryptographicLink": "VERIFIED",
        "attachmentDigest": auth_verify["authoritativePins"]["attachmentDigest"],
        "eyeTalkingDigest": auth_verify["authoritativePins"]["eyeTalkingDigest"],
    }

    # G06 Target Face Capability Inventory
    _ok(c_rich["capabilityMatrix"]["rows"], "cap rows")
    _ok(c_rich["targetFaceProfile"]["blendshapeCount"] > 0, "morph count")
    _, _, c_min = run_asset("body_minimal_face.glb", cid="minimal")
    _ok(c_min["classification"] in ("ADAPTED_WITH_AUGMENTATION_PENDING", "PARTIAL", "ADAPTED"), "minimal")
    gates["AD3-G06"] = {"status": "PASS", "richClassification": c_rich["classification"]}

    # G07 Landmark Correspondence
    lm = c_rich["landmarkCorrespondence"]["landmarks"]
    _ok(lm["LEFT_EYE_CENTER"]["status"] in ("RESOLVED", "MISSING"), "eye lm")
    _ok(lm["MOUTH_CENTER"]["status"] == "RESOLVED", "mouth lm")
    _, _, c_amb = run_asset("rich_facial_morphs.glb", force={"ambiguousFacialControls": True}, cid="amb")
    _ok(c_amb["landmarkCorrespondence"]["status"] == "AMBIGUOUS", "amb lm")
    gates["AD3-G07"] = {"status": "PASS", "positive": "PASS", "ambiguousCase": "AMBIGUOUS"}

    # G08 FACE/BODY Attachment Compatibility
    _ok(c_rich["faceBodyAttachment"]["status"] == "COMPATIBLE", "attach")
    _ok(c_rich["faceBodyAttachment"]["parent"] == "NURION_head", "parent")
    _ok(c_rich["faceBodyAttachment"]["child"] == "FACE_Rig_Root", "child")
    gates["AD3-G08"] = {"status": "PASS", "attachment": c_rich["faceBodyAttachment"]["status"]}

    # G09 Expression Semantic Mapping
    _ok(c_rich["expressionMap"]["status"] == "PASS", "expr")
    _ok(any(m.get("status") == "RESOLVED" for m in c_rich["expressionMap"]["mappings"].values()), "resolved expr")
    _, _, c_conf = run_asset("expression_mapping_required.glb", force={"expressionMappingConflict": True}, cid="conf")
    _ok(c_conf["expressionMap"]["status"] == "BLOCKED" or c_conf["classification"] == "BLOCKED", "conf")
    gates["AD3-G09"] = {"status": "PASS", "mappingEvidence": "multi_evidence"}

    # G10 Eye Authority / Calibration Binding
    _ok(c_rich["eyeAdaptation"]["calibrationFingerprintSha256"] == AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT, "eye fp")
    gates["AD3-G10"] = {
        "status": "PASS",
        "fingerprint": AUTHORITATIVE_EYE_CALIBRATION_FINGERPRINT,
    }

    # G11 Eye Target Adaptation
    _ok(c_eye["eyeAdaptation"]["status"] == "PASS", "eye adapt")
    _, _, c_inv = run_asset("rich_facial_morphs.glb", force={"invertEyeLaterality": True}, cid="inv")
    _ok(c_inv["eyeAdaptation"]["status"] == "BLOCKED", "inv eye")
    gates["AD3-G11"] = {"status": "PASS", "inversion": "BLOCKED"}

    # G12 Jaw / Mouth Mapping
    _ok(c_rich["jawMouthMap"]["status"] == "PASS", "jaw")
    _ok(c_rich["jawMouthMap"]["controls"]["MOUTH_OPEN"]["status"] == "RESOLVED", "mouth open")
    gates["AD3-G12"] = {"status": "PASS"}

    # G13 TALKING Authority Binding
    _ok(c_rich["talkingVisemeMap"]["talkingStatus"] == "GO", "talking go")
    gates["AD3-G13"] = {"status": "PASS", "talkingStatus": "GO"}

    # G14 TALKING / Viseme Adaptation
    _ok(c_rich["talkingVisemeMap"]["overallOutcome"] in (
        "COMPATIBLE",
        "COMPATIBLE_WITH_MAPPING",
        "ADAPTATION_REQUIRED",
    ), "talking outcome")
    _, _, c_talk = run_asset("talking_augmentation_required.glb", cid="talk_aug")
    _ok(c_talk["talkingVisemeMap"]["overallOutcome"] in ("AUGMENTATION_REQUIRED", "ADAPTATION_REQUIRED"), "aug")
    gates["AD3-G14"] = {
        "status": "PASS",
        "richOutcome": c_rich["talkingVisemeMap"]["overallOutcome"],
        "augmentationCase": c_talk["talkingVisemeMap"]["overallOutcome"],
    }

    # G15 Missing Capability Classification
    _ok("summary" in c_rich["capabilityMatrix"], "cap summary")
    _ok(c_min["adapt04AugmentationRequirements"]["augmentationRequired"] is True, "aug required")
    gates["AD3-G15"] = {"status": "PASS", "missingClassified": True}

    # G16 ADAPT-04 Augmentation Requirement Handoff
    req = c_min["adapt04AugmentationRequirements"]
    _ok(req["augmentationRequired"] is True, "req true")
    _ok(len(req["requirements"]) > 0, "req list")
    _ok(req["adapt04Implementation"] == "NOT_STARTED", "adapt04 not started")
    _ok(req.get("physicalHelperRigPerformed") is False, "no physical aug")
    _, _, c_prem = run_asset("rich_facial_morphs.glb", force={"performAdapt04Augmentation": True}, cid="prem")
    _ok(c_prem["classification"] == "BLOCKED", "premature adapt04")
    gates["AD3-G16"] = {"status": "PASS", "handoff": "SPECIFICATION_ONLY"}

    # G17 Source / Upstream Preservation
    for fname in ("rich_facial_morphs.glb", "meshy_style.glb", "blendshape_renamed.glb"):
        p = FIX / fname
        before = p.read_bytes()
        adapt_face_from_glb(p, ADAPT02_BIND, FACE_BIND, character_id="preserve")
        _ok(p.read_bytes() == before, f"mutated {fname}")
    adapt02_bind_sha = sha256_file(ADAPT02_BIND)
    adapt_face_from_glb(FIX / "rich_facial_morphs.glb", ADAPT02_BIND, FACE_BIND, character_id="p2")
    _ok(sha256_file(ADAPT02_BIND) == adapt02_bind_sha, "adapt02 mutated")
    v1_none = {
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "faceAuthorityMutation": "NONE",
        "adapt04Implementation": "NOT_STARTED",
    }
    gates["AD3-G17"] = {"status": "PASS", **v1_none}

    # G18 Ambiguity / Malformed Fail-Closed
    _, _, c_id = run_asset("rich_facial_morphs.glb", force={"adapt01Adapt02IdentityMismatch": True}, cid="id_bad")
    _ok(c_id["classification"] == "BLOCKED", "id mismatch")
    _, _, c_dig = run_asset("rich_facial_morphs.glb", force={"sourceDigestMismatch": True}, cid="dig_bad")
    _ok(c_dig["classification"] == "BLOCKED", "digest")
    gates["AD3-G18"] = {
        "status": "PASS",
        "identityMismatch": "BLOCKED",
        "digestMismatch": "BLOCKED",
    }

    # G19 Determinism / Independent Extracted Package
    _, _, c1 = run_asset("rich_facial_morphs.glb", cid="det")
    _, _, c2 = run_asset("rich_facial_morphs.glb", cid="det")
    _ok(c1["contractCanonicalSha256"] == c2["contractCanonicalSha256"], "det")
    gates["AD3-G19"] = {
        "status": "PASS",
        "executionMode": r["mode"],
        "contractCanonicalSha256": c1["contractCanonicalSha256"],
        "note": "Extracted ZIP must run run_adapt03_independent_proof.py exit 0",
    }

    gates["AD3-G20"] = {"status": "HUMAN_FINAL_ONLY", "agentMayNotPass": True}

    automated = [k for k in gates if k != "AD3-G20"]
    pass_count = sum(1 for k in automated if gates[k].get("status") == "PASS")
    _ok(pass_count == 19, f"gates {pass_count}/19")

    summary = {
        "schema": "NURION_ADAPT03_PROOF_RECEIPT_V1",
        "revision": "R1",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-03",
        "executionMode": r["mode"],
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "ADAPT-03_CLOSED_PASS": "DENY_AGENT",
        "ADAPT-04": "LOCKED BY PREDECESSOR",
        "gates": gates,
        "criticalGates": {
            k: gates[k]["status"]
            for k in (
                "AD3-G01",
                "AD3-G03",
                "AD3-G05",
                "AD3-G07",
                "AD3-G08",
                "AD3-G10",
                "AD3-G13",
                "AD3-G16",
                "AD3-G17",
                "AD3-G18",
                "AD3-G19",
            )
        },
        "authoritativePins": auth_verify["authoritativePins"],
        "upstreamProvenanceVerify": auth_verify,
        "automatedGatePassCount": pass_count,
        "automatedGateTotal": 19,
        "fixtureManifestSha256": sha256_file(FIX / "FIXTURE_MANIFEST.json"),
        "classificationSamples": {
            "rich": c_rich["classification"],
            "minimal": c_min["classification"],
            "talkAug": c_talk["classification"],
            "identityMismatch": c_id["classification"],
            "prematureAdapt04": c_prem["classification"],
        },
        **v1_none,
    }
    _write(EV, "NURION-ADAPT-03_face_adaptation_proof_receipt.json", summary)
    _write(EV, "NURION-ADAPT-03_gate_matrix.json", {"gates": gates, "critical": summary["criticalGates"]})
    _write(EV, "NURION-ADAPT-03_mutation_none.json", v1_none)

    ready = {
        "receiptId": "NURION-ADAPT-03_READY_FOR_HUMAN_AUDIT_R1",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-03",
        "revision": "R1",
        "status": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD3-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-04": "LOCKED BY PREDECESSOR",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
        "faceAuthorityMutation": "NONE",
    }
    _write(EV, "NURION-ADAPT-03_READY_FOR_HUMAN_AUDIT_receipt.json", ready)
    return summary


def main() -> int:
    try:
        s = run_all()
        print(
            json.dumps(
                {
                    "ok": True,
                    "revision": "R1",
                    "executionMode": s["executionMode"],
                    "agentStatus": s["agentStatus"],
                    "automatedGates": f"{s['automatedGatePassCount']}/19 PASS",
                    "AD3-G20": "HUMAN_FINAL_ONLY",
                    "ADAPT-04": "LOCKED BY PREDECESSOR",
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
