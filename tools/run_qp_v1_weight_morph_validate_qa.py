"""NURION Parametric Head Candidate A Jaw Lip Weight Map Eyelid Morph Numeric Validation And QA Camera Repair GO."""
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
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_deform_validate import (
    validate_deformation,
    write_weight_bundle,
)
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_nd_reconstruct import V1_BASELINE_SKIN_SHA

COMMAND = (
    "NURION Parametric Head Candidate A Jaw Lip Weight Map Eyelid Morph "
    "Numeric Validation And QA Camera Repair GO"
)
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
BASIS = CAND / "derived_v1_basis_nd"
SKIN = BASIS / "NURION_DerivedHead_v1_basis_skin.obj"
RIG = BASIS / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
WEIGHT_DIR = CAND / "derived_v1_weights"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_v1_weighted_morph_qa_render.py"

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
    out = CAND / "runs" / f"v1_weight_validate_qa_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if sha256_file(SKIN) != V1_BASELINE_SKIN_SHA:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "BASIS_SHA_MISMATCH"})
        return 2

    deform = validate_deformation(SKIN, RIG)
    write_weight_bundle(WEIGHT_DIR, deform)

    if not deform.pass_all:
        write_json(
            out / "RECEIPT.json",
            {
                "verdict": "ALGORITHM_FAIL_DEFORM_NUMERIC_VALIDATION",
                "reasons": deform.reasons,
                "byAngle": deform.by_angle,
            },
        )
        write_json(CAND / "V07_QP_V1_DEFORM_NUMERIC_VALIDATION_RECEIPT.json", {
            "verdict": "ALGORITHM_FAIL_DEFORM_NUMERIC_VALIDATION",
            "reasons": deform.reasons,
            "completedAt": now,
        })
        return 2

    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    weight_json = WEIGHT_DIR / "JAW_LIP_WEIGHT_MAP.json"
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
            f"--weight-json={weight_json}",
            f"--out-dir={cap}",
            "--label=V1_WEIGHTED",
            f"--meta-json={meta_path}",
            "--resolution=1280",
        ],
        capture_output=True,
        text=True,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "log": str(log)})
        return 2

    missing = [f"V1_WEIGHTED_{n}.png" for n in REQUIRED if not (cap / f"V1_WEIGHTED_{n}.png").is_file()]
    if missing:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "missing": missing, "log": str(log)})
        return 2

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED:
        src = cap / f"V1_WEIGHTED_{name}.png"
        (pres / src.name).write_bytes(src.read_bytes())

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>v1 Weighted Morph QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
h3{{margin:1rem 0 .4rem}}
</style></head><body>
<h1>v1 Weight Map + Morph QA (Camera Repair)</h1>
<span class="badge">QA_DEFORMATION_CAMERA_AWAITING_HUMAN</span>
<span class="badge">Numeric validation PASS</span>
<span class="badge">Basis skin unchanged</span>
<h3>Mouth closed / half / open</h3><div class="grid">
<img src="V1_WEIGHTED_mouth_closed_front.png"/><img src="V1_WEIGHTED_mouth_half_front.png"/><img src="V1_WEIGHTED_mouth_open_front.png"/>
<img src="V1_WEIGHTED_mouth_closed_left.png"/><img src="V1_WEIGHTED_mouth_half_left.png"/><img src="V1_WEIGHTED_mouth_open_left.png"/>
</div>
<h3>Mouth interior</h3><div class="grid"><img src="V1_WEIGHTED_mouth_interior.png"/></div>
<h3>Eye L closed / half / open</h3><div class="grid">
<img src="V1_WEIGHTED_eye_left_closed.png"/><img src="V1_WEIGHTED_eye_left_half.png"/><img src="V1_WEIGHTED_eye_left_open.png"/>
</div>
<h3>Eye R closed / half / open</h3><div class="grid">
<img src="V1_WEIGHTED_eye_right_closed.png"/><img src="V1_WEIGHTED_eye_right_half.png"/><img src="V1_WEIGHTED_eye_right_open.png"/>
</div>
</body></html>
"""
    desk_path = pres / "V1_WEIGHTED_MORPH_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_V1_WEIGHT_MORPH_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "QA_DEFORMATION_CAMERA_AWAITING_HUMAN",
        "priorQaVerdict": "REWORK_REQUIRED_DEFORMATION_WEIGHTS_AND_QA_CAMERA",
        "basisSkinSha256": V1_BASELINE_SKIN_SHA,
        "numericValidation": {"pass": True, "byAngle": deform.by_angle},
        "weightMap": str(weight_json.relative_to(ROOT)).replace("\\", "/"),
        "deformPolicy": {
            "rigidLowerLipOnly": "REJECTED",
            "falloffWeightMap": True,
            "jawAnglesDeg": [0, 8, 16, 24],
            "correspondenceNewLossAllowance": 0,
        },
        "reviewDesk": str(desk_path.relative_to(ROOT)).replace("\\", "/"),
        "identityFitting": "HOLD",
        "p001Reapply": "HOLD",
        "humanSimilarityEval": "DENY",
        "production": "NO-GO",
        "missing": missing,
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_WEIGHT_MORPH_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_V1_WEIGHT_MORPH_QA_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": receipt["verdict"],
            "activeBaselineSha256": V1_BASELINE_SKIN_SHA,
            "identityFitting": "HOLD",
            "p001Reapply": "HOLD",
            "humanSimilarityEval": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "reviewDesk": receipt["reviewDesk"],
        },
    )

    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(json.dumps({"verdict": receipt["verdict"], "reviewDesk": receipt["reviewDesk"], "numericPass": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
