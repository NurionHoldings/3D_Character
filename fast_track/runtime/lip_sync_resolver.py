"""FAST-04C — Minimal lip-sync resolver (FAST v0 phoneme classes)."""

from __future__ import annotations

import re
from typing import Iterable

from fast_track.runtime.narration_timeline import SpeechSegment, VisemeCue

# Hangul syllable block
_HANGUL = re.compile(r"[\uAC00-\uD7A3]")

OPEN_VOWELS = {"ㅏ", "ㅑ", "ㅘ", "ㅛ"}
SPREAD_VOWELS = {"ㅔ", "ㅐ", "ㅖ", "ㅢ", "ㅣ", "ㅚ", "ㅜ"}
ROUND_VOWELS = {"ㅗ", "ㅝ", "ㅟ", "ㅠ", "ㅡ"}
CLOSED_LABIAL = {"ㅁ", "ㅂ", "ㅍ", "ㅃ", "ㅹ"}


def _decompose_vowel(syllable: str) -> str | None:
    if not _HANGUL.fullmatch(syllable):
        return None
    code = ord(syllable) - 0xAC00
    vowel_idx = code % 588 // 28
    vowels = (
        "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ",
    )[0]
    if vowel_idx >= len(vowels):
        return None
    return vowels[vowel_idx]


def _final_consonant(syllable: str) -> str | None:
    if not _HANGUL.fullmatch(syllable):
        return None
    code = ord(syllable) - 0xAC00
    fi = code % 28
    if fi == 0:
        return None
    finals = (
        " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ",
    )[0]
    return finals[fi] if fi < len(finals) else None


def syllable_to_viseme_class(syllable: str) -> str:
    """Return A|E|O|M|JAW."""
    v = _decompose_vowel(syllable)
    f = _final_consonant(syllable)
    if f in CLOSED_LABIAL or (v is None and syllable in "Mm"):
        return "M"
    if v in OPEN_VOWELS:
        return "A"
    if v in SPREAD_VOWELS:
        return "E"
    if v in ROUND_VOWELS:
        return "O"
    return "JAW"


def viseme_class_to_actuator(vclass: str) -> tuple[str, float]:
    mapping = {
        "A": ("PRES_Viseme_A", 0.85),
        "E": ("PRES_Viseme_E", 0.85),
        "O": ("PRES_Viseme_O", 0.85),
        "M": ("PRES_Viseme_M", 0.9),
        "JAW": ("PRES_JawOpen", 0.55),
    }
    return mapping.get(vclass, ("PRES_JawOpen", 0.45))


def tokenize_transcript(transcript: str) -> list[str]:
    tokens: list[str] = []
    for ch in transcript:
        if _HANGUL.fullmatch(ch):
            tokens.append(ch)
        elif ch.isalpha():
            tokens.append(ch)
    return tokens


def resolve_cues(transcript: str, segments: list[SpeechSegment], min_cue_dur: float = 0.06) -> list[VisemeCue]:
    tokens = tokenize_transcript(transcript)
    if not tokens or not segments:
        return []

    speech_start = segments[0].start
    speech_end = segments[-1].end
    speech_dur = max(speech_end - speech_start, min_cue_dur * len(tokens))
    slot = speech_dur / len(tokens)

    cues: list[VisemeCue] = []
    t = speech_start
    for tok in tokens:
        vclass = syllable_to_viseme_class(tok)
        actuator, peak_w = viseme_class_to_actuator(vclass)
        start = t
        end = min(t + slot, speech_end)
        peak = (start + end) * 0.5
        cues.append(
            VisemeCue(
                start=start,
                peak=peak,
                end=end,
                viseme=actuator.replace("PRES_Viseme_", "").replace("PRES_", ""),
                weight=peak_w,
                source=f"resolver:{vclass}:{tok}",
            )
        )
        t = end
    return cues
