"""ADAPT-06 release outcome classifier — fail-closed, no repair."""

from __future__ import annotations

from typing import Any


def classify_release(report: dict[str, Any], *, force_flags: dict[str, Any] | None = None) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = list(report.get("blockers") or [])

    if force_flags.get("notReleaseEligible"):
        return {
            "finalClassification": "BLOCKED",
            "blockers": blockers + [{"code": "NOT_RELEASE_ELIGIBLE", "message": "forced ineligible"}],
            "policy": "Release requires QUALIFIED or QUALIFIED_WITH_LIMITATIONS",
        }

    qual_class = report.get("qualificationClassification")
    if qual_class not in ("QUALIFIED", "QUALIFIED_WITH_LIMITATIONS"):
        blockers.append({"code": "NOT_RELEASE_ELIGIBLE", "message": qual_class})

    consumer = report.get("consumerPackage") or {}
    if not consumer.get("complete"):
        blockers.append({"code": "CONSUMER_PACKAGE_INCOMPLETE", "message": "missing manifest entries"})

    runtime = report.get("runtimeBindingIntegrity") or {}
    if runtime.get("status") != "PASS":
        blockers.append({"code": "RUNTIME_BINDING_INTEGRITY_FAIL", "message": "runtime binding"})

    for section, key in (
        ("bodySemanticBinding", "bodyQualification"),
        ("faceBodyAttachmentPreservation", "faceAttachmentQualification"),
        ("motionLibraryCompatibility", "motionCompatibility"),
    ):
        sec = report.get(section) or {}
        if isinstance(sec, dict) and sec.get("status") not in (None, "PASS"):
            blockers.append({"code": f"{key.upper()}_FAIL", "message": section})

    face_bind = report.get("faceEyeTalkingBinding") or {}
    for sub in ("face", "eye", "talking"):
        if (face_bind.get(sub) or {}).get("status") not in (None, "PASS"):
            blockers.append({"code": f"FACE_EYE_TALKING_{sub.upper()}_FAIL", "message": sub})

    state_beh = report.get("runtimeStateBehaviorBinding") or {}
    for sub in ("runtimeState", "behavior"):
        if (state_beh.get(sub) or {}).get("status") not in (None, "PASS"):
            blockers.append({"code": f"RUNTIME_{sub.upper()}_FAIL", "message": sub})

    if blockers:
        return {
            "finalClassification": "BLOCKED",
            "blockers": blockers,
            "policy": "Fail-closed — no AUTO REPAIR",
        }

    if qual_class == "QUALIFIED_WITH_LIMITATIONS":
        return {
            "finalClassification": "RELEASED_WITH_LIMITATIONS",
            "blockers": [],
            "policy": "Released with declared limitations",
        }

    return {
        "finalClassification": "RELEASED",
        "blockers": [],
        "policy": "Qualified candidate sealed as NURION_ADAPTED_CHARACTER_RELEASE_V1",
    }
