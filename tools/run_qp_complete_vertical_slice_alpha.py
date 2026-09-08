"""NURION Quick Profile Complete Vertical Slice Alpha Implementation GO.

Isolated end-to-end Alpha for P001. Does not mutate sealed Gate1-5 / v0.3-v0.6.
Quality may be imperfect; Production remains NO-GO.
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
from nurion_qp_geometry_face_v2.integration_adapter import AdapterInput, GeometryFirstIntegrationAdapter
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from nurion_qp_geometry_face_v2.textured_landmark_head import (
    build_textured_landmark_head,
    eye_centers_metric,
    write_obj_mtl,
)
from nurion_quick_profile_core import (
    ARKAON_BIND,
    DEFAULT_HAIR,
    DEFAULT_OUTFIT,
    POLISHED,
    SILENT_PRESETS,
    recommend_body,
)
from run_quick_profile_gate3_consented_human_review import consent_ok

COMMAND = "NURION Quick Profile Complete Vertical Slice Alpha Implementation GO"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
P001_PIN = "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd"
BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
BLEND_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
ASSEMBLE = ROOT / "tools/blender_quick_profile_gate3_assemble.py"
EXPORT_PY = ROOT / "tools/blender_qp_complete_vertical_slice_alpha_export.py"
FACE_RENDER_PY = ROOT / "tools/blender_qp_gf_gate6_identity_grade_render.py"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake/packages/P001"
PARAMS = ROOT / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"
CONTRACT = ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_CONTRACT.json"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def run(cmd: list[str], log: Path) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(f"CMD_FAIL:{proc.returncode}:{cmd[0]}")


def render_face(obj_path: Path, albedo: Path, out_dir: Path, label: str, eye_l, eye_r) -> None:
    def fmt(v):
        return f"{float(v[0]):.8f};{float(v[1]):.8f};{float(v[2]):.8f}"

    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(FACE_RENDER_PY),
        "--",
        "--obj",
        str(obj_path),
        "--albedo",
        str(albedo),
        f"--out-dir={out_dir}",
        f"--draft-label={label}",
        f"--eye-l={fmt(eye_l)}",
        f"--eye-r={fmt(eye_r)}",
        "--resolution=1024",
    ]
    run(cmd, out_dir / f"_{label}_face_render_log.txt")


def compare_strip(original: Path, a: Path, b: Path, out: Path) -> None:
    imgs = [Image.open(p).convert("RGB").resize((384, 384)) for p in (original, a, b)]
    canvas = Image.new("RGB", (384 * 3 + 32, 384 + 40), (24, 26, 30))
    labels = ("ORIGINAL", "NATURAL_FACE", "POLISHED_FACE")
    draw = ImageDraw.Draw(canvas)
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x = 8 + i * (384 + 8)
        canvas.paste(im, (x, 28))
        draw.text((x, 6), lab, fill=(210, 210, 210))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = ALPHA / "runs" / f"alpha_{run_id}"
    out.mkdir(parents=True, exist_ok=True)
    stages: list[dict[str, Any]] = []

    # --- Baseline immutability checks (read-only) ---
    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("SEALED_GATE5_HASH_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")
    if sha256_file(BLEND) != BLEND_SHA:
        raise SystemExit("CANONICAL_BLEND_PIN_MISMATCH")
    if not BLENDER.is_file():
        raise SystemExit("BLENDER_MISSING")
    stages.append({"stage": "BASELINE_PIN_CHECK", "status": "PASS"})

    face = INTAKE / "face.png"
    consent = read_json(INTAKE / "consent.json")
    pin_reasons = consent_ok(consent, "P001")
    if sha256_file(face) != P001_PIN:
        pin_reasons.append("PINNED_IMAGE_HASH_MISMATCH")
    if pin_reasons:
        receipt = {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT_V1",
            "command": COMMAND,
            "runId": run_id,
            "verdict": "ABSTAIN",
            "reasons": pin_reasons,
            "production": "NO-GO",
            "completedAt": now,
        }
        write_json(out / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)
        write_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
        return 2

    participant = read_json(INTAKE / "participant_input.json")
    height = float(participant["heightCm"])
    weight = float(participant["weightKg"])
    pose = str(participant.get("declaredPose") or "FRONTAL")
    params_doc = read_json(PARAMS)

    # --- Face + capture quality analysis (isolated adapter, sealed core read-only) ---
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    adapter = GeometryFirstIntegrationAdapter(backend)
    analysis = adapter.analyze(
        AdapterInput("P001", face, height, weight, pose),
        params_doc,
        include_legacy_comparison=True,
    )
    write_json(out / "analysis/V07_QP_ALPHA_FACE_ANALYSIS.json", analysis)
    if analysis.get("verdict") == "ABSTAIN":
        # Soft path for Alpha: if geometry identity preview exists, continue with disclosure.
        if not ((analysis.get("identityLayer") or {}).get("values")):
            stages.append({"stage": "FACE_ANALYSIS", "status": "ABSTAIN", "detail": analysis.get("abstainReasons")})
            receipt = {
                "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT_V1",
                "command": COMMAND,
                "runId": run_id,
                "verdict": "ABSTAIN",
                "reasons": analysis.get("abstainReasons") or ["FACE_ANALYSIS_ABSTAIN"],
                "stages": stages,
                "production": "NO-GO",
                "completedAt": now,
            }
            write_json(out / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)
            write_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)
            print(json.dumps({"verdict": "ABSTAIN", "runId": run_id}, indent=2))
            return 2
        stages.append({"stage": "FACE_ANALYSIS", "status": "CONTINUE_WITH_LIMITATION", "detail": analysis.get("abstainReasons")})
    else:
        stages.append({"stage": "FACE_ANALYSIS", "status": "PASS", "verdict": analysis.get("verdict")})

    identity_layer = analysis.get("identityLayer") or {}
    identity = dict(identity_layer.get("values") or {})
    if not identity:
        raise SystemExit("NO_IDENTITY_VALUES")

    body = recommend_body(height, weight, params_doc)
    write_json(out / "analysis/V07_QP_ALPHA_BODY_RECOMMENDATION.json", body)
    stages.append({"stage": "BODY_RECOMMENDATION", "status": "PASS", "preset": body.get("recommendedPreset")})

    # --- NATURAL / POLISHED recipes ---
    base_recipe = {
        "identityValues": identity,
        "bodyPreset": body.get("recommendedPreset"),
        "bodyMorphValues": body.get("bodyMorphValues") or {},
        "hair": DEFAULT_HAIR,
        "outfit": DEFAULT_OUTFIT,
        "silentHomepagePresets": list(SILENT_PRESETS)[:5],
        "arkaonPresetBinding": list(ARKAON_BIND)[:5],
        "source": "COMPLETE_VERTICAL_SLICE_ALPHA",
        "alphaQualityImperfectAllowed": True,
        "distribution": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
    }
    natural = {
        **base_recipe,
        "beautificationMode": "NATURAL",
        "beautificationValues": {k: 0.0 for k in POLISHED},
    }
    polished = {
        **base_recipe,
        "beautificationMode": "POLISHED",
        "beautificationValues": {k: float(f"{v:.6f}") for k, v in POLISHED.items()},
    }
    write_json(out / "recipes/NATURAL.json", natural)
    write_json(out / "recipes/POLISHED.json", polished)
    stages.append({"stage": "RECIPES", "status": "PASS", "modes": ["NATURAL", "POLISHED"]})

    # --- Assemble BLEND (sealed source hash verified by assembler) ---
    for mode, recipe in (("NATURAL", natural), ("POLISHED", polished)):
        run(
            [
                str(BLENDER),
                "--background",
                "--python",
                str(ASSEMBLE),
                "--",
                "--source-blend",
                str(BLEND),
                "--expected-source-sha256",
                BLEND_SHA,
                "--recipe-json",
                str(out / f"recipes/{mode}.json"),
                "--out-dir",
                str(out),
                "--participant-id",
                "P001",
                "--mode",
                mode,
            ],
            out / f"logs/assemble_{mode}.txt",
        )
    stages.append({"stage": "BLEND_ASSEMBLE", "status": "PASS"})

    # --- Face textured landmark branch (triage-visible; body block proxy alone is BLOCKER) ---
    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    raw = backend.infer(rgb, "ORIGINAL_RGB")
    if raw is None:
        stages.append({"stage": "FACE_TEXTURE_BRANCH", "status": "ABSTAIN", "detail": ["NO_478"]})
        raise SystemExit("NO_478_FOR_FACE_BRANCH")
    face_dir = out / "face_branch"
    face_dir.mkdir(parents=True, exist_ok=True)
    full_albedo = face_dir / "albedo_full.png"
    Image.open(face).convert("RGB").save(full_albedo)
    eye_l, eye_r = eye_centers_metric(raw)
    for mode, polish in (("NATURAL", False), ("POLISHED", True)):
        verts, tris, uvs, _meta = build_textured_landmark_head(raw, polish=polish)
        obj_path = face_dir / f"{mode}_head.obj"
        write_obj_mtl(obj_path, verts, tris, uvs, albedo_name="albedo_full.png")
        render_face(obj_path, full_albedo, face_dir / "captures", mode, eye_l, eye_r)
    stages.append(
        {
            "stage": "FACE_TEXTURE_BRANCH",
            "status": "PASS",
            "note": "PRIMARY_TRIAGE_VIEW_FOR_LIKENESS",
        }
    )

    # --- Captures + GLB (canonical body — known low-poly block LIMITATION) ---
    for mode in ("NATURAL", "POLISHED"):
        blend_path = out / "drafts/P001" / mode / f"NURION_QP_Gate3_P001_{mode}.blend"
        if not blend_path.is_file():
            raise SystemExit(f"BLEND_MISSING:{mode}")
        export_dir = out / "exports" / mode
        cmd = [
            str(BLENDER),
            "--background",
            str(blend_path),
            "--python",
            str(EXPORT_PY),
            "--",
            "--blend",
            str(blend_path),
            "--out-dir",
            str(export_dir),
            "--label",
            mode,
            "--export-glb",
        ]
        if mode == "NATURAL":
            cmd.append("--export-video")
        run(cmd, out / f"logs/export_{mode}.txt")
    stages.append(
        {
            "stage": "BODY_CAPTURES_GLB",
            "status": "PASS_WITH_KNOWN_LIMITATION",
            "limitation": "CANONICAL_BODY_IS_BLOCK_PROXY_NOT_IDENTITY_FACE",
        }
    )

    # --- Compare pack uses FACE branch (not body blocks) ---
    compare_strip(
        face,
        face_dir / "captures/NATURAL_front.png",
        face_dir / "captures/POLISHED_front.png",
        out / "presentation/compare_original_natural_polished.png",
    )
    shutil.copy2(face, out / "presentation/original_face.png")
    for mode in ("NATURAL", "POLISHED"):
        for view in ("front", "left45", "right45"):
            src = face_dir / "captures" / f"{mode}_{view}.png"
            dst = out / "presentation" / f"face_{mode}_{view}.png"
            if src.is_file():
                shutil.copy2(src, dst)
    stages.append({"stage": "COMPARE_PACK", "status": "PASS", "primary": "FACE_BRANCH"})

    defects = {
        "schema": "NURION_V07_QP_ALPHA_DEFECT_TRIAGE_V1",
        "runId": run_id,
        "defects": [
            {
                "id": "D001",
                "grade": "BLOCKER",
                "code": "BODY_VIEW_IS_BLOCK_PROXY_NOT_FACE",
                "evidence": "exports/*/NATURAL_front.png shows white cuboid figure",
                "treatment": "Do not use body captures for likeness triage; use face_branch",
            },
            {
                "id": "D002",
                "grade": "MAJOR",
                "code": "FACE_BRANCH_NOT_YET_IDENTITY_GRADE",
                "evidence": "textured landmark head lacks eyelid/lip volume / may distort at 45deg",
                "treatment": "Beta1 batch: parametric structure + texture bind",
            },
            {
                "id": "D003",
                "grade": "MINOR",
                "code": "TURNTABLE_VIDEO_MISSING",
                "treatment": "Beta export robustness",
            },
        ],
    }
    write_json(out / "V07_QP_ALPHA_DEFECT_TRIAGE.json", defects)
    write_json(ALPHA / "V07_QP_ALPHA_DEFECT_TRIAGE.json", defects)

    # --- A/B review forms (empty; Alpha allows imperfect quality) ---
    for kind in ("SELF", "INTERNAL"):
        write_json(
            out / f"review/P001_{kind}_REVIEW.json",
            {
                "schema": f"NURION_V07_QP_ALPHA_{kind}_REVIEW_FORM_V1",
                "anonymousParticipantId": "P001",
                "phase": "ALPHA",
                "status": "NOT_COLLECTED",
                "completed": False,
                "preferredDraft": None,
                "overall": None,
                "comment": None,
                "alphaQualityImperfectAllowed": True,
                "production": "NO-GO",
            },
        )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>QP Complete Vertical Slice Alpha — P001</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#1a1c1f;color:#e8eaed}}
header{{padding:1rem 1.25rem;border-bottom:1px solid #333}}
.badge{{display:inline-block;margin:.2rem .3rem 0 0;padding:.2rem .5rem;border:1px solid #555;border-radius:999px;font-size:.75rem;color:#c4a574}}
.badge.bad{{border-color:#a55;color:#f0a0a0}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem;padding:1rem}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:1rem}}
img{{width:100%;background:#111;border-radius:.4rem}}
section{{padding:0 1rem 1.25rem}}
code{{color:#d7dde5;font-size:.85rem}}
.warn{{color:#f0c080}}
</style></head><body>
<header>
<h1>Complete Vertical Slice Alpha — P001</h1>
<p>유사성 트리아지 주뷰는 <b>얼굴 텍스처 분기</b>입니다. Canonical 몸 블록 캡처는 본인 비교용 아님.</p>
<span class="badge">ALPHA</span>
<span class="badge bad">BLOCKER: BODY_BLOCK_PROXY</span>
<span class="badge">run {run_id}</span>
<span class="badge">Production NO-GO</span>
</header>
<section><h2>원본 vs 얼굴 NATURAL/POLISHED (주 비교)</h2>
<img src="compare_original_natural_polished.png" alt="compare"/>
</section>
<div class="grid2">
<section><h2>NATURAL face</h2>
<img src="face_NATURAL_front.png"/><img src="face_NATURAL_left45.png"/><img src="face_NATURAL_right45.png"/>
</section>
<section><h2>POLISHED face</h2>
<img src="face_POLISHED_front.png"/><img src="face_POLISHED_left45.png"/><img src="face_POLISHED_right45.png"/>
</section>
</div>
<section><h2 class="warn">참고: Canonical 몸 Export (블록 프록시 — 유사성 평가 DENY)</h2>
<div class="grid2">
<div><img src="../exports/NATURAL/NATURAL_front.png"/><p><code>NATURAL.glb</code></p></div>
<div><img src="../exports/POLISHED/POLISHED_front.png"/><p><code>POLISHED.glb</code></p></div>
</div>
</section>
<section><h2>다음</h2>
<p>얼굴 분기에서 안 닮은 점(눈·코·입·측면·피부)을 고르고 review/*.json에 기록 → Beta1 일괄 보완</p>
</section></body></html>
"""
    (out / "presentation/ALPHA_REVIEW_DESK.html").write_text(desk, encoding="utf-8")
    stages.append({"stage": "AB_REVIEW_PACK", "status": "PASS"})

    # --- ARKAON Alpha stub (record + propose only) ---
    arkaon_events = [
        {
            "eventId": f"{run_id}_face_analysis",
            "recordedAtUtc": now,
            "anonymousSessionOrParticipantId": "P001",
            "consentScope": "INTERNAL_QUALITY_REVIEW",
            "eventType": "CAPTURE_QUALITY_JUDGMENT",
            "structuredCodes": ["ALPHA_VERTICAL_SLICE_EXECUTED"],
            "environmentTags": ["SINGLE_IMAGE", pose],
            "retentionClass": "REVIEW_ONLY",
            "originalFaceImageStored": False,
        },
        {
            "eventId": f"{run_id}_ab_ready",
            "recordedAtUtc": now,
            "anonymousSessionOrParticipantId": "P001",
            "consentScope": "INTERNAL_QUALITY_REVIEW",
            "eventType": "NATURAL_POLISHED_SELECTION",
            "structuredCodes": ["AB_PACK_READY_SELECTION_PENDING"],
            "environmentTags": ["ALPHA"],
            "retentionClass": "REVIEW_ONLY",
            "originalFaceImageStored": False,
        },
    ]
    write_json(out / "arkaon/V07_ARKAON_ALPHA_EXPERIENCE_EVENTS.json", {"events": arkaon_events})
    proposal = {
        "schema": "NURION_V07_ARKAON_ALPHA_IMPROVEMENT_PROPOSAL_V1",
        "autoApply": "DENY",
        "modelRetrain": "DENY",
        "autoDeploy": "DENY",
        "priorities": [
            {"code": "FACE_IDENTITY_LIKENESS", "priority": 1, "note": "본인 유사성 핵심"},
            {"code": "PROFILE_45DEG_STABILITY", "priority": 2, "note": "측면 형상"},
            {"code": "EYE_NOSE_MOUTH_STRUCTURE", "priority": 3, "note": "눈·코·입 구조"},
            {"code": "SKIN_HAIR_BIND", "priority": 4, "note": "피부·헤어 결합"},
            {"code": "HEAD_BODY_PROPORTION", "priority": 5, "note": "머리·몸 비율"},
            {"code": "EXPORT_ROBUSTNESS", "priority": 6, "note": "BLEND/GLB/영상"},
        ],
    }
    write_json(out / "arkaon/V07_ARKAON_ALPHA_IMPROVEMENT_PROPOSAL.json", proposal)
    stages.append({"stage": "ARKAON_ALPHA_STUB", "status": "PASS", "authority": "PROPOSE_ONLY"})

    # --- Inventory ---
    artifacts = {
        "naturalBlend": str(out / "drafts/P001/NATURAL/NURION_QP_Gate3_P001_NATURAL.blend"),
        "polishedBlend": str(out / "drafts/P001/POLISHED/NURION_QP_Gate3_P001_POLISHED.blend"),
        "naturalGlb": str(out / "exports/NATURAL/NATURAL.glb"),
        "polishedGlb": str(out / "exports/POLISHED/POLISHED.glb"),
        "naturalVideo": str(out / "exports/NATURAL/NATURAL_turntable.mp4"),
        "faceNaturalFront": str(out / "presentation/face_NATURAL_front.png"),
        "facePolishedFront": str(out / "presentation/face_POLISHED_front.png"),
        "reviewDesk": str(out / "presentation/ALPHA_REVIEW_DESK.html"),
        "compare": str(out / "presentation/compare_original_natural_polished.png"),
        "defectTriage": str(out / "V07_QP_ALPHA_DEFECT_TRIAGE.json"),
    }
    missing = [
        k
        for k, v in artifacts.items()
        if k not in ("naturalVideo",) and not Path(v).is_file()
    ]
    # video may fail on some ffmpeg builds — not blocker for Alpha connect
    if missing:
        stages.append({"stage": "ARTIFACT_CHECK", "status": "FAIL", "missing": missing})
        verdict = "ABSTAIN"
    else:
        stages.append(
            {
                "stage": "ARTIFACT_CHECK",
                "status": "PASS",
                "videoPresent": Path(artifacts["naturalVideo"]).is_file(),
            }
        )
        verdict = "ALPHA_VERTICAL_SLICE_CONNECTED"

    receipt = {
        "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "participant": "P001",
        "imageSha256": P001_PIN,
        "sealedGate5ParameterHash": EXP_G5,
        "sealedBaselineMutation": "DENY",
        "stages": stages,
        "artifacts": artifacts,
        "silentHomepagePresetsBound": list(SILENT_PRESETS)[:5],
        "hairOutfit": {"hair": DEFAULT_HAIR, "outfit": DEFAULT_OUTFIT, "meshAttach": "METADATA_ALPHA"},
        "alphaQualityImperfectAllowed": True,
        "humanReviewOpened": True,
        "production": "NO-GO",
        "productAccuracyClaim": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "arkaonModelRetrainOrAutoDeploy": "DENY",
        "next": "HUMAN_INSPECTS_ALPHA_THEN_BETA1_BATCH_FIXES",
        "contractSha256": sha256_file(CONTRACT),
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")}
    )
    write_json(out / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)
    write_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_RECEIPT.json", receipt)

    status = {
        "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS_V1",
        "track": "NURION Quick Profile Complete Vertical Slice Alpha",
        "phase": "ALPHA",
        "status": verdict,
        "LOCKED": False,
        "updatedAt": now,
        "lastRunId": run_id,
        "runDir": str(out.relative_to(ROOT)).replace("\\", "/"),
        "reviewDesk": str((out / "presentation/ALPHA_REVIEW_DESK.html").relative_to(ROOT)).replace("\\", "/"),
        "sealedBaselineMutation": "DENY",
        "production": "NO-GO",
        "next": "BETA1_CORE_QUALITY_BATCH_AFTER_HUMAN_TRIAGE",
    }
    write_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json", status)

    # Open desk for operator
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(out / "presentation/ALPHA_REVIEW_DESK.html")], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "runId": run_id,
                "reviewDesk": artifacts["reviewDesk"],
                "production": "NO-GO",
                "sealedBaselineMutation": "DENY",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "ALPHA_VERTICAL_SLICE_CONNECTED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
