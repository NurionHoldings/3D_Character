"""Transcript normalization and Korean pronunciation rules (candidates + confidence)."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Optional, Tuple

from .hangul import CHO, JONG, JUNG, compose, decompose, is_syllable

# Insurance / common loanword readings (surface → spoken hangul)
LEXICON: Dict[str, str] = {
    "AI": "에이아이",
    "OCR": "오씨알",
    "FAQ": "에프에이큐",
    "ID": "아이디",
    "OK": "오케이",
    "NURION": "누리온",
    "Gate": "게이트",
}

NUMBER_KO = {
    "0": "영",
    "1": "일",
    "2": "이",
    "3": "삼",
    "4": "사",
    "5": "오",
    "6": "육",
    "7": "칠",
    "8": "팔",
    "9": "구",
}

# Batchim that nasalize before ㄴ/ㅁ
NASAL_MAP = {"ㄱ": "ㅇ", "ㄲ": "ㅇ", "ㅋ": "ㅇ", "ㄷ": "ㄴ", "ㅌ": "ㄴ", "ㅅ": "ㄴ", "ㅆ": "ㄴ", "ㅈ": "ㄴ", "ㅊ": "ㄴ", "ㅎ": "ㄴ", "ㅂ": "ㅁ", "ㅍ": "ㅁ"}

# Tensification triggers (previous batchim class)
TENSE_MAP = {"ㄱ": "ㄲ", "ㄷ": "ㄸ", "ㅂ": "ㅃ", "ㅅ": "ㅆ", "ㅈ": "ㅉ"}

PALATAL_ONSET = {"ㄷ": "ㅈ", "ㅌ": "ㅊ"}


def normalize_transcript(text: str, language: str = "ko-KR") -> Dict:
    raw = text
    t = unicodedata.normalize("NFC", text.strip())
    # punctuation → pause markers
    t = t.replace("…", ".")
    t = re.sub(r"[!?]", ".", t)
    t = re.sub(r"[,，]", " ", t)
    t = re.sub(r"[\"'`“”‘’]", "", t)
    # lexicon / latin tokens
    for k, v in sorted(LEXICON.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(re.escape(k), v, t, flags=re.IGNORECASE)
    # digits → hangul readings (uncertain → candidate style later)
    def _digit(m):
        return "".join(NUMBER_KO.get(ch, ch) for ch in m.group(0))

    t = re.sub(r"\d+", _digit, t)
    t = re.sub(r"\s+", " ", t).strip()
    # keep hangul / spaces / period for pause
    cleaned = []
    for ch in t:
        if is_syllable(ch) or ch in " .":
            cleaned.append(ch)
        elif ch.isalpha():
            # unknown latin left as uncertain token marker space
            cleaned.append(" ")
    normalized = re.sub(r" +", " ", "".join(cleaned)).strip()
    return {
        "language": language,
        "raw": raw,
        "normalized": normalized,
        "ruleset": "NURION_KO_PRON_v1",
    }


def _syllables(text: str) -> List[str]:
    return [ch for ch in text if is_syllable(ch)]


def apply_pronunciation(normalized: str) -> Dict:
    """
    Apply liaison / nasalization / liquid / tensification / palatalization.
    Returns primary surface phoneme symbols + alternative candidates with confidence.
    """
    # Split on pauses
    parts = re.split(r"([.])", normalized)
    tokens: List[Dict] = []
    uncertain: List[Dict] = []

    for part in parts:
        if part == ".":
            tokens.append({"kind": "PAUSE", "symbol": "SIL", "confidence": 1.0, "rule": "PUNCT_BOUNDARY"})
            continue
        if not part.strip():
            continue
        syllables = list(part.replace(" ", ""))
        # work on (cho,jung,jong) triples
        cells: List[Optional[List[str]]] = []
        for ch in syllables:
            d = decompose(ch)
            if d is None:
                cells.append(None)
            else:
                cells.append([d[0], d[1], d[2]])

        i = 0
        while i < len(cells):
            if cells[i] is None:
                i += 1
                continue
            cho, jung, jong = cells[i]
            # look ahead next syllable onset
            j = i + 1
            while j < len(cells) and cells[j] is None:
                j += 1
            if j < len(cells) and cells[j] is not None:
                ncho, njung, njong = cells[j]
                # 1) Liaison: batchim + ㅇ onset → move
                if jong and ncho == "ㅇ":
                    cells[j][0] = jong
                    cells[i][2] = ""
                    uncertain.append(
                        {
                            "at": i,
                            "rule": "LIAISON",
                            "primary": jong,
                            "candidates": [jong],
                            "confidence": 0.92,
                        }
                    )
                    cho, jung, jong = cells[i]
                    ncho, njung, njong = cells[j]
                # 2) Nasalization
                if jong in NASAL_MAP and ncho in ("ㄴ", "ㅁ"):
                    mapped = NASAL_MAP[jong]
                    cells[i][2] = mapped
                    uncertain.append(
                        {
                            "at": i,
                            "rule": "NASALIZATION",
                            "primary": mapped,
                            "candidates": [mapped, jong],
                            "confidence": 0.88,
                        }
                    )
                    jong = mapped
                # 3) Liquid assimilation ㄴ+ㄹ / ㄹ+ㄴ → ㄹㄹ
                if jong == "ㄴ" and ncho == "ㄹ":
                    cells[i][2] = "ㄹ"
                    cells[j][0] = "ㄹ"
                    uncertain.append({"at": i, "rule": "LIQUID_NN_L", "primary": "ㄹㄹ", "candidates": ["ㄹㄹ", "ㄴㄹ"], "confidence": 0.85})
                elif jong == "ㄹ" and ncho == "ㄴ":
                    cells[j][0] = "ㄹ"
                    uncertain.append({"at": i, "rule": "LIQUID_LN_L", "primary": "ㄹㄹ", "candidates": ["ㄹㄹ", "ㄹㄴ"], "confidence": 0.85})
                # 4) Tensification after unreleased stops (approx)
                if cells[i][2] in ("ㄱ", "ㄷ", "ㅂ", "ㅅ", "ㅈ") and ncho in TENSE_MAP:
                    tensed = TENSE_MAP[ncho]
                    cells[j][0] = tensed
                    uncertain.append(
                        {
                            "at": j,
                            "rule": "TENSIFICATION",
                            "primary": tensed,
                            "candidates": [tensed, ncho],
                            "confidence": 0.7,
                        }
                    )
                # 5) Palatalization before ㅣ/ㅑ/ㅕ/ㅛ/ㅠ
                if cells[i][2] in PALATAL_ONSET and njung in ("ㅣ", "ㅑ", "ㅕ", "ㅛ", "ㅠ"):
                    # when liaison already moved, onset may be ㄷ/ㅌ
                    pass
                if ncho in PALATAL_ONSET and njung in ("ㅣ", "ㅑ", "ㅕ", "ㅛ", "ㅠ"):
                    alt = PALATAL_ONSET[ncho]
                    cells[j][0] = alt
                    uncertain.append(
                        {
                            "at": j,
                            "rule": "PALATALIZATION",
                            "primary": alt,
                            "candidates": [alt, ncho],
                            "confidence": 0.8,
                        }
                    )
            i += 1

        # emit phoneme stream: onset(+optional silent ㅇ skip), vowel, coda
        for cell in cells:
            if cell is None:
                continue
            cho, jung, jong = cell
            # onset: skip bare ㅇ (placeholder)
            if cho != "ㅇ":
                tokens.append({"kind": "PHONEME", "symbol": cho, "confidence": 0.95, "rule": "ONSET"})
            else:
                tokens.append({"kind": "PHONEME", "symbol": "ㅇ", "confidence": 0.9, "rule": "ONSET_NG_OR_NULL"})
            tokens.append({"kind": "PHONEME", "symbol": jung, "confidence": 0.97, "rule": "NUCLEUS"})
            if jong:
                tokens.append({"kind": "PHONEME", "symbol": jong, "confidence": 0.93, "rule": "CODA"})

        # word-internal spaces already removed; inter-word pause if original had spaces in part
        if " " in part:
            # soft pause already handled by splitting? keep mild SIL between words if multiple spaces chunks
            pass

    # Collapse consecutive identical SIL
    collapsed: List[Dict] = []
    for tok in tokens:
        if collapsed and tok["symbol"] == "SIL" and collapsed[-1]["symbol"] == "SIL":
            continue
        collapsed.append(tok)

    phoneme_symbols = [t["symbol"] for t in collapsed]
    return {
        "tokens": collapsed,
        "phonemes": phoneme_symbols,
        "uncertainRules": uncertain,
        "ruleset": "NURION_KO_PRON_v1",
    }
