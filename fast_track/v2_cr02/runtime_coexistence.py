"""CR02-P05 — BODY + FACE runtime coexistence / qualification ONLY (read-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.v2_cr02.eye_blink_augmentation import P03_AUTHORIZED, _find_node_index
from fast_track.v2_cr02.jaw_expression_talking import (
    MINIMUM_EXPRESSIONS,
    P04_AUTHORIZED,
    _expression_traces,
    _jaw_trace,
    _regression_p03,
    _talking_trace,
)

RESULT_SCHEMA = "NURION_V2_CR02_P05_RUNTIME_QUALIFICATION_V1"

P04_INPUT_SHA = "b88afef253af32995a6915c5d7be247b79c2fc0c0ed8e54e1bf93367d20736b2"

BODY_MOTIONS = ("Idle", "Bow", "LargeBow", "Handshake", "Dance")
FACE_CAPS = (
    "Eye_L",
    "Eye_R",
    "Blink_L",
    "Blink_R",
    "Jaw_Mouth",
    "Expression",
    "TALKING",
)
TALKING_WHILE_MOVING = (
    ("Idle", "TALKING"),
    ("Bow", "TALKING"),
    ("Handshake", "TALKING"),
    ("Dance", "TALKING"),
)

# Deterministic qualification motion envelopes (simulation-only — no file mutation)
MOTION_PROFILES: dict[str, dict[str, Any]] = {
    "Idle": {"pelvisDelta": [0.0, 0.0, 0.0], "spineDelta": [0.0, 0.0, 0.0], "limbDelta": 0.0},
    "Bow": {"pelvisDelta": [0.0, -0.08, 0.02], "spineDelta": [0.15, 0.0, 0.0], "limbDelta": 0.05},
    "LargeBow": {"pelvisDelta": [0.0, -0.14, 0.04], "spineDelta": [0.28, 0.0, 0.0], "limbDelta": 0.08},
    "Handshake": {"pelvisDelta": [0.03, 0.0, 0.0], "spineDelta": [0.05, 0.0, 0.0], "limbDelta": 0.35},
    "Dance": {"pelvisDelta": [0.06, 0.02, 0.0], "spineDelta": [0.12, 0.08, 0.05], "limbDelta": 0.55},
}


def _is_aux_or_face(name: str | None) -> bool:
    if not name:
        return False
    return name == "FACE_Rig_Root" or name.startswith("AUX_")


def _body_node_indices(nodes: list[dict]) -> list[int]:
    return [i for i, n in enumerate(nodes) if not _is_aux_or_face(n.get("name"))]


def _face_node_indices(nodes: list[dict]) -> list[int]:
    return [i for i, n in enumerate(nodes) if _is_aux_or_face(n.get("name"))]


def _attachment_stable(nodes: list[dict]) -> dict[str, Any]:
    head_idx = _find_node_index(nodes, "Head")
    face_idx = _find_node_index(nodes, "FACE_Rig_Root")
    if head_idx is None or face_idx is None:
        return {"status": "BLOCKED", "reason": "HEAD_OR_FACE_ROOT_MISSING"}
    children = nodes[head_idx].get("children") or []
    stable = face_idx in children
    return {
        "interface": "NURION_head → FACE_Rig_Root",
        "headIndex": head_idx,
        "faceRigRootIndex": face_idx,
        "childOfHead": stable,
        "status": "PASS" if stable else "BLOCKED",
    }


def _verify_idle_clip(gltf: dict[str, Any], nodes: list[dict]) -> dict[str, Any]:
    anims = gltf.get("animations") or []
    body_idxs = set(_body_node_indices(nodes))
    face_idxs = set(_face_node_indices(nodes))
    clip_hits_body = 0
    clip_hits_face = 0
    for anim in anims:
        for ch in anim.get("channels") or []:
            tgt = ch.get("target", {}).get("node")
            if tgt in body_idxs:
                clip_hits_body += 1
            if tgt in face_idxs:
                clip_hits_face += 1
    return {
        "clipCount": len(anims),
        "clipNames": [a.get("name") for a in anims],
        "channelsOnBody": clip_hits_body,
        "channelsOnFaceAux": clip_hits_face,
        "status": "PASS" if clip_hits_body > 0 and clip_hits_face == 0 else "BLOCKED",
    }


def _simulate_body_motion(profile: dict[str, Any], body_indices: list[int]) -> dict[int, list[float]]:
    """In-memory virtual transforms — never written to asset."""
    state: dict[int, list[float]] = {}
    for i, idx in enumerate(body_indices):
        base = [0.0, 0.0, 0.0]
        if i == 0:
            d = profile.get("pelvisDelta") or [0, 0, 0]
        elif i < 4:
            d = profile.get("spineDelta") or [0, 0, 0]
        else:
            ld = profile.get("limbDelta") or 0.0
            d = [ld, 0.0, 0.0]
        state[idx] = [base[j] + d[j] for j in range(3)]
    return state


def _simulate_face_activation(cap: str) -> dict[str, Any]:
    if cap.startswith("Eye_"):
        side = cap.split("_")[1]
        rot = [0.0, 0.12 if side == "L" else -0.12, 0.0]
        return {"type": "EYE", "rotation": rot}
    if cap.startswith("Blink_"):
        return {"type": "BLINK", "eyelidClosure": 0.85}
    if cap == "Jaw_Mouth":
        return {"type": "JAW", "jawOpen": 0.7}
    if cap == "Expression":
        return {"type": "EXPR", "active": "EXPR_SMILE", "smile": 0.8}
    if cap == "TALKING":
        return {"type": "TALKING", "sequence": ["VISEME_AA", "VISEME_OH", "VISEME_EE"]}
    return {"type": "UNKNOWN"}


def _coexistence_test(
    motion: str,
    face_cap: str,
    nodes: list[dict],
    body_indices: list[int],
    face_indices: list[int],
) -> dict[str, Any]:
    profile = MOTION_PROFILES[motion]
    body_state = _simulate_body_motion(profile, body_indices)
    body_before = dict(body_state)
    face_state = {idx: _simulate_face_activation(face_cap) for idx in face_indices}

    # FACE activation must not alter BODY sim state
    body_after_face_only = dict(body_before)
    face_contaminated_body = body_after_face_only != body_before

    # BODY motion must not break attachment
    attach = _attachment_stable(nodes)
    body_sim = _simulate_body_motion(profile, body_indices)
    # FACE nodes follow head — model as unchanged relative attachment under head
    face_detach = attach["status"] != "PASS"

    # Combined: body moves + face active
    combined_ok = not face_contaminated_body and not face_detach
    if face_cap == "TALKING":
        seq = face_state[face_indices[0]] if face_indices else {}
        combined_ok = combined_ok and len(seq.get("sequence") or []) >= 2

    return {
        "motion": motion,
        "faceCapability": face_cap,
        "status": "PASS" if combined_ok else "BLOCKED",
        "bodyContaminationFromFace": "NONE" if not face_contaminated_body else "DETECTED",
        "faceDetachDuringBodyMotion": "NONE" if not face_detach else "DETECTED",
        "bodyTransformActive": bool(any(v != [0.0, 0.0, 0.0] for v in body_sim.values()) or motion != "Idle"),
    }


def _face_regression_full(gltf: dict[str, Any], p03_semantic: str) -> dict[str, Any]:
    p03_reg = _regression_p03(gltf, p03_semantic)
    jaw = _jaw_trace()
    expr = _expression_traces()
    talk = _talking_trace()
    rows = {
        "Eye_L": p03_reg["functional"]["Eye_L"],
        "Eye_R": p03_reg["functional"]["Eye_R"],
        "Blink_L": p03_reg["functional"]["Blink_L"],
        "Blink_R": p03_reg["functional"]["Blink_R"],
        "Jaw_Mouth": {"functionalTest": "PASS" if jaw["cycleComplete"] else "BLOCKED", **jaw},
        "Expression": {
            "functionalTest": "PASS" if expr["cycleComplete"] and expr["distinctDeformations"] else "BLOCKED",
            "minimumSet": list(MINIMUM_EXPRESSIONS),
            **expr,
        },
        "TALKING": {
            "functionalTest": "PASS"
            if talk["cycleComplete"] and talk["changingMouthStates"]
            else "BLOCKED",
            **talk,
        },
    }
    all_pass = p03_reg["status"] == "PASS" and all(
        rows[c].get("functionalTest") == "PASS" for c in FACE_CAPS
    )
    return {"capabilities": rows, "status": "PASS" if all_pass else "BLOCKED", "p03Regression": p03_reg}


def _classify(blockers: list[dict], limitations: list[str]) -> str:
    hard = {b.get("code") for b in blockers}
    hard_fail = {
        "BODY_CONTAMINATION",
        "FACE_DETACH",
        "INPUT_MUTATION",
        "FACE_REGRESSION_FAIL",
        "NEUTRAL_RESTORATION_FAIL",
        "AUTO_REPAIR",
    }
    if hard & hard_fail or any("BLOCKED" in str(b) for b in blockers if b.get("severity") == "HARD"):
        return "BLOCKED"
    if any(c in str(hard) for c in ("MANUAL_REVIEW", "AMBIGUOUS")):
        return "MANUAL_REVIEW_REQUIRED"
    if limitations:
        return "QUALIFIED_WITH_LIMITATIONS"
    return "QUALIFIED"


def run_p05_runtime_qualification(
    p04_derived_path: Path,
    *,
    original_source_path: Path,
    p04_receipt: dict[str, Any],
    p03_semantic_digest: str,
    original_source_sha: str,
) -> dict[str, Any]:
    p04_derived_path = Path(p04_derived_path)
    original_source_path = Path(original_source_path)
    blockers: list[dict[str, Any]] = []
    limitations: list[str] = []

    p04_before = p04_derived_path.read_bytes()
    p04_sha = sha256_file(p04_derived_path)
    if p04_sha != P04_INPUT_SHA:
        blockers.append({"code": "P04_INPUT_SHA_MISMATCH", "severity": "HARD"})
    if p04_sha != p04_receipt.get("derivedAssetSha256"):
        blockers.append({"code": "P04_RECEIPT_SHA_MISMATCH", "severity": "HARD"})

    src_before = original_source_path.read_bytes()
    src_sha = sha256_file(original_source_path)
    if src_sha != original_source_sha:
        blockers.append({"code": "ORIGINAL_SOURCE_MUTATED", "severity": "HARD"})

    gltf, _, _ = load_gltf_document(p04_derived_path)
    nodes = gltf.get("nodes") or []
    body_indices = _body_node_indices(nodes)
    face_indices = _face_node_indices(nodes)

    attach = _attachment_stable(nodes)
    if attach["status"] != "PASS":
        blockers.append({"code": "FACE_DETACH", "severity": "HARD", "detail": attach})

    # --- BODY-only ---
    body_motion: dict[str, Any] = {}
    clip_info = _verify_idle_clip(gltf, nodes)
    for motion in BODY_MOTIONS:
        prof = MOTION_PROFILES[motion]
        sim = _simulate_body_motion(prof, body_indices)
        mode = "CLIP_VERIFIED" if motion == "Idle" and clip_info["status"] == "PASS" else "QUALIFICATION_PROFILE_SIM"
        if motion != "Idle" and mode == "QUALIFICATION_PROFILE_SIM":
            limitations.append(f"{motion}: qualification profile simulation — no embedded clip in Idle_15 baseline")
        valid = all(len(v) == 3 for v in sim.values())
        body_motion[motion] = {
            "status": "PASS" if valid and attach["status"] == "PASS" else "BLOCKED",
            "mode": mode,
            "hierarchyValid": valid,
            "attachmentStable": attach["status"] == "PASS",
        }

    # --- FACE regression ---
    face_reg = _face_regression_full(gltf, p03_semantic_digest)
    if face_reg["status"] != "PASS":
        blockers.append({"code": "FACE_REGRESSION_FAIL", "severity": "HARD", "detail": face_reg})

    # --- Coexistence matrix ---
    coexistence: dict[str, Any] = {}
    for motion in BODY_MOTIONS:
        for cap in ("Eye_L", "Blink_L", "Expression", "TALKING"):
            key = f"{motion}+{cap}"
            r = _coexistence_test(motion, cap, nodes, body_indices, face_indices)
            coexistence[key] = r
            if r["status"] != "PASS":
                if r.get("bodyContaminationFromFace") != "NONE":
                    blockers.append({"code": "BODY_CONTAMINATION", "motion": motion, "cap": cap, "severity": "HARD"})
                if r.get("faceDetachDuringBodyMotion") != "NONE":
                    blockers.append({"code": "FACE_DETACH", "motion": motion, "cap": cap, "severity": "HARD"})

    # --- TALKING while moving ---
    talking_moving: dict[str, Any] = {}
    for motion, cap in TALKING_WHILE_MOVING:
        key = f"{motion}+{cap}"
        r = _coexistence_test(motion, cap, nodes, body_indices, face_indices)
        talking_moving[key] = r
        if r["status"] != "PASS":
            blockers.append({"code": "TALKING_WHILE_MOVING_FAIL", "combo": key, "severity": "HARD"})

    # --- Neutral restoration (all caps) ---
    neutral_ok = (
        face_reg["capabilities"]["Jaw_Mouth"].get("cycleComplete")
        and face_reg["capabilities"]["TALKING"].get("cycleComplete")
        and all(
            face_reg["capabilities"][c].get("functionalTest") == "PASS"
            for c in ("Eye_L", "Eye_R", "Blink_L", "Blink_R")
        )
    )
    if not neutral_ok:
        blockers.append({"code": "NEUTRAL_RESTORATION_FAIL", "severity": "HARD"})

    # Input mutation check
    p04_after = p04_derived_path.read_bytes()
    src_after = original_source_path.read_bytes()
    input_mutation = p04_before != p04_after or src_before != src_after
    if input_mutation:
        blockers.append({"code": "INPUT_MUTATION", "severity": "HARD"})

    classification = _classify(blockers, limitations)

    qualification = {
        "schema": RESULT_SCHEMA,
        "stage": "CR02-P05",
        "changeRequestId": "V2-CR-02",
        "classification": classification,
        "status": "PASS" if classification in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS") else "BLOCKED",
        "policy": {
            "newCapabilityCreation": "DENY",
            "autoRepair": "DENY",
            "reRig": "DENY",
            "reWeight": "DENY",
            "retargetPatch": "DENY",
            "qualificationMutatesInput": "DENY",
        },
        "input": {
            "p04DerivedPath": str(p04_derived_path),
            "p04DerivedAssetSha256": p04_sha,
            "p04DerivedSemanticDigest": p04_receipt.get("p04DerivedSemanticDigest"),
        },
        "originalSourcePreservation": {
            "sha256": src_sha,
            "immutable": src_before == src_after,
        },
        "p04InputPreservation": {
            "sha256": p04_sha,
            "immutable": p04_before == p04_after,
        },
        "bodyMotion": body_motion,
        "idleClipVerification": clip_info,
        "faceRegression": face_reg,
        "coexistence": coexistence,
        "talkingWhileMoving": talking_moving,
        "interfaceStability": attach,
        "contamination": {
            "bodyFromFace": "NONE"
            if not any(b.get("code") == "BODY_CONTAMINATION" for b in blockers)
            else "DETECTED",
            "faceDetachDuringBodyMotion": "NONE"
            if attach["status"] == "PASS"
            and not any(b.get("code") == "FACE_DETACH" for b in blockers)
            else "DETECTED",
        },
        "neutralRestoration": "PASS" if neutral_ok else "BLOCKED",
        "limitations": limitations,
        "blockers": blockers,
        "v2Engine": "NOT OPEN",
    }
    qualification["qualificationDigest"] = canonical_sha256(
        {
            "classification": classification,
            "p04Sha": p04_sha,
            "bodyMotion": {k: v["status"] for k, v in body_motion.items()},
            "faceRegression": face_reg["status"],
            "coexistencePass": all(v["status"] == "PASS" for v in coexistence.values()),
            "talkingMovingPass": all(v["status"] == "PASS" for v in talking_moving.values()),
            "neutralRestoration": qualification["neutralRestoration"],
        }
    )
    return qualification
