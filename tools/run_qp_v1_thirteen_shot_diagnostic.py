"""NURION Parametric Head Candidate A Full 13-Shot Diagnostic And Native Capture Evidence Human-Readability Confirmation GO."""
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
    "NURION Parametric Head Candidate A Full 13-Shot Diagnostic "
    "And Native Capture Evidence Human-Readability Confirmation GO"
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
AH_PREFLIGHT_SOURCE = (
    CAND / "runs" / "v1_lsfq_qa_20260821T151012Z_ah_confirm" / "preflight_gates.json"
)
FROZEN_BASELINE_RUN_ID = "20260821T151012Z"
CONSUMER_PATH_MUTATION_ID = "HEAD_13SHOT_MANIFEST_CONSUMPTION_PATH_REPAIR"
MANIFEST_LOCK_KEYS = (
    "mouth_front",
    "mouth_left",
    "mouth_interior",
    "eye_left",
    "eye_right",
)

REQUIRED_SHOTS = (
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

HUMAN_READABLE_FEATURE_SHOTS = {
    "lip": ("mouth_closed_front", "mouth_half_front", "mouth_open_front"),
    "lip_corner_l": ("mouth_closed_front", "mouth_half_front", "mouth_open_front"),
    "lip_corner_r": ("mouth_closed_front", "mouth_half_front", "mouth_open_front"),
    "chin": ("mouth_closed_front", "mouth_closed_left", "mouth_half_front", "mouth_half_left"),
    "upper_teeth": ("mouth_half_front", "mouth_open_front", "mouth_half_left", "mouth_open_left", "mouth_interior"),
    "lower_teeth": ("mouth_half_front", "mouth_open_front", "mouth_half_left", "mouth_open_left", "mouth_interior"),
    "tongue": ("mouth_interior",),
    "oralOpening": ("mouth_interior",),
    "eyeball": ("eye_left_closed", "eye_left_half", "eye_left_open", "eye_right_closed", "eye_right_half", "eye_right_open"),
    "eyelid_upper": ("eye_left_closed", "eye_left_half", "eye_left_open", "eye_right_closed", "eye_right_half", "eye_right_open"),
    "eyelid_lower": ("eye_left_closed", "eye_left_half", "eye_left_open", "eye_right_closed", "eye_right_half", "eye_right_open"),
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _shot_beauty_path(captures_dir: Path, label: str, shot: str) -> Path:
    return captures_dir / f"{label}_{shot}.png"


def _feature_pass_in_shot(shot_semantic: dict, feature: str) -> bool:
    if feature == "oralOpening":
        oral = shot_semantic.get("oralOpening") or {}
        if oral.get("pass") is not None:
            return bool(oral.get("pass"))
        return bool(shot_semantic.get("pass"))
    vis = shot_semantic.get("featureVisibility") or {}
    row = vis.get(feature) or {}
    if row.get("pass") is not None:
        return bool(row.get("pass"))
    counts = shot_semantic.get("featurePixelCounts") or {}
    return int(counts.get(feature, 0)) > 0


def _human_readability_confirmation(captures_dir: Path, label: str, semantic_report: dict) -> dict:
    shot_semantics = semantic_report.get("shots") or {}
    per_feature: dict[str, dict] = {}
    failures: list[str] = []
    for feature, candidate_shots in HUMAN_READABLE_FEATURE_SHOTS.items():
        matched = None
        for shot in candidate_shots:
            sem = shot_semantics.get(shot) or {}
            if _feature_pass_in_shot(sem, feature):
                matched = shot
                break
        per_feature[feature] = {
            "pass": matched is not None,
            "confirmedInShot": matched,
            "candidateShots": list(candidate_shots),
        }
        if matched is None:
            failures.append(f"HUMAN_READABLE_MISSING_{feature}")
    return {
        "pass": not failures,
        "perFeature": per_feature,
        "failures": failures,
    }


def _required_shot_capture_evidence(captures_dir: Path, label: str) -> dict:
    present: list[str] = []
    missing: list[str] = []
    for shot in REQUIRED_SHOTS:
        path = _shot_beauty_path(captures_dir, label, shot)
        if path.is_file() and path.stat().st_size > 0:
            present.append(shot)
        else:
            missing.append(shot)
    return {
        "requiredCount": len(REQUIRED_SHOTS),
        "presentCount": len(present),
        "present": present,
        "missing": missing,
        "pass": len(missing) == 0,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_lsfq_qa_{run_id}_13shot_diag"
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
    if not AH_PREFLIGHT_SOURCE.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "AH_PREFLIGHT_SOURCE_MISSING"})
        return 2

    frozen_manifest_path = AH_PREFLIGHT_SOURCE.with_name("camera_lock_manifest.json")
    frozen_manifest = json.loads(frozen_manifest_path.read_text(encoding="utf-8")) if frozen_manifest_path.is_file() else {}
    frozen_manifest_hash = frozen_manifest.get("solverReceiptHash")
    frozen_locks = frozen_manifest.get("locks") or {}
    frozen_lock_count = len(frozen_locks)

    cap = out / "captures"
    overlay = out / "overlays"
    cap.mkdir(parents=True, exist_ok=True)
    overlay.mkdir(parents=True, exist_ok=True)
    semantic_path = out / "semantic_feature_validation.json"
    validation_path = out / "final_pixel_validation.json"
    meta_path = out / "render_meta.json"
    probe_path = out / "thirteen_shot_human_readability_probe.json"
    preflight_path = out / "preflight_gates.json"
    mutation_path = out / "consumer_path_mutation_receipt.json"
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
            f"--meta-json={meta_path}",
            f"--validation-json={validation_path}",
            f"--semantic-validation-json={semantic_path}",
            f"--preflight-json={preflight_path}",
            "--resolution=1280",
            "--diagnostic-mode",
            "--thirteen-shot-diagnostic-only",
            f"--ah-preflight-source={AH_PREFLIGHT_SOURCE}",
        ],
        capture_output=True,
        text=True,
        env=env,
    )
    log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

    semantic = json.loads(semantic_path.read_text(encoding="utf-8")) if semantic_path.is_file() else {}
    validation = json.loads(validation_path.read_text(encoding="utf-8")) if validation_path.is_file() else {}
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.is_file() else {}
    preflight = json.loads(preflight_path.read_text(encoding="utf-8")) if preflight_path.is_file() else {}
    manifest_assert = (
        semantic.get("thirteenShotManifestConsumptionAssert")
        or meta.get("thirteenShotManifestConsumptionAssert")
        or preflight.get("gates", {}).get("13_SHOT_MANIFEST_CONSUMPTION_ASSERT")
        or {}
    )
    ah_probe = {}
    ah_probe_path = AH_PREFLIGHT_SOURCE.with_name("ah_preflight_capture_evidence_probe.json")
    if ah_probe_path.is_file():
        ah_probe = json.loads(ah_probe_path.read_text(encoding="utf-8"))

    shots_pass = int(semantic.get("shotsPassed", 0))
    shots_required = len(REQUIRED_SHOTS)
    semantic_pass = bool(semantic.get("pass"))
    mask_pass = bool(validation.get("pass"))
    capture_evidence = _required_shot_capture_evidence(cap, LABEL)
    human_readability = _human_readability_confirmation(cap, LABEL, semantic)
    total_regression = int((ah_probe.get("closedAxisRegression") or {}).get("totalRegressionCount", 0))
    mutation_policy = ah_probe.get("mutationPolicy") or meta.get("mutationPolicy") or {}
    manifest_consumed = int(manifest_assert.get("manifestConsumed", 0))
    manifest_consumed_required = int(manifest_assert.get("manifestConsumedRequired", len(MANIFEST_LOCK_KEYS)))
    manifest_assert_pass = bool(manifest_assert.get("pass"))
    manifest_hash_preserved = (
        frozen_manifest_hash is not None
        and manifest_assert.get("manifestHash") == frozen_manifest_hash
    )
    shots_completed = int(semantic.get("shotsCompleted", meta.get("shotsCompleted", 0)) or 0)

    mutation_receipt = {
        "schema": "NURION_V07_V1_LSFQ_CONSUMER_PATH_MUTATION_RECEIPT",
        "mutationId": CONSUMER_PATH_MUTATION_ID,
        "mutationClass": "CONSUMER_PATH_ONLY",
        "baselineRunId": FROZEN_BASELINE_RUN_ID,
        "baselineManifestHash": frozen_manifest_hash,
        "baselineLockCount": frozen_lock_count,
        "appliedAt": now,
        "manifestConsumptionAssert": manifest_assert,
        "manifestHashPreserved": manifest_hash_preserved,
        "policy": {
            "ahPreflightRerun": "DENY",
            "cameraSolverRerun": "DENY",
            "thresholdChange": "DENY",
            "morphChange": "DENY",
            "semanticContractChange": "DENY",
        },
    }
    write_json(mutation_path, mutation_receipt)

    diagnostic_pass = bool(
        manifest_assert_pass
        and manifest_consumed == manifest_consumed_required
        and manifest_hash_preserved
        and semantic_pass
        and mask_pass
        and capture_evidence.get("pass")
        and human_readability.get("pass")
        and shots_pass >= shots_required
        and shots_completed >= shots_required
        and total_regression == 0
    )

    probe = {
        "schema": "NURION_V07_V1_LSFQ_THIRTEEN_SHOT_HUMAN_READABILITY_PROBE",
        "gate": "FULL_13_SHOT_DIAGNOSTIC_AND_HUMAN_READABILITY_CONFIRMATION",
        "diagnosticPass": diagnostic_pass,
        "pass": diagnostic_pass,
        "shotsPassed": shots_pass,
        "shotsRequired": shots_required,
        "semanticPass": semantic_pass,
        "maskPass": mask_pass,
        "requiredShotCaptureEvidence": capture_evidence,
        "humanReadability": human_readability,
        "totalRegressionCount": total_regression,
        "mutationPolicy": mutation_policy,
        "manifestConsumptionAssert": manifest_assert,
        "manifestConsumed": f"{manifest_consumed}/{manifest_consumed_required}",
        "manifestHashPreserved": manifest_hash_preserved,
        "shotsCompleted": shots_completed,
        "consumerPathMutation": str(mutation_path.relative_to(ROOT)).replace("\\", "/"),
        "ahPreflightSource": str(AH_PREFLIGHT_SOURCE.relative_to(ROOT)).replace("\\", "/"),
        "nextGo": "HUMAN_QA_HTML_PUBLICATION" if diagnostic_pass else "CLASSIFY_13_SHOT_FAIL_THEN_DECIDE",
        "policy": {
            "humanQaHtml": "ALLOW" if diagnostic_pass else "HOLD",
            "production": "NO-GO",
        },
    }
    write_json(probe_path, probe)

    receipt = {
        "schema": "NURION_V07_V1_LSFQ_QA_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": "THIRTEEN_SHOT_DIAGNOSTIC_PASS" if diagnostic_pass else "THIRTEEN_SHOT_DIAGNOSTIC_OPEN",
        "diagnosticPass": diagnostic_pass,
        "ahPreflightSource": "v1_lsfq_qa_20260821T151012Z_ah_confirm",
        "shotsPassed": f"{shots_pass}/{shots_required}",
        "semanticPass": semantic_pass,
        "maskPass": mask_pass,
        "requiredShotCaptureEvidence": capture_evidence,
        "humanReadability": human_readability,
        "totalRegressionCount": total_regression,
        "mutationPolicy": mutation_policy,
        "manifestConsumptionAssert": manifest_assert,
        "manifestConsumed": f"{manifest_consumed}/{manifest_consumed_required}",
        "manifestHashPreserved": manifest_hash_preserved,
        "shotsCompleted": shots_completed,
        "consumerPathMutation": str(mutation_path.relative_to(ROOT)).replace("\\", "/"),
        "probe": str(probe_path.relative_to(ROOT)).replace("\\", "/"),
        "production": "NO-GO",
        "humanQaHtml": "ALLOW" if diagnostic_pass else "HOLD",
        "nextGo": probe.get("nextGo"),
        "blenderExitCode": proc.returncode,
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_LSFQ_QA_RECEIPT.json", receipt)

    print(json.dumps({k: receipt[k] for k in (
        "command", "runId", "diagnosticPass", "shotsPassed", "shotsCompleted",
        "manifestConsumed", "manifestHashPreserved", "semanticPass",
        "requiredShotCaptureEvidence", "humanReadability", "nextGo", "blenderExitCode",
    )}, indent=2, ensure_ascii=False))
    return 0 if diagnostic_pass and proc.returncode == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
