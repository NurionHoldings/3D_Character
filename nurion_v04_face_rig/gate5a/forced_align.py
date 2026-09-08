"""Forced alignment: map pronunciation phonemes onto VAD speech energy."""

from __future__ import annotations

from typing import Dict, List

from nurion_v04_face_rig.gate4.phoneme_map import class_for

from .parameters import GATE5A_PARAMETERS


def _prior_ms(symbol: str) -> float:
    cls = class_for(symbol)
    priors = GATE5A_PARAMETERS["phonemeDurationPriorMs"]
    return float(priors.get(cls, 80))


def forced_align(
    phoneme_tokens: List[Dict],
    energies: List[float],
    centers_ms: List[int],
    speech_segments: List[Dict],
    duration_ms: int,
) -> Dict:
    """
    Deterministic energy-weighted forced alignment.
    SIL tokens consume silence / inter-segment gaps; speech phonemes share speech mass.
    """
    pad_lead = int(GATE5A_PARAMETERS["padLeadMs"])
    pad_trail = int(GATE5A_PARAMETERS["padTrailMs"])
    low_thr = float(GATE5A_PARAMETERS["lowConfidenceThreshold"])

    if not phoneme_tokens:
        return {
            "phonemes": [],
            "lowConfidenceSegments": [],
            "speechSegments": speech_segments,
        }

    # Build speech timeline union
    speech_ms: List[int] = []
    for seg in speech_segments:
        for t in range(int(seg["startMs"]), int(seg["endMs"])):
            speech_ms.append(t)
    if not speech_ms and duration_ms > 0:
        # fallback: treat middle region as speech
        a = pad_lead
        b = max(a + 1, duration_ms - pad_trail)
        speech_ms = list(range(a, b))

    speech_tokens = [t for t in phoneme_tokens if t["symbol"] != "SIL"]
    sil_tokens = [t for t in phoneme_tokens if t["symbol"] == "SIL"]

    weights = [_prior_ms(t["symbol"]) for t in speech_tokens]
    wsum = sum(weights) or 1.0

    # Energy lookup by ms (nearest frame)
    def energy_at(ms: int) -> float:
        if not centers_ms:
            return 0.0
        best_i = 0
        best_d = abs(centers_ms[0] - ms)
        for i, c in enumerate(centers_ms):
            d = abs(c - ms)
            if d < best_d:
                best_d = d
                best_i = i
        return float(energies[best_i])

    # Allocate contiguous spans along speech_ms proportional to prior * local energy boost
    n = len(speech_ms)
    # cumulative allocation in speech index space
    boosted = []
    for i, t in enumerate(speech_tokens):
        # sample energy near proportional position
        frac = (sum(weights[:i]) + weights[i] * 0.5) / wsum
        idx = int(frac * max(0, n - 1))
        e = energy_at(speech_ms[idx]) if n else 0.0
        boosted.append(weights[i] * (0.65 + 0.7 * min(1.0, e / 0.15)))
    bsum = sum(boosted) or 1.0

    aligned_speech: List[Dict] = []
    cursor = 0.0
    for i, tok in enumerate(speech_tokens):
        span = (boosted[i] / bsum) * n
        i0 = int(round(cursor))
        cursor += span
        i1 = int(round(cursor))
        if i1 <= i0:
            i1 = i0 + 1
        i0 = max(0, min(i0, n - 1))
        i1 = max(i0 + 1, min(i1, n))
        start = speech_ms[i0]
        end = speech_ms[i1 - 1] + 1
        # confidence: token prior confidence * energy presence
        e_mean = 0.0
        cnt = 0
        for ms in range(start, end):
            e_mean += energy_at(ms)
            cnt += 1
        e_mean = e_mean / max(1, cnt)
        conf = float(tok.get("confidence", 0.9)) * (0.55 + 0.45 * min(1.0, e_mean / 0.12))
        conf = max(0.05, min(0.99, conf))
        aligned_speech.append(
            {
                "symbol": tok["symbol"],
                "startMs": int(start),
                "endMs": int(end),
                "confidence": round(conf, 4),
                "rule": tok.get("rule", ""),
            }
        )

    # Merge SIL into gaps / leading / trailing
    events: List[Dict] = []
    # leading silence
    first_start = aligned_speech[0]["startMs"] if aligned_speech else pad_lead
    if first_start > 0:
        events.append(
            {
                "symbol": "SIL",
                "startMs": 0,
                "endMs": int(first_start),
                "confidence": 1.0,
                "rule": "LEAD_SILENCE",
            }
        )

    for idx, p in enumerate(aligned_speech):
        events.append(p)
        if idx + 1 < len(aligned_speech):
            gap0 = p["endMs"]
            gap1 = aligned_speech[idx + 1]["startMs"]
            if gap1 > gap0 + 15:
                events.append(
                    {
                        "symbol": "SIL",
                        "startMs": int(gap0),
                        "endMs": int(gap1),
                        "confidence": 0.95,
                        "rule": "INTER_SPEECH_PAUSE",
                    }
                )

    last_end = events[-1]["endMs"] if events else 0
    if last_end < duration_ms:
        events.append(
            {
                "symbol": "SIL",
                "startMs": int(last_end),
                "endMs": int(duration_ms),
                "confidence": 1.0,
                "rule": "TRAIL_SILENCE",
            }
        )

    # If transcript requested explicit SIL count exceeds automatic, keep automatic (deterministic)
    _ = sil_tokens

    # Enforce non-decreasing and min 1ms
    fixed: List[Dict] = []
    for p in events:
        start = int(p["startMs"])
        end = int(p["endMs"])
        if fixed:
            start = max(start, fixed[-1]["endMs"])
        if end <= start:
            end = start + 1
        end = min(end, duration_ms if duration_ms > 0 else end)
        if end <= start and duration_ms > 0:
            continue
        q = dict(p)
        q["startMs"] = start
        q["endMs"] = end
        fixed.append(q)

    low = []
    for p in fixed:
        if p["symbol"] == "SIL":
            continue
        if p["confidence"] < low_thr:
            low.append({"startMs": p["startMs"], "endMs": p["endMs"], "confidence": p["confidence"], "symbol": p["symbol"]})

    return {
        "phonemes": [
            {
                "symbol": p["symbol"],
                "startMs": p["startMs"],
                "endMs": p["endMs"],
                "confidence": p["confidence"],
            }
            for p in fixed
        ],
        "lowConfidenceSegments": low,
        "speechSegments": speech_segments,
        "detail": fixed,
    }
