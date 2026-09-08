#!/usr/bin/env python3
"""Declare NURION-RIG-01C PASS + BODY Canonical Bone Spec v1 FULL LOCK."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EV = WORK / "evidence"
SEM = WORK / "semantic"
LEDGER = WORK / "mutation_ledger.json"

CONV = SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1_DRAFT.json"
# Promote to locked companion filename while keeping draft path as historical alias via copy
CONV_LOCKED = SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"
DRAFT = SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1_DRAFT.json"
CAND = SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1_LOCK_CANDIDATE.json"
SPEC_LOCKED = SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json"
FACE_LOCK = SEM / "NURION_FACE_PRODUCT_LOCK_V1.json"
BODY_LOCK = SEM / "NURION_BODY_PRODUCT_LOCK_V1.json"

RIG01C_RECEIPT = EV / "NURION-RIG-01C_axis_retarget_convention_receipt.json"
RIG01C_PASS = EV / "NURION-RIG-01C_PASS_receipt.json"
BODY_LOCK_RECEIPT = EV / "NURION_BODY_CANONICAL_V1_FULL_LOCK_receipt.json"
ZIP = EV / "NURION-RIG-01C_convention_source_review.zip"

EXPECTED = {
    "zip": "264f6de3b317f37010b01c7388cfcd4da219ead4fa5f9fd0580afc2f20e66bc2",
    "convention": "19da5a00f4943a144426efaf675d364f64d244773dc60ede7db81be5bb8c6d9a",
    "raw": "27d13e1c09d87d6ba5487595c1a9a4fb48d21775118f3af5e59da1c618e385c2",
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    zip_sha = sha(ZIP)
    conv_sha = sha(CONV)
    raw_sha = sha(EV / "NURION-RIG-01C_axis_rest_forensic_raw.json")
    if zip_sha != EXPECTED["zip"] or conv_sha != EXPECTED["convention"] or raw_sha != EXPECTED["raw"]:
        raise SystemExit(
            json.dumps(
                {"error": "integrity mismatch", "zip": zip_sha, "conv": conv_sha, "raw": raw_sha},
                ensure_ascii=True,
            )
        )

    conv = json.loads(CONV.read_text(encoding="utf-8"))
    conv["status"] = "ACCEPTED_LOCKED"
    conv["rig01cPass"] = "PASS"
    conv["bodyCanonicalV1FullLock"] = "DECLARED"
    conv["acceptedAtUtc"] = ts
    conv["reviewer"] = "etherean"
    conv["clauseVerdicts"] = {
        "§1_§13": "ACCEPT",
        "§14": "ACCEPT",
        "§15": "ACCEPT",
        "§16": "ACCEPT",
        "§17": "ACCEPT",
        "§18": "ACCEPT",
        "§19": "ACCEPT",
        "§20": "ACCEPT",
        "§6_wording": "ACCEPT",
    }
    conv["reviewGate"] = {
        "measurementForensic": "ACCEPTED_AS_BASIS",
        "convention": "ACCEPTED",
        "rig01cPass": "PASS",
        "fullLock": "DECLARED",
    }
    conv["next"] = "NURION-RIG-02_RETARGET_ADAPTER_PROOF"
    CONV.write_text(json.dumps(conv, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    shutil.copy2(CONV, CONV_LOCKED)

    cand = json.loads(CAND.read_text(encoding="utf-8"))
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))

    spec = {
        "schema": "NURION_BODY_CANONICAL_BONE_SPEC_V1",
        "status": "FULL_LOCK_DECLARED",
        "sot": True,
        "productLock": True,
        "lockedAtUtc": ts,
        "reviewer": "etherean",
        "chain": {
            "RIG-01A": "PASS",
            "RIG-01B": "PASS_HIERARCHY_ACCEPTED",
            "RIG-01C": "PASS",
        },
        "tiers": {
            "BODY_CORE_V1": cand["core"],
            "HAND_EXTENSION_V1": cand["handExtension"],
            "DEFORM_EXTENSION_V1": cand["deformExtension"],
        },
        "hierarchySemantics": cand.get("hierarchySemanticsAccept", draft.get("hierarchySemanticsAccept")),
        "jakeToNurionAccepted": cand.get("hierarchySemanticsAccept", {}).get("jakeToNurionAccepted")
        or draft.get("jakeToNurionAccepted"),
        "mjnAdapterDraft": cand.get("mjnAdapterDraft"),
        "faceBodyBoundary": {
            "BODY_owns": ["root", "pelvis", "torso", "limbs", "neck", "head_transform"],
            "FACE_owns": ["eye", "eyelid", "jaw", "tongue", "facial_deformation", "FACE_Canonical_v1"],
            "soleAttachment": "NURION_head → FACE Rig Root / Face Space",
            "rigMustNotMutate": [
                "FACE_PRODUCT_LOCK_V1",
                "Eye_Calibration",
                "TALKING_GO",
            ],
        },
        "axisRetargetConvention": {
            "artifact": str(CONV_LOCKED),
            "sha256AtLock": conv_sha,
            "status": "ACCEPTED_LOCKED",
        },
        "donorPolicy": {
            "MJN": "reference/donor — Adapter must map TO Canonical",
            "Jake": "reference/donor — Adapter must map TO Canonical",
            "futureRigs": "reference/donor — Adapter must map TO Canonical",
            "canonicalIsSoT": True,
            "donorsMustNotChangeCanonical": True,
        },
        "classificationBuckets": ["CORE", "HAND_EXTENSION", "DEFORM_EXTENSION", "FACE", "HELPER"],
        "policy": {
            "bodyStructureChanges": "DENY — reopen requires BODY v2, not v1 SoT mutation",
            "tasteTweaks": "SEPARATE_VERSION_ONLY",
            "nextTrack": "NURION-RIG-02_RETARGET_ADAPTER_PROOF",
        },
        "evidence": {
            "rig01cPassReceipt": str(RIG01C_PASS),
            "conventionReviewZip": str(ZIP),
            "conventionReviewZipSha256": zip_sha,
        },
    }
    # Prefer accepted mapping from cand hierarchy block
    hs = cand.get("hierarchySemanticsAccept") or {}
    if hs.get("jakeToNurionAccepted"):
        spec["jakeToNurionAccepted"] = hs["jakeToNurionAccepted"]
    elif draft.get("jakeToNurionAccepted"):
        spec["jakeToNurionAccepted"] = draft["jakeToNurionAccepted"]

    SPEC_LOCKED.write_text(json.dumps(spec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    cand["status"] = "SUPERSEDED_BY_FULL_LOCK"
    cand["fullLockDeclaredAtUtc"] = ts
    cand["lockedSpec"] = str(SPEC_LOCKED)
    CAND.write_text(json.dumps(cand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    draft["status"] = "SUPERSEDED_BY_FULL_LOCK"
    DRAFT.write_text(json.dumps(draft, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    body_lock = {
        "schema": "NURION_BODY_PRODUCT_LOCK_V1",
        "declaredAtUtc": ts,
        "status": "DECLARED",
        "canonical_contract": "NURION_BODY_CANONICAL_V1",
        "productLock": True,
        "sot": True,
        "talking_status": "GO",
        "faceProductLock": "DECLARED",
        "chain": spec["chain"],
        "lockedArtifacts": {
            "boneSpec": str(SPEC_LOCKED),
            "axisRetargetConvention": str(CONV_LOCKED),
            "boneSpecSha256": sha(SPEC_LOCKED),
            "conventionSha256AtLock": conv_sha,
        },
        "faceBodyBoundary": spec["faceBodyBoundary"],
        "donorPolicy": spec["donorPolicy"],
        "policy": spec["policy"],
        "humanAccept": {
            "reviewer": "etherean",
            "verdict": "ACCEPT",
            "rig01c": "PASS",
            "bodyCanonicalV1": "FULL_LOCK",
            "packageSha256": zip_sha,
            "conventionSha256": conv_sha,
        },
    }
    BODY_LOCK.write_text(json.dumps(body_lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if FACE_LOCK.exists():
        face = json.loads(FACE_LOCK.read_text(encoding="utf-8"))
        face["policy"]["nextTrack"] = "NURION-RIG-02_RETARGET_ADAPTER_PROOF"
        face["bodyCanonicalV1"] = "FULL_LOCK_DECLARED"
        face["bodyLockArtifact"] = str(BODY_LOCK)
        FACE_LOCK.write_text(json.dumps(face, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rig01c_pass = {
        "receiptId": f"NURION-RIG-01C_PASS_{ts}",
        "stage": "NURION-RIG-01C_AXIS_RETARGET_CONVENTION",
        "status": "PASS",
        "rig01cPass": "PASS",
        "bodyCanonicalV1": "FULL_LOCK_DECLARED",
        "fullLock": "DECLARED",
        "reviewer": "etherean",
        "integrity": EXPECTED,
        "clauseVerdicts": conv["clauseVerdicts"],
        "conventionLocked": str(CONV_LOCKED),
        "next": "NURION-RIG-02_RETARGET_ADAPTER_PROOF",
    }
    RIG01C_PASS.write_text(json.dumps(rig01c_pass, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    RIG01C_RECEIPT.write_text(json.dumps({**rig01c_pass, "priorStatus": "PATCHED_AWAITING_REAUDIT"}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lock_receipt = {
        "receiptId": f"NURION_BODY_CANONICAL_V1_FULL_LOCK_{ts}",
        "stage": "NURION_BODY_CANONICAL_BONE_SPEC_V1_FULL_LOCK",
        "status": "DECLARED",
        "sot": str(SPEC_LOCKED),
        "bodyProductLock": str(BODY_LOCK),
        "axisConvention": str(CONV_LOCKED),
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "denyMutationsFromRigTrack": [
            "FACE_PRODUCT_LOCK_V1",
            "Eye_Calibration",
            "TALKING_GO",
        ],
        "next": "NURION-RIG-02_RETARGET_ADAPTER_PROOF",
    }
    BODY_LOCK_RECEIPT.write_text(json.dumps(lock_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE PRODUCT LOCK DECLARED + BODY CANONICAL V1 FULL LOCK DECLARED — TALKING GO; "
        "next = NURION-RIG-02 Retarget Adapter proof"
    )
    ledger["bodyProductLock"] = {
        "status": "DECLARED",
        "declaredAtUtc": ts,
        "lockArtifact": str(BODY_LOCK),
        "boneSpec": str(SPEC_LOCKED),
        "convention": str(CONV_LOCKED),
    }
    for e in ledger.get("entries", []):
        if e.get("id") == "NURION-RIG-01C":
            e["status"] = "PASS"
            e["rig01cPass"] = "PASS"
            e["fullLock"] = "DECLARED"
            e["passReceipt"] = str(RIG01C_PASS)
            e["next"] = "NURION-RIG-02"
    ids = {e.get("id") for e in ledger.get("entries", [])}
    if "NURION-BODY-CANONICAL-LOCK-V1" not in ids:
        ledger["entries"].append(
            {
                "id": "NURION-BODY-CANONICAL-LOCK-V1",
                "type": "BODY_CANONICAL_FULL_LOCK",
                "mutation": 0,
                "scope": "NURION BODY Canonical Bone Spec v1 SoT + Axis/Retarget Convention v1",
                "output": str(SPEC_LOCKED),
                "bodyLock": str(BODY_LOCK),
                "evidence": str(BODY_LOCK_RECEIPT),
                "status": "DECLARED",
                "sot": True,
                "next": "NURION-RIG-02_RETARGET_ADAPTER_PROOF",
            }
        )
    ledger["bodyCanonicalTrack"] = {
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "rig01a": "PASS",
        "rig01b": "PASS_HIERARCHY_ACCEPTED",
        "rig01c": "PASS",
        "bodyCore23": "ACCEPTED",
        "handExtension30": "ACCEPTED",
        "bodyCanonicalV1": "FULL_LOCK_DECLARED",
        "fullLock": "DECLARED",
        "updatedAtUtc": ts,
    }
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "rig01c": "PASS",
                "bodyCanonicalV1": "FULL_LOCK_DECLARED",
                "spec": str(SPEC_LOCKED),
                "bodyLock": str(BODY_LOCK),
                "convention": str(CONV_LOCKED),
                "next": "NURION-RIG-02_RETARGET_ADAPTER_PROOF",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
