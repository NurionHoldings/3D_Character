"""Gate 6 Identity-Grade Parametric Face Reconstruction GO runner.

Priority track. Does not mutate Gate 3–5 baselines. Production remains NO-GO.
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

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.gate6_contract import GATE6_CONTRACT, gate6_parameter_hash
from nurion_qp_geometry_face_v2.gate6_visual_quality import evaluate_identity_visual_quality
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from nurion_qp_geometry_face_v2.textured_landmark_head import (
    build_textured_landmark_head,
    eye_centers_metric,
    write_obj_mtl,
)
from nurion_qp_geometry_face_v2.parametric_face_v0 import (
    fit_parametric_from_478,
    mild_polish_identity,
    write_face_albedo_crop,
)
from nurion_quick_profile_core import POLISHED
from run_quick_profile_gate3_consented_human_review import consent_ok

COMMAND = "NURION Quick Profile Geometry-First Face Analyzer v2 Gate 6 Identity-Grade Parametric Face Reconstruction GO"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
EXP_G4 = "92ebd6e7dd9b5d79cfdee17cf9cac37d4dfd3cdf3860a973b7ba91f829af88c4"
PINS = {
    "P001": "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd",
    "P002": "b0f6e6a21b0cefd7fc6f088f54eabe16df986bc40c6b2a74479ed0f9e6dee6c7",
    "P003": "fb2616167b9612f7de668d31ef5c215fb834896f0b7b5527af8a54d7da89307f",
}
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
OWNERSHIP = ROOT / "dist/v0.7/canonical/gate1/asset/OWNERSHIP_DECLARATION.txt"
RENDER_PY = ROOT / "tools/blender_qp_gf_gate6_identity_grade_render.py"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake"
G5 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate5"
G6 = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate6"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def make_compare_strip(original: Path, front_render: Path, out_path: Path) -> None:
    a = Image.open(original).convert("RGB")
    b = Image.open(front_render).convert("RGB")
    size = 512
    a = a.resize((size, size), Image.Resampling.LANCZOS)
    b = b.resize((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", (size * 2 + 24, size + 48), (28, 30, 34))
    canvas.paste(a, (8, 32))
    canvas.paste(b, (size + 16, 32))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 8), "ORIGINAL", fill=(200, 200, 200))
    draw.text((size + 16, 8), "GATE6_RENDER", fill=(200, 200, 200))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def render_mode(obj_path: Path, albedo: Path, out_dir: Path, label: str, eye_l, eye_r) -> dict:
    def fmt(v):
        return f"{float(v[0]):.8f};{float(v[1]):.8f};{float(v[2]):.8f}"

    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(RENDER_PY),
        "--",
        "--obj",
        str(obj_path),
        "--albedo",
        str(albedo),
        "--out-dir",
        str(out_dir),
        f"--draft-label={label}",
        f"--eye-l={fmt(eye_l)}",
        f"--eye-r={fmt(eye_r)}",
        "--resolution=1024",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    (out_dir / f"_{label}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (out_dir / f"_{label}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"RENDER_FAIL:{label}:{proc.returncode}")
    meta_path = out_dir / f"{label}_render_meta.json"
    return read_json(meta_path) if meta_path.is_file() else {}


def process_case(
    case_id: str,
    face: Path,
    backend: MediaPipeLandmarkerBackend,
    out_root: Path,
    *,
    waive_blur: bool = False,
) -> dict[str, Any]:
    case_dir = out_root / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    raw = backend.infer(rgb, "ORIGINAL_RGB")
    if raw is None:
        return {
            "caseId": case_id,
            "judgment": "ABSTAIN",
            "reasons": ["NO_478_LANDMARKS"],
            "humanReviewAllowed": False,
        }

    np.save(case_dir / "landmarks_raw_478.npy", raw)
    fit = fit_parametric_from_478(raw)
    # Keep cropped albedo for analytics; rendering uses full-frame for landmark UV.
    albedo_meta = write_face_albedo_crop(face, fit.face_bbox_norm, case_dir / "albedo_face_1024.png")
    shutil.copy2(face, case_dir / "original_face.png")
    full_albedo = case_dir / "albedo_full.png"
    Image.open(face).convert("RGB").save(full_albedo)

    polished_fit_vals = mild_polish_identity(fit.identity_values, 0.12)
    write_json(case_dir / "fit.json", {
        "identityValues": fit.identity_values,
        "polishedIdentityValues": polished_fit_vals,
        "geometryRatios": fit.geometry_ratios,
        "pose": fit.pose,
        "disclosures": list(fit.disclosures) + ["TEXTURED_LANDMARK_HEAD_UV_FROM_IMAGE_XY"],
        "modelId": "NURION_PARAMETRIC_FACE_V0_TEXTURED_LANDMARK_HEAD",
        "beautificationReference": {k: float(f"{v:.6f}") for k, v in POLISHED.items()},
    })

    eye_l, eye_r = eye_centers_metric(raw)
    verts_n, tris_n, uvs_n, meta_mesh = build_textured_landmark_head(raw, polish=False)
    write_obj_mtl(case_dir / "meshes/NATURAL_head.obj", verts_n, tris_n, uvs_n, albedo_name="albedo_full.png")
    shutil.copy2(full_albedo, case_dir / "meshes/albedo_full.png")
    verts_p, tris_p, uvs_p, _ = build_textured_landmark_head(raw, polish=True)
    write_obj_mtl(case_dir / "meshes/POLISHED_head.obj", verts_p, tris_p, uvs_p, albedo_name="albedo_full.png")

    cap = case_dir / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    meta_n = render_mode(case_dir / "meshes/NATURAL_head.obj", full_albedo, cap, "NATURAL", eye_l, eye_r)
    meta_p = render_mode(case_dir / "meshes/POLISHED_head.obj", full_albedo, cap, "POLISHED", eye_l, eye_r)

    renders = {
        "front": cap / "NATURAL_front.png",
        "left45": cap / "NATURAL_left45.png",
        "right45": cap / "NATURAL_right45.png",
    }
    compare = case_dir / "compare_original_vs_natural_front.png"
    make_compare_strip(face, renders["front"], compare)

    q = evaluate_identity_visual_quality(
        render_paths=renders,
        albedo_meta=albedo_meta,
        has_eyeballs=bool(meta_n.get("eyeballs")),
        has_photo_texture=bool(meta_n.get("photoTexture")),
        mesh_vertex_count=int(meta_n.get("vertexCount") or meta_mesh.get("vertexCount") or 0),
        compare_path=compare,
    )
    write_json(case_dir / "V07_QP_GF_FACE_V2_GATE6_VISUAL_QUALITY.json", q)
    write_json(
        case_dir / "V07_QP_GF_FACE_V2_GATE6_CASE_JUDGMENT.json",
        {
            "caseId": case_id,
            "imageSha256": sha256_file(face),
            "modelId": "NURION_PARAMETRIC_FACE_V0",
            "fit": fit.identity_values,
            "pose": fit.pose,
            "quality": q,
            "judgment": q["verdict"],
            "humanReviewAllowed": q["humanReviewAllowed"],
            "waiveBlurPrecheck": waive_blur,
            "production": "NO-GO",
        },
    )
    return {
        "caseId": case_id,
        "judgment": q["verdict"],
        "reasons": q.get("reasons", []),
        "humanReviewAllowed": q["humanReviewAllowed"],
        "vertexCount": meta_n.get("vertexCount"),
        "polishedMeta": {"vertexCount": meta_p.get("vertexCount")},
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    g6_hash = gate6_parameter_hash()

    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("GATE5_HASH_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")
    if not OWNERSHIP.is_file():
        raise SystemExit("OWNERSHIP_DECLARATION_MISSING")
    if not BLENDER.is_file():
        raise SystemExit("BLENDER_MISSING")

    G6.mkdir(parents=True, exist_ok=True)
    out = G6 / f"run_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    license_reg = {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY_V1",
        "selected": "NURION_PARAMETRIC_FACE_V0",
        "commercialClearance": "PASS_NURION_OWNED_PARAMETRIC_HEAD",
        "topology": "NURION_ELLIPSOID_PARAMETRIC_HEAD_NOT_MP_854_NOT_RESEARCH_3DMM",
        "ownershipDeclaration": str(OWNERSHIP.relative_to(ROOT)).replace("\\", "/"),
        "blockedResearchOnly": ["FLAME", "DECA", "BASEL_BFM", "FACESCAPE_WEIGHTS"],
        "note": "Research 3DMM weights are not imported. Operator commercial license required before switching.",
        "production": "NO-GO",
    }
    write_json(out / "V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY.json", license_reg)
    write_json(G6 / "V07_QP_GF_FACE_V2_GATE6_COMMERCIAL_MODEL_REGISTRY.json", license_reg)
    write_json(G6 / "V07_QP_GF_FACE_V2_GATE6_CONTRACT.json", GATE6_CONTRACT)

    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")

    # Synthetic oval fixture for determinism smoke (non-participant).
    syn_dir = out / "synthetic"
    syn_dir.mkdir(parents=True, exist_ok=True)
    syn_img = syn_dir / "synthetic_face.png"
    # Prefer prior dense landmark fixture if present; else generate blank and ABSTAIN gracefully.
    prior_lm = G5 / "synthetic"
    syn_results = []
    fixture_png = None
    for p in prior_lm.glob("**/*.png") if prior_lm.exists() else []:
        fixture_png = p
        break
    if fixture_png is None:
        # Minimal face-like gray oval for pipeline wiring only.
        img = Image.new("RGB", (512, 512), (40, 40, 42))
        draw = ImageDraw.Draw(img)
        draw.ellipse((140, 80, 370, 420), fill=(180, 150, 140))
        draw.ellipse((190, 180, 230, 210), fill=(30, 30, 30))
        draw.ellipse((280, 180, 320, 210), fill=(30, 30, 30))
        draw.ellipse((240, 230, 270, 280), fill=(150, 120, 110))
        draw.ellipse((210, 310, 300, 340), fill=(120, 70, 70))
        img.save(syn_img)
    else:
        shutil.copy2(fixture_png, syn_img)

    syn_results.append(process_case("SYNTHETIC", syn_img, backend, out))

    # Determinism: re-run fit twice on same landmarks file if created.
    det = {"status": "SKIP", "pass": False}
    syn_lm = out / "cases/SYNTHETIC/landmarks_raw_478.npy"
    if syn_lm.is_file():
        a = fit_parametric_from_478(np.load(syn_lm)).identity_values
        b = fit_parametric_from_478(np.load(syn_lm)).identity_values
        det = {"status": "RAN", "pass": a == b, "values": a}

    participant_results = []
    for pid in ("P001", "P002", "P003"):
        folder = INTAKE / "packages" / pid
        face = folder / "face.png"
        consent = read_json(folder / "consent.json")
        reasons = consent_ok(consent, pid)
        got = sha256_file(face)
        if got != PINS[pid]:
            reasons.append("PINNED_IMAGE_HASH_MISMATCH")
        if reasons:
            participant_results.append(
                {
                    "caseId": pid,
                    "judgment": "ABSTAIN",
                    "reasons": reasons,
                    "humanReviewAllowed": False,
                }
            )
            continue
        waive = pid == "P002"  # prior false-abstain adjudication path
        participant_results.append(process_case(pid, face, backend, out, waive_blur=waive))

    any_human = any(r.get("humanReviewAllowed") for r in participant_results)
    overall = "GATE6_PIPELINE_EXECUTED"
    if any(r.get("judgment") == "IDENTITY_VISUAL_QUALITY_GATE_PASS_TECHNICAL_MINIMUM" for r in participant_results):
        overall = "GATE6_IDENTITY_VISUAL_QUALITY_PARTIAL_OR_PASS"
    if not any_human:
        overall = "GATE6_EXECUTED_IDENTITY_REVIEW_NOT_READY"

    receipt = {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_IDENTITY_GRADE_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": overall,
        "gate6ParameterHash": g6_hash,
        "gate5ParameterHash": EXP_G5,
        "gate5Mutation": "DENY",
        "gate4ParameterHash": EXP_G4,
        "gate4Mutation": "DENY",
        "selectedModel": "NURION_PARAMETRIC_FACE_V0",
        "commercialLicense": "PASS_NURION_OWNED_PLUS_MEDIAPIPE_APACHE_TOPOLOGY",
        "research3dmmImported": "DENY",
        "priorFalseAutoPassRetracted": "20260816T081723Z_BLOB_RENDER_NOT_IDENTITY",
        "determinismFit": det,
        "synthetic": syn_results,
        "participants": participant_results,
        "humanReviewOpened": False if not any_human else "READY_TO_OPEN_COMBINED_SELF_INTERNAL",
        "skipProxyOnlyGates": True,
        "production": "NO-GO",
        "countsAsGate8ParticipantEvidence": "DENY",
        "next": (
            "OPEN_COMBINED_HUMAN_REVIEW"
            if any_human
            else "INCREASE_FACE_MESH_DENSITY_OR_CLEAR_COMMERCIAL_3DMM_THEN_RERUN"
        ),
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(out / "V07_QP_GF_FACE_V2_GATE6_IDENTITY_GRADE_RECEIPT.json", receipt)
    write_json(G6 / "V07_QP_GF_FACE_V2_GATE6_IDENTITY_GRADE_RECEIPT.json", receipt)

    status = {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_STATUS_V1",
        "V07_QP_GF_FACE_V2_GATE6": "IN_PROGRESS",
        "LOCKED": False,
        "parameterHash": g6_hash,
        "selectedModel": "NURION_PARAMETRIC_FACE_V0",
        "commercialLicense": "PASS_NURION_OWNED",
        "lastRunId": run_id,
        "lastVerdict": overall,
        "identityDraftQualityPass": "DENY" if not any_human else "PENDING_HUMAN_REVIEW",
        "humanReview": "HOLD_UNTIL_QUALITY_GATE_PASS" if not any_human else "READY",
        "gate5Pipeline": "PASS_LOCKED_UNCHANGED",
        "production": "NO-GO",
        "updatedAt": now,
        "next": receipt["next"],
    }
    write_json(G6 / "V07_QP_GF_FACE_V2_GATE6_STATUS.json", status)

    # Update Gate5 pointer only; do not unlock Gate5.
    g5s = read_json(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json")
    g5s["updatedAt"] = now
    g5s["gate6"] = {
        "status": "IN_PROGRESS",
        "parameterHash": g6_hash,
        "lastVerdict": overall,
        "implementation": "STARTED",
    }
    g5s["next"] = "GATE6_IN_PROGRESS"
    write_json(G5 / "V07_QP_GF_FACE_V2_GATE5_STATUS.json", g5s)

    # Hold file superseded
    hold = G5 / "V07_QP_GF_FACE_V2_GATE6_DESIGN_HOLD.json"
    if hold.is_file():
        doc = read_json(hold)
        doc["status"] = "SUPERSEDED_BY_GATE6_GO"
        doc["implementation"] = "STARTED"
        doc["updatedAt"] = now
        write_json(hold, doc)

    print(json.dumps({"verdict": overall, "runId": run_id, "gate6Hash": g6_hash, "participants": participant_results, "production": "NO-GO"}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
