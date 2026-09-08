"""FAST-04D — Coarticulation, jaw envelope, weight normalization."""

from __future__ import annotations

import math
from typing import Iterable

import numpy as np

from fast_track.runtime.narration_timeline import VisemeCue, read_wav_mono, rms_envelope

MOUTH_KEYS = (
    "PRES_JawOpen",
    "PRES_Viseme_A",
    "PRES_Viseme_E",
    "PRES_Viseme_O",
    "PRES_Viseme_M",
)

ACTUATOR_FROM_CUE = {
    "JAWOPEN": "PRES_JawOpen",
    "JAW": "PRES_JawOpen",
    "A": "PRES_Viseme_A",
    "E": "PRES_Viseme_E",
    "O": "PRES_Viseme_O",
    "M": "PRES_Viseme_M",
}


def _smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def cue_weight_at(cue: VisemeCue, t: float, attack_frac: float = 0.25, release_frac: float = 0.25) -> float:
    if t < cue.start or t > cue.end:
        return 0.0
    dur = max(cue.end - cue.start, 1e-6)
    rel = (t - cue.start) / dur
    if rel <= attack_frac:
        env = _smoothstep(rel / max(attack_frac, 1e-6))
    elif rel >= 1.0 - release_frac:
        env = _smoothstep((1.0 - rel) / max(release_frac, 1e-6))
    else:
        env = 1.0
    return cue.weight * env


def jaw_envelope(audio_path, t: float, speech_start: float, speech_end: float, gain: float = 0.75) -> float:
    if t < speech_start - 0.02 or t > speech_end + 0.05:
        return 0.0
    samples, sr = jaw_envelope._cache.get(str(audio_path), (None, None))  # type: ignore[attr-defined]
    if samples is None:
        samples, sr = read_wav_mono(audio_path)
        jaw_envelope._cache[str(audio_path)] = (samples, sr)  # type: ignore[attr-defined]
    idx = int(t * sr)
    if idx < 0 or idx >= len(samples):
        return 0.0
    win = max(1, int(sr * 0.02))
    lo = max(0, idx - win)
    hi = min(len(samples), idx + win)
    rms = float(np.sqrt(np.mean(samples[lo:hi] ** 2)))
    return min(1.0, rms * gain * 8.0)


jaw_envelope._cache = {}  # type: ignore[attr-defined]


def normalize_mouth_weights(weights: dict[str, float], mouth_sum_cap: float = 1.0) -> tuple[dict[str, float], bool]:
    mouth = {k: weights.get(k, 0.0) for k in MOUTH_KEYS}
    total = sum(mouth.values())
    clamped = False
    if total > mouth_sum_cap and total > 1e-9:
        scale = mouth_sum_cap / total
        mouth = {k: v * scale for k, v in mouth.items()}
        clamped = True
    out = dict(weights)
    for k in MOUTH_KEYS:
        out[k] = mouth[k]
    return out, clamped


def blend_cues_at(
    cues: Iterable[VisemeCue],
    t: float,
    audio_path,
    speech_start: float,
    speech_end: float,
) -> tuple[dict[str, float], bool]:
    raw: dict[str, float] = {k: 0.0 for k in MOUTH_KEYS}
    if t < speech_start - 0.01 or t > speech_end + 0.05:
        return raw, False
    for cue in cues:
        w = cue_weight_at(cue, t)
        if w <= 0.0:
            continue
        key = ACTUATOR_FROM_CUE.get(cue.viseme.upper(), f"PRES_Viseme_{cue.viseme}" if cue.viseme in "AEO" else "PRES_JawOpen")
        if key not in raw:
            key = "PRES_JawOpen"
        raw[key] = max(raw[key], w)

    jaw = jaw_envelope(audio_path, t, speech_start, speech_end)
    raw["PRES_JawOpen"] = max(raw["PRES_JawOpen"], jaw * 0.65)
    return normalize_mouth_weights(raw)
