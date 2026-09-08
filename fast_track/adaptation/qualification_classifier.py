"""ADAPT-05 qualification classifier — observe → verify → classify (no repair)."""

from __future__ import annotations

from typing import Any

OUTCOMES = (
    "QUALIFIED",
    "QUALIFIED_WITH_LIMITATIONS",
    "MANUAL_REVIEW_REQUIRED",
    "BLOCKED",
)


def classify_qualification(
    sections: dict[str, dict[str, Any]],
    *,
    force_flags: dict[str, Any] | None = None,
) -> dict[str, Any]:
    force_flags = force_flags or {}
    blockers: list[dict[str, Any]] = []
    limitations: list[dict[str, Any]] = []
    manual: list[dict[str, Any]] = []

    for name, sec in sections.items():
        if not isinstance(sec, dict):
            continue
        if sec.get("status") == "BLOCKED":
            for b in sec.get("blockers") or [{"code": f"{name}_BLOCKED"}]:
                blockers.append({"section": name, **(b if isinstance(b, dict) else {"code": str(b)})})
        if sec.get("talkingClassification") == "TALKING_LIMITED":
            limitations.append({"section": name, "code": "TALKING_LIMITED", "permittedByRuntimeContract": True})
        if sec.get("status") == "MANUAL_REVIEW_REQUIRED":
            manual.append({"section": name})

    if force_flags.get("manualReviewRequired"):
        manual.append({"code": "MANUAL_REVIEW_FORCED", "message": "fixture-driven manual review"})
    if force_flags.get("hideFailedCapabilityAsLimitation"):
        blockers.append(
            {
                "code": "LIMITATION_ABUSE_DENIED",
                "message": "QUALIFIED_WITH_LIMITATIONS must not hide required capability failure",
            }
        )

    if blockers:
        classification = "BLOCKED"
    elif manual:
        classification = "MANUAL_REVIEW_REQUIRED"
    elif limitations:
        classification = "QUALIFIED_WITH_LIMITATIONS"
    else:
        classification = "QUALIFIED"

    return {
        "finalClassification": classification,
        "blockers": blockers,
        "limitations": limitations,
        "manualReviewItems": manual,
        "policy": "observe → verify → classify → qualify or reject; no fix-then-PASS",
        "autoRepair": "DENY",
    }
