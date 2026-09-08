#!/usr/bin/env python3
"""Ensure FAST-04/05 narration WAV assets exist (Windows SAPI)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
NARR = ROOT / "fast_track/working/meshy_silver_starlight/narration"

NARRATIONS = [
    ("FAST-04_sample_narration.wav", "안녕하세요. 누리온 안내 캐릭터입니다. 오늘도 좋은 하루 되세요."),
    ("FAST-05_menu_company_intro.wav", "누리온은 AI 캐릭터 Identity Engine을 개발합니다."),
    ("FAST-05_menu_service_intro.wav", "저희 서비스는 안내형 프레젠테이션 캐릭터를 제공합니다."),
    ("FAST-05_menu_product_intro.wav", "제품 소개입니다. 실시간 나레이션과 표정 연동을 지원합니다."),
]


def synthesize(filename: str, text: str) -> Path:
    out = NARR / filename
    NARR.mkdir(parents=True, exist_ok=True)
    win_path = str(out).replace("/", "\\")
    ps = (
        "Add-Type -AssemblyName System.Speech\n"
        f"$s = New-Object System.Speech.Synthesis.SpeechSynthesizer\n"
        f"$s.SetOutputToWaveFile('{win_path}')\n"
        f"$s.Speak('{text}')\n"
        f"$s.Dispose()\n"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=True)
    if not out.exists() or out.stat().st_size < 1000:
        raise RuntimeError(f"Failed to synthesize {out}")
    return out


def main() -> int:
    created = []
    for name, text in NARRATIONS:
        path = NARR / name
        if not path.exists() or path.stat().st_size < 1000:
            synthesize(name, text)
            created.append(name)
    print({"ok": True, "created": created, "dir": str(NARR)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
