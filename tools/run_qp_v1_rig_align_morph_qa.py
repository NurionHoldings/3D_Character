"""NURION Parametric Head Candidate A v1 Non-Destructive Oral Eye Rig Local-Space Alignment And Morph QA GO."""
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
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_rig_align import validate_full

COMMAND = (
    "NURION Parametric Head Candidate A v1 Non-Destructive Oral Eye "
    "Rig Local-Space Alignment And Morph QA GO"
)
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
BASIS = CAND / "derived_v1_basis_nd"
SKIN = BASIS / "NURION_DerivedHead_v1_basis_skin.obj"
RIG = BASIS / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
CORR = BASIS / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_v1_rig_aligned_morph_qa_render.py"

REQUIRED_CAPTURES = (
    "mouth_closed_front",
    "mouth_closed_left",
    "mouth_open_front",
    "mouth_open_left",
    "mouth_interior",
    "eye_left_closed",
    "eye_left_open",
    "eye_right_closed",
    "eye_right_open",
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_rig_align_morph_{run_id}"
    out.mkdir(parents=True, exist_ok=True)
    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if sha256_file(SKIN) != V1_BASELINE_SKIN_SHA:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "BASIS_SHA_MISMATCH"})
        return 2

    validation = validate_full(BASIS, CORR)
    align_path = out / "RIG_ALIGNMENT_VALIDATION.json"
    write_json(align_path, validation)

    if not validation["pass"]:
        write_json(
            out / "RECEIPT.json",
            {"verdict": "ALGORITHM_FAIL_RIG_ALIGNMENT", "reasons": validation["reasons"]},
        )
        return 2

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
            f"--alignment-json={align_path}",
            f"--out-dir={cap}",
            "--label=V1_RIG_ALIGNED",
            f"--meta-json={meta_path}",
            "--resolution=1280",
        ],
        capture_output=True,
        text=True,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")
    if proc.returncode != 0 or "Traceback (most recent call last):" in (proc.stderr or ""):
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "log": str(log)})
        return 2

    missing = [f"V1_RIG_ALIGNED_{n}.png" for n in REQUIRED_CAPTURES if not (cap / f"V1_RIG_ALIGNED_{n}.png").is_file()]
    if missing:
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "missing": missing})
        return 2

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED_CAPTURES:
        src = cap / f"V1_RIG_ALIGNED_{name}.png"
        (pres / src.name).write_bytes(src.read_bytes())

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>v1 Rig Aligned Morph QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
h3{{margin:1rem 0 .4rem}}
</style></head><body>
<h1>v1 Rig Local-Space Alignment + Morph QA</h1>
<span class="badge">QA_ARTICULATION_ASSEMBLY_AWAITING_HUMAN</span>
<span class="badge">Basis skin bytes unchanged</span>
<span class="badge">Production NO-GO</span>
<h3>Mouth closed vs open</h3><div class="grid">
<img src="V1_RIG_ALIGNED_mouth_closed_front.png"/><img src="V1_RIG_ALIGNED_mouth_open_front.png"/>
<img src="V1_RIG_ALIGNED_mouth_closed_left.png"/><img src="V1_RIG_ALIGNED_mouth_open_left.png"/>
</div>
<h3>Mouth interior</h3><div class="grid"><img src="V1_RIG_ALIGNED_mouth_interior.png"/></div>
<h3>Eye blink/open L/R</h3><div class="grid">
<img src="V1_RIG_ALIGNED_eye_left_closed.png"/><img src="V1_RIG_ALIGNED_eye_left_open.png"/>
<img src="V1_RIG_ALIGNED_eye_right_closed.png"/><img src="V1_RIG_ALIGNED_eye_right_open.png"/>
</div>
</body></html>
"""
    desk_path = pres / "V1_RIG_ALIGNED_MORPH_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_V1_RIG_ALIGN_MORPH_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "QA_ARTICULATION_ASSEMBLY_AWAITING_HUMAN",
        "priorQaVerdict": "QA_REWORK_REQUIRED_ARTICULATION_ASSEMBLY",
        "basisSkinSha256": V1_BASELINE_SKIN_SHA,
        "validation": validation,
        "nonDestructiveRules": {
            "skinFaceDeletion": "DENY",
            "rigParenting": "JAW_PIVOT_HIERARCHY",
            "correspondenceNewLossAllowance": 0,
        },
        "captures": list(REQUIRED_CAPTURES),
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
    write_json(out / "V07_QP_V1_RIG_ALIGN_MORPH_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_V1_RIG_ALIGN_MORPH_QA_RECEIPT.json", receipt)
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

    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "reviewDesk": receipt["reviewDesk"],
                "floatingOralHelpers": validation["rigAlignment"]["floatingOralHelperCount"],
                "captures": len(REQUIRED_CAPTURES) - len(missing),
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
