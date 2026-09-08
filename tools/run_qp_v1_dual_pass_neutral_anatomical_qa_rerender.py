"""NURION Parametric Head Candidate A Dual-Pass Neutral Anatomical Feature Visibility QA Rerender GO."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import EXP_G5, sha256_file
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_nd_reconstruct import V1_BASELINE_SKIN_SHA

COMMAND = (
    "NURION Parametric Head Candidate A Dual-Pass Neutral Anatomical "
    "Feature Visibility QA Rerender GO"
)
VERDICT_PASS = "QA_DUAL_PASS_NEUTRAL_ANATOMICAL_AWAITING_HUMAN"
VERDICT_FAIL = "QA_REWORK_HUMAN_VISIBILITY_MATERIAL_LIGHTING_AND_ANATOMICAL_FEATURES_NOT_EVALUABLE"
VERDICT_ABORT = "SAFE_ABORT_HUMAN_VISIBILITY_VALIDATION"

ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
BASIS = CAND / "derived_v1_basis_nd"
SKIN = BASIS / "NURION_DerivedHead_v1_basis_skin.obj"
RIG = BASIS / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
WEIGHT_DIR = CAND / "derived_v1_weights"
NUMERIC_JSON = WEIGHT_DIR / "DEFORM_NUMERIC_VALIDATION.json"
WEIGHT_JSON = WEIGHT_DIR / "JAW_LIP_WEIGHT_MAP.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_v1_dual_pass_neutral_anatomical_qa_render.py"
LABEL = "V1_DQA"

REQUIRED = (
    "mouth_closed_front",
    "mouth_closed_left",
    "mouth_half_front",
    "mouth_half_left",
    "mouth_open_front",
    "mouth_open_left",
    "mouth_interior",
    "eye_left_closed",
    "eye_left_half",
    "eye_left_open",
    "eye_right_closed",
    "eye_right_half",
    "eye_right_open",
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_dqa_neutral_visibility_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if sha256_file(SKIN) != V1_BASELINE_SKIN_SHA:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "BASIS_SHA_MISMATCH"})
        return 2
    if not NUMERIC_JSON.is_file() or not WEIGHT_JSON.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "WEIGHT_BUNDLE_MISSING"})
        return 2
    numeric = json.loads(NUMERIC_JSON.read_text(encoding="utf-8"))
    if not numeric.get("pass"):
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "NUMERIC_VALIDATION_NOT_PASS"})
        return 2

    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    mask_val_path = out / "final_pixel_validation.json"
    human_val_path = out / "human_visibility_validation.json"
    meta_path = out / "render_meta.json"
    log = out / "logs/render.txt"
    log.parent.mkdir(parents=True, exist_ok=True)

    proc = subprocess.run(
        [
            str(BLENDER),
            "--background",
            "--python",
            str(RENDER_PY),
            "--",
            f"--skin-obj={SKIN}",
            f"--rig-obj={RIG}",
            f"--weight-json={WEIGHT_JSON}",
            f"--out-dir={cap}",
            f"--label={LABEL}",
            f"--meta-json={meta_path}",
            f"--validation-json={mask_val_path}",
            f"--human-validation-json={human_val_path}",
            "--resolution=1280",
        ],
        capture_output=True,
        text=True,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    if not mask_val_path.is_file() or not human_val_path.is_file():
        write_json(out / "V07_QP_V1_DQA_QA_RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "log": str(log)})
        return 2

    mask_validation = json.loads(mask_val_path.read_text(encoding="utf-8"))
    human_validation = json.loads(human_val_path.read_text(encoding="utf-8"))
    missing = [f"{LABEL}_{n}.png" for n in REQUIRED if not (cap / f"{LABEL}_{n}.png").is_file()]
    mask_pass = bool(mask_validation.get("pass"))
    if not mask_pass and mask_validation.get("shots"):
        mask_pass = all(s.get("maskPass") for s in mask_validation["shots"].values())
    human_pass = bool(human_validation.get("pass"))
    safe_abort = bool(human_validation.get("safeAbort")) or proc.returncode == 4
    passed = mask_pass and human_pass and proc.returncode == 0 and not missing and not safe_abort

    if passed:
        verdict = VERDICT_PASS
    elif safe_abort:
        verdict = VERDICT_ABORT
    else:
        verdict = VERDICT_FAIL

    receipt = {
        "schema": "NURION_V07_V1_DQA_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "priorQaVerdict": "QA_REWORK_HUMAN_VISIBILITY_MATERIAL_LIGHTING_AND_ANATOMICAL_FEATURES_NOT_EVALUABLE",
        "basisSkinSha256": V1_BASELINE_SKIN_SHA,
        "numericValidation": {
            "pass": True,
            "preserved": True,
            "path": str(NUMERIC_JSON.relative_to(ROOT)).replace("\\", "/"),
        },
        "weightMap": str(WEIGHT_JSON.relative_to(ROOT)).replace("\\", "/"),
        "weightModified": False,
        "renderPolicy": {
            "dualPass": True,
            "maskPass": "FINAL_1280_OBJECT_ID_MASK",
            "humanQaPass": "NEUTRAL_FEATURE_VISIBILITY",
            "regionShells": "REJECTED",
            "occupancyWidthHeight": [0.65, 0.85],
            "cameraLockPerSeries": True,
            "lighting": "KEY_FILL_RIM_NEUTRAL",
            "materials": "NEUTRAL_QA_FEATURE_COLORS",
            "htmlOnFail": "DENY",
        },
        "finalPixelValidation": str(mask_val_path.relative_to(ROOT)).replace("\\", "/"),
        "maskPass": mask_pass,
        "humanVisibilityValidation": str(human_val_path.relative_to(ROOT)).replace("\\", "/"),
        "humanPass": human_pass,
        "validationPass": passed,
        "safeAbort": safe_abort,
        "morphDiff": mask_validation.get("morphDiff", {}),
        "missingCaptures": missing,
        "identityFitting": "HOLD",
        "p001Reapply": "HOLD",
        "humanSimilarityEval": "DENY",
        "humanQa": "AWAITING" if passed else "DENY",
        "production": "NO-GO",
    }

    if passed:
        pres = out / "presentation"
        pres.mkdir(parents=True, exist_ok=True)
        for name in REQUIRED:
            src = cap / f"{LABEL}_{name}.png"
            if src.is_file():
                (pres / src.name).write_bytes(src.read_bytes())
        desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>v1 Dual-Pass Neutral Anatomical QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#f0f1f3;color:#1a1d21;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #888;border-radius:999px;font-size:.78rem;background:#fff}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#e8e8ea;border-radius:.35rem;border:1px solid #ccc}}
h3{{margin:1rem 0 .4rem}}
.legend{{font-size:.85rem;color:#444;margin:.5rem 0 1rem}}
</style></head><body>
<h1>v1 Dual-Pass Neutral Anatomical Feature QA</h1>
<span class="badge">{verdict}</span>
<span class="badge">MASK_PASS preserved</span>
<span class="badge">HUMAN_QA_PASS neutral lighting</span>
<p class="legend">밝은 중립 QA 재질 · feature-ID 색 구분 · key/fill/rim 조명 · 동일 카메라 lock</p>
<h3>Mouth closed / half / open (front)</h3><div class="grid">
<img src="{LABEL}_mouth_closed_front.png"/><img src="{LABEL}_mouth_half_front.png"/><img src="{LABEL}_mouth_open_front.png"/>
</div>
<h3>Mouth closed / half / open (left)</h3><div class="grid">
<img src="{LABEL}_mouth_closed_left.png"/><img src="{LABEL}_mouth_half_left.png"/><img src="{LABEL}_mouth_open_left.png"/>
</div>
<h3>Mouth interior</h3><div class="grid"><img src="{LABEL}_mouth_interior.png"/></div>
<h3>Eye L closed / half / open</h3><div class="grid">
<img src="{LABEL}_eye_left_closed.png"/><img src="{LABEL}_eye_left_half.png"/><img src="{LABEL}_eye_left_open.png"/>
</div>
<h3>Eye R closed / half / open</h3><div class="grid">
<img src="{LABEL}_eye_right_closed.png"/><img src="{LABEL}_eye_right_half.png"/><img src="{LABEL}_eye_right_open.png"/>
</div>
</body></html>
"""
        desk_path = pres / "V1_DQA_MORPH_QA_DESK.html"
        desk_path.write_text(desk, encoding="utf-8")
        receipt["reviewDesk"] = str(desk_path.relative_to(ROOT)).replace("\\", "/")
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
        except Exception:
            pass
    else:
        receipt["reviewDesk"] = None

    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_DQA_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_V1_DQA_QA_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": verdict,
            "activeBaselineSha256": V1_BASELINE_SKIN_SHA,
            "maskPass": mask_pass,
            "humanPass": human_pass,
            "identityFitting": "HOLD",
            "p001Reapply": "HOLD",
            "humanSimilarityEval": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "reviewDesk": receipt.get("reviewDesk"),
        },
    )

    print(
        json.dumps(
            {
                "verdict": verdict,
                "maskPass": mask_pass,
                "humanPass": human_pass,
                "validationPass": passed,
                "safeAbort": safe_abort,
                "reviewDesk": receipt.get("reviewDesk"),
            },
            indent=2,
        )
    )
    return 0 if passed else 4 if safe_abort else 2


if __name__ == "__main__":
    raise SystemExit(main())
