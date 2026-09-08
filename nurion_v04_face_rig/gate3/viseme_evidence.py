"""Lightweight multiview evidence flags for viseme readability."""

from __future__ import annotations

from typing import Dict, List


def multiview_readability(signatures: Dict[str, List[float]], yaw_deg: List[float]) -> Dict:
    """
    Proxy readability: require REST vs active visemes distinct, and WIDE vs ROUND separable.
    Full image renders are optional; structural signature used for determinism.
    """
    notes = []
    if "REST" not in signatures:
        return {"status": "FAIL", "notes": ["REST signature missing"], "views": yaw_deg}

    rest = signatures["REST"]
    distinct = 0
    for name, sig in signatures.items():
        if name in ("REST", "TONGUE_LIMITED"):
            continue
        sep = max(abs(a - b) for a, b in zip(rest, sig))
        if sep >= 0.005:
            distinct += 1
        else:
            notes.append(f"lowDistinct:{name}:{sep}")

    wide_round_ok = True
    if "WIDE" in signatures and "ROUND" in signatures:
        sep = max(abs(a - b) for a, b in zip(signatures["WIDE"], signatures["ROUND"]))
        wide_round_ok = sep >= 0.005
        if not wide_round_ok:
            notes.append(f"wideRoundCollapse:{sep}")

    ok = distinct >= 4 and wide_round_ok
    return {
        "status": "PASS" if ok else "FAIL",
        "distinctActiveCount": distinct,
        "wideRoundSeparated": wide_round_ok,
        "viewsDeclared": yaw_deg,
        "notes": notes,
    }
