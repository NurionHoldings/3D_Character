"""Coarticulation solver — Anticipation → Target → Hold → Release → Next."""

from __future__ import annotations

from typing import Dict, List, Tuple

from .parameters import GATE4_PARAMETERS
from .phoneme_map import class_for, recipe_for_class


def _clamp01(x: float) -> float:
    return 0.0 if x < 0 else (1.0 if x > 1 else float(x))


def _smoothstep(t: float) -> float:
    t = _clamp01(t)
    return t * t * (3.0 - 2.0 * t)


def enforce_min_hold(phonemes: List[Dict], min_hold_ms: int) -> List[Dict]:
    """Ensure short consonants are not dropped between frames."""
    out = []
    for p in phonemes:
        q = dict(p)
        dur = int(q["endMs"]) - int(q["startMs"])
        cls = class_for(q["symbol"])
        if cls in ("CLOSED", "TEETH", "TONGUE_LIMITED", "RESTRICTED") and dur < min_hold_ms:
            q["endMs"] = int(q["startMs"]) + min_hold_ms
        out.append(q)
    # resolve forward overlaps by pushing later starts
    for i in range(1, len(out)):
        if out[i]["startMs"] < out[i - 1]["endMs"]:
            # allow planned coarticulation overlap up to anticipation window
            max_overlap = int(GATE4_PARAMETERS["anticipationMs"])
            overlap = out[i - 1]["endMs"] - out[i]["startMs"]
            if overlap > max_overlap:
                out[i]["startMs"] = out[i - 1]["endMs"] - max_overlap
        if out[i]["endMs"] <= out[i]["startMs"]:
            out[i]["endMs"] = out[i]["startMs"] + min_hold_ms
    return out


def validate_order(phonemes: List[Dict]) -> Dict:
    order_err = 0
    overlap_conflict = 0
    missing_short = 0
    min_hold = int(GATE4_PARAMETERS["minConsonantHoldMs"])
    for i, p in enumerate(phonemes):
        if p["endMs"] < p["startMs"]:
            order_err += 1
        if i > 0 and p["startMs"] < phonemes[i - 1]["startMs"]:
            order_err += 1
        if i > 0:
            ov = phonemes[i - 1]["endMs"] - p["startMs"]
            if ov > int(GATE4_PARAMETERS["anticipationMs"]) + 5:
                overlap_conflict += 1
        cls = class_for(p["symbol"])
        if cls in ("CLOSED", "TEETH", "TONGUE_LIMITED") and (p["endMs"] - p["startMs"]) < min_hold:
            missing_short += 1
    return {
        "phonemeOrderError": order_err,
        "timelineOverlapConflict": overlap_conflict,
        "missingShortPhoneme": missing_short,
    }


def blend_axes_at_ms(phonemes: List[Dict], t_ms: float) -> Tuple[Dict[str, float], Dict]:
    """
    Mix axis recipes with anticipation/hold/release windows.
    Returns (axes, meta).
    """
    ant = float(GATE4_PARAMETERS["anticipationMs"])
    rel = float(GATE4_PARAMETERS["releaseMs"])
    contrib: List[Tuple[str, float, Dict[str, float]]] = []

    for i, p in enumerate(phonemes):
        s = float(p["startMs"])
        e = float(p["endMs"])
        cls = class_for(p["symbol"])
        recipe = recipe_for_class(cls)
        # look-ahead for rounding anticipation on next ROUND vowel
        next_cls = class_for(phonemes[i + 1]["symbol"]) if i + 1 < len(phonemes) else "REST"
        prep = dict(recipe)
        if next_cls == "ROUND" and cls in ("CLOSED", "TEETH", "TONGUE_LIMITED", "RESTRICTED"):
            prep = dict(recipe)
            prep["lipRound"] = max(float(prep.get("lipRound", 0.0)), 0.35)
        if cls == "CLOSED":
            # seal lips slightly before start
            s_eff = s - ant * 0.6
        else:
            s_eff = s
        e_eff = e + rel * 0.35

        if t_ms < s_eff - ant or t_ms > e_eff + rel:
            continue

        # envelope
        if t_ms < s:
            # anticipation
            w = _smoothstep((t_ms - (s - ant)) / max(ant, 1.0)) * 0.65
        elif t_ms <= e:
            # target/hold
            w = 1.0
        else:
            # release
            w = 1.0 - _smoothstep((t_ms - e) / max(rel, 1.0))
        w *= float(p.get("confidence", 1.0))
        if w > 1e-4:
            contrib.append((cls, w, prep))

    # always have REST baseline
    if not contrib:
        return {}, {"primary": "REST", "sources": [], "weightSum": 0.0}

    # keep top N
    contrib.sort(key=lambda x: -x[1])
    contrib = contrib[: int(GATE4_PARAMETERS["maxBlendSources"])]
    wsum = sum(w for _, w, _ in contrib) or 1.0
    # Coarticulation intentionally overlaps; always renormalize → no overflow when sum≈1 after norm
    axes: Dict[str, float] = {}
    sources = []
    for cls, w, recipe in contrib:
        nw = w / wsum
        sources.append({"class": cls, "weight": round(nw, 5)})
        for k, v in recipe.items():
            axes[k] = axes.get(k, 0.0) + float(v) * nw
    primary = sources[0]["class"] if sources else "REST"
    norm_sum = sum(s["weight"] for s in sources)
    overflow = 0 if abs(norm_sum - 1.0) <= 1e-4 else 1
    return axes, {"primary": primary, "sources": sources, "weightSum": norm_sum, "weightOverflow": overflow, "rawWeightSum": wsum}


def ms_to_frame(ms: float, fps: int) -> int:
    return int(round(float(ms) * float(fps) / 1000.0))


def frame_to_ms(frame: int, fps: int) -> float:
    return float(frame) * 1000.0 / float(fps)
