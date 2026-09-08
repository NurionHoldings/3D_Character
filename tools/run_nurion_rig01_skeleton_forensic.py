#!/usr/bin/env python3
"""NURION-RIG-01A receipt + kick RIG-01B hierarchy forensic packaging."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
WORK = ROOT / "fast_track/working/meshy_silver_starlight"
EVIDENCE = WORK / "evidence"
SEMANTIC = WORK / "semantic"
LEDGER = WORK / "mutation_ledger.json"

JAKE = ROOT / "fast_track/assets/external/hr05_jake/Jake.fbx"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
BLENDER_PY = ROOT / "tools/blender_rig01b_jake_hierarchy_forensic.py"

DRAFT = SEMANTIC / "NURION_BODY_CANONICAL_BONE_SPEC_V1_DRAFT.json"
RIG01A = EVIDENCE / "NURION-RIG-01A_skeleton_capability_forensic_receipt.json"
RIG01B_RAW = EVIDENCE / "NURION-RIG-01B_jake_hierarchy_forensic_raw.json"
RIG01B = EVIDENCE / "NURION-RIG-01B_jake_hierarchy_forensic_receipt.json"
LOCK_CANDIDATE = SEMANTIC / "NURION_BODY_CANONICAL_BONE_SPEC_V1_LOCK_CANDIDATE.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_01a(ts: str) -> dict:
    receipt = {
        "receiptId": f"NURION-RIG-01A_{ts}",
        "stage": "NURION-RIG-01A_SKELETON_CAPABILITY_FORENSIC",
        "status": "PASS",
        "inputs": {
            "externalReviewPackage": "dist/external_source_review (prior)",
            "jakeFbx": str(JAKE),
            "jakeSha256": sha256(JAKE) if JAKE.exists() else None,
            "mjnFastBodyJointCount": 24,
        },
        "conclusion": {
            "bodyCanonicalStrategy": (
                "Neither rename-only MJN nor clone Jake CC skeleton. "
                "Use MJN-validated Body Motion chain as mandatory core; "
                "selectively absorb Jake finger/twist/face-adjacent capability as extensions."
            ),
            "bodyCoreV1": "23-bone draft ESTABLISHED",
            "handExtensionV1": "30-bone draft ESTABLISHED",
            "deformExtensionV1": "optional twist draft ESTABLISHED",
            "rootPelvisSplit": "REQUIRED",
            "faceBodyBoundary": "FACE owns jaw/eye/tongue/facial; BODY owns head transform only",
            "bodyCanonicalV1Lock": "NOT_YET — requires RIG-01B exact Jake hierarchy",
        },
        "artifacts": {
            "bodyCanonicalDraft": str(DRAFT),
        },
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "next": "NURION-RIG-01B_JAKE_SKELETON_HIERARCHY_FORENSIC",
    }
    RIG01A.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


def summarize_01b(raw: dict) -> dict:
    bones = raw["bones"]
    # Extract critical parent chain facts
    def parent_of(n):
        return bones.get(n, {}).get("parent")

    spine_chain = {
        "BoneRoot": parent_of("CC_Base_BoneRoot"),
        "Hip_parent": parent_of("CC_Base_Hip"),
        "Pelvis_parent": parent_of("CC_Base_Pelvis"),
        "Waist_parent": parent_of("CC_Base_Waist"),
        "Spine01_parent": parent_of("CC_Base_Spine01"),
        "Spine02_parent": parent_of("CC_Base_Spine02"),
        "NeckTwist01_parent": parent_of("CC_Base_NeckTwist01"),
        "NeckTwist02_parent": parent_of("CC_Base_NeckTwist02"),
        "Head_parent": parent_of("CC_Base_Head"),
    }
    clavicle = {
        "L_parent": parent_of("CC_Base_L_Clavicle"),
        "R_parent": parent_of("CC_Base_R_Clavicle"),
    }
    twists = {
        n: {"parent": b["parent"], "children": b["children"]}
        for n, b in bones.items()
        if "Twist" in n
    }
    fingers = {
        n: {"parent": b["parent"], "children": b["children"]}
        for n, b in bones.items()
        if b["classification"] == "HAND_EXTENSION_CANDIDATE"
    }
    toes = {
        n: {"parent": b["parent"], "children": b["children"]}
        for n, b in bones.items()
        if b["classification"] == "TOE_EXTENSION_OR_HELPER"
        or ("Toe" in n and "Share" not in n)
    }
    face = raw.get("faceBoundaryReminder", {})

    # Recommend spine mapping from actual order
    # Walk from Pelvis up
    torso_path = raw.get("focusPathsToRoot", {}).get("CC_Base_Head", [])
    # path is leaf→root; reverse for root→leaf
    torso_root_to_head = list(reversed(torso_path)) if torso_path else []

    return {
        "boneCount": raw["boneCount"],
        "rootBones": raw["rootBones"],
        "classificationCounts": raw["classificationCounts"],
        "spineAndRootFacts": spine_chain,
        "torsoRootToHead": torso_root_to_head,
        "clavicleParents": clavicle,
        "twistCount": len(twists),
        "fingerCount": len(fingers),
        "toeRelatedCount": len(toes),
        "faceOwnedDoNotAbsorb": face.get("doNotAbsorb", []),
        "lrSymmetry": raw.get("lrSymmetry"),
        "lengthRatios": raw.get("lengthRatios"),
        "focusPathsToRoot": raw.get("focusPathsToRoot"),
    }


def write_lock_candidate(ts: str, summary: dict) -> dict:
    draft = json.loads(DRAFT.read_text(encoding="utf-8"))
    # Promote to LOCK_CANDIDATE only — still not LOCKED
    torso = summary.get("torsoRootToHead") or []
    cand = {
        "schema": "NURION_BODY_CANONICAL_BONE_SPEC_V1_LOCK_CANDIDATE",
        "status": "LOCK_CANDIDATE_NOT_LOCKED",
        "declaredAtUtc": ts,
        "basedOn": {
            "rig01a": str(RIG01A),
            "rig01b": str(RIG01B),
            "draft": str(DRAFT),
        },
        "core": draft["tiers"]["BODY_CORE_V1"],
        "handExtension": draft["tiers"]["HAND_EXTENSION_V1"],
        "deformExtension": draft["tiers"]["DEFORM_EXTENSION_V1"],
        "mjnAdapterDraft": draft["mjnAdapterDraft"],
        "faceBodyBoundary": draft["faceBodyBoundary"],
        "jakeHierarchyEvidence": {
            "torsoRootToHead": torso,
            "spineAndRootFacts": summary.get("spineAndRootFacts"),
            "clavicleParents": summary.get("clavicleParents"),
            "classificationCounts": summary.get("classificationCounts"),
        },
        "stillOpenBeforeFullLock": [
            "Confirm Waist role vs NURION_spine01 (fold vs keep)",
            "Confirm Spine01/Spine02 → spine01/spine02/chest mapping with rest axes",
            "Confirm NeckTwist01/02 collapse policy into NURION_neck",
            "Confirm Hip vs BoneRoot vs Pelvis → NURION_root/pelvis split exact rule",
            "Axis convention document for retarget (Blender Y-bone vs engine)",
        ],
        "lockGate": "Human ACCEPT on LOCK_CANDIDATE after reviewing RIG-01B receipt",
    }
    LOCK_CANDIDATE.write_text(json.dumps(cand, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return cand


def update_ledger(ts: str) -> None:
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    ledger["presentationLayer"] = (
        "FACE PRODUCT LOCK DECLARED / TALKING GO — "
        "NURION-RIG-01A PASS; RIG-01B hierarchy forensic complete; "
        "BODY Canonical v1 = LOCK_CANDIDATE (NOT LOCKED)"
    )
    ids = {e.get("id") for e in ledger.get("entries", [])}
    if "NURION-RIG-01A" not in ids:
        ledger["entries"].append(
            {
                "id": "NURION-RIG-01A",
                "type": "SKELETON_CAPABILITY_FORENSIC",
                "mutation": 0,
                "scope": "MJN 24-joint + Jake capability compare; BODY Core 23 + Hand 30 drafts",
                "evidence": str(RIG01A),
                "draft": str(DRAFT),
                "status": "PASS",
                "body_canonical_v1": "NOT_LOCKED",
                "next": "NURION-RIG-01B",
            }
        )
    if "NURION-RIG-01B" not in ids:
        ledger["entries"].append(
            {
                "id": "NURION-RIG-01B",
                "type": "JAKE_SKELETON_HIERARCHY_FORENSIC",
                "mutation": 0,
                "scope": "Jake parent hierarchy / rest / axes / L-R symmetry / length ratios",
                "evidence": str(RIG01B),
                "raw": str(RIG01B_RAW),
                "lockCandidate": str(LOCK_CANDIDATE),
                "status": "PASS",
                "body_canonical_v1": "LOCK_CANDIDATE_NOT_LOCKED",
                "next": "HUMAN_REVIEW_LOCK_CANDIDATE_OR_RIG01C_AXIS_POLICY",
            }
        )
    ledger["bodyCanonicalTrack"] = {
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "rig01a": "PASS",
        "rig01b": "PASS",
        "bodyCoreDraft": "ESTABLISHED_23",
        "handExtensionDraft": "ESTABLISHED_30",
        "bodyCanonicalV1": "LOCK_CANDIDATE_NOT_LOCKED",
        "updatedAtUtc": ts,
    }
    LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    write_01a(ts)

    cmd = [
        str(BLENDER),
        "--background",
        "--python",
        str(BLENDER_PY),
        "--",
        "--fbx",
        str(JAKE),
        "--out-json",
        str(RIG01B_RAW),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)

    raw = json.loads(RIG01B_RAW.read_text(encoding="utf-8"))
    summary = summarize_01b(raw)
    cand = write_lock_candidate(ts, summary)

    receipt = {
        "receiptId": f"NURION-RIG-01B_{ts}",
        "stage": "NURION-RIG-01B_JAKE_SKELETON_HIERARCHY_FORENSIC",
        "status": "PASS",
        "fbx": str(JAKE),
        "fbxSha256": sha256(JAKE),
        "rawArtifact": str(RIG01B_RAW),
        "summary": summary,
        "bodyCanonicalV1": "LOCK_CANDIDATE_NOT_LOCKED",
        "lockCandidateArtifact": str(LOCK_CANDIDATE),
        "stillOpenBeforeFullLock": cand["stillOpenBeforeFullLock"],
        "faceProductLock": "DECLARED",
        "talking_status": "GO",
        "next": "Human review of LOCK_CANDIDATE / optional RIG-01C axis+retarget policy",
        "blenderStdoutTail": (proc.stdout or "")[-2000:],
    }
    RIG01B.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    update_ledger(ts)

    print(
        json.dumps(
            {
                "rig01a": str(RIG01A),
                "rig01b": str(RIG01B),
                "lockCandidate": str(LOCK_CANDIDATE),
                "boneCount": summary["boneCount"],
                "roots": summary["rootBones"],
                "torsoRootToHead": summary["torsoRootToHead"],
                "bodyCanonicalV1": "LOCK_CANDIDATE_NOT_LOCKED",
            },
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
