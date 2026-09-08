"""Evidence-based adaptation classification for ADAPT-01."""

from __future__ import annotations

from typing import Any


def _status(cap: dict[str, Any], key: str = "status") -> str:
    return str(cap.get(key) or "NOT_DETECTED")


def classify_adaptation(report: dict[str, Any]) -> dict[str, Any]:
    """
    Deterministic classification from inspection evidence.
    Does not promote compatibility from a single node name alone.
    """
    issues = list(report.get("issues") or [])
    blockers = [i for i in issues if i.get("severity") == "BLOCKER"]
    if blockers or report.get("parseStatus") == "FAILED":
        return {
            "adaptationClass": "BLOCKED",
            "body": "INCOMPATIBLE",
            "face": "UNKNOWN",
            "eye": "UNKNOWN",
            "jaw": "UNKNOWN",
            "talking": "UNKNOWN",
            "rationale": [b.get("code") or b.get("message") for b in blockers]
            or ["parse_or_structural_blocker"],
            "evidenceBased": True,
        }

    sem = report.get("semanticBoneCandidates") or {}
    cands = sem.get("candidates") or {}

    def detected(role: str, min_conf: float = 0.5) -> bool:
        block = cands.get(role) or {}
        if block.get("status") not in ("DETECTED", "AMBIGUOUS"):
            return False
        sel = block.get("selected") or {}
        if block.get("status") == "AMBIGUOUS" and float(sel.get("confidence") or 0) < 0.65:
            return False
        return float(sel.get("confidence") or 0) >= min_conf

    core_body = ["pelvis", "spine", "chest", "neck", "head", "thigh_L", "thigh_R", "upperArm_L", "upperArm_R"]
    body_hits = sum(1 for r in core_body if detected(r))
    skel = report.get("skeleton") or {}
    has_skin = bool(skel.get("skinsDetected"))
    has_joints = int(skel.get("jointCount") or 0) >= 8
    mesh_ok = int((report.get("meshes") or {}).get("count") or 0) >= 1

    if not mesh_ok:
        return {
            "adaptationClass": "BLOCKED",
            "body": "INCOMPATIBLE",
            "face": "MISSING",
            "eye": "MISSING",
            "jaw": "MISSING",
            "talking": "MISSING",
            "rationale": ["no_usable_mesh"],
            "evidenceBased": True,
        }

    body_compatible = has_skin and has_joints and body_hits >= 6
    body_partial = has_skin and has_joints and body_hits >= 3

    face_cap = report.get("faceCapabilities") or {}
    facial_bones = _status(face_cap.get("facialBones") or {})
    blend = report.get("expressionCapabilities") or {}
    blend_detected = _status(blend.get("blendshapes") or {}) == "DETECTED"
    blend_count = int(blend.get("blendshapeCount") or 0)

    eye = report.get("eyeCapabilities") or {}
    eye_l = _status(eye.get("leftEyeBone") or {}) == "DETECTED"
    eye_r = _status(eye.get("rightEyeBone") or {}) == "DETECTED"
    jaw = report.get("jawCapabilities") or {}
    jaw_ok = _status(jaw.get("bone") or {}) == "DETECTED"
    talking = report.get("talkingCapabilities") or {}
    viseme = _status(talking.get("visemeCandidates") or {}) == "DETECTED"

    face_status = "MISSING"
    if facial_bones == "DETECTED" or (blend_detected and blend_count >= 8):
        face_status = "COMPATIBLE" if (blend_detected and blend_count >= 20) or facial_bones == "DETECTED" else "PARTIAL"
    elif blend_detected:
        face_status = "PARTIAL"

    eye_status = "COMPATIBLE" if eye_l and eye_r else ("PARTIAL" if eye_l or eye_r else "MISSING")
    jaw_status = "COMPATIBLE" if jaw_ok else "MISSING"
    talking_status = "COMPATIBLE" if viseme else "MISSING"

    rationale: list[str] = []
    if not body_compatible and not body_partial:
        cls = "BLOCKED" if not has_skin else "CLASS_D"
        rationale.append(f"body_hits={body_hits}")
        if not has_skin:
            rationale.append("no_skin")
        return {
            "adaptationClass": cls,
            "body": "INCOMPATIBLE" if not has_skin else "PARTIAL",
            "face": face_status,
            "eye": eye_status,
            "jaw": jaw_status,
            "talking": talking_status,
            "rationale": rationale or ["insufficient_body_semantics"],
            "evidenceBased": True,
            "bodyCoreHits": body_hits,
        }

    body_label = "COMPATIBLE" if body_compatible else "PARTIAL"
    rationale.append(f"body_hits={body_hits}")
    rationale.append(f"blendshapes={blend_count}")
    rationale.append(f"eyes={eye_l}/{eye_r}")
    rationale.append(f"jaw={jaw_ok}")
    rationale.append(f"viseme={viseme}")

    # CLASS selection
    if body_compatible and face_status == "COMPATIBLE" and eye_status == "COMPATIBLE" and jaw_status == "COMPATIBLE":
        cls = "CLASS_A"
        rationale.append("near_complete_capabilities")
    elif body_compatible and face_status in ("COMPATIBLE", "PARTIAL") and eye_status != "MISSING":
        cls = "CLASS_B"
        rationale.append("body_ok_face_adaptation")
    elif body_compatible or (body_partial and body_hits >= 6):
        if face_status == "MISSING" or eye_status == "MISSING" or jaw_status == "MISSING":
            cls = "CLASS_C"
            rationale.append("body_ok_needs_face_eye_jaw_helper")
        else:
            cls = "CLASS_B"
    else:
        cls = "CLASS_D"
        rationale.append("major_adaptation")

    return {
        "adaptationClass": cls,
        "body": body_label,
        "face": face_status,
        "eye": eye_status,
        "jaw": jaw_status,
        "talking": talking_status,
        "rationale": rationale,
        "evidenceBased": True,
        "bodyCoreHits": body_hits,
    }
