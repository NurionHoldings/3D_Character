"""NURION Quick Profile Beta 1.1 Head-Only Scene Isolation Object Audit And True Parametric Depth GO.

No full-body renders. Outputs only: wireframe, front, left45, right45.
Screenshots DENY until auto structural audit PASS.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.mediapipe_backend import EXP_LM, MediaPipeLandmarkerBackend, sha256_file
from nurion_qp_geometry_face_v2.nurion_parametric_head_v1 import (
    depth_order_metrics,
    fit_parametric_head_from_478,
    write_obj,
)
from nurion_qp_geometry_face_v2.parametric_face_v0 import write_face_albedo_crop
from run_quick_profile_gate3_consented_human_review import consent_ok
from write_qp_beta1_1_partial_adjudication import main as write_adjudication

COMMAND = "NURION Quick Profile Beta 1.1 Head-Only Scene Isolation Object Audit And True Parametric Depth GO"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"
P001_PIN = "67d862644c3700586ad70fafc81d318d540bf55734a1156875fa1023e32548bd"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_beta1_1_head_only_audit_render.py"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake/packages/P001"
OUT_ROOT = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ONLY_VIEWS = ("head_wireframe", "head_front", "head_left45", "head_right45")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run(cmd: list[str], log: Path) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    text = (proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or "")
    log.write_text(text, encoding="utf-8")
    if "Traceback (most recent call last):" in text:
        return 1
    return int(proc.returncode)


def main() -> int:
    write_adjudication()

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = OUT_ROOT / "runs" / f"beta1_1_headonly_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        raise SystemExit("SEALED_GATE5_HASH_MISMATCH")
    if sha256_file(MODELS / "face_landmarker_float16_v1.task") != EXP_LM:
        raise SystemExit("LANDMARKER_SHA_MISMATCH")

    face = INTAKE / "face.png"
    reasons = consent_ok(json.loads((INTAKE / "consent.json").read_text(encoding="utf-8")), "P001")
    if sha256_file(face) != P001_PIN:
        reasons.append("PIN_MISMATCH")
    if reasons:
        write_json(out / "RECEIPT.json", {"verdict": "ABSTAIN", "reasons": reasons})
        return 2

    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
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
    write_face_albedo_crop(face, bbox, out / "albedo_face_1024.png")

    # NATURAL only for head-only audit (no NATURAL/POLISHED body pair)
    fit = fit_parametric_head_from_478(raw, polish=False)
    obj_path = out / "meshes/HEAD_param_head_v1_1.obj"
    meta = write_obj(obj_path, fit)
    corr_path = out / "meshes/HEAD_corr.json"
    write_json(corr_path, fit.correspondences)
    depth = depth_order_metrics(fit)
    write_json(out / "meshes/HEAD_fit.json", {**meta, "depthOrder": depth})

    pre_audit = {
        "facemesh854FinalRender": meta["triangleCount"] == 854,
        "triangleCount": meta["triangleCount"],
        "vertexCount": meta["vertexCount"],
        "parametricTopology": meta["triangleCount"] > 2000 and meta["triangleCount"] != 854,
        "depthOrder": depth,
        "mediapipeZAsDepth": "DENY",
        "fullBodyAssembly": "DENY",
        "grayBarPriorObject": "Beta1Hair_SHORT_NEAT_01",
        "grayBarPriorScript": "tools/blender_qp_beta1_visual_assembly.py",
    }
    write_json(out / "PRE_RENDER_MESH_AUDIT.json", pre_audit)
    if pre_audit["facemesh854FinalRender"] or not pre_audit["parametricTopology"]:
        write_json(
            out / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json",
            {"verdict": "AUTO_AUDIT_FAIL", "stage": "PRE_RENDER_MESH", "pre_audit": pre_audit},
        )
        return 3
    if not (depth["noseForwardOfLips"] and depth["noseForwardOfCheek"]):
        write_json(
            out / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json",
            {"verdict": "AUTO_AUDIT_FAIL", "stage": "PRE_RENDER_DEPTH", "pre_audit": pre_audit},
        )
        return 3

    cap = out / "captures"
    audit_path = out / "SCENE_OBJECT_AUDIT.json"
    rc = run(
        [
            str(BLENDER),
            "--background",
            "--python",
            str(RENDER_PY),
            "--",
            f"--obj={obj_path}",
            f"--albedo={out / 'albedo_face_1024.png'}",
            f"--corr-json={corr_path}",
            f"--out-dir={cap}",
            "--label=HEAD",
            f"--audit-json={audit_path}",
            "--resolution=1024",
        ],
        out / "logs/head_only_render.txt",
    )

    audit = {}
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))

    if rc == 3 or (audit and not audit.get("pass")):
        receipt = {
            "schema": "NURION_V07_QP_BETA1_1_HEAD_ONLY_RECEIPT_V1",
            "command": COMMAND,
            "runId": run_id,
            "verdict": "AUTO_AUDIT_FAIL",
            "completedAt": now,
            "pre_audit": pre_audit,
            "scene_audit": audit,
            "fullBodyAssembly": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "outputs": [],
        }
        write_json(out / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json", receipt)
        write_json(OUT_ROOT / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json", receipt)
        write_json(
            OUT_ROOT / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
            {
                "status": "BETA1_1_HEAD_ONLY_AUTO_AUDIT_FAIL",
                "prior": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
                "updatedAt": now,
                "fullBodyAssembly": "DENY",
                "forcedPass": "DENY",
                "production": "NO-GO",
                "lastRunId": run_id,
            },
        )
        print(json.dumps({"verdict": "AUTO_AUDIT_FAIL", "audit": audit}, indent=2, ensure_ascii=False))
        return 3

    if rc != 0:
        raise RuntimeError(f"BLENDER_FAIL:{rc}:{out / 'logs/head_only_render.txt'}")

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    outputs = []
    for view in ONLY_VIEWS:
        src = cap / f"HEAD_{view}.png"
        if not src.is_file():
            raise RuntimeError(f"MISSING_OUTPUT:{src}")
        dst = pres / f"HEAD_{view}.png"
        shutil.copy2(src, dst)
        outputs.append(str(dst.relative_to(ROOT)).replace("\\", "/"))

    # Explicitly ensure no body captures exist in this run presentation
    for bad in pres.glob("*body*"):
        bad.unlink()

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>Beta 1.1 Head-Only Audit — P001</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed}}
header{{padding:1rem 1.2rem;border-bottom:1px solid #333}}
.badge{{display:inline-block;margin-right:.35rem;padding:.2rem .5rem;border:1px solid #666;border-radius:999px;font-size:.75rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:.75rem;padding:1rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
</style></head><body>
<header>
<h1>Beta 1.1 Head-Only Isolation + Object Audit</h1>
<p>전신 조립 DENY. 회색 막대 추적: Beta1Hair_SHORT_NEAT_01 (헤어 프록시 큐브). 머리 단독 4장만.</p>
<span class="badge">AUTO_AUDIT PASS</span>
<span class="badge">run {run_id}</span>
<span class="badge">Production NO-GO</span>
<span class="badge">강제 PASS 금지</span>
</header>
<div class="grid">
<figure><img src="HEAD_head_wireframe.png"/><figcaption>와이어프레임</figcaption></figure>
<figure><img src="HEAD_head_front.png"/><figcaption>정면</figcaption></figure>
<figure><img src="HEAD_head_left45.png"/><figcaption>좌 45°</figcaption></figure>
<figure><img src="HEAD_head_right45.png"/><figcaption>우 45°</figcaption></figure>
</div>
</body></html>
"""
    (pres / "BETA1_1_HEAD_ONLY_REVIEW_DESK.html").write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_QP_BETA1_1_HEAD_ONLY_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "BETA1_1_HEAD_ONLY_AUDIT_PASS_AWAITING_HUMAN",
        "priorVerdict": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
        "grayBarTrace": {
            "object": "Beta1Hair_SHORT_NEAT_01",
            "type": "CUBE_SHELL_PROXY",
            "excludedFromHeadOnlyScene": True,
            "hideOnlyInsufficient": True,
        },
        "pre_audit": pre_audit,
        "scene_audit": audit,
        "outputsOnly": outputs,
        "forbiddenOutputs": ["body_*", "NATURAL_BODY", "POLISHED_BODY", "full_body"],
        "fullBodyAssembly": "DENY",
        "forcedPass": "DENY",
        "production": "NO-GO",
        "reviewDesk": str(pres / "BETA1_1_HEAD_ONLY_REVIEW_DESK.html"),
        "next": "HUMAN_CONFIRM_STABLE_FACE_THEN_RESUME_BODY_BIND",
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json", receipt)
    write_json(OUT_ROOT / "V07_QP_BETA1_1_HEAD_ONLY_RECEIPT.json", receipt)
    write_json(
        OUT_ROOT / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": "BETA1_1_HEAD_ONLY_AUDIT_PASS_AWAITING_HUMAN",
            "prior": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
            "updatedAt": now,
            "lastRunId": run_id,
            "reviewDesk": str((pres / "BETA1_1_HEAD_ONLY_REVIEW_DESK.html").relative_to(ROOT)).replace("\\", "/"),
            "fullBodyAssembly": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
            "outputsOnly": list(ONLY_VIEWS),
            "grayBarObject": "Beta1Hair_SHORT_NEAT_01",
            "next": receipt["next"],
        },
    )

    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(pres / "BETA1_1_HEAD_ONLY_REVIEW_DESK.html")], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "runId": run_id,
                "outputs": outputs,
                "grayBarObject": "Beta1Hair_SHORT_NEAT_01",
                "fullBodyAssembly": "DENY",
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
