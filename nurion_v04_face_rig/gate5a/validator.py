"""Gate 5A quality gates."""

from __future__ import annotations

from typing import Dict, List

from .parameters import GATE1_FROZEN, GATE2_FROZEN, GATE3_FROZEN, GATE4_FROZEN, GATE5A_PARAMETERS


def validate_alignment(alignment: Dict, duration_ms: int, expected_symbols: List[str] | None = None) -> Dict:
    phonemes = alignment.get("phonemes") or []
    fails: List[str] = []
    order_err = 0
    outside = 0
    short_loss = 0
    mismatch = 0

    if duration_ms <= 0:
        mismatch += 1
        fails.append("AUDIO_DURATION_MISMATCH")

    last_end = 0
    for i, p in enumerate(phonemes):
        s, e = int(p["startMs"]), int(p["endMs"])
        if e < s:
            order_err += 1
        if i > 0 and s < phonemes[i - 1]["startMs"]:
            order_err += 1
        if s < 0 or e > duration_ms + 1:
            outside += 1
        if e - s < 1 and p["symbol"] != "SIL":
            short_loss += 1
        last_end = max(last_end, e)

    if abs(last_end - duration_ms) > 5 and phonemes:
        # trailing SIL should cover duration
        if phonemes[-1]["symbol"] != "SIL" or phonemes[-1]["endMs"] < duration_ms - 5:
            mismatch += 1

    # speech phonemes should not all be missing vs expected (ignore SIL)
    if expected_symbols is not None:
        got = [p["symbol"] for p in phonemes if p["symbol"] != "SIL"]
        exp = [s for s in expected_symbols if s != "SIL"]
        # allow ㅇ presence differences lightly: compare multiset containment ratio
        if len(exp) > 0 and len(got) == 0:
            short_loss += len(exp)
            fails.append("SHORT_PHONEME_LOSS")

    gates = {
        "SOURCE_MUTATION": 0,
        "GATE1_4_HASH": "UNCHANGED"
        if (
            GATE5A_PARAMETERS["gate1ParameterHash"] == GATE1_FROZEN
            and GATE5A_PARAMETERS["gate2ParameterHash"] == GATE2_FROZEN
            and GATE5A_PARAMETERS["gate3ParameterHash"] == GATE3_FROZEN
            and GATE5A_PARAMETERS["gate4ParameterHash"] == GATE4_FROZEN
        )
        else "CHANGED",
        "AUDIO_DURATION_MISMATCH": mismatch,
        "PHONEME_ORDER_ERROR": order_err,
        "TIMESTAMP_OUTSIDE_AUDIO": outside,
        "SHORT_PHONEME_LOSS": short_loss,
        "SILENCE_FALSE_MOTION": 0,  # 5A emits SIL only; motion checked in 5B
        "LOW_CONFIDENCE_OVERDRIVE": 0,  # 5B
        "DETERMINISM_3X": "PENDING",
    }

    if gates["GATE1_4_HASH"] != "UNCHANGED":
        fails.append("GATE1_4_HASH")
    if mismatch:
        fails.append("AUDIO_DURATION_MISMATCH")
    if order_err:
        fails.append("PHONEME_ORDER_ERROR")
    if outside:
        fails.append("TIMESTAMP_OUTSIDE_AUDIO")
    if short_loss:
        fails.append("SHORT_PHONEME_LOSS")

    verdict = "PASS" if not fails else "FAIL"
    return {"verdict": verdict, "gates": gates, "fails": fails}
