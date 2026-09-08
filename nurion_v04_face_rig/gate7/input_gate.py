"""Input admission — Gate6 domain grades only."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import CORE_IDS, GATE7_PARAMETERS, STRESS_IDS


BLOCKED = set(GATE7_PARAMETERS["blockedInputs"])


def classify_utterance(uid: str) -> str:
    if uid in CORE_IDS:
        return "SUPPORTED_WITH_FALLBACK"
    if uid in STRESS_IDS:
        return "SUPPORTED_WITH_FALLBACK"
    return "NOT_VALIDATED"


def admit_jobs(timelines: Dict[str, Dict], *, core_only_for_pass: bool = True) -> Tuple[List[str], List[str], List[str]]:
    """
    Returns (core_ids, stress_ids, rejected_ids).
    Rejected = NOT_VALIDATED or missing.
    """
    core, stress, rejected = [], [], []
    for uid in list(timelines.keys()):
        grade = classify_utterance(uid)
        if grade not in GATE7_PARAMETERS["allowedGrades"]:
            rejected.append(uid)
            continue
        if uid in CORE_IDS:
            core.append(uid)
        elif uid in STRESS_IDS:
            stress.append(uid)
        else:
            rejected.append(uid)
    # stable order
    core = [u for u in CORE_IDS if u in core]
    stress = [u for u in STRESS_IDS if u in stress]
    return core, stress, rejected


def assert_no_blocked_flags(flags: List[str]) -> None:
    bad = [f for f in flags if f in BLOCKED]
    if bad:
        raise ValueError(f"Blocked Gate7 inputs: {bad}")
