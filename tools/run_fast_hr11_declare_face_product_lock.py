#!/usr/bin/env python3
"""FAST-HR11 — declare Human Visual PASS + TALKING GO + FACE PRODUCT LOCK."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
SEMANTIC = WORK / "semantic"
LEDGER = WORK / "mutation_ledger.json"

ZIP = EVIDENCE / "FAST-HR11R_human_visual_evidence.zip"
EXPECTED_ZIP_SHA = "698c28793e2722428212207cb48cbb88ffa064e21979dd126f01bf3cb8e649aa"

HR11R_RECEIPT = EVIDENCE / "FAST-HR11R_human_visual_gate_receipt.json"
HR11_FINAL = EVIDENCE / "FAST-HR11_human_visual_gate_PASS_receipt.json"
LOCK = SEMANTIC / "NURION_FACE_PRODUCT_LOCK_V1.json"
MANIFEST = EVIDENCE / "FAST-HR11R_human_visual_evidence_manifest.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_sha = sha256(ZIP) if ZIP.exists() else None
    if zip_sha != EXPECTED_ZIP_SHA:
        raise SystemExit(f"ZIP sha mismatch: {zip_sha} != {EXPECTED_ZIP_SHA}")

    human = {
        "reviewer": "etherean",
        "verdict": "ACCEPT",
        "stageClosedAs": "FAST-HR11_PASS",
        "package": str(ZIP),
        "packageSha256": zip_sha,
        "criteria": {
            "04_noEyeballLeakDuringBlink": "PASS",
            "06_smileSurvivesSpeech": "PASS",
            "regression_concerned_surprised_listening_speakingNeutral": "PASS",
        },
        "notes": [
            "Blink peak eyeball/highlight leak removed; both eyes read as fully closed; 1.12 overdrive without periocular collapse.",
            "Happy+Speaking non-MBP retains smile identity; MBP still prioritizes closure — speech-class attenuation confirmed.",
            "No face collapse / over-deformation regression on remaining four scenarios.",
        ],
        "meaning": (
            "Jake is verification donor/reference only — not a finished product face. "
            "NURION FACE Canonical → Legacy Adapter → Actuator → Expression Mixer → "
            "Korean Lip Sync → Composition → Human Visual chain is product-locked as FACE v1 SoT."
        ),
    }

    lock = {
        "schema": "NURION_FACE_PRODUCT_LOCK_V1",
        "declaredAtUtc": ts,
        "status": "DECLARED",
        "talking_status": "GO",
        "canonical_contract": "NURION_FACE_CANONICAL_V1",
        "productLock": True,
        "sot": True,
        "chain": {
            "HR05": "PASS",
            "HR06": "PASS",
            "HR07": "PASS",
            "HR08": "PASS",
            "HR09": "PASS",
            "HR10": "PASS",
            "HR11": "PASS",
        },
        "lockedArtifacts": {
            "namingTable": str(SEMANTIC / "NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"),
            "compositionPolicy": str(SEMANTIC / "NURION_FACE_COMPOSITION_POLICY_V1.json"),
            "legacyAdapter": "fast_track/runtime/legacy_face_adapter.py",
            "canonicalActuator": "fast_track/runtime/canonical_facial_actuator.py",
            "expressionMixer": "fast_track/runtime/expression_mixer.py",
            "koreanLipSyncV2": "fast_track/runtime/korean_lip_sync_v2.py",
            "faceComposition": "fast_track/runtime/face_composition.py",
        },
        "donorRole": {
            "asset": "fast_track/assets/external/hr05_jake/Jake.fbx",
            "role": "facial reference/verification donor",
            "product_use": False,
            "attribution": "Canino3d / CC BY",
        },
        "policy": {
            "faceStructureChanges": "DENY — reopen requires new version, not FACE v1 SoT mutation",
            "microExpressionTasteTweaks": "SEPARATE_VERSION_ONLY",
            "nextTrack": "NURION_CANONICAL_RIG_V1 — BODY bone specification forensic baseline",
        },
        "humanAccept": human,
        "evidence": {
            "hr11rReceipt": str(HR11R_RECEIPT),
            "hr11FinalPassReceipt": str(HR11_FINAL),
            "visualPackage": str(ZIP),
            "visualPackageSha256": zip_sha,
        },
    }
    LOCK.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Finalize HR11R receipt
    hr11r = json.loads(HR11R_RECEIPT.read_text(encoding="utf-8"))
    hr11r.update(
        {
            "receiptId": f"FAST-HR11R_human_visual_gate_PASS_{ts}",
            "status": "PASS",
            "talking_status": "GO",
            "face_product_lock": "DECLARED",
            "humanAccept": human,
            "closedAtUtc": ts,
            "next": "NURION_CANONICAL_RIG_V1_BODY_BONE_SPEC_FORENSIC",
        }
    )
    for k in hr11r.get("criteria", {}):
        if k == "18_humanReviewerAccept":
            hr11r["criteria"][k] = "ACCEPT"
        elif str(hr11r["criteria"][k]).startswith("PASS"):
            continue
        else:
            hr11r["criteria"][k] = "PASS"
    hr11r["agentVisualPrecheck"] = {
        "verdict": "SUPERSEDED_BY_HUMAN_ACCEPT",
        "humanVerdict": "ACCEPT",
        "recommendation": "FACE v1 product-locked. Do not reopen HR05~HR11 architecture.",
    }
    HR11R_RECEIPT.write_text(json.dumps(hr11r, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    final = {
        "receiptId": f"FAST-HR11_human_visual_gate_PASS_{ts}",
        "stage": "FAST-HR11_HUMAN_VISUAL_GATE",
        "status": "PASS",
        "talking_status": "GO",
        "face_product_lock": "DECLARED",
        "closedVia": "FAST-HR11R quality patch + etherean ACCEPT",
        "canonical_contract": "NURION_FACE_CANONICAL_V1",
        "humanAccept": human,
        "productLock": str(LOCK),
        "chain": lock["chain"],
        "next": "NURION_CANONICAL_RIG_V1_BODY_BONE_SPEC_FORENSIC",
    }
    HR11_FINAL.write_text(json.dumps(final, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if MANIFEST.exists():
        man = json.loads(MANIFEST.read_text(encoding="utf-8"))
        man.update(
            {
                "status": "PASS",
                "talking_status": "GO",
                "face_product_lock": "DECLARED",
                "humanVerdict": "ACCEPT",
                "closedAtUtc": ts,
            }
        )
        MANIFEST.write_text(json.dumps(man, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "NURION FACE v1 PRODUCT LOCK DECLARED — TALKING GO; face structure SoT frozen; "
        "next = Canonical Rig v1 BODY bone forensic"
    )
    ledger["faceProductLock"] = {
        "status": "DECLARED",
        "talking_status": "GO",
        "declaredAtUtc": ts,
        "lockArtifact": str(LOCK),
        "hr11FinalPass": str(HR11_FINAL),
    }

    # Update HR10 talking annotation for clarity at ledger tip only (historical receipts stay)
    for entry in ledger.get("entries", []):
        if entry.get("id") == "FAST-HR10":
            entry["talking_status_at_close"] = "HOLD"
            entry["talking_status_current"] = "GO"
        if entry.get("id") == "FAST-HR11":
            entry["status"] = "PASS"
            entry["humanVerdict"] = "ACCEPT_VIA_HR11R"
            entry["talking_status"] = "GO"
            entry["face_product_lock"] = "DECLARED"
            entry["finalPassReceipt"] = str(HR11_FINAL)
            entry["next"] = "FACE_PRODUCT_LOCKED"
            entry.pop("failItems", None)
        if entry.get("id") == "FAST-HR11R":
            entry["status"] = "PASS"
            entry["humanVerdict"] = "ACCEPT"
            entry["talking_status"] = "GO"
            entry["face_product_lock"] = "DECLARED"
            entry["next"] = "NURION_CANONICAL_RIG_V1"

    # Append lock entry if not present
    ids = {e.get("id") for e in ledger.get("entries", [])}
    if "FAST-FACE-PRODUCT-LOCK-V1" not in ids:
        ledger["entries"].append(
            {
                "id": "FAST-FACE-PRODUCT-LOCK-V1",
                "type": "FACE_PRODUCT_LOCK",
                "mutation": 0,
                "scope": "NURION FACE Canonical v1 SoT — structure freeze after HR11 Human ACCEPT",
                "output": str(LOCK),
                "evidence": str(HR11_FINAL),
                "status": "DECLARED",
                "talking_status": "GO",
                "face_product_lock": "DECLARED",
                "next": "NURION_CANONICAL_RIG_V1_BODY_BONE_SPEC_FORENSIC",
            }
        )

    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "talking": "GO",
                "face_product_lock": "DECLARED",
                "lock": str(LOCK),
                "hr11Final": str(HR11_FINAL),
                "next": "NURION_CANONICAL_RIG_V1_BODY_BONE_SPEC_FORENSIC",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
