"""NURION HEAD — 13-Shot Occupancy Failure Forensic Isolation (mouth_closed_front)."""
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
FAIL_RUN_SEMANTIC = CAND / "runs/v1_lsfq_qa_20260822T045013Z_13shot_diag/semantic_feature_validation.json"
FORENSIC_SHOT = "mouth_closed_front"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_lsfq_qa_{run_id}_13shot_occ_forensic"
    out.mkdir(parents=True, exist_ok=True)
    cap = out / "captures"
    overlay = out / "overlays"
    cap.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True)
    receipt_path = out / "thirteen_shot_occupancy_forensic_receipt.json"
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
            "--thirteen-shot-occupancy-forensic-only",
            f"--forensic-shot={FORENSIC_SHOT}",
            f"--occupancy-forensic-json={receipt_path}",
            f"--fail-run-semantic-json={FAIL_RUN_SEMANTIC}",
            f"--ah-preflight-source={AH_PREFLIGHT_SOURCE}",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}
    summary = {
        "schema": "NURION_V07_V1_LSFQ_THIRTEEN_SHOT_OCCUPANCY_FORENSIC_RUN_SUMMARY",
        "runId": run_id,
        "forensicShot": FORENSIC_SHOT,
        "baselineRunId": "20260821T151012Z",
        "failRunId": "20260822T045013Z",
        "blenderExitCode": proc.returncode,
        "isolationBucket": (receipt.get("isolation") or {}).get("classificationBucket"),
        "captureAbortReason": (receipt.get("captureEvidence") or {}).get("abortReason"),
        "cameraParityPass": (receipt.get("captureEvidence") or {}).get("cameraParity", {}).get("pass"),
        "firstZeroStage": (receipt.get("captureEvidence") or {}).get("firstZeroStage"),
        "receipt": str(receipt_path.relative_to(ROOT)).replace("\\", "/"),
        "officialState": {
            "manifestRepair": "PASS / CLOSED",
            "thirteenShotDiagnostic": "FAIL / OPEN",
            "occupancyForensic": "ACTIVE",
        },
    }
    write_json(out / "FORENSIC_RUN_SUMMARY.json", summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if proc.returncode == 0 and receipt else 2


if __name__ == "__main__":
    raise SystemExit(main())
