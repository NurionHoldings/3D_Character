"""NURION Parametric Head Candidate A A-H Full Preflight Confirmation And Evidence Rollup Closure GO."""
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
    "NURION Parametric Head Candidate A A-H Full Preflight Confirmation "
    "And Evidence Rollup Closure GO"
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
FROZEN_INTERIOR_CAMERA_LOCK = (
    CAND
    / "runs"
    / "v1_lsfq_semantic_qa_20260817T053837Z"
    / "camera_lock_manifest.json"
)
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
    out = CAND / "runs" / f"v1_lsfq_qa_{run_id}_ah_confirm"
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
    overlay = out / "overlays"
    cap.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True)
    preflight_path = out / "preflight_gates.json"
    ah_probe_path = out / "ah_preflight_capture_evidence_probe.json"
    log = out / "logs/render.txt"
    log.parent.mkdir(parents=True, exist_ok=True)

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
            f"--meta-json={out / 'render_meta.json'}",
            f"--validation-json={out / 'final_pixel_validation.json'}",
            f"--semantic-validation-json={out / 'semantic_feature_validation.json'}",
            f"--preflight-json={preflight_path}",
            f"--camera-lock-manifest={out / 'camera_lock_manifest.json'}",
            f"--interior-frozen-camera-lock-manifest={FROZEN_INTERIOR_CAMERA_LOCK}",
            f"--closed-baseline-preflight={CLOSED_EYE_MOUTH_CHIN_BASELINE}",
            f"--d-interior-baseline-probe={D_INTERIOR_BASELINE_PROBE}",
            "--resolution=1280",
            "--diagnostic-mode",
            "--preflight-ah-only",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.is_file() else {}
    ah_probe = {}
    if ah_probe_path.is_file():
        ah_probe = json.loads(ah_probe_path.read_text(encoding="utf-8"))
    else:
        ah_probe = preflight.get("ahPreflightCaptureEvidenceRegressionConfirmation") or {}

    ah_pass = bool(ah_probe.get("pass"))
    ah_gates_all_pass = bool(ah_probe.get("ahGatesAllPass"))
    total_regression = int((ah_probe.get("closedAxisRegression") or {}).get("totalRegressionCount", -1))
    capture_evidence = ah_probe.get("requiredNativeCaptureEvidence") or {}
    gate_h = ((preflight.get("gates") or {}).get("H_CAPTURE_LOCK_MANIFEST_CONSISTENCY") or {})
    h_executed = "H_CAPTURE_LOCK_MANIFEST_CONSISTENCY" in (preflight.get("gates") or {})
    h_pass = bool(gate_h.get("pass")) if h_executed else False

    receipt = {
        "schema": "NURION_V07_V1_LSFQ_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "AH_PREFLIGHT_CONFIRMATION_PASS" if ah_pass else "AH_PREFLIGHT_CONFIRMATION_OPEN",
        "priorEvidenceRun": "v1_lsfq_qa_20260820T162836Z_ah",
        "closedBaselines": {
            "eyeMouthChin": "v1_lsfq_semantic_qa_20260819T085754Z",
            "dInterior": "v1_lsfq_semantic_qa_20260820T070720Z_d_interior_revalidation",
        },
        "ahPass": ah_pass,
        "ahGatesAllPass": ah_gates_all_pass,
        "preflightPass": bool(preflight.get("pass")),
        "hExecuted": h_executed,
        "hPass": h_pass,
        "totalRegressionCount": total_regression,
        "requiredNativeCaptureEvidencePresent": bool(capture_evidence.get("pass")),
        "requiredNativeCaptureEvidenceCount": f"{capture_evidence.get('presentCount', 0)}/{capture_evidence.get('requiredCount', 13)}",
        "failClassifications": ah_probe.get("failClassifications") or [],
        "mutationPolicy": ah_probe.get("mutationPolicy") or {
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "eyeMutation": 0,
            "mouthMutation": 0,
            "chinMutation": 0,
        },
        "preflightGates": str(preflight_path.relative_to(ROOT)).replace("\\", "/") if preflight_path.is_file() else None,
        "ahPreflightCaptureEvidenceProbe": str(ah_probe_path.relative_to(ROOT)).replace("\\", "/")
        if ah_probe_path.is_file()
        else None,
        "cameraLockManifest": str((out / "camera_lock_manifest.json").relative_to(ROOT)).replace("\\", "/")
        if (out / "camera_lock_manifest.json").is_file()
        else None,
        "production": "NO-GO",
        "thirteenShot": "13-SHOT_DIAGNOSTIC_GO" if ah_pass else "HOLD",
        "humanQaHtml": "HOLD",
        "nextGo": "13-SHOT_DIAGNOSTIC_GO" if ah_pass else "CLASSIFY_FAIL_THEN_DECIDE_NEXT_GO",
        "policy": {
            "autoFixOnFail": False,
            "jsonPassAloneInsufficient": True,
            "semanticMutation": "DENY",
        },
        "blenderExitCode": proc.returncode,
    }

    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_LSFQ_QA_RECEIPT.json", receipt)

    print(
        json.dumps(
            {
                "command": COMMAND,
                "runId": run_id,
                "ahPass": ah_pass,
                "ahGatesAllPass": ah_gates_all_pass,
                "hExecuted": h_executed,
                "hPass": h_pass,
                "preflightPass": bool(preflight.get("pass")),
                "totalRegressionCount": total_regression,
                "requiredNativeCaptureEvidenceCount": receipt.get("requiredNativeCaptureEvidenceCount"),
                "failClassifications": receipt.get("failClassifications"),
                "preflightGates": receipt.get("preflightGates"),
                "ahProbe": receipt.get("ahPreflightCaptureEvidenceProbe"),
                "blenderExitCode": proc.returncode,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if ah_pass and proc.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
