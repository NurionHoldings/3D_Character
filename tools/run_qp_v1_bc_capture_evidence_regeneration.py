"""NURION Parametric Head Candidate A B-C Required Capture Evidence Regeneration And A-H Evidence Rollup Confirmation GO."""
from __future__ import annotations

import hashlib
import json
import os
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
    "NURION Parametric Head Candidate A B-C Required Capture Evidence Regeneration "
    "And A-H Evidence Rollup Confirmation GO"
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
RENDER_PY = ROOT / "tools/blender_qp_v1_landmark_semantic_feature_qa_render.py"
LABEL = "V1_LSFQ"
SOURCE_RUN = CAND / "runs" / "v1_lsfq_qa_20260820T162836Z_ah"
CLOSED_EYE_MOUTH_CHIN_BASELINE = (
    CAND / "runs" / "v1_lsfq_semantic_qa_20260819T085754Z" / "preflight_gates.json"
)
D_INTERIOR_BASELINE_PROBE = (
    CAND
    / "runs"
    / "v1_lsfq_semantic_qa_20260820T070720Z_d_interior_revalidation"
    / "d_interior_revalidation_probe.json"
)


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt_out = SOURCE_RUN / f"bc_evidence_regeneration_{run_id}"
    receipt_out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(receipt_out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2
    if sha256_file(SKIN) != V1_BASELINE_SKIN_SHA:
        write_json(receipt_out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "BASIS_SHA_MISMATCH"})
        return 2

    source_preflight = SOURCE_RUN / "preflight_gates.json"
    cap = SOURCE_RUN / "captures"
    overlay = SOURCE_RUN / "overlays"
    log = receipt_out / "render.txt"
    bc_probe_path = SOURCE_RUN / "bc_required_capture_evidence_regeneration_probe.json"
    ah_probe_path = SOURCE_RUN / "ah_preflight_capture_evidence_probe.json"

    tmp_dir = ROOT / ".nurion_blender_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TEMP"] = str(tmp_dir)
    env["TMP"] = str(tmp_dir)

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
            f"--overlay-dir={overlay}",
            f"--label={LABEL}",
            f"--meta-json={receipt_out / 'render_meta.json'}",
            f"--validation-json={receipt_out / 'final_pixel_validation.json'}",
            f"--semantic-validation-json={receipt_out / 'semantic_feature_validation.json'}",
            f"--preflight-json={source_preflight}",
            f"--bc-evidence-source-preflight={source_preflight}",
            f"--closed-baseline-preflight={CLOSED_EYE_MOUTH_CHIN_BASELINE}",
            f"--d-interior-baseline-probe={D_INTERIOR_BASELINE_PROBE}",
            "--resolution=1280",
            "--diagnostic-mode",
            "--bc-evidence-only",
            "--bc-evidence-regenerate-rollup",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    bc_probe = json.loads(bc_probe_path.read_text(encoding="utf-8")) if bc_probe_path.is_file() else {}
    ah_probe = json.loads(ah_probe_path.read_text(encoding="utf-8")) if ah_probe_path.is_file() else {}
    bc_pass = bool(bc_probe.get("pass"))
    ah_pass = bool(ah_probe.get("pass"))

    receipt = {
        "schema": "NURION_V07_V1_LSFQ_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "BC_CAPTURE_EVIDENCE_REGENERATION_PASS" if bc_pass else "BC_CAPTURE_EVIDENCE_REGENERATION_OPEN",
        "sourceRun": "v1_lsfq_qa_20260820T162836Z_ah",
        "p0Classification": "B_C_REQUIRED_CAPTURE_EVIDENCE_GENERATION_MISSING",
        "bcRegenerationPass": bc_pass,
        "ahRollupPass": ah_pass,
        "ahGatesAllPass": bool(ah_probe.get("ahGatesAllPass")),
        "totalRegressionCount": int((ah_probe.get("closedAxisRegression") or {}).get("totalRegressionCount", -1)),
        "requiredNativeCaptureEvidence": bc_probe.get("requiredNativeCaptureEvidence"),
        "numericReceiptParity": bc_probe.get("numericReceiptParity"),
        "bcProbe": str(bc_probe_path.relative_to(ROOT)).replace("\\", "/") if bc_probe_path.is_file() else None,
        "ahProbe": str(ah_probe_path.relative_to(ROOT)).replace("\\", "/") if ah_probe_path.is_file() else None,
        "production": "NO-GO",
        "thirteenShot": "HOLD" if not ah_pass else "READY_FOR_DIAGNOSTIC_GO",
        "nextGo": "A_H_FULL_PREFLIGHT_CONFIRMATION_RUN" if bc_pass and not ah_pass else "13-SHOT_DIAGNOSTIC_GO",
        "policy": {
            "eyeMutation": "DENY",
            "mouthChinSemanticMutation": "DENY",
            "dInteriorMutation": "DENY",
            "cameraRetune": "DENY",
            "thresholdMutation": "DENY",
        },
        "blenderExitCode": proc.returncode,
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(receipt_out / "V07_QP_V1_LSFQ_QA_RECEIPT.json", receipt)

    print(json.dumps({k: receipt[k] for k in (
        "command", "runId", "bcRegenerationPass", "ahRollupPass", "ahGatesAllPass",
        "totalRegressionCount", "requiredNativeCaptureEvidence", "nextGo", "blenderExitCode",
    )}, indent=2, ensure_ascii=False))
    return 0 if bc_pass and proc.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
