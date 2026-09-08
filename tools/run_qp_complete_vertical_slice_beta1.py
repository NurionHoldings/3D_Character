"""NURION Quick Profile Complete Vertical Slice Beta 1 Product Visual Assembly Remediation GO.

Isolated. Does not mutate sealed Gate1-5 / v0.3-v0.6.
Done criterion: human can specifically point likeness gaps beside P001 original.
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
from nurion_quick_profile_core import DEFAULT_HAIR, DEFAULT_OUTFIT, POLISHED, SILENT_PRESETS, recommend_body
from run_quick_profile_gate3_consented_human_review import consent_ok

COMMAND = "NURION Quick Profile Complete Vertical Slice Beta 1 Product Visual Assembly Remediation GO"
DONE_KO = "P001 원본 옆에서 얼굴·헤어·의상·전신을 실제로 보고, 닮은 부분과 안 닮은 부분을 사람이 구체적으로 지적할 수 있을 것"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
P001_PIN = "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd"
BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
BLEND_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
ASSEMBLE = ROOT / "tools/blender_quick_profile_gate3_assemble.py"
BETA1_PY = ROOT / "tools/blender_qp_beta1_visual_assembly.py"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake/packages/P001"
PARAMS = ROOT / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"
BETA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"


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
        raise RuntimeError(f"CMD_FAIL:{proc.returncode}:{Path(cmd[0]).name}")


def compare_row(paths: list[Path], labels: list[str], out: Path) -> None:
    imgs = [Image.open(p).convert("RGB").resize((360, 360)) for p in paths]
    canvas = Image.new("RGB", (360 * len(imgs) + 16 * (len(imgs) + 1), 400), (22, 24, 28))
    draw = ImageDraw.Draw(canvas)
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x = 16 + i * (360 + 16)
        canvas.paste(im, (x, 32))
        draw.text((x, 8), lab, fill=(220, 220, 220))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = BETA / "runs" / f"beta1_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("SEALED_GATE5_HASH_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")
    if sha256_file(BLEND) != BLEND_SHA:
        raise SystemExit("CANONICAL_BLEND_PIN_MISMATCH")

    face = INTAKE / "face.png"
    reasons = consent_ok(read_json(INTAKE / "consent.json"), "P001")
    if sha256_file(face) != P001_PIN:
        reasons.append("PINNED_IMAGE_HASH_MISMATCH")
    if reasons:
        write_json(out / "RECEIPT.json", {"verdict": "ABSTAIN", "reasons": reasons, "production": "NO-GO"})
        return 2

    participant = read_json(INTAKE / "participant_input.json")
    params = read_json(PARAMS)
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    adapter = GeometryFirstIntegrationAdapter(backend)
    analysis = adapter.analyze(
        AdapterInput("P001", face, float(participant["heightCm"]), float(participant["weightKg"]), "FRONTAL"),
        params,
    )
    write_json(out / "analysis.json", analysis)
    identity = dict(((analysis.get("identityLayer") or {}).get("values")) or {})
    if not identity:
        raise SystemExit("NO_IDENTITY_VALUES")
    body = recommend_body(float(participant["heightCm"]), float(participant["weightKg"]), params)

    base = {
        "identityValues": identity,
        "bodyPreset": body.get("recommendedPreset"),
        "bodyMorphValues": body.get("bodyMorphValues") or {},
        "hair": DEFAULT_HAIR,
        "outfit": DEFAULT_OUTFIT,
        "silentHomepagePresets": list(SILENT_PRESETS)[:5],
        "source": "BETA1_VISUAL_ASSEMBLY",
        "production": "NO-GO",
        "countsAsGate8ParticipantEvidence": "DENY",
    }
    recipes = {
        "NATURAL": {**base, "beautificationMode": "NATURAL", "beautificationValues": {k: 0.0 for k in POLISHED}},
        "POLISHED": {
            **base,
            "beautificationMode": "POLISHED",
            "beautificationValues": {k: float(f"{v:.6f}") for k, v in POLISHED.items()},
        },
    }
    for mode, recipe in recipes.items():
        write_json(out / f"recipes/{mode}.json", recipe)
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

    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    raw = backend.infer(rgb, "ORIGINAL_RGB")
    if raw is None:
        raise SystemExit("NO_478")
    eye_l, eye_r = eye_centers_metric(raw)
    albedo = out / "face/albedo_full.png"
    albedo.parent.mkdir(parents=True, exist_ok=True)
    Image.open(face).convert("RGB").save(albedo)

    def fmt(v):
        return f"{float(v[0]):.8f};{float(v[1]):.8f};{float(v[2]):.8f}"

    for mode, polish in (("NATURAL", False), ("POLISHED", True)):
        verts, tris, uvs, _ = build_textured_landmark_head(raw, polish=polish)
        obj_path = out / f"face/{mode}_head.obj"
        write_obj_mtl(obj_path, verts, tris, uvs, albedo_name="albedo_full.png")
        blend_path = out / f"drafts/P001/{mode}/NURION_QP_Gate3_P001_{mode}.blend"
        export_dir = out / "visual" / mode
        run(
            [
                str(BLENDER),
                "--background",
                str(blend_path),
                "--python",
                str(BETA1_PY),
                "--",
                f"--blend={blend_path}",
                f"--face-obj={obj_path}",
                f"--albedo={albedo}",
                f"--eye-l={fmt(eye_l)}",
                f"--eye-r={fmt(eye_r)}",
                f"--out-dir={export_dir}",
                f"--label={mode}",
                "--resolution=1024",
            ],
            out / f"logs/beta1_{mode}.txt",
        )

    # Presentation
    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    shutil.copy2(face, pres / "original_face.png")
    for mode in ("NATURAL", "POLISHED"):
        for view in ("face_front", "face_left45", "face_right45", "body_front", "body_left45", "body_right45"):
            src = out / "visual" / mode / f"{mode}_{view}.png"
            if src.is_file():
                shutil.copy2(src, pres / f"{mode}_{view}.png")

    compare_row(
        [pres / "original_face.png", pres / "NATURAL_face_front.png", pres / "POLISHED_face_front.png"],
        ["ORIGINAL", "NATURAL_FACE", "POLISHED_FACE"],
        pres / "compare_face.png",
    )
    compare_row(
        [pres / "original_face.png", pres / "NATURAL_body_front.png", pres / "POLISHED_body_front.png"],
        ["ORIGINAL", "NATURAL_BODY", "POLISHED_BODY"],
        pres / "compare_body.png",
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Beta 1 Visual Assembly — P001</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#17191c;color:#e8eaed}}
header{{padding:1rem 1.25rem;border-bottom:1px solid #333}}
.badge{{display:inline-block;margin-right:.35rem;padding:.2rem .55rem;border:1px solid #666;border-radius:999px;font-size:.75rem;color:#c4a574}}
img{{width:100%;border-radius:.4rem;background:#0e0f11}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:1rem}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.6rem}}
section{{padding:0 1rem 1.2rem}}
.crit{{color:#f0c080}}
</style></head><body>
<header>
<h1>Beta 1 Product Visual Assembly — P001</h1>
<p class="crit">완료 기준: {DONE_KO}</p>
<span class="badge">BETA1</span><span class="badge">run {run_id}</span><span class="badge">Production NO-GO</span>
</header>
<section><h2>얼굴 비교 (정면)</h2><img src="compare_face.png"/></section>
<section><h2>얼굴 ±45°</h2>
<div class="grid2">
<div class="grid3"><img src="NATURAL_face_front.png"/><img src="NATURAL_face_left45.png"/><img src="NATURAL_face_right45.png"/><p>NATURAL</p></div>
<div class="grid3"><img src="POLISHED_face_front.png"/><img src="POLISHED_face_left45.png"/><img src="POLISHED_face_right45.png"/><p>POLISHED</p></div>
</div></section>
<section><h2>전신 홈페이지 구도</h2><img src="compare_body.png"/>
<div class="grid2">
<div class="grid3"><img src="NATURAL_body_front.png"/><img src="NATURAL_body_left45.png"/><img src="NATURAL_body_right45.png"/></div>
<div class="grid3"><img src="POLISHED_body_front.png"/><img src="POLISHED_body_left45.png"/><img src="POLISHED_body_right45.png"/></div>
</div></section>
<section><h2>산출</h2>
<p>BLEND/GLB: <code>visual/NATURAL|POLISHED/*_Beta1_Visual.*</code></p>
<p>블록 머리 프록시 단독 렌더는 제품 비교에서 제외. 얼굴 헤드·헤어·의상 셸이 장면에 유지됩니다.</p>
</section>
</body></html>
"""
    (pres / "BETA1_REVIEW_DESK.html").write_text(desk, encoding="utf-8")

    required = [
        pres / "compare_face.png",
        pres / "NATURAL_face_front.png",
        pres / "POLISHED_face_front.png",
        pres / "NATURAL_body_front.png",
        out / "visual/NATURAL/NATURAL_Beta1_Visual.blend",
        out / "visual/NATURAL/NATURAL_Beta1_Visual.glb",
        out / "visual/POLISHED/POLISHED_Beta1_Visual.blend",
        out / "visual/POLISHED/POLISHED_Beta1_Visual.glb",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    # Human-evaluable proxy score: face front files exist and not tiny
    face_ok = all(p.is_file() and p.stat().st_size > 40000 for p in (
        pres / "NATURAL_face_front.png",
        pres / "POLISHED_face_front.png",
        pres / "compare_face.png",
    ))
    if missing:
        verdict = "ABSTAIN"
    elif face_ok:
        verdict = "BETA1_VISUAL_ASSEMBLY_READY_FOR_HUMAN_TRIAGE"
    else:
        verdict = "BETA1_EXECUTED_STILL_NOT_HUMAN_EVALUABLE"

    receipt = {
        "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "doneCriterionKo": DONE_KO,
        "alphaOfficialVerdict": "ALPHA_PIPELINE_CONNECTED_VISUAL_PRODUCT_NOT_EVALUABLE",
        "remediationsAttempted": [
            "COLLAPSE_BLOCK_HEAD_PROXY",
            "BIND_TEXTURED_PARAMETRIC_FACE_HEAD",
            "ADD_EYEBALLS",
            "KEEP_HAIR_AND_OUTFIT_SHELLS",
            "SKIN_MATERIAL_ON_BODY",
            "SEPARATE_FACE_AND_BODY_CAMERAS",
            "EXPORT_BLEND_GLB_WITH_APPEARANCE",
        ],
        "missing": missing,
        "reviewDesk": str(pres / "BETA1_REVIEW_DESK.html"),
        "sealedBaselineMutation": "DENY",
        "gate5ParameterHash": EXP_G5,
        "production": "NO-GO",
        "productAccuracyClaim": "DENY",
        "turntable": "DEPRIORITIZED",
        "next": "HUMAN_TRIAGE_LIKENESS_GAPS_THEN_BATCH_FIX" if face_ok else "CONTINUE_VISUAL_REMEDIATION",
    }
    receipt["executionFingerprintSha256"] = sha256_obj(
        {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    )
    write_json(out / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_RECEIPT.json", receipt)
    write_json(BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_RECEIPT.json", receipt)
    write_json(
        BETA / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": verdict,
            "LOCKED": False,
            "updatedAt": now,
            "lastRunId": run_id,
            "doneCriterionKo": DONE_KO,
            "reviewDesk": str((pres / "BETA1_REVIEW_DESK.html").relative_to(ROOT)).replace("\\", "/"),
            "production": "NO-GO",
            "sealedBaselineMutation": "DENY",
        },
    )

    # Point alpha next to beta1
    ast = read_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json")
    ast["updatedAt"] = now
    ast["beta1"] = {"status": verdict, "runId": run_id}
    write_json(ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json", ast)

    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(pres / "BETA1_REVIEW_DESK.html")], shell=False)
    except Exception:
        pass

    print(json.dumps({"verdict": verdict, "runId": run_id, "reviewDesk": receipt["reviewDesk"], "production": "NO-GO"}, indent=2, ensure_ascii=False))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
