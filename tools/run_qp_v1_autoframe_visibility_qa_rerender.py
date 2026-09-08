"""NURION Parametric Head Candidate A World-Space Auto Framing Visibility Smoke And QA Rerender GO."""
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
    "NURION Parametric Head Candidate A World-Space Auto Framing Visibility Smoke "
    "And QA Rerender GO"
)
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
BASIS = CAND / "derived_v1_basis_nd"
SKIN = BASIS / "NURION_DerivedHead_v1_basis_skin.obj"
RIG = BASIS / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
WEIGHT_DIR = CAND / "derived_v1_weights"
NUMERIC_JSON = WEIGHT_DIR / "DEFORM_NUMERIC_VALIDATION.json"
WEIGHT_JSON = WEIGHT_DIR / "JAW_LIP_WEIGHT_MAP.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_v1_autoframe_morph_qa_render.py"
LABEL = "V1_AUTOFRAME"

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
    out = CAND / "runs" / f"v1_autoframe_qa_{run_id}"
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
        write_json(
            out / "RECEIPT.json",
            {"verdict": "ALGORITHM_FAIL", "reason": "NUMERIC_VALIDATION_NOT_PASS"},
        )
        return 2

    cap = out / "captures"
    cap.mkdir(parents=True, exist_ok=True)
    vis_path = out / "visibility_report.json"
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
            f"--visibility-json={vis_path}",
            "--resolution=1280",
        ],
        capture_output=True,
        text=True,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    if not vis_path.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "log": str(log)})
        return 2

    visibility = json.loads(vis_path.read_text(encoding="utf-8"))
    missing = [f"{LABEL}_{n}.png" for n in REQUIRED if not (cap / f"{LABEL}_{n}.png").is_file()]
    visibility_pass = bool(visibility.get("pass")) and proc.returncode == 0 and not missing

    if visibility_pass:
        verdict = "QA_AUTOFRAME_VISIBILITY_AWAITING_HUMAN"
    else:
        verdict = "QA_FAIL_CAMERA_TARGET_AND_VISIBILITY_EVIDENCE_INVALID"

    pres = out / "presentation"
    pres.mkdir(parents=True, exist_ok=True)
    for name in REQUIRED:
        src = cap / f"{LABEL}_{name}.png"
        if src.is_file():
            (pres / src.name).write_bytes(src.read_bytes())

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>v1 AutoFrame Morph QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
h3{{margin:1rem 0 .4rem}}
.fail{{color:#e57373}}
</style></head><body>
<h1>v1 World-Space AutoFrame Morph QA</h1>
<span class="badge">{verdict}</span>
<span class="badge">Weight numeric PASS (unchanged)</span>
<span class="badge">Basis skin unchanged</span>
<span class="badge">Hardcoded camera: REJECTED</span>
<h3>Mouth closed / half / open (auto frame)</h3><div class="grid">
<img src="{LABEL}_mouth_closed_front.png"/><img src="{LABEL}_mouth_half_front.png"/><img src="{LABEL}_mouth_open_front.png"/>
<img src="{LABEL}_mouth_closed_left.png"/><img src="{LABEL}_mouth_half_left.png"/><img src="{LABEL}_mouth_open_left.png"/>
</div>
<h3>Mouth interior</h3><div class="grid"><img src="{LABEL}_mouth_interior.png"/></div>
<h3>Eye L closed / half / open</h3><div class="grid">
<img src="{LABEL}_eye_left_closed.png"/><img src="{LABEL}_eye_left_half.png"/><img src="{LABEL}_eye_left_open.png"/>
</div>
<h3>Eye R closed / half / open</h3><div class="grid">
<img src="{LABEL}_eye_right_closed.png"/><img src="{LABEL}_eye_right_half.png"/><img src="{LABEL}_eye_right_open.png"/>
</div>
<p class="{'fail' if not visibility_pass else ''}">Visibility auto-check: {"PASS" if visibility_pass else "FAIL"} — morph diff bbox + occupancy {visibility.get('thresholds', {}).get('occupancyMin', 0.65)}–{visibility.get('thresholds', {}).get('occupancyMax', 0.85)}</p>
</body></html>
"""
    desk_path = pres / "V1_AUTOFRAME_MORPH_QA_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")

    receipt = {
        "schema": "NURION_V07_V1_AUTOFRAME_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "priorQaVerdict": "QA_FAIL_CAMERA_TARGET_AND_VISIBILITY_EVIDENCE_INVALID",
        "basisSkinSha256": V1_BASELINE_SKIN_SHA,
        "numericValidation": {"pass": True, "preserved": True, "path": str(NUMERIC_JSON.relative_to(ROOT)).replace("\\", "/")},
        "weightMap": str(WEIGHT_JSON.relative_to(ROOT)).replace("\\", "/"),
        "weightModified": False,
        "cameraPolicy": {
            "hardcodedCoordinates": "REJECTED",
            "framing": "WORLD_BOUNDS_AFTER_HEADROOT",
            "occupancyTarget": [0.65, 0.88],
            "smokeBeforeFinal": True,
            "morphDiffBboxRequired": True,
        },
        "visibilityReport": str(vis_path.relative_to(ROOT)).replace("\\", "/"),
        "visibilityAutoPass": visibility_pass,
        "morphDiff": visibility.get("morphDiff", {}),
        "missingCaptures": missing,
        "reviewDesk": str(desk_path.relative_to(ROOT)).replace("\\", "/"),
        "identityFitting": "HOLD",
        "p001Reapply": "HOLD",
        "humanSimilarityEval": "DENY",
        "production": "NO-GO",
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_AUTOFRAME_QA_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_V1_AUTOFRAME_QA_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": verdict,
            "activeBaselineSha256": V1_BASELINE_SKIN_SHA,
            "identityFitting": "HOLD",
            "p001Reapply": "HOLD",
            "humanSimilarityEval": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "reviewDesk": receipt["reviewDesk"],
        },
    )

    if visibility_pass:
        try:
            subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
        except Exception:
            pass

    print(json.dumps({"verdict": verdict, "visibilityPass": visibility_pass, "reviewDesk": receipt["reviewDesk"]}, indent=2))
    return 0 if visibility_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
