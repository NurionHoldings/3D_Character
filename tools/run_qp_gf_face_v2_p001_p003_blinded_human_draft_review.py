"""P001–P003 Blinded Human Draft Review GO.

Assembles NATURAL/POLISHED internal review drafts, presents them as anonymous
A/B labels, and opens empty human review forms. Never invents similarity scores
or interpolates human responses.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.gate4_contract import gate4_parameter_hash
from nurion_quick_profile_core import POLISHED, SILENT_PRESETS, ARKAON_BIND, DEFAULT_HAIR, DEFAULT_OUTFIT

COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 P001-P003 Blinded Human Draft Review GO"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
GATE5_BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
GATE5_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
ASSEMBLER = ROOT / "tools/blender_quick_profile_gate3_assemble.py"
G4 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4"
PRIOR_EXEC = G4 / "execution/V07_QP_GF_FACE_V2_P001_P003_CONSENTED_DRAFT_REVIEW_EXECUTE_RECEIPT.json"
P002_RE = G4 / "V07_QP_GF_FACE_V2_P002_FALSE_ABSTAIN_REANALYSIS_RECEIPT.json"
RUN_SCHEMA = "NURION_V07_QP_GF_FACE_V2_BLINDED_HUMAN_DRAFT_REVIEW_V1"

SOURCES = {
    "P001": G4 / "execution/run_20260815T132911Z/participants/P001/V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE.json",
    "P002": G4 / "execution/p002_reanalysis_20260815T143352Z/V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE.json",
    "P003": G4 / "execution/run_20260815T132911Z/participants/P003/V07_QP_GF_FACE_V2_INTERNAL_DRAFT_RECIPE.json",
}
PINS = {
    "P001": "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd",
    "P002": "b0f6e6a21b0cefd7fc6f088f54eabe16df986bc40c6b2a74479ed0f9e6dee6c7",
    "P003": "fb2616167b9612f7de668d31ef5c215fb834896f0b7b5527af8a54d7da89307f",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def blind_assignment(pid: str) -> dict[str, str]:
    bit = int(hashlib.sha256(f"{RUN_SCHEMA}:{pid}".encode()).hexdigest(), 16) & 1
    return {"A": "NATURAL", "B": "POLISHED"} if bit == 0 else {"A": "POLISHED", "B": "NATURAL"}


def build_recipes(internal: dict) -> tuple[dict, dict]:
    identity = dict(internal["identityLayer"]["values"])
    body = dict(internal["bodyRecommendation"]["bodyMorphValues"])
    preset = internal["bodyRecommendation"]["recommendedPreset"]
    polished_vals = {k: float(f"{v:.6f}") for k, v in POLISHED.items()}
    natural_vals = {k: 0.0 for k in polished_vals}
    base = {
        "identityValues": identity,
        "bodyPreset": preset,
        "bodyMorphValues": body,
        "hair": DEFAULT_HAIR,
        "outfit": DEFAULT_OUTFIT,
        "silentHomepagePresets": list(SILENT_PRESETS),
        "arkaonPresetBinding": list(ARKAON_BIND),
        "source": "GEOMETRY_FIRST_V2_ISOLATED",
        "distribution": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }
    natural = {**base, "beautificationMode": "NATURAL", "beautificationValues": natural_vals}
    polished = {**base, "beautificationMode": "POLISHED", "beautificationValues": polished_vals}
    return natural, polished


def empty_self_review(pid: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_BLINDED_SELF_REVIEW_FORM_V1",
        "anonymousParticipantId": pid,
        "status": "NOT_COLLECTED",
        "completed": False,
        "reviewedAtUtc": None,
        "blindDraftsPresented": ["A", "B"],
        "preferredDraft": None,
        "scores": {
            "FACE_SHAPE_AND_MAJOR_PROPORTIONS_SIMILARITY": None,
            "EYE_BROW_NOSE_MOUTH_JAW_SIGNATURE": None,
            "NATURAL_ASYMMETRY_PRESERVED": None,
            "IDENTITY_PRESERVED_AFTER_POLISH_COMPARISON": None,
            "NO_EXCESSIVE_BEAUTIFICATION": None,
            "NO_VIEWPOINT_COLLAPSE_DISTORTION": None,
            "SILENT_EXPRESSION_IMPRESSION": None,
        },
        "overall": None,
        "allowedOverall": [
            "INTERNAL_FACE_DRAFT_REVIEW_PASS",
            "PASS_WITH_LIMITATIONS",
            "REVIEW_REQUIRED",
            "ABSTAIN",
        ],
        "comment": None,
        "automaticSimilarityScoreUsed": "DENY",
        "responseInterpolation": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }


def empty_internal_review(pid: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_BLINDED_INTERNAL_REVIEW_FORM_V1",
        "anonymousParticipantId": pid,
        "status": "NOT_COLLECTED",
        "completed": False,
        "reviewerId": None,
        "reviewedAtUtc": None,
        "blindDraftsPresented": ["A", "B"],
        "scores": {
            "FACE_SHAPE_AND_MAJOR_PROPORTIONS": None,
            "EYE_BROW_NOSE_MOUTH_JAW_SIGNATURE": None,
            "NATURAL_ASYMMETRY_NOT_OVER_REMOVED": None,
            "POLISHED_IDENTITY_PRESERVATION": None,
            "NO_EXCESSIVE_BEAUTIFY_GENDER_AGE_SHIFT": None,
            "OFF_FRONTAL_VIRTUAL_VIEW_COLLAPSE_DISTORTION": None,
            "STANDARD_BODY_DOES_NOT_BLOCK_FACE_RECOGNITION": None,
            "UNOBSERVABLE_PARTS_CLEAR_DISCLOSURE": None,
        },
        "overall": None,
        "allowedOverall": [
            "INTERNAL_FACE_DRAFT_REVIEW_PASS",
            "PASS_WITH_LIMITATIONS",
            "REVIEW_REQUIRED",
            "ABSTAIN",
        ],
        "comment": None,
        "automaticSimilarityScoreUsed": "DENY",
        "responseInterpolation": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }


def assemble(pid: str, mode: str, recipe_path: Path, out_dir: Path) -> dict:
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(ASSEMBLER),
        "--",
        "--source-blend",
        str(GATE5_BLEND),
        "--expected-source-sha256",
        GATE5_SHA,
        "--recipe-json",
        str(recipe_path),
        "--out-dir",
        str(out_dir),
        "--participant-id",
        pid,
        "--mode",
        mode,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log = out_dir / "logs"
    log.mkdir(parents=True, exist_ok=True)
    (log / f"{pid}_{mode}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (log / f"{pid}_{mode}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"ASSEMBLE_FAIL:{pid}:{mode}:{proc.returncode}")
    return read_json(out_dir / "drafts" / pid / mode / "V07_QP_GATE3_ASSEMBLE_REPORT.json")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = G4 / "human_review" / f"blinded_bundle_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate4_parameter_hash() != EXP_G4:
        raise SystemExit("GATE4_HASH_MISMATCH")
    if not BLENDER.is_file():
        raise SystemExit("BLENDER_MISSING")
    if sha256_file(GATE5_BLEND) != GATE5_SHA:
        raise SystemExit("GATE5_BLEND_HASH_MISMATCH")

    prior = read_json(PRIOR_EXEC)
    prior_sha = sha256_file(PRIOR_EXEC)
    p002_re = read_json(P002_RE)
    if prior["participantJudgments"]["P001"] != "DRAFT_READY" or prior["participantJudgments"]["P003"] != "DRAFT_READY":
        raise SystemExit("P001_P003_NOT_DRAFT_READY")
    if prior["participantJudgments"]["P002"] != "ABSTAIN_RECAPTURE":
        raise SystemExit("PRIOR_P002_HISTORY_NOT_PRESERVED")
    if p002_re.get("reanalysisJudgment") != "DRAFT_READY":
        raise SystemExit("P002_REANALYSIS_NOT_DRAFT_READY")
    if p002_re.get("gate4Mutation") != "DENY" or p002_re.get("thresholdMutation") != "DENY":
        raise SystemExit("P002_REANALYSIS_MUTATION_FLAGS_INVALID")

    results = []
    for pid in ("P001", "P002", "P003"):
        internal = read_json(SOURCES[pid])
        natural, polished = build_recipes(internal)
        pdir = out / "participants" / pid
        nat_path = pdir / "recipes" / "NATURAL.json"
        pol_path = pdir / "recipes" / "POLISHED.json"
        write_json(nat_path, natural)
        write_json(pol_path, polished)

        nat_rep = assemble(pid, "NATURAL", nat_path, pdir)
        pol_rep = assemble(pid, "POLISHED", pol_path, pdir)

        mapping = blind_assignment(pid)
        write_json(
            pdir / "blind" / f"{pid}_BLIND_MAPPING_OPERATOR_ONLY.json",
            {
                "participantId": pid,
                "access": "OPERATOR_ONLY",
                "mapping": mapping,
                "note": "Do not show NATURAL/POLISHED labels to reviewers.",
            },
        )

        # Anonymous presentation copies (A/B filenames only)
        pres = pdir / "presentation"
        pres.mkdir(parents=True, exist_ok=True)
        labeled = {}
        for label, mode in mapping.items():
            src = pdir / "drafts" / pid / mode / f"NURION_QP_Gate3_{pid}_{mode}.blend"
            dst = pres / f"Draft_{label}.blend"
            shutil.copy2(src, dst)
            labeled[label] = {
                "file": f"Draft_{label}.blend",
                "sha256": sha256_file(dst),
                # mode intentionally omitted from participant-facing presentation index
            }
        presentation = {
            "schema": "NURION_V07_QP_GF_FACE_V2_BLINDED_PRESENTATION_V1",
            "anonymousParticipantId": pid,
            "instructionKo": "Draft A와 Draft B를 순서와 무관하게 비교하세요. 어느 쪽이 NATURAL/POLISHED인지는 공개되지 않습니다.",
            "drafts": labeled,
            "doNotRevealModeLabels": True,
            "automaticSimilarityScore": "DENY",
            "distribution": "DENY",
            "production": "NO-GO",
        }
        write_json(pres / f"{pid}_BLINDED_PRESENTATION.json", presentation)

        self_form = empty_self_review(pid)
        internal_form = empty_internal_review(pid)
        write_json(pdir / "review" / f"{pid}_SELF_REVIEW.json", self_form)
        write_json(pdir / "review" / f"{pid}_INTERNAL_REVIEW.json", internal_form)

        results.append(
            {
                "participantId": pid,
                "imageSha256": PINS[pid],
                "draftReadySource": "REANALYSIS" if pid == "P002" else "INITIAL_EXECUTE",
                "assemble": {
                    "NATURAL": {
                        "outputBlendSha256": nat_rep["outputBlendSha256"],
                        "assembleFingerprintSha256": nat_rep["assembleFingerprintSha256"],
                    },
                    "POLISHED": {
                        "outputBlendSha256": pol_rep["outputBlendSha256"],
                        "assembleFingerprintSha256": pol_rep["assembleFingerprintSha256"],
                    },
                },
                "blindLabels": ["A", "B"],
                "selfReviewStatus": "NOT_COLLECTED",
                "internalReviewStatus": "NOT_COLLECTED",
                "presentation": f"participants/{pid}/presentation/{pid}_BLINDED_PRESENTATION.json",
            }
        )

    if sha256_file(PRIOR_EXEC) != prior_sha:
        raise SystemExit("PRIOR_EXECUTE_MUTATED")
    if sha256_file(GATE5_BLEND) != GATE5_SHA:
        raise SystemExit("GATE5_MUTATED_DURING_RUN")

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P001_P003_BLINDED_HUMAN_DRAFT_REVIEW_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "BLINDED_PACKAGES_READY_AWAITING_HUMAN_RESPONSES",
        "gate4ParameterHash": EXP_G4,
        "gate4Mutation": "DENY",
        "thresholdMutation": "DENY",
        "perAssetTuning": "DENY",
        "priorExecuteP002History": {
            "judgmentUnchanged": "ABSTAIN_RECAPTURE",
            "receiptSha256": prior_sha,
        },
        "p002ReanalysisJudgment": "DRAFT_READY",
        "participants": results,
        "humanResponsesCollected": False,
        "automaticSimilarityScoreUsed": "DENY",
        "responseInterpolation": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "characterGenerationProductClaim": "DENY",
        "blenderDraftsRole": "INTERNAL_BLINDED_HUMAN_REVIEW_ONLY",
        "production": "NO-GO",
        "bundlePath": f"human_review/blinded_bundle_{run_id}",
        "next": "COLLECT_SELF_AND_INTERNAL_REVIEW_FORMS_WITHOUT_AUTO_SCORES",
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(out / "V07_QP_GF_FACE_V2_P001_P003_BLINDED_HUMAN_DRAFT_REVIEW_RECEIPT.json", receipt)
    write_json(G4 / "V07_QP_GF_FACE_V2_P001_P003_BLINDED_HUMAN_DRAFT_REVIEW_RECEIPT.json", receipt)

    # operator unhold note
    write_json(
        out / "V07_QP_GF_FACE_V2_BLINDED_REVIEW_OPERATOR_PACKET.json",
        {
            "schema": "NURION_V07_QP_GF_FACE_V2_BLINDED_REVIEW_OPERATOR_PACKET_V1",
            "registeredAt": now,
            "howToPresent": [
                "Open participants/P00X/presentation/Draft_A.blend and Draft_B.blend in Blender",
                "Do not reveal NATURAL/POLISHED or blind mapping to the participant",
                "Ask participant to complete review/P00X_SELF_REVIEW.json fields only",
                "Internal reviewer completes review/P00X_INTERNAL_REVIEW.json separately",
                "Never paste automatic similarity scores into the forms",
            ],
            "blindMappingsLocation": "participants/*/blind/*_BLIND_MAPPING_OPERATOR_ONLY.json",
            "production": "NO-GO",
        },
    )

    g4s = read_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json")
    g4s["updatedAt"] = now
    g4s["blindedHumanDraftReview"] = {
        "verdict": "BLINDED_PACKAGES_READY_AWAITING_HUMAN_RESPONSES",
        "runId": run_id,
        "humanResponsesCollected": False,
        "gate4Mutation": "DENY",
    }
    g4s["next"] = "AWAIT_SELF_AND_INTERNAL_HUMAN_REVIEW_FORM_COMPLETION"
    write_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json", g4s)

    qp3_path = ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_STATUS.json"
    qp3 = read_json(qp3_path)
    qp3["updatedAt"] = now
    qp3["geometryFirstBlindedHumanDraftReview"] = {
        "verdict": "BLINDED_PACKAGES_READY_AWAITING_HUMAN_RESPONSES",
        "runId": run_id,
        "humanResponsesCollected": False,
        "automaticSimilarityScoreUsed": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
        "bundle": f"dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4/human_review/blinded_bundle_{run_id}",
    }
    qp3["parallelTracks"] = {
        "P001P003HumanDraftReview": "BLINDED_PACKAGE_OPEN",
        "P002Path": "INCLUDED_VIA_REANALYSIS_DRAFT_READY",
        "geometryFirstFaceV2": "GATE4_PASS_LOCKED_UNCHANGED",
        "threeParticipantReviewBundle": "AWAITING_HUMAN_FORM_COMPLETION",
    }
    write_json(qp3_path, qp3)

    print(
        json.dumps(
            {
                "verdict": "BLINDED_PACKAGES_READY_AWAITING_HUMAN_RESPONSES",
                "runId": run_id,
                "participants": [r["participantId"] for r in results],
                "humanResponsesCollected": False,
                "automaticSimilarityScoreUsed": "DENY",
                "production": "NO-GO",
                "bundle": str(out),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
