"""FAST-HR09 — Korean Lip Sync v2 → FACE Canonical speech weights.

Independent of PRES_Viseme_* SoT. Expression Mixer is not mutated here.
Outputs ESSENTIAL_V1 FACE speech primitives only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable

from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter

_HANGUL = re.compile(r"[\uAC00-\uD7A3]")
_CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
_JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
_JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

# Visual speech classes for Korean (coarse, production-safe).
VISEME_A = "A"
VISEME_EI = "EI"
VISEME_OU = "OU"
VISEME_MBP = "MBP"
VISEME_FV = "FV"
VISEME_SJCH = "SJCH"
VISEME_LN = "LN"
VISEME_NEUTRAL = "NEUTRAL"

OPEN_VOWELS = {"ㅏ", "ㅑ", "ㅘ"}
SPREAD_VOWELS = {"ㅔ", "ㅐ", "ㅖ", "ㅒ", "ㅣ", "ㅢ", "ㅚ", "ㅙ", "ㅓ", "ㅕ"}
ROUND_VOWELS = {"ㅗ", "ㅛ", "ㅜ", "ㅠ", "ㅝ", "ㅟ", "ㅡ", "ㅞ"}
LABIAL_CHO = {"ㅁ", "ㅂ", "ㅃ", "ㅍ"}
LABIAL_JONG = {"ㅁ", "ㅂ", "ㅄ", "ㄿ", "ㄻ", "ㄼ"}
DENTAL_LIKE = {"ㅍ"}  # approximation for F/V-like closure when labiodental absent
SIBILANT_CHO = {"ㅅ", "ㅆ", "ㅈ", "ㅉ", "ㅊ"}
LATERAL_NASAL = {"ㄴ", "ㄹ", "ㄵ", "ㄶ", "ㄺ", "ㄹ"}

# ESSENTIAL_V1 speech recipes (no V1_1/HOLD, no PRES_*).
VISEME_TO_FACE: dict[str, dict[str, float]] = {
    VISEME_A: {
        "FACE_mouthOpen": 0.78,
        "FACE_lipsPart": 0.28,
    },
    VISEME_EI: {
        "FACE_mouthWiden": 0.72,
        "FACE_lipsPart": 0.22,
    },
    VISEME_OU: {
        "FACE_mouthPucker": 0.68,
        "FACE_mouthOpen": 0.22,
    },
    VISEME_MBP: {
        "FACE_mouthPlosive": 0.92,
        "FACE_lipsTight": 0.40,
    },
    VISEME_FV: {
        "FACE_dentalLip": 0.88,
        "FACE_lipsTight": 0.24,
    },
    VISEME_SJCH: {
        "FACE_lipsTight": 0.48,
        "FACE_mouthWiden": 0.26,
    },
    VISEME_LN: {
        "FACE_lipsPart": 0.32,
        "FACE_mouthWiden": 0.16,
    },
    VISEME_NEUTRAL: {},
}

SHORT_PHONEME_SEC = 0.055
BLEND_OVERLAP_SEC = 0.045


@dataclass(frozen=True)
class PhonemeEvent:
    start: float
    end: float
    phoneme: str
    viseme: str
    peak_weight: float = 1.0

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


def _decompose(syllable: str) -> tuple[str, str, str] | None:
    if not _HANGUL.fullmatch(syllable):
        return None
    code = ord(syllable) - 0xAC00
    cho = code // 588
    jung = (code % 588) // 28
    jong = code % 28
    return _CHO[cho], _JUNG[jung], _JONG[jong]


def phoneme_to_viseme(token: str) -> str:
    """Deterministic Korean token → coarse viseme class."""
    if not token or token.isspace():
        return VISEME_NEUTRAL
    # Latin fallback for mixed transcripts.
    low = token.lower()
    if low in {"m", "b", "p"}:
        return VISEME_MBP
    if low in {"f", "v"}:
        return VISEME_FV
    if low in {"s", "j", "ch"}:
        return VISEME_SJCH
    if low in {"l", "n"}:
        return VISEME_LN
    if low in {"a"}:
        return VISEME_A
    if low in {"e", "i"}:
        return VISEME_EI
    if low in {"o", "u"}:
        return VISEME_OU

    parts = _decompose(token)
    if parts is None:
        return VISEME_NEUTRAL
    cho, jung, jong = parts
    if cho in LABIAL_CHO or jong in LABIAL_JONG:
        return VISEME_MBP
    if cho in SIBILANT_CHO or jong in {"ㅅ", "ㅆ", "ㅈ", "ㅊ"}:
        return VISEME_SJCH
    if cho in {"ㄴ", "ㄹ"} or jong in {"ㄴ", "ㄹ", "ㄵ", "ㄶ", "ㄺ"}:
        # Lateral/nasal often coexists with vowel; vowel still dominates visually,
        # but expose LN when vowel is weak schwa-like ㅡ.
        if jung == "ㅡ":
            return VISEME_LN
    if jung in OPEN_VOWELS:
        return VISEME_A
    if jung in SPREAD_VOWELS:
        return VISEME_EI
    if jung in ROUND_VOWELS:
        return VISEME_OU
    if cho in DENTAL_LIKE:
        return VISEME_FV
    return VISEME_NEUTRAL


def tokenize_korean(text: str) -> list[str]:
    tokens: list[str] = []
    for ch in text:
        if _HANGUL.fullmatch(ch) or ch.isalpha():
            tokens.append(ch)
    return tokens


def _smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def short_phoneme_scale(duration: float) -> float:
    """Suppress exaggerated mouth motion for very short phonemes."""
    if duration >= SHORT_PHONEME_SEC:
        return 1.0
    if duration <= 1e-6:
        return 0.0
    return _clamp01((duration / SHORT_PHONEME_SEC) * 0.65)


def viseme_to_face_weights(viseme: str, intensity: float = 1.0) -> dict[str, float]:
    recipe = VISEME_TO_FACE.get(viseme, VISEME_TO_FACE[VISEME_NEUTRAL])
    intensity = _clamp01(intensity)
    if intensity <= 0.0 or not recipe:
        return {}
    return {k: _clamp01(v * intensity) for k, v in sorted(recipe.items())}


def build_phoneme_timeline(
    text: str,
    *,
    start: float = 0.0,
    end: float | None = None,
    min_slot: float = 0.06,
) -> list[PhonemeEvent]:
    tokens = tokenize_korean(text)
    if not tokens:
        return []
    if end is None:
        end = start + max(min_slot * len(tokens), 0.2)
    dur = max(end - start, min_slot * len(tokens))
    slot = dur / len(tokens)
    events: list[PhonemeEvent] = []
    t = start
    for tok in tokens:
        viseme = phoneme_to_viseme(tok)
        ev_end = min(t + slot, end)
        scale = short_phoneme_scale(ev_end - t)
        peak = 0.9 * scale if viseme != VISEME_NEUTRAL else 0.0
        events.append(
            PhonemeEvent(
                start=t,
                end=ev_end,
                phoneme=tok,
                viseme=viseme,
                peak_weight=peak,
            )
        )
        t = ev_end
    return events


def _event_envelope(event: PhonemeEvent, t: float) -> float:
    if t < event.start - BLEND_OVERLAP_SEC or t > event.end + BLEND_OVERLAP_SEC:
        return 0.0
    # Extend effective window slightly for coarticulation overlap.
    start = event.start - BLEND_OVERLAP_SEC * 0.5
    end = event.end + BLEND_OVERLAP_SEC * 0.5
    if t < start or t > end:
        return 0.0
    dur = max(end - start, 1e-6)
    rel = (t - start) / dur
    attack = 0.28
    release = 0.32
    if rel <= attack:
        env = _smoothstep(rel / max(attack, 1e-6))
    elif rel >= 1.0 - release:
        env = _smoothstep((1.0 - rel) / max(release, 1e-6))
    else:
        env = 1.0
    return event.peak_weight * env


class KoreanLipSyncV2:
    """Korean phoneme timeline → ESSENTIAL FACE speech weights."""

    def __init__(self, naming_table_path=None):
        self.adapter = LegacyFaceAdapter(naming_table_path)
        # Ensure all recipe targets are ESSENTIAL_V1.
        for viseme, recipe in VISEME_TO_FACE.items():
            for face in recipe:
                if face not in self.adapter.essential_active:
                    raise ValueError(f"{viseme} recipe uses non-essential {face}")

    def map_phoneme(self, token: str) -> str:
        return phoneme_to_viseme(token)

    def face_for_viseme(self, viseme: str, intensity: float = 1.0) -> dict[str, float]:
        weights = viseme_to_face_weights(viseme, intensity)
        if not weights:
            return {}
        return self.adapter.request_canonical(weights)

    def evaluate_timeline(self, events: Iterable[PhonemeEvent], t: float) -> dict[str, float]:
        acc: dict[str, float] = {}
        active = False
        for event in events:
            env = _event_envelope(event, t)
            if env <= 1e-6:
                continue
            active = True
            face = viseme_to_face_weights(event.viseme, env)
            for k, v in face.items():
                acc[k] = max(acc.get(k, 0.0), v)
        if not active:
            return {}
        # Clamp + ESSENTIAL filter
        for k, v in list(acc.items()):
            acc[k] = _clamp01(v)
        return self.adapter.request_canonical(acc) if acc else {}

    def resolve_text(
        self,
        text: str,
        *,
        start: float = 0.0,
        end: float | None = None,
        sample_times: list[float] | None = None,
    ) -> dict[str, Any]:
        events = build_phoneme_timeline(text, start=start, end=end)
        if sample_times is None:
            if not events:
                sample_times = [start]
            else:
                sample_times = []
                for ev in events:
                    sample_times.append((ev.start + ev.end) * 0.5)
                sample_times.append(events[-1].end + 0.02)
        frames = []
        for t in sample_times:
            frames.append({"t": t, "faceWeights": self.evaluate_timeline(events, t)})
        return {
            "text": text,
            "events": [
                {
                    "start": e.start,
                    "end": e.end,
                    "phoneme": e.phoneme,
                    "viseme": e.viseme,
                    "peak_weight": e.peak_weight,
                    "duration": e.duration,
                }
                for e in events
            ],
            "frames": frames,
        }

    def snapshot_contract(self) -> dict[str, Any]:
        return {
            "stage": "FAST-HR09_KOREAN_LIP_SYNC_V2",
            "canonical_contract": "NURION_FACE_CANONICAL_V1",
            "active_tier": "ESSENTIAL_V1",
            "pres_viseme_as_sot": False,
            "expression_mixer_mutated": False,
            "talking_status": "HOLD",
            "visemeClasses": sorted(VISEME_TO_FACE),
            "visemeToFace": VISEME_TO_FACE,
            "shortPhonemeSec": SHORT_PHONEME_SEC,
            "blendOverlapSec": BLEND_OVERLAP_SEC,
        }
