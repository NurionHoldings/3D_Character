"""Expanded lexicon / mixed-language pronunciation candidates for Gate5A.2."""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, List, Tuple

from nurion_v04_face_rig.gate5a.hangul import is_syllable
from nurion_v04_face_rig.gate5a.pronunciation import NUMBER_KO, apply_pronunciation

# surface → preferred hangul reading (loanword)
LEXICON_V2: Dict[str, str] = {
    "AI": "에이아이",
    "IT": "아이티",
    "ESS": "이에스에스",
    "EDA": "이디에이",
    "OCR": "오씨알",
    "FAQ": "에프에이큐",
    "ID": "아이디",
    "OK": "오케이",
    "NURION": "누리온",
    "Gate": "게이트",
    "bottom dock": "바텀독",
    "Bottom Dock": "바텀독",
    "BOTTOM DOCK": "바텀독",
    "cascade": "캐스케이드",
    "Cascade": "캐스케이드",
    "CASCADE": "캐스케이드",
    "data center": "데이터센터",
    "data센터": "데이터센터",
    "Data Center": "데이터센터",
    "datacenter": "데이터센터",
    "실리콘 인텔리전스": "실리콘인텔리전스",
    "실리콘인텔리전스": "실리콘인텔리전스",
    "거버넌스": "거버넌스",
    "가버넌스": "거버넌스",
    "governance": "거버넌스",
}

# alternate candidates (evidence selection later)
LEXICON_ALTS: Dict[str, List[str]] = {
    "AI": ["에이아이", "에이 아이"],
    "IT": ["아이티", "아이 티"],
    "ESS": ["이에스에스", "이에스에스"],
    "EDA": ["이디에이", "이디에이"],
    "cascade": ["캐스케이드", "캐스캐이드"],
    "bottom dock": ["바텀독", "바텀 도크"],
    "data center": ["데이터센터", "데이터 센터"],
}


def normalize_transcript_v2(text: str, language: str = "ko-KR") -> Dict:
    raw = text
    t = unicodedata.normalize("NFC", text.strip())
    t = t.replace("…", ".")
    t = re.sub(r"[!?]", ".", t)
    t = re.sub(r"[,，/&]", " ", t)
    t = re.sub(r"[\"'`“”‘’:：]", " ", t)
    chosen: List[Dict] = []
    for k, v in sorted(LEXICON_V2.items(), key=lambda kv: -len(kv[0])):
        if re.search(re.escape(k), t, flags=re.IGNORECASE):
            alts = LEXICON_ALTS.get(k, [v])
            chosen.append({"surface": k, "primary": v, "candidates": alts, "confidence": 0.86})
            t = re.sub(re.escape(k), v, t, flags=re.IGNORECASE)

    def _digit(m):
        return "".join(NUMBER_KO.get(ch, ch) for ch in m.group(0))

    t = re.sub(r"\d+", _digit, t)
    t = re.sub(r"\s+", " ", t).strip()
    cleaned = []
    for ch in t:
        if is_syllable(ch) or ch in " .":
            cleaned.append(ch)
        elif ch.isalpha():
            cleaned.append(" ")
    normalized = re.sub(r" +", " ", "".join(cleaned)).strip()
    return {
        "language": language,
        "raw": raw,
        "normalized": normalized,
        "ruleset": "NURION_KO_PRON_v2_LEXICON",
        "lexiconChoices": chosen,
    }


def pronounce_v2(normalized: str) -> Dict:
    pron = apply_pronunciation(normalized)
    pron["ruleset"] = "NURION_KO_PRON_v2_LEXICON"
    return pron
