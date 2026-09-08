"""Fixed synthetic phoneme timelines for Gate4 diagnostic sentences."""

from __future__ import annotations

from typing import Dict, List


def _ev(symbol: str, start: int, end: int, confidence: float = 1.0) -> Dict:
    return {"symbol": symbol, "startMs": int(start), "endMs": int(end), "confidence": float(confidence)}


def _pack(name: str, events: List[Dict]) -> Dict:
    return {"name": name, "phonemes": events}


DIAGNOSTIC_TIMELINES: Dict[str, Dict] = {
    # 바보 — 폐쇄→개방→폐쇄→원순
    "바보": _pack(
        "바보",
        [
            _ev("ㅂ", 0, 80),
            _ev("ㅏ", 80, 220),
            _ev("ㅂ", 220, 300),
            _ev("ㅗ", 300, 480),
            _ev("SIL", 480, 560),
        ],
    ),
    # 미소 — 폐쇄→WIDE→TEETH→ROUND
    "미소": _pack(
        "미소",
        [
            _ev("ㅁ", 0, 70),
            _ev("ㅣ", 70, 180),
            _ev("ㅅ", 180, 260),
            _ev("ㅗ", 260, 420),
            _ev("SIL", 420, 500),
        ],
    ),
    # 보험 — 폐쇄·복합 모음·종성
    "보험": _pack(
        "보험",
        [
            _ev("ㅂ", 0, 70),
            _ev("ㅗ", 70, 160),
            _ev("ㅎ", 160, 210),
            _ev("ㅓ", 210, 300),
            _ev("ㅁ", 300, 390),
            _ev("SIL", 390, 470),
        ],
    ),
    # 분석
    "분석": _pack(
        "분석",
        [
            _ev("ㅂ", 0, 60),
            _ev("ㅜ", 60, 140),
            _ev("ㄴ", 140, 200),
            _ev("ㅅ", 200, 270),
            _ev("ㅓ", 270, 360),
            _ev("ㄱ", 360, 430),
            _ev("SIL", 430, 510),
        ],
    ),
    # 안녕하세요
    "안녕하세요": _pack(
        "안녕하세요",
        [
            _ev("ㅇ", 0, 40),
            _ev("ㅏ", 40, 120),
            _ev("ㄴ", 120, 170),
            _ev("ㄴ", 170, 210),
            _ev("ㅕ", 210, 300),
            _ev("ㅇ", 300, 340),
            _ev("ㅎ", 340, 390),
            _ev("ㅏ", 390, 470),
            _ev("ㅅ", 470, 530),
            _ev("ㅔ", 530, 620),
            _ev("ㅇ", 620, 660),
            _ev("ㅛ", 660, 760),
            _ev("SIL", 760, 860),
        ],
    ),
    # ABA-like long utterance
    "보험을_분석해_드릴게요": _pack(
        "보험을_분석해_드릴게요",
        [
            _ev("ㅂ", 0, 60),
            _ev("ㅗ", 60, 130),
            _ev("ㅎ", 130, 170),
            _ev("ㅓ", 170, 250),
            _ev("ㅁ", 250, 310),
            _ev("ㅇ", 310, 340),
            _ev("ㅡ", 340, 400),
            _ev("ㄹ", 400, 450),
            _ev("ㅂ", 450, 500),
            _ev("ㅜ", 500, 560),
            _ev("ㄴ", 560, 610),
            _ev("ㅅ", 610, 670),
            _ev("ㅓ", 670, 740),
            _ev("ㄱ", 740, 790),
            _ev("ㅎ", 790, 830),
            _ev("ㅐ", 830, 900),
            _ev("ㄷ", 900, 950),
            _ev("ㅡ", 950, 1010),
            _ev("ㄹ", 1010, 1060),
            _ev("ㄹ", 1060, 1100),
            _ev("게", 1100, 1100),  # placeholder replaced below
        ],
    ),
}


def _fix_long() -> None:
    # rebuild last sentence cleanly without placeholder
    DIAGNOSTIC_TIMELINES["보험을_분석해_드릴게요"] = _pack(
        "보험을_분석해_드릴게요",
        [
            _ev("ㅂ", 0, 60),
            _ev("ㅗ", 60, 130),
            _ev("ㅎ", 130, 170),
            _ev("ㅓ", 170, 250),
            _ev("ㅁ", 250, 310),
            _ev("ㅇ", 310, 340),
            _ev("ㅡ", 340, 400),
            _ev("ㄹ", 400, 450),
            _ev("ㅂ", 450, 500),
            _ev("ㅜ", 500, 560),
            _ev("ㄴ", 560, 610),
            _ev("ㅅ", 610, 670),
            _ev("ㅓ", 670, 740),
            _ev("ㄱ", 740, 790),
            _ev("ㅎ", 790, 830),
            _ev("ㅐ", 830, 900),
            _ev("ㄷ", 900, 950),
            _ev("ㅡ", 950, 1010),
            _ev("ㄹ", 1010, 1060),
            _ev("ㄹ", 1060, 1110),
            _ev("ㄱ", 1110, 1160),
            _ev("ㅔ", 1160, 1240),
            _ev("ㅇ", 1240, 1280),
            _ev("ㅛ", 1280, 1380),
            _ev("SIL", 1380, 1500),
        ],
    )


_fix_long()


def all_timelines() -> Dict[str, Dict]:
    return DIAGNOSTIC_TIMELINES
