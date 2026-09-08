"""NURION Quick Profile Complete Vertical Slice Beta 1 Parametric Head Replacement And Visual Assembly GO."""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.integration_adapter import AdapterInput, GeometryFirstIntegrationAdapter
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from nurion_qp_geometry_face_v2.nurion_parametric_head_v1 import fit_parametric_head_from_478, write_obj
from nurion_qp_geometry_face_v2.parametric_face_v0 import write_face_albedo_crop
from nurion_quick_profile_core import DEFAULT_HAIR, DEFAULT_OUTFIT, POLISHED, SILENT_PRESETS, recommend_body
from run_quick_profile_gate3_consented_human_review import consent_ok

COMMAND = "NURION Quick Profile Complete Vertical Slice Beta 1 Parametric Head Replacement And Visual Assembly GO"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
P001_PIN = "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd"
BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
BLEND_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
ASSEMBLE = ROOT / "tools/blender_quick_profile_gate3_assemble.py"
RENDER_PY = ROOT / "tools/blender_qp_beta1_parametric_head_replace.py"
ASSEMBLY_PY = ROOT / "tools/blender_qp_beta1_visual_assembly.py"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake/packages/P001"
PARAMS = ROOT / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json"
OUT_ROOT = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ALPHA_STATUS = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha/V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json"
DONE_CHECKS = [
    "NO_PER_TRIANGLE_TEXTURE_TEARING",
    "NO_EYEBALL_PROTRUSION",
    "EYELID_NOSE_LIP_JAW_IDENTIFIABLE",
    "FRONTAL_COMPARABLE_TO_ORIGINAL",
    "NO_45DEG_COLLAPSE",
    "NATURAL_POLISHED_HUMAN_EXPLAINABLE",
    "HEAD_BODY_CONNECTED",
]


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run(cmd: list[str], log: Path, *, expect_files: list[Path] | None = None) -> None:
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = (proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or "")
    log.write_text(text, encoding="utf-8")
    if proc.returncode != 0 or "Traceback (most recent call last):" in text:
        raise RuntimeError(f"CMD_FAIL:{proc.returncode}:{log}")
    if expect_files:
        missing = [str(p) for p in expect_files if not p.is_file()]
        if missing:
            raise RuntimeError(f"RENDER_MISSING:{missing}")


def compare_row(paths: list[Path], labels: list[str], out: Path) -> None:
    imgs = [Image.open(p).convert("RGB").resize((380, 380)) for p in paths]
    canvas = Image.new("RGB", (380 * len(imgs) + 20 * (len(imgs) + 1), 420), (20, 22, 26))
    draw = ImageDraw.Draw(canvas)
    for i, (im, lab) in enumerate(zip(imgs, labels)):
        x = 20 + i * (380 + 20)
        canvas.paste(im, (x, 36))
        draw.text((x, 10), lab, fill=(230, 230, 230))
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out)


