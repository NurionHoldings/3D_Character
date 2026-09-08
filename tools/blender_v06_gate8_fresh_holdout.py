"""
v0.6 Gate 8 — Fresh Holdout and RC candidate harness.

Usage:
  blender --background --python tools/blender_v06_gate8_fresh_holdout.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.6" / "gate8"
HOLDOUT_ZIP = OUT / "inbox" / "ailawfriend-idle15-biped.zip"
GATE7_HASH = "32e9fe4fef0f2d534d9a623f8dbfdedc0d4b9c60a5b5fe1a104c9620c4a07833"
GATE6_HASH = "3207531397c6372bbba4e38aebb3024fdc1e85f1792526a5f3115e36bbdf746e"
V03 = ROOT / "dist/v0.3/universal_eye/gate7a/package/NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
V04 = ROOT / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
V05 = ROOT / "dist/v0.5/gate9/package/NURION_Body_Motion_Retarget_v0.5.0-rc.1.zip"
V03_SHA = "9c3a69b723ed8ac43fc67757ba2168c316104fff1f1e3d5fa84c6960b0679238"
V04_SHA = "10483d6ba847a28f5ce64f7179394ddc338e08871414ea72b73c44ceb4bd6bc5"
V05_SHA = "1580f5871ba7737e34b0dfe99ef974aa7d3ed6b6656599aa51d08b8de5384722"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _baseline_ok() -> bool:
    for path, expected in [(V03, V03_SHA), (V04, V04_SHA), (V05, V05_SHA)]:
        if not path.is_file() or _sha(path) != expected:
            return False
    return True


def main() -> int:
    sys.path.insert(0, str(ROOT))
    from nurion_v06_unified_runtime.gate6.parameters import parameter_hash as g6_hash
    from nurion_v06_unified_runtime.gate7.parameters import parameter_hash as g7_hash
    from nurion_v06_unified_runtime.gate8.holdout import run_gate8_holdout
    from nurion_v06_unified_runtime.gate8.parameters import GATE8_PARAMETERS, parameter_hash
    from nurion_v06_unified_runtime.gate8.rc_candidate import build_rc_candidate

    if g6_hash() != GATE6_HASH or g7_hash() != GATE7_HASH:
        raise RuntimeError("Gate6/7 hash drift — DENY")
    if not HOLDOUT_ZIP.is_file():
        raise FileNotFoundError(HOLDOUT_ZIP)

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    label = "AILAWFRIEND"
    asset_dir = OUT / label
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Novelty / asset lock before run
    zip_sha = _sha(HOLDOUT_ZIP)
    _write(
        asset_dir / "HOLDOUT_ASSET_LOCK.json",
        {
            "schema": "NURION_V06_HOLDOUT_ASSET_LOCK",
            "label": label,
            "meshyName": "AI_법률_파트너",
            "meshyNameAscii": "AI_Beobryul_Partner",
            "originalZipName": "Meshy_AI_AI_법률_파트너_biped.zip",
            "zipAlias": "ailawfriend-idle15-biped.zip",
            "zip": str(HOLDOUT_ZIP).replace("\\", "/"),
            "zipSha256": zip_sha,
            "expectedZipSha256": GATE8_PARAMETERS["holdoutZipSha256"],
            "expectedFbxSha256": GATE8_PARAMETERS["holdoutFbxSha256"],
            "animation": "Idle_15",
            "presetId": "Idle",
            "submissionForm": "MESHY_ORIGINAL_RIGGED_WITHSKIN_ZIP",
            "siblingZipMix": "DENY",
            "excludedSiblings": ["Gentlemans_Bow", "Victory_Cheer"],
            "priorOfficialHoldout": False,
            "noveltyNote": "Unused in v0.6 Gate1–7; prior tracks treated as style-stress candidate only.",
            "gate6ParameterHash": GATE6_HASH,
            "gate7ParameterHash": GATE7_HASH,
            "lockedAt": now,
        },
    )

    result = run_gate8_holdout(
        zip_path=HOLDOUT_ZIP,
        label=label,
        out_dir=asset_dir,
        baseline_hash_ok=_baseline_ok(),
        runs=3,
    )

    _write(asset_dir / "GATE8_PROFILE.json", result.profile)
    _write(asset_dir / "GATE8_VALIDATION.json", result.validation)
    _write(asset_dir / "GATE8_NOVELTY.json", result.novelty)
    _write(asset_dir / "GATE8_WORKFLOW.json", result.workflow)

    ph = parameter_hash()
    asset_status = {
        "schema": "NURION_V06_GATE8_ASSET_STATUS",
        "gate": "8",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "FRESH_HOLDOUT",
        "label": label,
        "holdoutVerdict": result.verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate7ParameterHash": GATE7_HASH,
        "gate6Locked": True,
        "gate7Locked": True,
        "zipSha256": result.zip_sha256,
        "fbxSha256": result.fbx_sha256,
        "sourceMutation": result.source_mutation,
        "manualCorrection": result.manual_correction,
        "assetSpecificTuning": result.asset_specific_tuning,
        "partialExportPublish": "DENY",
        "autoSeal": "DENY",
        "production": "NO-GO",
        "lipsyncMode": "REST_FALLBACK",
        "inheritedLimitationsFromV05": GATE8_PARAMETERS["inheritedLimitationsFromV05"],
        "limitationAutoClear": "DENY",
        "gates": result.validation.get("gates"),
        "hardFails": result.validation.get("hardFails"),
        "notes": result.notes,
        "updatedAt": now,
        "next": "FINAL_SEAL_REVIEW_OR_RC_HOLD",
    }
    _write(asset_dir / "V06_GATE8_ASSET_STATUS.json", asset_status)

    track_verdict = result.verdict if result.verdict in ("PASS", "PASS_WITH_LIMITATIONS") else "FAIL"
    rc_info = {"ok": False, "skipped": True}
    if track_verdict in ("PASS", "PASS_WITH_LIMITATIONS"):
        receipt_for_rc = {
            "V06_GATE8": track_verdict,
            "parameterHash": ph,
            "holdout": label,
            "zipSha256": result.zip_sha256,
            "fbxSha256": result.fbx_sha256,
            "hardFails": result.validation.get("hardFails") or [],
            "autoSeal": "DENY",
            "production": "NO-GO",
        }
        status_for_rc = {
            "V06_GATE8": track_verdict,
            "parameterHash": ph,
            "production": "NO-GO",
            "autoSeal": "DENY",
        }
        rc_info = build_rc_candidate(
            root=ROOT,
            out_dir=OUT,
            holdout_receipt=receipt_for_rc,
            gate8_status=status_for_rc,
        )

    # Post-run mutation check
    post_mut = 0
    if _sha(HOLDOUT_ZIP) != zip_sha or not _baseline_ok():
        post_mut = 1
        track_verdict = "FAIL"

    receipt = {
        "schema": "NURION_V06_GATE8_RECEIPT",
        "gate": "8",
        "name": "FRESH_HOLDOUT_AND_RC",
        "V06_GATE8": track_verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate7ParameterHash": GATE7_HASH,
        "gate6Locked": True,
        "gate7Locked": True,
        "holdoutLabel": label,
        "holdoutZipSha256": result.zip_sha256,
        "holdoutFbxSha256": result.fbx_sha256,
        "production": "NO-GO",
        "autoSeal": "DENY",
        "sourceMutationTotal": result.source_mutation + post_mut,
        "manualCorrectionTotal": 0,
        "partialExportPublish": "DENY",
        "rcCandidate": rc_info,
        "inheritedLimitationsFromV05": GATE8_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": result.validation.get("hardFails") or [],
        "updatedAt": now,
        "next": "FINAL_SEAL_REVIEW_SEPARATE_TRACK",
    }
    status = {
        "schema": "NURION_V06_GATE8_STATUS",
        "gate": "8",
        "track": "v0.6 Unified Character Animation Runtime",
        "name": "FRESH_HOLDOUT_AND_RC",
        "V06_GATE8": track_verdict,
        "parameterHash": ph,
        "gate6ParameterHash": GATE6_HASH,
        "gate7ParameterHash": GATE7_HASH,
        "gate6Locked": True,
        "gate7Locked": True,
        "holdoutLabel": label,
        "production": "NO-GO",
        "autoSeal": "DENY",
        "rcCandidateCreated": bool(rc_info.get("ok")),
        "rcPackageSha256": rc_info.get("packageSha256"),
        "sourceMutationTotal": result.source_mutation + post_mut,
        "inheritedLimitationsFromV05": GATE8_PARAMETERS["inheritedLimitationsFromV05"],
        "hardFails": result.validation.get("hardFails") or [],
        "updatedAt": now,
        "artifacts": {
            "receipt": "V06_GATE8_RECEIPT.json",
            "parameters": "V06_GATE8_PARAMETERS.json",
            "rcFreeze": "package/RC1_CANDIDATE_FREEZE.json" if rc_info.get("ok") else None,
        },
        "next": "FINAL_SEAL_REVIEW_SEPARATE_TRACK",
    }
    track = {
        "schema": "NURION_V0.6_STATUS",
        "track": "Unified Character Animation Runtime",
        "product": "NURION Unified Character Animation Runtime",
        "implementation": "V0.6_GATE8",
        "status": "RC_CANDIDATE" if rc_info.get("ok") else "IN_PROGRESS",
        "V06_GATE6": "PASS_WITH_LIMITATIONS",
        "gate6ParameterHash": GATE6_HASH,
        "gate6Locked": True,
        "V06_GATE7": "PASS_WITH_LIMITATIONS",
        "gate7ParameterHash": GATE7_HASH,
        "gate7Locked": True,
        "V06_GATE8": track_verdict,
        "gate8ParameterHash": ph,
        "production": "NO-GO",
        "autoSeal": "DENY",
        "sealedBaselineMutation": "DENY",
        "limitationAutoClear": "DENY",
        "holdoutLabel": label,
        "rcCandidate": rc_info,
        "inheritedLimitationsFromV05": GATE8_PARAMETERS["inheritedLimitationsFromV05"],
        "next": "FINAL_SEAL_REVIEW_SEPARATE_TRACK",
        "updatedAt": now,
    }

    _write(OUT / "V06_GATE8_PARAMETERS.json", GATE8_PARAMETERS)
    _write(OUT / "V06_GATE8_RECEIPT.json", receipt)
    _write(OUT / "V06_GATE8_STATUS.json", status)
    _write(ROOT / "dist" / "v0.6" / "STATUS.json", track)

    print(
        json.dumps(
            {
                "V06_GATE8": track_verdict,
                "parameterHash": ph,
                "hardFails": result.validation.get("hardFails"),
                "determinism": result.validation.get("determinism"),
                "novelty": {"ok": result.novelty.get("ok"), "ailaw": result.novelty.get("ailawfriendCanonicalIdle15")},
                "rcCandidate": {
                    "ok": rc_info.get("ok"),
                    "sha256": rc_info.get("packageSha256"),
                    "SEALED": False,
                    "production": "NO-GO",
                },
                "sourceMutation": result.source_mutation + post_mut,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if track_verdict in ("PASS", "PASS_WITH_LIMITATIONS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
