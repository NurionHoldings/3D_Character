"""P001-P003 Dense Identity Draft Capture And Blinded Review GO.

Prepares dense A/B capture packages from consented 478 landmarks.
Does NOT invent human responses or run collection/adjudication.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.analyzer import GeometryFirstAnalyzer
from nurion_qp_geometry_face_v2.dense_identity_draft import build_dense_identity_draft, write_obj, write_region_sidecar
from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from run_quick_profile_gate3_consented_human_review import consent_ok

COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 P001-P003 Dense Identity Draft Capture And Blinded Review GO"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
PINS = {
    "P001": "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd",
    "P002": "b0f6e6a21b0cefd7fc6f088f54eabe16df986bc40c6b2a74479ed0f9e6dee6c7",
    "P003": "fb2616167b9612f7de668d31ef5c215fb834896f0b7b5527af8a54d7da89307f",
}
ADJ_P002 = "FALSE_ABSTAIN_LARGE_IMAGE_EDGE_VARIANCE_WITH_BACKLIGHT_SOFTNESS"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
CAPTURE_PY = ROOT / "tools/blender_qp_gf_gate5_dense_face_capture.py"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake"
G4 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate4"
G5 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate5"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
RUN_SCHEMA = "NURION_V07_QP_GF_FACE_V2_DENSE_BLINDED_CAPTURE_PACKAGE_V1"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def blind_assignment(pid: str) -> dict[str, str]:
    bit = int(hashlib.sha256(f"{RUN_SCHEMA}:{pid}".encode()).hexdigest(), 16) & 1
    return {"A": "NATURAL", "B": "POLISHED"} if bit == 0 else {"A": "POLISHED", "B": "NATURAL"}


def empty_self_review(pid: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_BLINDED_SELF_REVIEW_FORM_V1",
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
        "sourceCaptureClass": "DENSE_IDENTITY_FACEMESH_478",
        "photorealClaim": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }


def empty_internal_review(pid: str) -> dict:
    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_BLINDED_INTERNAL_REVIEW_FORM_V1",
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
            "DENSE_FEATURE_VISIBILITY_EYES_NOSE_LIPS_JAW": None,
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
        "sourceCaptureClass": "DENSE_IDENTITY_FACEMESH_478",
        "photorealClaim": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }


def infer_raw_478(backend: MediaPipeLandmarkerBackend, face: Path) -> tuple[np.ndarray | None, dict]:
    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    analyzer = GeometryFirstAnalyzer(backend)
    analysis = analyzer.analyze(rgb)
    # Dense mesh requires image-normalized raw landmarks, not eye/IOD-normalized consensus.
    raw = backend.infer(rgb, "ORIGINAL_RGB")
    meta = {
        "analyzerOutcome": analysis.outcome,
        "successfulBranches": list(analysis.successful_branches),
        "medianBranchDisagreement": analysis.median_branch_disagreement,
        "p95BranchDisagreement": analysis.p95_branch_disagreement,
        "rawOriginalRgb478": raw is not None and raw.shape == (478, 3),
    }
    return raw, meta


def render_obj(obj: Path, out_dir: Path, label: str) -> None:
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(CAPTURE_PY),
        "--",
        "--obj",
        str(obj),
        "--out-dir",
        str(out_dir),
        "--draft-label",
        label,
        "--resolution",
        "1024",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"_render_{label}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (out_dir / f"_render_{label}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"RENDER_FAIL:{label}:{proc.returncode}")
    for view in ("front", "left45", "right45"):
        if not (out_dir / f"Draft_{label}_{view}.png").is_file():
            raise RuntimeError(f"PNG_MISSING:{label}:{view}")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("GATE5_HASH_MISMATCH")
    g5s = read_json(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json")
    if g5s.get("V07_QP_GF_FACE_V2_GATE5") != "PASS" or g5s.get("LOCKED") is not True:
        raise SystemExit("GATE5_NOT_PASS_LOCKED")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")
    if not BLENDER.is_file():
        raise SystemExit("BLENDER_MISSING")

    adj = read_json(G4 / "adjudication/P002/V07_QP_GF_FACE_V2_P002_CAPTURE_QUALITY_HUMAN_ADJUDICATION_RECEIPT.json")
    if adj.get("verdict") != ADJ_P002:
        raise SystemExit("P002_ADJUDICATION_MISSING")

    pinned = read_json(INTAKE / "V07_QP_GATE3_PINNED_SHA256_RECORD.json")["pinnedSha256"]
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    bundle = G5 / "human_review" / f"dense_blinded_bundle_{run_id}"
    bundle.mkdir(parents=True, exist_ok=True)

    results = []
    for pid in ("P001", "P002", "P003"):
        folder = INTAKE / "packages" / pid
        face = folder / "face.png"
        consent = read_json(folder / "consent.json")
        reasons = consent_ok(consent, pid)
        got = sha256_file(face)
        if pinned.get(pid) != PINS[pid] or got != PINS[pid]:
            reasons.append("PINNED_IMAGE_HASH_MISMATCH")
        if pid == "P002":
            # Blur precheck not applied; adjudication authorizes dense reanalysis path.
            pass

        entry: dict[str, Any] = {
            "participantId": pid,
            "imageSha256": got,
            "packageReasons": reasons,
            "captureEligible": False,
            "judgment": None,
        }
        pdir = bundle / "participants" / pid
        if reasons:
            entry["judgment"] = "ABSTAIN_PACKAGE_INVALID"
            write_json(pdir / "V07_QP_GF_FACE_V2_DENSE_CAPTURE_JUDGMENT.json", entry)
            results.append(entry)
            continue

        raw, meta = infer_raw_478(backend, face)
        entry["geometryMeta"] = meta
        if raw is None:
            entry["judgment"] = "ABSTAIN_NO_478_LANDMARKS"
            write_json(pdir / "V07_QP_GF_FACE_V2_DENSE_CAPTURE_JUDGMENT.json", entry)
            results.append(entry)
            continue

        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "meshes").mkdir(parents=True, exist_ok=True)
        (pdir / "blind").mkdir(parents=True, exist_ok=True)
        (pdir / "presentation" / "captures").mkdir(parents=True, exist_ok=True)
        (pdir / "review").mkdir(parents=True, exist_ok=True)
        np.save(pdir / "landmarks_raw_478.npy", raw)
        natural = build_dense_identity_draft(raw, "NATURAL")
        polished = build_dense_identity_draft(raw, "POLISHED")
        write_obj(natural, pdir / "meshes" / "NATURAL_dense_identity.obj")
        write_obj(polished, pdir / "meshes" / "POLISHED_dense_identity.obj")
        write_region_sidecar(natural, pdir / "meshes" / "NATURAL_regions.json")
        write_region_sidecar(polished, pdir / "meshes" / "POLISHED_regions.json")

        mapping = blind_assignment(pid)
        write_json(
            pdir / "blind" / f"{pid}_BLIND_MAPPING_OPERATOR_ONLY.json",
            {
                "participantId": pid,
                "access": "OPERATOR_ONLY",
                "mapping": mapping,
                "note": "Do not reveal NATURAL/POLISHED to reviewers before evaluation ends.",
            },
        )

        cap_dir = pdir / "presentation" / "captures"
        for label, mode in mapping.items():
            render_obj(pdir / "meshes" / f"{mode}_dense_identity.obj", cap_dir, label)

        files = {}
        for label in ("A", "B"):
            files[f"Draft_{label}"] = {
                view: {
                    "file": f"Draft_{label}_{view}.png",
                    "sha256": sha256_file(cap_dir / f"Draft_{label}_{view}.png"),
                    "bytes": (cap_dir / f"Draft_{label}_{view}.png").stat().st_size,
                }
                for view in ("front", "left45", "right45")
            }

        presentation = {
            "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_BLINDED_PRESENTATION_V1",
            "anonymousParticipantId": pid,
            "instructionKo": "Dense Identity FaceMesh Draft A/B입니다. 같은 조명·카메라·표정 조건 캡처로 비교하세요. NATURAL/POLISHED 라벨은 없습니다.",
            "views": ["front", "left45", "right45"],
            "captures": files,
            "meshClass": "DENSE_IDENTITY_FACEMESH_478_854TRI",
            "photorealClaim": "DENY",
            "automaticSimilarityScore": "DENY",
            "distribution": "DENY",
            "production": "NO-GO",
        }
        write_json(pdir / "presentation" / f"{pid}_DENSE_BLINDED_PRESENTATION.json", presentation)
        write_json(cap_dir / f"{pid}_DENSE_CAPTURE_INDEX.json", presentation)

        write_json(pdir / "review" / f"{pid}_SELF_REVIEW.json", empty_self_review(pid))
        write_json(pdir / "review" / f"{pid}_INTERNAL_REVIEW.json", empty_internal_review(pid))

        entry.update(
            {
                "captureEligible": True,
                "judgment": "DENSE_CAPTURE_READY",
                "expressedRegions": list(natural.expressed_regions),
                "triangleCount": natural.triangle_count,
                "humanResponsesCollected": False,
                "photorealClaim": "DENY",
            }
        )
        write_json(pdir / "V07_QP_GF_FACE_V2_DENSE_CAPTURE_JUDGMENT.json", entry)
        results.append(entry)

    eligible = [r for r in results if r.get("captureEligible")]
    if len(eligible) != 3:
        verdict = "SAFE_ABORT_NOT_ALL_PARTICIPANTS_CAPTURE_ELIGIBLE"
    else:
        verdict = "DENSE_CAPTURES_READY_AWAITING_HUMAN_RESPONSES"

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_P001_P003_DENSE_IDENTITY_DRAFT_CAPTURE_AND_BLINDED_REVIEW_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "gate5ParameterHash": EXP_G5,
        "gate5Mutation": "DENY",
        "gate4ParameterHash": EXP_G4,
        "gate4Mutation": "DENY",
        "participantResults": [
            {
                "participantId": r["participantId"],
                "imageSha256": r.get("imageSha256"),
                "captureEligible": r.get("captureEligible"),
                "judgment": r.get("judgment"),
                "analyzerOutcome": (r.get("geometryMeta") or {}).get("analyzerOutcome"),
                "expressedRegions": r.get("expressedRegions"),
            }
            for r in results
        ],
        "humanResponsesCollected": False,
        "automaticSimilarityScoreUsed": "DENY",
        "responseInterpolation": "DENY",
        "collectionAdjudicationExecuted": "DENY",
        "photorealAutomaticPass": "DENY",
        "lowPolyCapturesStillNotIdentityEvidence": True,
        "countsAsGate8ParticipantEvidence": "DENY",
        "partialResultDistribution": "DENY",
        "production": "NO-GO",
        "bundle": f"human_review/dense_blinded_bundle_{run_id}",
        "next": "HUMAN_FILLS_DENSE_SELF_AND_INTERNAL_REVIEW_FORMS",
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(bundle / "V07_QP_GF_FACE_V2_P001_P003_DENSE_CAPTURE_BLINDED_REVIEW_RECEIPT.json", receipt)
    write_json(G5 / "V07_QP_GF_FACE_V2_P001_P003_DENSE_CAPTURE_BLINDED_REVIEW_RECEIPT.json", receipt)

    write_json(
        bundle / "V07_QP_GF_FACE_V2_DENSE_REVIEW_OPERATOR_PACKET.json",
        {
            "schema": "NURION_V07_QP_GF_FACE_V2_DENSE_REVIEW_OPERATOR_PACKET_V1",
            "registeredAt": now,
            "howToPresent": [
                "Open participants/P00X/presentation/captures/Draft_A_*.png and Draft_B_*.png",
                "Keep NATURAL/POLISHED mapping sealed in blind/*_OPERATOR_ONLY.json",
                "Participant fills review/*_SELF_REVIEW.json",
                "Internal reviewer fills review/*_INTERNAL_REVIEW.json without seeing self answers",
                "Do not invent or interpolate scores",
            ],
            "awaitCommand": "NURION Quick Profile Geometry-First Face Analyzer v2 P001-P003 Human Review Collection And Adjudication GO",
            "production": "NO-GO",
        },
    )

    g5_status = read_json(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json")
    g5_status["updatedAt"] = now
    g5_status["denseParticipantCaptures"] = {
        "verdict": verdict,
        "runId": run_id,
        "humanResponsesCollected": False,
    }
    g5_status["next"] = "AWAIT_HUMAN_DENSE_REVIEW_FORM_COMPLETION"
    write_json(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json", g5_status)

    g4_status = read_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json")
    g4_status["updatedAt"] = now
    g4_status["humanSimilarityCollectionAdjudication"] = "HOLD_AWAITING_DENSE_FORM_COMPLETION"
    g4_status["denseCaptureBundle"] = f"../gate5/human_review/dense_blinded_bundle_{run_id}"
    write_json(G4 / "V07_QP_GF_FACE_V2_GATE4_STATUS.json", g4_status)

    qp3 = ROOT / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_STATUS.json"
    doc = read_json(qp3)
    doc["updatedAt"] = now
    doc["geometryFirstDenseCaptureBlindedReview"] = {
        "verdict": verdict,
        "runId": run_id,
        "humanResponsesCollected": False,
        "production": "NO-GO",
        "bundle": f"dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate5/human_review/dense_blinded_bundle_{run_id}",
    }
    doc["parallelTracks"] = {
        "lowPolyIdentityReview": "HOLD_INSUFFICIENT_VISUAL_FIDELITY",
        "denseIdentityCaptures": verdict,
        "humanFormCompletion": "AWAITING",
        "geometryFirstFaceV2": "GATE5_PASS_LOCKED_UNCHANGED",
    }
    write_json(qp3, doc)

    print(
        json.dumps(
            {
                "verdict": verdict,
                "runId": run_id,
                "eligible": [r["participantId"] for r in eligible],
                "humanResponsesCollected": False,
                "production": "NO-GO",
                "bundle": str(bundle),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "DENSE_CAPTURES_READY_AWAITING_HUMAN_RESPONSES" else 2


if __name__ == "__main__":
    raise SystemExit(main())
