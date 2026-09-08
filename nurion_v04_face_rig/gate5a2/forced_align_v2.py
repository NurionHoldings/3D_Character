"""Gate5A.2 forced alignment — class-aware, duration-capped, breath-excluding."""

from __future__ import annotations

from typing import Dict, List

from nurion_v04_face_rig.gate4.phoneme_map import class_for

from .breath import classify_energy_regions
from .parameters import GATE5A2_PARAMETERS


def _prior_ms(symbol: str) -> float:
    cls = class_for(symbol)
    return float(GATE5A2_PARAMETERS["phonemeDurationPriorMs"].get(cls, 80))


def _min_ms(symbol: str) -> int:
    return int(GATE5A2_PARAMETERS["phonemeDurationMinMs"].get(class_for(symbol), 30))


def _max_ms(symbol: str) -> int:
    return int(GATE5A2_PARAMETERS["phonemeDurationMaxMs"].get(class_for(symbol), 300))


def _energy_dep(symbol: str) -> float:
    return float(GATE5A2_PARAMETERS["energyDependence"].get(class_for(symbol), 0.5))


def forced_align_v2(
    phoneme_tokens: List[Dict],
    energies: List[float],
    centers_ms: List[int],
    speech_segments: List[Dict],
    duration_ms: int,
) -> Dict:
    pad_lead = int(GATE5A2_PARAMETERS["padLeadMs"])
    pad_trail = int(GATE5A2_PARAMETERS["padTrailMs"])
    low_thr = float(GATE5A2_PARAMETERS["lowConfidenceThreshold"])

    regions = classify_energy_regions(energies, centers_ms, speech_segments)
    speech_ms = list(regions["speechMs"])
    breath_segments = list(regions["breathSegments"])

    if not phoneme_tokens:
        return {"phonemes": [], "lowConfidenceSegments": [], "speechSegments": speech_segments, "breathSegments": breath_segments}

    if not speech_ms and duration_ms > 0:
        a = pad_lead
        b = max(a + 1, duration_ms - pad_trail)
        # exclude breath from fallback
        breath_set = set()
        for bseg in breath_segments:
            for t in range(int(bseg["startMs"]), int(bseg["endMs"])):
                breath_set.add(t)
        speech_ms = [t for t in range(a, b) if t not in breath_set]

    speech_tokens = [t for t in phoneme_tokens if t["symbol"] != "SIL"]

    def energy_at(ms: int) -> float:
        if not centers_ms:
            return 0.0
        best_i = min(range(len(centers_ms)), key=lambda i: abs(centers_ms[i] - ms))
        return float(energies[best_i])

    n = len(speech_ms)
    w_all = sum(_prior_ms(t["symbol"]) for t in speech_tokens) or 1.0
    weights = []
    for i, tok in enumerate(speech_tokens):
        prior = _prior_ms(tok["symbol"])
        dep = _energy_dep(tok["symbol"])
        w_prefix = sum(_prior_ms(speech_tokens[j]["symbol"]) for j in range(i))
        idx = int(((w_prefix + prior * 0.5) / w_all) * max(0, n - 1)) if n else 0
        e = energy_at(speech_ms[idx]) if n else 0.0
        # class-aware boost: vowels follow energy; closed/restricted barely
        boost = (1.0 - dep) + dep * (0.55 + 0.9 * min(1.0, e / 0.14))
        weights.append(max(1e-3, prior * boost))

    wsum = sum(weights) or 1.0
    raw_spans: List[Dict] = []
    cursor = 0.0
    for i, tok in enumerate(speech_tokens):
        span = (weights[i] / wsum) * n
        i0 = int(round(cursor))
        cursor += span
        i1 = int(round(cursor))
        if i1 <= i0:
            i1 = i0 + 1
        i0 = max(0, min(i0, max(0, n - 1)))
        i1 = max(i0 + 1, min(i1, n)) if n else 1
        if not n:
            start, end = pad_lead, pad_lead + _min_ms(tok["symbol"])
        else:
            start = speech_ms[i0]
            end = speech_ms[min(i1 - 1, n - 1)] + 1
        raw_spans.append({"token": tok, "startMs": int(start), "endMs": int(end)})

    # Enforce min/max duration by iterative clamp + redistribute slack into vowels
    for _ in range(3):
        for sp in raw_spans:
            sym = sp["token"]["symbol"]
            dur = sp["endMs"] - sp["startMs"]
            mn, mx = _min_ms(sym), _max_ms(sym)
            if dur < mn:
                sp["endMs"] = sp["startMs"] + mn
            elif dur > mx:
                sp["endMs"] = sp["startMs"] + mx
        # resolve overlaps / gaps forward
        for i in range(1, len(raw_spans)):
            if raw_spans[i]["startMs"] < raw_spans[i - 1]["endMs"]:
                raw_spans[i]["startMs"] = raw_spans[i - 1]["endMs"]
            if raw_spans[i]["endMs"] <= raw_spans[i]["startMs"]:
                raw_spans[i]["endMs"] = raw_spans[i]["startMs"] + _min_ms(raw_spans[i]["token"]["symbol"])
        # clamp to duration
        for sp in raw_spans:
            sp["startMs"] = max(0, min(sp["startMs"], max(0, duration_ms - 1)))
            sp["endMs"] = max(sp["startMs"] + 1, min(sp["endMs"], duration_ms))

    # If last exceeds speech mass end, pull back
    if speech_ms and raw_spans:
        last_speech = speech_ms[-1] + 1
        if raw_spans[-1]["endMs"] > last_speech:
            # shrink from the end preferentially on vowels already at max — simple pull
            overflow = raw_spans[-1]["endMs"] - last_speech
            raw_spans[-1]["endMs"] = last_speech
            if raw_spans[-1]["endMs"] <= raw_spans[-1]["startMs"]:
                raw_spans[-1]["startMs"] = max(0, raw_spans[-1]["endMs"] - _min_ms(raw_spans[-1]["token"]["symbol"]))

    aligned_speech: List[Dict] = []
    for sp in raw_spans:
        tok = sp["token"]
        start, end = int(sp["startMs"]), int(sp["endMs"])
        cls = class_for(tok["symbol"])
        dep = _energy_dep(tok["symbol"])
        e_mean = 0.0
        cnt = 0
        for ms in range(start, max(start + 1, end)):
            e_mean += energy_at(ms)
            cnt += 1
        e_mean /= max(1, cnt)
        base = float(tok.get("confidence", 0.9))
        # unvoiced/closed: do not treat low energy as low confidence alone
        if cls in ("CLOSED", "RESTRICTED", "TONGUE_LIMITED"):
            conf = base * (0.75 + 0.2 * min(1.0, e_mean / 0.10))
        elif cls == "TEETH":
            conf = base * (0.65 + 0.3 * min(1.0, e_mean / 0.11))
        else:
            conf = base * (0.50 + 0.5 * min(1.0, e_mean / 0.12))
        # long monopoly in low energy → reduce confidence
        dur = end - start
        if dur > _max_ms(tok["symbol"]) * 0.9 and e_mean < 0.05:
            conf *= 0.55
        conf = max(0.05, min(0.99, conf))
        aligned_speech.append(
            {
                "symbol": tok["symbol"],
                "startMs": start,
                "endMs": end,
                "confidence": round(conf, 4),
                "rule": tok.get("rule", ""),
                "class": cls,
            }
        )

    # Insert SIL for lead/trail/gaps + breath segments
    events: List[Dict] = []
    first_start = aligned_speech[0]["startMs"] if aligned_speech else pad_lead
    if first_start > 0:
        events.append({"symbol": "SIL", "startMs": 0, "endMs": int(first_start), "confidence": 1.0, "rule": "LEAD_SILENCE"})

    for idx, p in enumerate(aligned_speech):
        events.append(p)
        if idx + 1 < len(aligned_speech):
            gap0, gap1 = p["endMs"], aligned_speech[idx + 1]["startMs"]
            if gap1 > gap0 + 10:
                events.append(
                    {
                        "symbol": "SIL",
                        "startMs": int(gap0),
                        "endMs": int(gap1),
                        "confidence": 0.95,
                        "rule": "INTER_SPEECH_PAUSE",
                    }
                )

    # Overlay breath as SIL (may split) — merge into timeline without phoneme assignment
    for bseg in breath_segments:
        events.append(
            {
                "symbol": "SIL",
                "startMs": int(bseg["startMs"]),
                "endMs": int(bseg["endMs"]),
                "confidence": 1.0,
                "rule": "BREATH_AS_SILENCE",
            }
        )

    last_end = max((e["endMs"] for e in events), default=0)
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

    # Sort and flatten overlapping SIL/speech: speech wins inside its window; breath SIL carves speech
    events.sort(key=lambda e: (e["startMs"], 0 if e["symbol"] != "SIL" else 1, e["endMs"]))
    fixed: List[Dict] = []
    for p in events:
        start, end = int(p["startMs"]), int(p["endMs"])
        if end <= start:
            continue
        if not fixed:
            fixed.append(dict(p, startMs=start, endMs=end))
            continue
        prev = fixed[-1]
        if p["symbol"] == "SIL" and prev["symbol"] != "SIL":
            # carve: trim prev if breath overlaps
            if start < prev["endMs"] and p.get("rule") == "BREATH_AS_SILENCE":
                if start > prev["startMs"]:
                    prev["endMs"] = start
                else:
                    fixed.pop()
                fixed.append(dict(p, startMs=start, endMs=end))
                continue
        if start < prev["endMs"]:
            if p["symbol"] == "SIL" and prev["symbol"] == "SIL":
                prev["endMs"] = max(prev["endMs"], end)
                continue
            start = prev["endMs"]
        if end <= start:
            continue
        q = dict(p)
        q["startMs"] = start
        q["endMs"] = end
        fixed.append(q)

    # final chain repair
    out = []
    for p in fixed:
        start, end = int(p["startMs"]), int(p["endMs"])
        if out:
            start = max(start, out[-1]["endMs"])
        if end <= start:
            if p["symbol"] == "SIL":
                continue
            end = start + _min_ms(p["symbol"])
        end = min(end, duration_ms)
        if end <= start:
            continue
        out.append(
            {
                "symbol": p["symbol"],
                "startMs": start,
                "endMs": end,
                "confidence": float(p["confidence"]),
                "rule": p.get("rule", ""),
            }
        )
    if out and out[-1]["endMs"] < duration_ms:
        out.append({"symbol": "SIL", "startMs": out[-1]["endMs"], "endMs": duration_ms, "confidence": 1.0, "rule": "TRAIL_SILENCE"})

    low = [
        {"startMs": p["startMs"], "endMs": p["endMs"], "confidence": p["confidence"], "symbol": p["symbol"]}
        for p in out
        if p["symbol"] != "SIL" and p["confidence"] < low_thr
    ]
    breath_as_phoneme = 0  # by construction breath → SIL

    return {
        "phonemes": [{"symbol": p["symbol"], "startMs": p["startMs"], "endMs": p["endMs"], "confidence": p["confidence"]} for p in out],
        "lowConfidenceSegments": low,
        "speechSegments": speech_segments,
        "breathSegments": breath_segments,
        "breathAsPhoneme": breath_as_phoneme,
        "detail": out,
    }
