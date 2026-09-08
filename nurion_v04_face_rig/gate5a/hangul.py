"""Hangul syllable ↔ jamo helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple

CHO = list("ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ")
JUNG = list("ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ")
JONG = [""] + list("ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ")

# Compatibility jamo → canonical
COMPAT_CHO = {
    "ㄱ": "ㄱ",
    "ㄲ": "ㄲ",
    "ㄴ": "ㄴ",
    "ㄷ": "ㄷ",
    "ㄸ": "ㄸ",
    "ㄹ": "ㄹ",
    "ㅁ": "ㅁ",
    "ㅂ": "ㅂ",
    "ㅃ": "ㅃ",
    "ㅅ": "ㅅ",
    "ㅆ": "ㅆ",
    "ㅇ": "ㅇ",
    "ㅈ": "ㅈ",
    "ㅉ": "ㅉ",
    "ㅊ": "ㅊ",
    "ㅋ": "ㅋ",
    "ㅌ": "ㅌ",
    "ㅍ": "ㅍ",
    "ㅎ": "ㅎ",
}


def is_syllable(ch: str) -> bool:
    return len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3


def decompose(ch: str) -> Optional[Tuple[str, str, str]]:
    if not is_syllable(ch):
        return None
    code = ord(ch) - 0xAC00
    cho = code // 588
    jung = (code % 588) // 28
    jong = code % 28
    return CHO[cho], JUNG[jung], JONG[jong]


def compose(cho: str, jung: str, jong: str = "") -> str:
    ci = CHO.index(cho)
    ji = JUNG.index(jung)
    ki = JONG.index(jong) if jong else 0
    return chr(0xAC00 + ci * 588 + ji * 28 + ki)


def decompose_text(text: str) -> List[Tuple[str, Optional[Tuple[str, str, str]]]]:
    out = []
    for ch in text:
        out.append((ch, decompose(ch)))
    return out
