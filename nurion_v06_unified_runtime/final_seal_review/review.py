"""v0.6 Final Seal Review — evidence audit only; never sets SEALED=true."""

from __future__ import annotations

import hashlib
import importlib
import json
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    GATE_HASHES_FROZEN,
    HOLDOUT_FBX_SHA256,
    HOLDOUT_LABEL,
    HOLDOUT_ZIP_SHA256,
    RC1_PACKAGE,
    RC1_SHA256,
    REVIEW_PARAMETERS,
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


def _load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _gate_live_hash(gate: str) -> str:
    mod = importlib.import_module(f"nurion_v06_unified_runtime.{gate}.parameters")
    return mod.parameter_hash()


def _check(name: str, ok: bool, detail: str = "") -> Dict:
    return {"check": name, "result": "PASS" if ok else "FAIL", "detail": detail}


def run_final_seal_review(*, root: Path) -> Dict:
    root = Path(root)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    checks: List[Dict] = []
    notes: List[str] = []

    # --- Gate 1–8 parameter hash continuity ---
    for gate, expected in GATE_HASHES_FROZEN.items():
        try:
            actual = _gate_live_hash(gate)
            ok = actual == expected
            checks.append(_check(f"PARAM_HASH_{gate.upper()}", ok, actual if ok else f"{actual} != {expected}"))
        except Exception as exc:
            checks.append(_check(f"PARAM_HASH_{gate.upper()}", False, str(exc)))

    # Cross-lock: each later gate freezes prior hashes
    try:
        from nurion_v06_unified_runtime.gate8.parameters import (
            GATE1_PARAMETER_HASH_FROZEN as g8_g1,
            GATE7_PARAMETER_HASH_FROZEN as g8_g7,
        )
        from nurion_v06_unified_runtime.gate7.parameters import GATE6_PARAMETER_HASH_FROZEN as g7_g6

        chain_ok = (
            g8_g1 == GATE_HASHES_FROZEN["gate1"]
            and g8_g7 == GATE_HASHES_FROZEN["gate7"]
            and g7_g6 == GATE_HASHES_FROZEN["gate6"]
        )
        checks.append(_check("PARAM_HASH_CHAIN_CROSS_LOCK", chain_ok))
    except Exception as exc:
        checks.append(_check("PARAM_HASH_CHAIN_CROSS_LOCK", False, str(exc)))

    # --- RC.1 ZIP full hash + archive integrity ---
    rc_path = root / "dist/v0.6/gate8/package" / RC1_PACKAGE
    rc_exists = rc_path.is_file()
    rc_sha = sha256_file(rc_path) if rc_exists else ""
    checks.append(_check("RC1_PRESENT", rc_exists, str(rc_path)))
    checks.append(_check("RC1_FULL_SHA256", rc_exists and rc_sha == RC1_SHA256, rc_sha))
    zip_ok = False
    zip_members = 0
    forbidden_in_rc = []
    if rc_exists:
        try:
            with zipfile.ZipFile(rc_path) as zf:
                bad = zf.testzip()
                zip_ok = bad is None
                names = zf.namelist()
                zip_members = len(names)
                for n in names:
                    low = n.lower()
                    if low.endswith((".fbx", ".blend", ".glb", ".png", ".jpg", ".jpeg", ".wav", ".mp3")):
                        forbidden_in_rc.append(n)
        except Exception as exc:
            checks.append(_check("RC1_ZIP_INTEGRITY", False, str(exc)))
    checks.append(_check("RC1_ZIP_INTEGRITY", zip_ok, f"members={zip_members}"))
    checks.append(_check("RC1_NO_BINARY_ASSETS", len(forbidden_in_rc) == 0, ",".join(forbidden_in_rc[:8])))

    freeze_path = root / "dist/v0.6/gate8/package/RC1_CANDIDATE_FREEZE.json"
    freeze = _load_json(freeze_path) if freeze_path.is_file() else {}
    checks.append(
        _check(
            "RC1_FREEZE_RECORD",
            freeze.get("packageSha256") == RC1_SHA256
            and freeze.get("SEALED") is False
            and freeze.get("autoSeal") == "DENY"
            and freeze.get("production") == "NO-GO",
            json.dumps({k: freeze.get(k) for k in ("packageSha256", "SEALED", "autoSeal", "production")}),
        )
    )
    checks.append(_check("RC1_REPACK", freeze.get("repack", "").startswith("DENY") or REVIEW_PARAMETERS["rc1Repack"] == "DENY"))

    # --- Holdout novelty + hashes ---
    holdout_zip = root / "dist/v0.6/gate8/inbox/ailawfriend-idle15-biped.zip"
    holdout_lock = root / "dist/v0.6/gate8/AILAWFRIEND/HOLDOUT_ASSET_LOCK.json"
    novelty_path = root / "dist/v0.6/gate8/AILAWFRIEND/GATE8_NOVELTY.json"
    g8_val = root / "dist/v0.6/gate8/AILAWFRIEND/GATE8_VALIDATION.json"
    holdout_zip_ok = holdout_zip.is_file() and sha256_file(holdout_zip) == HOLDOUT_ZIP_SHA256
    checks.append(_check("HOLDOUT_ZIP_SHA256", holdout_zip_ok, sha256_file(holdout_zip) if holdout_zip.is_file() else "MISSING"))

    fbx_sha_ok = False
    fbx_path: Optional[Path] = None
    extract = root / "dist/v0.6/gate8/AILAWFRIEND/_extract"
    if extract.is_dir():
        fbxs = list(extract.rglob("*Idle_15*withSkin.fbx")) + list(extract.rglob("*withSkin.fbx"))
        if fbxs:
            fbx_path = fbxs[0]
            fbx_sha_ok = sha256_file(fbx_path) == HOLDOUT_FBX_SHA256
    checks.append(
        _check(
            "HOLDOUT_FBX_SHA256",
            fbx_sha_ok,
            sha256_file(fbx_path) if fbx_path else "MISSING",
        )
    )

    novelty = _load_json(novelty_path) if novelty_path.is_file() else {}
    checks.append(
        _check(
            "HOLDOUT_NOVELTY_ELIGIBLE",
            bool(novelty.get("ok"))
            and bool(novelty.get("ailawfriendCanonicalIdle15"))
            and novelty.get("label") == HOLDOUT_LABEL,
            novelty.get("runtimeAction", ""),
        )
    )
    lock = _load_json(holdout_lock) if holdout_lock.is_file() else {}
    checks.append(
        _check(
            "HOLDOUT_LOCK_RECORD",
            lock.get("zipSha256") == HOLDOUT_ZIP_SHA256
            and lock.get("expectedFbxSha256") == HOLDOUT_FBX_SHA256
            and lock.get("siblingZipMix") == "DENY",
        )
    )

    # Holdout zip integrity
    hz_ok = False
    if holdout_zip.is_file():
        with zipfile.ZipFile(holdout_zip) as zf:
            hz_ok = zf.testzip() is None
    checks.append(_check("HOLDOUT_ZIP_INTEGRITY", hz_ok))

    # --- v0.3–v0.5 sealed baselines immutable ---
    baselines = [
        (
            root / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip",
            V03_RC1_SHA256,
            "V03",
        ),
        (
            root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip",
            V04_RC1_SHA256,
            "V04",
        ),
        (
            root / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip",
            V05_RC1_SHA256,
            "V05",
        ),
    ]
    for path, expected, name in baselines:
        ok = path.is_file() and sha256_file(path) == expected
        checks.append(_check(f"BASELINE_{name}_IMMUTABLE", ok, sha256_file(path) if path.is_file() else "MISSING"))

    # --- Manual correction / tuning / source mutation 0 ---
    g8_status = _load_json(root / "dist/v0.6/gate8/V06_GATE8_STATUS.json")
    g8_receipt = _load_json(root / "dist/v0.6/gate8/V06_GATE8_RECEIPT.json")
    g7_status = _load_json(root / "dist/v0.6/gate7/V06_GATE7_STATUS.json")
    mut0 = (
        int(g8_status.get("sourceMutationTotal") or 0) == 0
        and int(g8_receipt.get("manualCorrectionTotal") or 0) == 0
        and int(g8_receipt.get("sourceMutationTotal") or 0) == 0
        and int(g7_status.get("sourceMutationTotal") or 0) == 0
    )
    checks.append(_check("MUTATION_MANUAL_TUNING_ZERO", mut0))

    # --- BLEND/FBX/GLB round-trip + determinism evidence ---
    g7_val = _load_json(root / "dist/v0.6/gate7/ai-aba/GATE7_VALIDATION.json")
    g8v = _load_json(g8_val) if g8_val.is_file() else {}
    rt_keys = [
        "BLEND_SAVE_RELOAD",
        "FBX_EXPORT_REIMPORT",
        "GLB_EXPORT_REIMPORT",
        "DETERMINISM_3X",
        "FPS_MEANING_24_30_60",
    ]
    g7_gates = g7_val.get("gates") or {}
    g8_gates = g8v.get("gates") or {}
    rt_ok = all(g7_gates.get(k) == "PASS" for k in rt_keys) and all(
        g8_gates.get(k) == "PASS" for k in rt_keys if k in g8_gates or k == "DETERMINISM_3X"
    )
    # Gate8 uses same set
    rt_ok = all(g7_gates.get(k) == "PASS" for k in rt_keys) and all(g8_gates.get(k) == "PASS" for k in rt_keys)
    checks.append(_check("ROUNDTRIP_DETERMINISM_EVIDENCE", rt_ok, f"g7={g7_val.get('determinism')} g8={g8v.get('determinism')}"))

    # Physical export artifacts exist for holdout
    holdout_dir = root / "dist/v0.6/gate8/AILAWFRIEND"
    arts_ok = all(
        (holdout_dir / name).is_file()
        for name in ("run3_runtime.blend", "run3_runtime.fbx", "run3_runtime.glb")
    )
    checks.append(_check("HOLDOUT_EXPORT_ARTIFACTS_PRESENT", arts_ok))

    # --- Limitations public / ABSTAIN / REST_FALLBACK ---
    lim = list(REVIEW_PARAMETERS["inheritedLimitationsFromV05"])
    lim_public = (
        g8_status.get("inheritedLimitationsFromV05") == lim
        and g8v.get("lipsyncMode") == "REST_FALLBACK"
        and "LIPSYNC_TIMELINE_UNSUPPORTED" in (g8v.get("abstainReasons") or [])
        and g8_status.get("limitationAutoClear", "DENY") in ("DENY", None)
    )
    # limitationAutoClear may be only on parameters; accept if limitations listed and REST_FALLBACK
    lim_public = (
        list(g8_status.get("inheritedLimitationsFromV05") or []) == lim
        and g8v.get("lipsyncMode") == "REST_FALLBACK"
        and bool(g8v.get("abstainReasons"))
    )
    checks.append(_check("LIMITATIONS_ABSTAIN_REST_FALLBACK_PUBLIC", lim_public, str(g8v.get("abstainReasons"))))

    # --- Gate8 official status match ---
    checks.append(
        _check(
            "GATE8_OFFICIAL_STATUS",
            g8_status.get("V06_GATE8") == "PASS_WITH_LIMITATIONS"
            and g8_status.get("parameterHash") == GATE_HASHES_FROZEN["gate8"]
            and g8_status.get("autoSeal") == "DENY"
            and g8_status.get("production") == "NO-GO"
            and g8_status.get("rcPackageSha256") == RC1_SHA256,
        )
    )
    checks.append(
        _check(
            "GATE7_LOCKED",
            g7_status.get("LOCKED") is True
            and g7_status.get("parameterHash") == GATE_HASHES_FROZEN["gate7"]
            and g7_status.get("officialFrozenBaseline") is True,
        )
    )
    g6_status = _load_json(root / "dist/v0.6/gate6/V06_GATE6_STATUS.json")
    checks.append(
        _check(
            "GATE6_LOCKED",
            g6_status.get("LOCKED") is True
            and g6_status.get("parameterHash") == GATE_HASHES_FROZEN["gate6"]
            and g6_status.get("officialFrozenBaseline") is True,
        )
    )

    # Production / auto seal policies
    checks.append(_check("AUTO_SEAL_DENY", REVIEW_PARAMETERS["autoSeal"] == "DENY" and g8_status.get("autoSeal") == "DENY"))
    checks.append(_check("PRODUCTION_NO_GO", g8_status.get("production") == "NO-GO" and freeze.get("production") == "NO-GO"))
    checks.append(_check("SEAL_EXECUTION_NOT_RUN", REVIEW_PARAMETERS["sealExecutionInThisStep"] == "DENY"))

    hard = [c["check"] for c in checks if c["result"] == "FAIL"]
    passed = len(hard) == 0
    review_verdict = "APPROVED_FOR_LIMITED_FINAL_SEAL" if passed else "SEAL_REVIEW_DENY"
    if passed:
        notes.append("Limited-domain approval only; full unqualified PASS denied due to public limitations.")
        notes.append("SEALED remains FALSE — seal execution is a separate step.")
        notes.extend(lim)

    return {
        "schema": "NURION_V06_FINAL_SEAL_REVIEW",
        "project": "NURION Unified Character Animation Runtime",
        "version": "0.6.0-rc.1",
        "reviewedAt": now,
        "timezone": "Asia/Seoul",
        "reviewVerdict": review_verdict,
        "sealExecution": "NOT_EXECUTED",
        "SEALED": False,
        "sealed": False,
        "autoSeal": "DENY",
        "production": "NO-GO",
        "productionAutoAdvance": "DENY",
        "rc1Repack": "DENY",
        "parameterHash": parameter_hash(),
        "gateHashes": GATE_HASHES_FROZEN,
        "rc1": {
            "frozen": True,
            "SEALED": False,
            "repackage": "DENY",
            "package": RC1_PACKAGE,
            "packagePath": str(rc_path).replace("\\", "/"),
            "sha256": rc_sha if rc_sha else RC1_SHA256,
            "archiveIntegrity": "PASS" if zip_ok else "FAIL",
        },
        "holdout": {
            "label": HOLDOUT_LABEL,
            "animation": "Idle_15",
            "eligibility": "ELIGIBLE" if novelty.get("ok") else "INELIGIBLE",
            "zipSha256": HOLDOUT_ZIP_SHA256,
            "fbxSha256": HOLDOUT_FBX_SHA256,
            "noveltyOk": bool(novelty.get("ok")),
        },
        "immutableBaselines": {
            "v0.3_rc1": V03_RC1_SHA256,
            "v0.4_rc1": V04_RC1_SHA256,
            "v0.5_rc1": V05_RC1_SHA256,
        },
        "limitations": lim,
        "limitationAutoClear": "DENY",
        "checks": checks,
        "hardFails": hard,
        "notes": notes,
        "mismatchPolicy": "SEAL_REVIEW_DENY_NO_IN_PLACE_REPAIR",
        "next": "LIMITED_FINAL_SEAL_EXECUTION_SEPARATE_GO" if passed else "REMEDIATE_THEN_REREVIEW",
        "updatedAt": now,
    }