def fmt_vec(v: np.ndarray) -> str:
    return f"{float(v[0]):.8f};{float(v[1]):.8f};{float(v[2]):.8f}"


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / "runs" / f"paramhead_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("SEALED_GATE5_HASH_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")
    if sha256_file(BLEND) != BLEND_SHA:
        raise SystemExit("CANONICAL_BLEND_SHA_MISMATCH")

    face = INTAKE / "face.png"
    reasons = consent_ok(json.loads((INTAKE / "consent.json").read_text(encoding="utf-8")), "P001")
    if sha256_file(face) != P001_PIN:
        reasons.append("PIN_MISMATCH")
    if reasons:
        write_json(out / "RECEIPT.json", {"verdict": "ABSTAIN", "reasons": reasons})
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

    rgb = np.asarray(Image.open(face).convert("RGB"), dtype=np.uint8)
    raw = backend.infer(rgb, "ORIGINAL_RGB")
    if raw is None:
        raise SystemExit("NO_478")

    xs, ys = raw[:, 0], raw[:, 1]
    pad = 0.06
    bbox = (
        float(max(0, xs.min() - pad)),
        float(max(0, ys.min() - pad)),
        float(min(1, xs.max() + pad)),
        float(min(1, ys.max() + pad)),
    )
    albedo_meta = write_face_albedo_crop(face, bbox, out / "albedo_face_1024.png")
    write_json(out / "albedo_meta.json", albedo_meta)

    base = {
        "identityValues": identity,
        "bodyPreset": body.get("recommendedPreset"),
        "bodyMorphValues": body.get("bodyMorphValues") or {},
        "hair": DEFAULT_HAIR,
        "outfit": DEFAULT_OUTFIT,
        "silentHomepagePresets": list(SILENT_PRESETS)[:5],
        "source": "BETA1_PARAMETRIC_HEAD_REPLACEMENT",
        "production": "NO-GO",
        "countsAsGate8ParticipantEvidence": "DENY",
        "faceRenderPath": "NURION_PARAMETRIC_HEAD_V1",
        "directFaceMeshRender": "DENY",
    }
    recipes = {
        "NATURAL": {**base, "beautificationMode": "NATURAL", "beautificationValues": {k: 0.0 for k in POLISHED}},
        "POLISHED": {
            **base,
            "beautificationMode": "POLISHED",
            "beautificationValues": {k: float(f"{v:.6f}") for k, v in POLISHED.items()},
        },
    }

    fits = {}
    for mode, polish in (("NATURAL", False), ("POLISHED", True)):
        fit = fit_parametric_head_from_478(raw, polish=polish)
        fits[mode] = fit
        obj_path = out / f"meshes/{mode}_param_head_v1.obj"
        meta = write_obj(obj_path, fit)
        corr_path = out / f"meshes/{mode}_corr.json"
        write_json(corr_path, fit.correspondences)
        write_json(out / f"meshes/{mode}_fit.json", {"params": fit.params, "disclosures": list(fit.disclosures), **meta})

        # Isolated face QA captures (parametric head only)
        cap = out / "captures" / mode
        run(
            [
                str(BLENDER),
                "--background",
                "--python",
                str(RENDER_PY),
                "--",
                f"--obj={obj_path}",
                f"--albedo={out / 'albedo_face_1024.png'}",
                f"--out-dir={cap}",
                f"--label={mode}",
                f"--corr-json={corr_path}",
                "--resolution=1024",
            ],
            out / f"logs/render_{mode}.txt",
            expect_files=[
                cap / f"{mode}_face_front.png",
                cap / f"{mode}_face_left45.png",
                cap / f"{mode}_face_right45.png",
            ],
        )

        # Canonical body assemble (sealed blend copy) + head bind
        write_json(out / f"recipes/{mode}.json", recipes[mode])
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
        blend_path = out / f"drafts/P001/{mode}/NURION_QP_Gate3_P001_{mode}.blend"
        eye_l = fit.vertices[fit.correspondences["L_EYE"]]
        eye_r = fit.vertices[fit.correspondences["R_EYE"]]
        export_dir = out / "visual" / mode
        run(
            [
                str(BLENDER),
                "--background",
                str(blend_path),
                "--python",
                str(ASSEMBLY_PY),
                "--",
                f"--blend={blend_path}",
                f"--face-obj={obj_path}",
                f"--albedo={out / 'albedo_face_1024.png'}",
                f"--eye-l={fmt_vec(eye_l)}",
                f"--eye-r={fmt_vec(eye_r)}",
                f"--out-dir={export_dir}",
                f"--label={mode}",
                "--resolution=1024",
            ],
            out / f"logs/assemble_visual_{mode}.txt",
            expect_files=[
                export_dir / f"{mode}_face_front.png",
                export_dir / f"{mode}_body_front.png",
            ],
        )

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    shutil.copy2(face, pres / "original_face.png")
    for mode in ("NATURAL", "POLISHED"):
        for view in ("face_front", "face_left45", "face_right45", "body_front", "body_left45", "body_right45"):
            for src in (
                out / "visual" / mode / f"{mode}_{view}.png",
                out / "captures" / mode / f"{mode}_{view}.png",
            ):
                if src.is_file():
                    shutil.copy2(src, pres / f"{mode}_{view}.png")
                    break

    compare_row(
        [pres / "original_face.png", pres / "NATURAL_face_front.png", pres / "POLISHED_face_front.png"],
        ["ORIGINAL", "NATURAL_PARAM_HEAD", "POLISHED_PARAM_HEAD"],
        pres / "compare_face.png",
    )
    if (pres / "NATURAL_body_front.png").is_file() and (pres / "POLISHED_body_front.png").is_file():
        compare_row(
            [pres / "original_face.png", pres / "NATURAL_body_front.png", pres / "POLISHED_body_front.png"],
            ["ORIGINAL", "NATURAL_BODY", "POLISHED_BODY"],
            pres / "compare_body.png",
        )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Beta1 Parametric Head + Visual Assembly — P001</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed}}
