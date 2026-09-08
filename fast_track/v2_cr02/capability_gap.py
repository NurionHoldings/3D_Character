"""CR02-P01 — Capability Gap Inspection (read-only; no augmentation)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.inspector import canonical_sha256, inspect_character, sha256_file
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter

REPORT_SCHEMA = "NURION_V2_CR02_CAPABILITY_GAP_INSPECTION_V1"
CR01_DIGEST = "c6aecfa1a90e81afa878a08ca7cdfc0ed34135b60bbdd2d48e597955d485393d"
IDLE15_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"


def _cap_status(block: dict[str, Any] | None) -> str:
    if not block:
        return "MISSING"
    st = (block.get("status") or "").upper()
    if st in ("DETECTED", "PRESENT", "COMPATIBLE"):
        return "PRESENT"
    if st in ("AMBIGUOUS",):
        return "AMBIGUOUS"
    return "MISSING"


def inspect_capability_gap(path: Path | str, *, expected_sha: str | None = IDLE15_SHA) -> dict[str, Any]:
    path = Path(path)
    before = path.read_bytes()
    source_sha = sha256_file(path)
    blockers: list[dict[str, Any]] = []

    if expected_sha and source_sha != expected_sha:
        blockers.append({"code": "SOURCE_SHA_MISMATCH", "got": source_sha, "want": expected_sha})

    # V1 ADAPT-01 inspector — CONSUME / READ_ONLY
    intake = inspect_character(path, character_id="cr02_p01", read_only_assert=True)
    after_intake = path.read_bytes()
    if after_intake != before:
        blockers.append({"code": "SOURCE_MUTATED_BY_INTAKE"})

    # CR01 Flexible Adapter — CONSUME ONLY
    cr01 = run_flexible_adapter(path)
    after_cr01 = path.read_bytes()
    if after_cr01 != before:
        blockers.append({"code": "SOURCE_MUTATED_BY_CR01"})
    if cr01.get("semanticAdapterDigest") != CR01_DIGEST:
        blockers.append(
            {
                "code": "CR01_DIGEST_MISMATCH",
                "got": cr01.get("semanticAdapterDigest"),
                "want": CR01_DIGEST,
            }
        )
    if cr01.get("status") != "PASS":
        blockers.append({"code": "CR01_ADAPTER_NOT_PASS", "status": cr01.get("status")})

    mapping = cr01.get("mappingView") or {}
    head = mapping.get("NURION_head")
    if not head:
        blockers.append({"code": "NURION_HEAD_UNRESOLVED"})

    face = intake.get("faceCapabilities") or {}
    eye = intake.get("eyeCapabilities") or {}
    jaw = intake.get("jawCapabilities") or {}
    expr = intake.get("expressionCapabilities") or {}
    talking = intake.get("talkingCapabilities") or {}
    morph_total = int(expr.get("blendshapeCount") or 0)
    cls = intake.get("adaptationClassification") or {}

    def _eye_side(key: str) -> str:
        return _cap_status(eye.get(key) if isinstance(eye.get(key), dict) else None)

    inventory = {
        "BODY": {
            "status": "PRESENT" if cr01.get("status") == "PASS" else "GAP",
            "via": "V2-CR-01 CONSUME",
            "mappingViewCore": {
                "NURION_pelvis": mapping.get("NURION_pelvis"),
                "NURION_chest": mapping.get("NURION_chest"),
                "NURION_neck": mapping.get("NURION_neck"),
                "NURION_head": head,
            },
        },
        "SKIN": {
            "status": "PRESENT",
            "note": "skinned mesh present on Meshy baseline; source IMMUTABLE under CR02",
        },
        "FACE_Rig_Root": {"status": "MISSING", "requiredInterface": "NURION_head → FACE_Rig_Root"},
        "Eye": {
            "status": "PRESENT"
            if _eye_side("leftEyeBone") == "PRESENT" and _eye_side("rightEyeBone") == "PRESENT"
            else "MISSING",
            "left": _eye_side("leftEyeBone"),
            "right": _eye_side("rightEyeBone"),
            "detail": eye,
            "requiredFunctional": "LEFT/RIGHT deterministic; independent motion observable",
        },
        "Blink": {
            "status": "MISSING",
            "requiredFunctional": "eyelid/eye-region deformation observable; N→A→N",
        },
        "Jaw_Mouth": {
            "status": _cap_status(jaw.get("bone") if isinstance(jaw.get("bone"), dict) else jaw),
            "detail": jaw,
            "requiredFunctional": "jaw/open-close deformation observable; N→A→N",
        },
        "Expression": {
            "status": "MISSING" if morph_total == 0 else "PARTIAL",
            "blendshapeCount": morph_total,
            "facialBones": (face.get("facialBones") or {}).get("status"),
            "requiredFunctional": "minimum expression set → distinct deformation; N→A→N",
        },
        "TALKING": {
            "status": _cap_status((talking.get("visemeCandidates") or {}) if talking else None),
            "detail": talking,
            "requiredFunctional": "timed viseme sequence → changing mouth states; static open ≠ PASS",
        },
        "blendshapes": {
            "count": morph_total,
            "status": "NONE" if morph_total == 0 else "PRESENT",
            "implication": "augmentation must create deformation via explicit mechanism + provenance",
        },
    }

    gaps = [k for k, v in inventory.items() if v.get("status") in ("MISSING", "GAP", "NONE", "PARTIAL")]
    augmentation_required = [
        c
        for c in ("FACE_Rig_Root", "Eye", "Blink", "Jaw_Mouth", "Expression", "TALKING")
        if inventory[c]["status"] in ("MISSING", "PARTIAL", "AMBIGUOUS")
    ]

    status = "PASS" if not blockers else "BLOCKED"
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "stage": "CR02-P01",
        "changeRequestId": "V2-CR-02",
        "status": status,
        "sourceIdentity": {
            "path": str(path),
            "sha256": source_sha,
            "byteLength": len(before),
            "immutable": True,
        },
        "sourcePreservation": {
            "bytesUnchanged": before == path.read_bytes(),
            "shaBefore": source_sha,
            "shaAfter": sha256_file(path),
        },
        "cr01Consume": {
            "role": "CONSUME ONLY",
            "status": cr01.get("status"),
            "semanticAdapterDigest": cr01.get("semanticAdapterDigest"),
            "expectedDigest": CR01_DIGEST,
            "digestMatch": cr01.get("semanticAdapterDigest") == CR01_DIGEST,
            "NURION_head": head,
            "CR01_REOPEN": "DENY",
        },
        "intakeClassification": {
            "class": cls.get("class") or cls.get("adaptationClass"),
            "face": cls.get("face"),
            "eye": cls.get("eye"),
            "jaw": cls.get("jaw"),
            "talking": cls.get("talking"),
        },
        "capabilityInventory": inventory,
        "gaps": gaps,
        "augmentationRequired": augmentation_required,
        "provenanceImplication": {
            "blendshapeCount": morph_total,
            "mustRecordMechanism": morph_total == 0,
            "recordSchema": "NURION_V2_CR02_CAPABILITY_PROVENANCE_V1",
        },
        "policy": {
            "SOURCE_MUTATION": "DENY",
            "AUTO_BODY_RE_RIG": "DENY",
            "GLOBAL_AUTO_WEIGHT": "DENY",
            "functionalWithoutDeformation": "BLOCKED",
        },
        "blockers": blockers,
        "v2Engine": "NOT OPEN",
        "engineV1": "CLOSED / PASS / CONSUME ONLY",
    }
    report["gapInspectionDigest"] = canonical_sha256(
        {
            "sourceSha256": source_sha,
            "cr01Digest": cr01.get("semanticAdapterDigest"),
            "inventory": inventory,
            "augmentationRequired": augmentation_required,
        }
    )
    return report
