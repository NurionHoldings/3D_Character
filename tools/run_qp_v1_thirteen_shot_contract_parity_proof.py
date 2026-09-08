"""NURION HEAD — 13-Shot Native Semantic Evidence Contract Parity Proof (mouth_closed_front)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
BASIS = CAND / "derived_v1_basis_nd"
SKIN = BASIS / "NURION_DerivedHead_v1_basis_skin.obj"
RIG = BASIS / "NURION_DerivedHead_v1_basis_rig_helpers.obj"
WEIGHT_JSON = CAND / "derived_v1_weights/JAW_LIP_WEIGHT_MAP.json"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_v1_landmark_semantic_feature_qa_render.py"
LABEL = "V1_LSFQ"
AH_PREFLIGHT_SOURCE = CAND / "runs/v1_lsfq_qa_20260821T151012Z_ah_confirm/preflight_gates.json"
FORENSIC_SHOT = "mouth_closed_front"
MUTATION_ID = "HEAD_13SHOT_NATIVE_SEMANTIC_EVIDENCE_CONTRACT_PARITY_REPAIR"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_lsfq_qa_{run_id}_13shot_contract_parity_proof"
    out.mkdir(parents=True, exist_ok=True)
    cap = out / "captures"
    overlay = out / "overlays"
    cap.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True)
    proof_path = out / "thirteen_shot_contract_parity_proof_receipt.json"
    mutation_path = out / "consumer_evaluator_contract_mutation_receipt.json"
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
            f"--semantic-validation-json={out / 'semantic_feature_validation.json'}",
            f"--validation-json={out / 'final_pixel_validation.json'}",
            f"--meta-json={out / 'render_meta.json'}",
            "--resolution=1280",
            "--thirteen-shot-contract-parity-proof-only",
            f"--forensic-shot={FORENSIC_SHOT}",
            f"--contract-parity-proof-json={proof_path}",
            f"--ah-preflight-source={AH_PREFLIGHT_SOURCE}",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    proof = json.loads(proof_path.read_text(encoding="utf-8")) if proof_path.is_file() else {}
    mutation = {
        "schema": "NURION_V07_V1_LSFQ_CONSUMER_EVALUATOR_CONTRACT_MUTATION_RECEIPT",
        "mutationId": MUTATION_ID,
        "mutationClass": "CONSUMER_EVALUATOR_CONTRACT_ONLY",
        "baselineRunId": "20260821T151012Z",
        "forensicShot": FORENSIC_SHOT,
        "rootCause": "EVALUATOR_CONTRACT_PARITY",
        "proofReceipt": proof,
        "proofPass": bool(proof.get("pass")),
        "policy": {
            "thresholdChange": "DENY",
            "cameraRetune": "DENY",
            "morphChange": "DENY",
            "semanticContractChange": "DENY",
            "ahPreflightRerun": "DENY",
        },
    }
    write_json(mutation_path, mutation)

    summary = {
        "schema": "NURION_V07_V1_LSFQ_THIRTEEN_SHOT_CONTRACT_PARITY_PROOF_SUMMARY",
        "runId": run_id,
        "forensicShot": FORENSIC_SHOT,
        "proofPass": bool(proof.get("pass")),
        "blenderExitCode": proc.returncode,
        "proofChecks": proof.get("proofChecks"),
        "failures": proof.get("failures"),
        "mutationId": MUTATION_ID,
        "receipt": str(proof_path.relative_to(ROOT)).replace("\\", "/"),
        "officialState": {
            "manifestRepair": "PASS / CLOSED",
            "occupancyForensic": "PASS / CLOSED",
            "rootCause": "EVALUATOR_CONTRACT_PARITY CONFIRMED",
            "contractParityProof": "PASS" if proof.get("pass") else "OPEN",
        },
    }
    write_json(out / "PROOF_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if proof.get("pass") and proc.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
