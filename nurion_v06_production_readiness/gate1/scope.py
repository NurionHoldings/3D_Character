"""Gate 1 — verify sealed baseline and emit deployment scope / asset matrix."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .parameters import (
    GATE1_PARAMETERS,
    V03_RC1_SHA256,
    V04_RC1_SHA256,
    V05_RC1_SHA256,
    V06_RC1_SHA256,
    V06_RC1_PACKAGE,
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


def run_pr_gate1(*, root: Path) -> Dict:
    root = Path(root)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    checks: List[Dict] = []

    lock_path = root / "dist/v0.6/V06_FINAL_BASELINE_LOCK.json"
    receipt_path = root / "dist/v0.6/V06_FINAL_SEAL_RECEIPT.json"
    rc_path = root / "dist/v0.6/gate8/package" / V06_RC1_PACKAGE

    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.is_file() else {}
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.is_file() else {}

    checks.append(
        _check(
            "V06_OFFICIAL_READONLY_BASELINE",
            lock.get("SEALED") is True
            and lock.get("baselineRole") == "OFFICIAL_READONLY_BASELINE"
            and lock.get("status") == "SEALED_WITH_LIMITATIONS"
            and lock.get("READ_ONLY") is True,
            lock.get("baselineRole", ""),
        )
    )
    checks.append(
        _check(
            "V06_RC1_SHA256",
            rc_path.is_file() and sha256_file(rc_path) == V06_RC1_SHA256,
            sha256_file(rc_path) if rc_path.is_file() else "MISSING",
        )
    )
    checks.append(
        _check(
            "V06_SEAL_RECEIPT_MATCH",
            receipt.get("SEALED") is True
            and receipt.get("verdict") == "SEALED_WITH_LIMITATIONS"
            and receipt.get("packageSha256") == V06_RC1_SHA256
            and receipt.get("production") == "NO-GO",
        )
    )
    checks.append(_check("RC1_REPACK_DENY", lock.get("rc1Repack") == "DENY" and receipt.get("rc1Repack") == "DENY"))
    checks.append(_check("IN_PLACE_REPAIR_DENY", lock.get("inPlaceRepair") == "DENY"))
    checks.append(
        _check(
            "LIMITATIONS_PUBLIC",
            list(lock.get("limitations") or []) == list(GATE1_PARAMETERS["publicLimitations"]),
        )
    )
    checks.append(_check("LIMITATION_AUTO_CLEAR_DENY", GATE1_PARAMETERS["limitationAutoClear"] == "DENY"))
    checks.append(_check("PRODUCTION_NO_GO", GATE1_PARAMETERS["production"] == "NO-GO" and lock.get("production") == "NO-GO"))
    checks.append(
        _check(
            "IMMEDIATE_PRODUCTION_GO_DENY",
            GATE1_PARAMETERS["immediateProductionGoReview"] == "DENY",
        )
    )

    baselines = [
        (root / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip", V03_RC1_SHA256, "V03"),
        (root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip", V04_RC1_SHA256, "V04"),
        (root / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip", V05_RC1_SHA256, "V05"),
    ]
    for path, expected, name in baselines:
        actual = sha256_file(path) if path.is_file() else ""
        checks.append(_check(f"DEPENDENCY_{name}_IMMUTABLE", actual == expected, actual))

    # Scope completeness
    scope = GATE1_PARAMETERS["deploymentScope"]
    checks.append(_check("SCOPE_CHANNEL_LIMITED", scope.get("channel") == "LIMITED_INTERNAL_OPERATOR"))
    checks.append(_check("SCOPE_EXPORT_FORMATS", set(scope.get("exportFormats") or []) == {"BLEND", "FBX", "GLB"}))
    checks.append(_check("SCOPE_FPS", scope.get("fps") == [24, 30, 60]))
    checks.append(_check("SCOPE_PARTIAL_EXPORT_DENY", scope.get("partialExportPublish") == "DENY"))

    assets = GATE1_PARAMETERS["supportedCharacterEvidence"]
    labels = {a["label"] for a in assets}
    checks.append(
        _check(
            "ASSET_MATRIX_CORE_LABELS",
            {"ai-aba.bow", "ai-baeby", "hyerie", "ai-aba.15", "AILAWFRIEND", "empty-control"} <= labels,
        )
    )
    checks.append(
        _check(
            "ASSET_AILAWFRIEND_HOLDOUT",
            any(
                a["label"] == "AILAWFRIEND" and a.get("role") == "V06_FRESH_HOLDOUT" and a.get("class") == "LIMITED"
                for a in assets
            ),
        )
    )
    checks.append(
        _check(
            "UNSUPPORTED_POLICIES_DECLARED",
            GATE1_PARAMETERS["unsupportedOrAbstain"].get("lipsyncUnsupported") == "REST_FALLBACK"
            and GATE1_PARAMETERS["unsupportedOrAbstain"].get("missingMotionPreset") == "ABSTAIN"
            and GATE1_PARAMETERS["unsupportedOrAbstain"].get("ineligibleAsset") == "ABSTAIN",
        )
    )

    hard = [c["check"] for c in checks if c["result"] == "FAIL"]
    verdict = "PASS" if not hard else "FAIL"

    deployment_scope = {
        "schema": "NURION_V06_PR_DEPLOYMENT_SCOPE",
        "track": "Production Readiness",
        "gate": "1",
        "sealedBaseline": GATE1_PARAMETERS["sealedBaseline"],
        "deploymentScope": GATE1_PARAMETERS["deploymentScope"],
        "supportedAssetClasses": GATE1_PARAMETERS["supportedAssetClasses"],
        "unsupportedOrAbstain": GATE1_PARAMETERS["unsupportedOrAbstain"],
        "publicLimitations": GATE1_PARAMETERS["publicLimitations"],
        "outOfScopeForImmediateGo": GATE1_PARAMETERS["outOfScopeForImmediateGo"],
        "production": "NO-GO",
        "updatedAt": now,
    }
    supported_assets = {
        "schema": "NURION_V06_PR_SUPPORTED_ASSETS",
        "track": "Production Readiness",
        "gate": "1",
        "submissionFormRequired": GATE1_PARAMETERS["submissionFormRequired"],
        "characters": GATE1_PARAMETERS["supportedCharacterEvidence"],
        "notes": [
            "LIMITED domain only — limitations and REST_FALLBACK/ABSTAIN must remain operator-visible.",
            "Immediate Production GO is out of scope until later PR gates complete.",
        ],
        "production": "NO-GO",
        "updatedAt": now,
    }

    return {
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "checks": checks,
        "hardFails": hard,
        "deploymentScope": deployment_scope,
        "supportedAssets": supported_assets,
        "next": "PR_GATE2_FAILURE_ABSTAIN_RECOVERY_POLICY",
        "updatedAt": now,
    }