header{{padding:1rem 1.2rem;border-bottom:1px solid #333}}
.badge{{display:inline-block;margin-right:.35rem;padding:.2rem .5rem;border:1px solid #666;border-radius:999px;font-size:.75rem;color:#c4a574}}
img{{width:100%;border-radius:.4rem;background:#111}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;padding:1rem}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.5rem}}
section{{padding:0 1rem 1rem}}
</style></head><body>
<header>
<h1>Parametric Head Replacement + Visual Assembly — P001</h1>
<p>MediaPipe FaceMesh 직접 렌더 DENY. NURION_PARAMETRIC_HEAD_V1 · 연속 UV · Canonical 몸 결합.</p>
<span class="badge">DIRECT_FACEMESH_PATH_REMOVED</span>
<span class="badge">run {run_id}</span>
<span class="badge">Production NO-GO</span>
<span class="badge">강제 PASS 금지</span>
</header>
<section><h2>원본 vs 얼굴</h2><img src="compare_face.png"/></section>
<section><h2>NATURAL / POLISHED 얼굴 ±45°</h2>
<div class="grid2">
<div class="grid3"><img src="NATURAL_face_front.png"/><img src="NATURAL_face_left45.png"/><img src="NATURAL_face_right45.png"/></div>
<div class="grid3"><img src="POLISHED_face_front.png"/><img src="POLISHED_face_left45.png"/><img src="POLISHED_face_right45.png"/></div>
</div></section>
<section><h2>전신 조립</h2>
{"<img src='compare_body.png'/>" if (pres / "compare_body.png").is_file() else "<p>body compare 없음</p>"}
</section>
<section><p>완료 기준 미달 시 REVIEW_REQUIRED. 강제 PASS 금지.</p></section>
</body></html>
"""
    (pres / "BETA1_PARAMHEAD_REVIEW_DESK.html").write_text(desk, encoding="utf-8")

    required = [
        pres / "compare_face.png",
        pres / "NATURAL_face_front.png",
        pres / "POLISHED_face_front.png",
        pres / "NATURAL_face_left45.png",
        pres / "POLISHED_face_left45.png",
        pres / "NATURAL_body_front.png",
        pres / "POLISHED_body_front.png",
    ]
    missing = [str(p) for p in required if not p.is_file()]
    head_body = not missing and (pres / "NATURAL_body_front.png").is_file()

    # Honest machine status: path replaced, quality not auto-PASS
    auto = {
        "usesDirectFaceMeshRender": False,
        "usesMediapipeZAsDepth": False,
        "modelId": "NURION_PARAMETRIC_HEAD_V1",
        "filesPresent": not missing,
        "doneChecksPendingHuman": DONE_CHECKS,
        "headBodyConnected": head_body,
        "forcedPass": "DENY",
        "humanEvaluableClaim": "PENDING_HUMAN",
    }
    if missing:
        verdict = "ABSTAIN"
    else:
        # Path fix executed; Beta1 done criteria still require human — never force PASS
        verdict = "BETA1_PARAMETRIC_HEAD_REPLACED_REVIEW_REQUIRED"

    receipt = {
        "schema": "NURION_V07_QP_BETA1_PARAMETRIC_HEAD_REPLACEMENT_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "priorBlocker": "BLOCKER_DIRECT_FACEMESH_RENDERING_INVALID",
        "directFaceMeshRenderPath": "REMOVED",
        "alphaFaceOutput": "IDENTITY_RENDER_INVALID",
        "alphaPreservedAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
        "selectedModel": "NURION_PARAMETRIC_HEAD_V1",
        "commercialClearance": "NURION_OWNED",
        "research3dmmImported": "DENY",
        "mediapipeRole": "FITTING_CONSTRAINT_2D_ONLY",
        "mediapipeZAsDepth": "DENY",
        "doNotPatchApplied": True,
        "auto": auto,
        "missing": missing,
        "doneChecks": DONE_CHECKS,
        "reviewDesk": str(pres / "BETA1_PARAMHEAD_REVIEW_DESK.html"),
        "forcedPass": "DENY",
        "production": "NO-GO",
        "sealedGate5Mutation": "DENY",
        "next": "HUMAN_VISUAL_CHECKS_THEN_ITERATE_PARAMETRIC_FIT_IF_REVIEW_REQUIRED",
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_BETA1_PARAMETRIC_HEAD_REPLACEMENT_RECEIPT.json", receipt)
    write_json(OUT_ROOT / "V07_QP_BETA1_PARAMETRIC_HEAD_REPLACEMENT_RECEIPT.json", receipt)
    write_json(
        OUT_ROOT / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": verdict,
            "blockerPath": "DIRECT_FACEMESH_RENDER_PATH_REMOVED",
            "qualityGate": "REVIEW_REQUIRED",
            "parametricHead": "NURION_PARAMETRIC_HEAD_V1",
            "updatedAt": now,
            "lastRunId": run_id,
            "reviewDesk": str((pres / "BETA1_PARAMHEAD_REVIEW_DESK.html").relative_to(ROOT)).replace("\\", "/"),
            "forcedPass": "DENY",
            "production": "NO-GO",
            "headBodyConnected": head_body,
            "doneChecks": DONE_CHECKS,
            "next": receipt["next"],
        },
    )

    # Keep Alpha as plumbing evidence; face output stays IDENTITY_RENDER_INVALID
    if ALPHA_STATUS.is_file():
        alpha = read_json(ALPHA_STATUS)
        alpha.update(
            {
                "faceOutput": "IDENTITY_RENDER_INVALID",
                "faceRenderPath": "BLOCKER_DIRECT_FACEMESH_RENDERING_INVALID",
                "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
                "visualProductEvaluable": "DENY",
                "beta1Command": COMMAND,
                "beta1LastRunId": run_id,
                "beta1Status": verdict,
                "updatedAt": now,
            }
        )
        write_json(ALPHA_STATUS, alpha)

    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(pres / "BETA1_PARAMHEAD_REVIEW_DESK.html")], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "runId": run_id,
                "reviewDesk": receipt["reviewDesk"],
                "headBodyConnected": head_body,
                "forcedPass": "DENY",
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
