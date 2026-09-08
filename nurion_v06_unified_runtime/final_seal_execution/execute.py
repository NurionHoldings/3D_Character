"""v0.6 Limited Final Seal Execution — readonly hash compare; seal or SEAL_DENY."""

from __future__ import annotations

import hashlib
import importlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from nurion_v06_unified_runtime.final_seal_review.parameters import GATE_HASHES_FROZEN

from .parameters import (
    HOLDOUT_FBX_SHA256,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    RC1_PACKAGE,
    RC1_SHA256,
    REVIEW_PARAMETER_HASH_FROZEN,
    REVIEW_VERDICT_REQUIRED,
    SEAL_EXECUTION_PARAMETERS,
    V03_RC1_SHA256,
    V04_RC1_SHA256,
    V05_RC1_SHA256,
    parameter_hash,
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _check(name: str, ok: bool, detail: str = "") -> Dict:
    return {"check": name, "result": "PASS" if ok else "FAIL", "detail": detail}


def _live_gate_hash(gate: str) -> str:
    return importlib.import_module(f"nurion_v06_unified_runtime.{gate}.parameters").parameter_hash()


def execute_limited_final_seal(*, root: Path) -> Dict:
    """Readonly hash compare. On full match → SEALED_WITH_LIMITATIONS; else SEAL_DENY."""
    root = Path(root)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    sealed_date = now[:10]
    checks: List[Dict] = []

    review_path = root / "dist/v0.6/NURION_v0.6_FINAL_SEAL_REVIEW.json"
    review = json.loads(review_path.read_text(encoding="utf-8")) if review_path.is_file() else {}
    checks.append(
        _check(
            "FINAL_SEAL_REVIEW_PRESENT",
            bool(review),
            str(review_path),
        )
    )
    checks.append(
        _check(
            "FINAL_SEAL_REVIEW_VERDICT",
            review.get("reviewVerdict") == REVIEW_VERDICT_REQUIRED,
            str(review.get("reviewVerdict")),
        )
    )
    checks.append(
        _check(
            "FINAL_SEAL_REVIEW_PARAMETER_HASH",
            review.get("parameterHash") == REVIEW_PARAMETER_HASH_FROZEN,
            str(review.get("parameterHash")),
        )
    )
    # Live review module hash must still match frozen review hash
    from nurion_v06_unified_runtime.final_seal_review.parameters import parameter_hash as review_ph

    checks.append(
        _check(
            "FINAL_SEAL_REVIEW_LIVE_HASH",
            review_ph() == REVIEW_PARAMETER_HASH_FROZEN,
            review_ph(),
        )
    )

    for gate, expected in GATE_HASHES_FROZEN.items():
        actual = _live_gate_hash(gate)
        checks.append(_check(f"GATE_HASH_{gate.upper()}", actual == expected, actual))

    rc_path = root / "dist/v0.6/gate8/package" / RC1_PACKAGE
    rc_sha = sha256_file(rc_path) if rc_path.is_file() else ""
    checks.append(_check("RC1_PRESENT", rc_path.is_file()))
    checks.append(_check("RC1_SHA256", rc_sha == RC1_SHA256, rc_sha))
    zip_ok = False
    if rc_path.is_file():
        with zipfile.ZipFile(rc_path) as zf:
            zip_ok = zf.testzip() is None
    checks.append(_check("RC1_ZIP_INTEGRITY", zip_ok))

    freeze = json.loads((root / "dist/v0.6/gate8/package/RC1_CANDIDATE_FREEZE.json").read_text(encoding="utf-8"))
    checks.append(
        _check(
            "RC1_FREEZE_SHA",
            freeze.get("packageSha256") == RC1_SHA256 and freeze.get("FROZEN") is True,
        )
    )

    holdout_zip = root / "dist/v0.6/gate8/inbox/ailawfriend-idle15-biped.zip"
    hz = sha256_file(holdout_zip) if holdout_zip.is_file() else ""
    checks.append(_check("HOLDOUT_ZIP_SHA256", hz == HOLDOUT_ZIP_SHA256, hz))
    fbx_sha = ""
    extract = root / "dist/v0.6/gate8/AILAWFRIEND/_extract"
    if extract.is_dir():
        fbxs = list(extract.rglob("*Idle_15*withSkin.fbx")) or list(extract.rglob("*withSkin.fbx"))
        if fbxs:
            fbx_sha = sha256_file(fbxs[0])
    checks.append(_check("HOLDOUT_FBX_SHA256", fbx_sha == HOLDOUT_FBX_SHA256, fbx_sha))

    baselines = [
        (root / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip", V03_RC1_SHA256, "V03"),
        (root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip", V04_RC1_SHA256, "V04"),
        (root / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip", V05_RC1_SHA256, "V05"),
    ]
    for path, expected, name in baselines:
        actual = sha256_file(path) if path.is_file() else ""
        checks.append(_check(f"BASELINE_{name}", actual == expected, actual))

    g8 = json.loads((root / "dist/v0.6/gate8/V06_GATE8_STATUS.json").read_text(encoding="utf-8"))
    checks.append(
        _check(
            "GATE8_LOCKED_STATUS",
            g8.get("V06_GATE8") == "PASS_WITH_LIMITATIONS"
            and g8.get("parameterHash") == GATE_HASHES_FROZEN["gate8"]
            and g8.get("LOCKED") is True
            and g8.get("production") == "NO-GO"
            and g8.get("autoSeal") == "DENY",
        )
    )

    # Policy locks — no repair/repack path in this executor
    checks.append(_check("IN_PLACE_REPAIR_DENY", SEAL_EXECUTION_PARAMETERS["inPlaceRepair"] == "DENY"))
    checks.append(_check("RC1_REPACK_DENY", SEAL_EXECUTION_PARAMETERS["rc1Repack"] == "DENY"))
    checks.append(_check("PRODUCTION_NO_GO", SEAL_EXECUTION_PARAMETERS["production"] == "NO-GO"))

    hard = [c["check"] for c in checks if c["result"] == "FAIL"]
    passed = len(hard) == 0
    verdict = "SEALED_WITH_LIMITATIONS" if passed else "SEAL_DENY"
    seal_execution = "PASS" if passed else "FAIL"

    limitations = list(SEAL_EXECUTION_PARAMETERS["inheritedLimitationsFromV05"])
    package_rel = f"dist/v0.6/gate8/package/{RC1_PACKAGE}"

    receipt = {
        "schema": "NURION_V06_FINAL_SEAL_RECEIPT",
        "product": "NURION Unified Character Animation Runtime",
        "version": "v0.6",
        "package": RC1_PACKAGE,
        "packagePath": package_rel,
        "packageSha256": RC1_SHA256 if passed else rc_sha,
        "packageSha256Length": 64,
        "packageSha256Verified": passed and rc_sha == RC1_SHA256,
        "rc1Repack": "DENY",
        "zipHashChange": "DENY",
        "inPlaceRepair": "DENY",
        "FINAL_SEAL_REVIEW": REVIEW_VERDICT_REQUIRED,
        "finalSealReviewParameterHash": REVIEW_PARAMETER_HASH_FROZEN,
        "sealExecution": seal_execution,
        "verdict": verdict,
        "sealed": passed,
        "SEALED": passed,
        "sealedAt": sealed_date if passed else None,
        "createdAt": now,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "autoSeal": "DENY",
        "parameterChange": 0,
        "manualCorrection": 0,
        "parameterTuning": 0,
        "sourceZipFbxActionMutation": 0,
        "gateParameterHashes": dict(GATE_HASHES_FROZEN),
        "reviewParameterHash": REVIEW_PARAMETER_HASH_FROZEN,
        "sealExecutionParameterHash": parameter_hash(),
        "v05Dependency": {
            "package": "NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip",
            "sha256": V05_RC1_SHA256,
            "role": "SEALED_READONLY_BODY_MOTION",
            "unchanged": True,
        },
        "v04Dependency": {
            "package": "NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip",
            "sha256": V04_RC1_SHA256,
            "role": "SEALED_READONLY_FACE_EYE_LIPSYNC",
            "unchanged": True,
        },
        "v03Dependency": {
            "package": "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip",
            "sha256": V03_RC1_SHA256,
            "role": "SEALED_READONLY_EYE_STACK",
            "unchanged": True,
        },
        "freshHoldoutAsset": {
            "role": "FRESH_HOLDOUT",
            "asset": HOLDOUT_LABEL,
            "meshyName": "AI_법률_파트너",
            "animation": "Idle_15",
            "verdict": "PASS_WITH_LIMITATIONS",
            "eligibility": "ELIGIBLE",
            "zip": "ailawfriend-idle15-biped.zip",
            "zipSha256": HOLDOUT_ZIP_SHA256,
            "fbxSha256": HOLDOUT_FBX_SHA256,
            "siblingZipMix": "DENY",
            "manualCorrection": 0,
            "parameterTuning": 0,
            "lipsyncMode": "REST_FALLBACK",
        },
        "limitations": limitations,
        "limitationAutoClear": "DENY",
        "immutableBaselines": {
            "v0.3_rc1": V03_RC1_SHA256,
            "v0.4_rc1": V04_RC1_SHA256,
            "v0.5_rc1": V05_RC1_SHA256,
            "v0.6_rc1": RC1_SHA256,
        },
        "sealScope": [
            "Unified Character Animation Runtime contract (Gate1)",
            "Auto asset diagnosis FULL/LIMITED/INELIGIBLE (Gate2)",
            "Bone role mapping with L/R majority vote (Gate3)",
            "Body+Face+Eye bind with REST_FALLBACK lipsync (Gate4)",
            "Motion presets in NURION_UnifiedRuntime_* Actions (Gate5)",
            "Ordered Blender workflow with export precheck (Gate6)",
            "BLEND/FBX/GLB output regression and determinism (Gate7)",
            "Fresh holdout AILAWFRIEND Idle_15 + RC.1 candidate (Gate8)",
            "Limited final seal after APPROVED_FOR_LIMITED_FINAL_SEAL",
        ],
        "checks": checks,
        "hardFails": hard,
        "mismatchPolicy": "SEAL_DENY_NO_IN_PLACE_REPAIR_NO_REPACK",
        "READ_ONLY": True if passed else False,
        "baselineRole": "OFFICIAL_READONLY_BASELINE" if passed else None,
        "next": "PRODUCTION_READINESS_SEPARATE_TRACK" if passed else "REMEDIATE_THEN_REREVIEW",
    }

    baseline_lock = {
        "schema": "NURION_V06_FINAL_BASELINE_LOCK",
        "product": "NURION Unified Character Animation Runtime",
        "version": "v0.6",
        "status": verdict if passed else "SEAL_DENY",
        "sealed": passed,
        "SEALED": passed,
        "READ_ONLY": True if passed else False,
        "baselineRole": "OFFICIAL_READONLY_BASELINE" if passed else "NOT_SEALED",
        "sealedAt": sealed_date if passed else None,
        "package": RC1_PACKAGE,
        "packagePath": package_rel,
        "packageSha256": RC1_SHA256,
        "rc1Repack": "DENY",
        "zipHashChange": "DENY",
        "parameterChange": "DENY",
        "manualCorrection": "DENY",
        "parameterTuning": "DENY",
        "inPlaceRepair": "DENY",
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "productionRequires": [
            "SEPARATE_PRODUCTION_READINESS_TRACK",
            "EXPLICIT_PRODUCTION_APPROVAL",
        ],
        "fullUnrestricted": "HOLD",
        "GATE1": "LOCKED_PASS",
        "GATE2": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE3": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE4": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE5": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE6": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE7": "LOCKED_PASS_WITH_LIMITATIONS",
        "GATE8": "LOCKED_PASS_WITH_LIMITATIONS",
        "FINAL_SEAL_REVIEW": REVIEW_VERDICT_REQUIRED,
        "SEAL_EXECUTION": seal_execution,
        "gateParameterHashes": dict(GATE_HASHES_FROZEN),
        "finalSealReviewParameterHash": REVIEW_PARAMETER_HASH_FROZEN,
        "sealExecutionParameterHash": parameter_hash(),
        "v05DependencySha256": V05_RC1_SHA256,
        "v04DependencySha256": V04_RC1_SHA256,
        "v03DependencySha256": V03_RC1_SHA256,
        "freshHoldoutAsset": {
            "role": "FRESH_HOLDOUT",
            "asset": HOLDOUT_LABEL,
            "animation": "Idle_15",
            "zipSha256": HOLDOUT_ZIP_SHA256,
            "fbxSha256": HOLDOUT_FBX_SHA256,
            "eligibility": "ELIGIBLE",
        },
        "limitations": limitations,
        "limitationAutoClear": "DENY",
        "createdAt": now,
        "next": "PRODUCTION_READINESS_SEPARATE_TRACK" if passed else "REMEDIATE_THEN_REREVIEW",
    }

    validation_status = {
        "schema": "NURION_V06_VALIDATION_STATUS",
        "product": "NURION Unified Character Animation Runtime",
        "version": "v0.6",
        "SEALED": passed,
        "sealed": passed,
        "READ_ONLY": True if passed else False,
        "verdict": verdict,
        "sealExecution": seal_execution,
        "finalSealReview": REVIEW_VERDICT_REQUIRED,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "rc1Package": RC1_PACKAGE,
        "rc1Sha256": RC1_SHA256,
        "holdout": HOLDOUT_LABEL,
        "limitations": limitations,
        "hardFails": hard,
        "updatedAt": now,
        "artifacts": {
            "sealReceipt": "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json",
            "baselineLock": "dist/v0.6/V06_FINAL_BASELINE_LOCK.json",
            "finalSealReview": "dist/v0.6/NURION_v0.6_FINAL_SEAL_REVIEW.json",
            "rc1": package_rel,
        },
        "next": baseline_lock["next"],
    }

    return {
        "passed": passed,
        "verdict": verdict,
        "sealExecution": seal_execution,
        "receipt": receipt,
        "baselineLock": baseline_lock,
        "validationStatus": validation_status,
        "parameterHash": parameter_hash(),
        "hardFails": hard,
        "checks": checks,
    }
