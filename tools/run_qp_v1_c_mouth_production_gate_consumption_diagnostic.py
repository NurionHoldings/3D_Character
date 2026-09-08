"""NURION Parametric Head Candidate A C-Mouth Production Gate Consumption And Closed-Evidence Binding Diagnostic GO."""
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
    "NURION Parametric Head Candidate A C-Mouth Production Gate Consumption "
    "And Closed-Evidence Binding Diagnostic GO"
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
CLOSED_EYE_MOUTH_CHIN_BASELINE = (
    CAND / "runs" / "v1_lsfq_semantic_qa_20260819T085754Z" / "preflight_gates.json"
)
REFERENCE_CONFIRM_RUN = CAND / "runs" / "v1_lsfq_qa_20260821T000011Z_ah_confirm"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_lsfq_qa_{run_id}_c_consumption_diag"
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
    c_probe_path = out / "c_mouth_production_gate_consumption_probe.json"
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
            f"--closed-baseline-preflight={CLOSED_EYE_MOUTH_CHIN_BASELINE}",
            f"--c-consumption-baseline-preflight={CLOSED_EYE_MOUTH_CHIN_BASELINE}",
            "--resolution=1280",
            "--diagnostic-mode",
            "--c-mouth-consumption-diagnostic-only",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    c_probe = json.loads(c_probe_path.read_text(encoding="utf-8")) if c_probe_path.is_file() else {}
    diagnostic_pass = bool(c_probe.get("diagnosticPass"))
    c_front = c_probe.get("C_FRONT") or {}
    c_left = c_probe.get("C_LEFT") or {}

    receipt = {
        "schema": "NURION_V07_V1_LSFQ_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "C_CONSUMPTION_BINDING_DIAGNOSTIC_PASS" if diagnostic_pass else "C_CONSUMPTION_BINDING_DIAGNOSTIC_OPEN",
        "referenceConfirmRun": "v1_lsfq_qa_20260821T000011Z_ah_confirm",
        "diagnosticPass": diagnostic_pass,
        "cFailureClass": c_probe.get("cFailureClass"),
        "C_FRONT": {
            "primaryClassification": c_front.get("primaryClassification"),
            "classifications": c_front.get("classifications"),
            "feasibleShots": (c_front.get("productionGateConsumption") or {}).get("feasibleShots"),
            "closedEvidenceBound": (c_front.get("closedEvidenceBinding") or {}).get("mouthVisibilityPass"),
            "framingReason": (c_front.get("framingGate") or {}).get("reason"),
        },
        "C_LEFT": {
            "primaryClassification": c_left.get("primaryClassification"),
            "classifications": c_left.get("classifications"),
            "feasibleShots": (c_left.get("productionGateConsumption") or {}).get("feasibleShots"),
            "closedNativePass": (c_left.get("closedEvidenceBinding") or {}).get("closedNativeSemanticEvidencePass"),
            "halfOpenNativeFail": (c_left.get("feasibleShotsAggregation") or {}).get("halfOpenNativeFail"),
        },
        "successCriteria": c_probe.get("successCriteria"),
        "recommendedRepair": c_probe.get("recommendedRepair"),
        "nextGo": c_probe.get("nextGo"),
        "mutationPolicy": c_probe.get("mutationPolicy"),
        "cProbe": str(c_probe_path.relative_to(ROOT)).replace("\\", "/") if c_probe_path.is_file() else None,
        "production": "NO-GO",
        "thirteenShot": "HOLD",
        "ahPass": False,
        "policy": {
            "goal": "PROVENANCE_RESOLUTION_NOT_GATE_PASS",
            "semanticMutation": "DENY",
            "cameraRetune": "DENY",
            "thresholdMutation": "DENY",
            "fidMutation": "DENY",
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
                k: receipt[k]
                for k in (
                    "command",
                    "runId",
                    "diagnosticPass",
                    "cFailureClass",
                    "C_FRONT",
                    "C_LEFT",
                    "recommendedRepair",
                    "nextGo",
                    "blenderExitCode",
                )
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if diagnostic_pass and proc.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
