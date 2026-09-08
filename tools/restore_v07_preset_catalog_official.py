"""Restore official V07_HOMEPAGE_PRESET_CATALOG.json to exact SHA-256."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
OUT = ROOT / "dist" / "v0.7" / "gate1" / "V07_HOMEPAGE_PRESET_CATALOG.json"


def _build_text(dot: str) -> str:
    return (
        "{\n"
        '  "schema": "NURION_V07_HOMEPAGE_PRESET_CATALOG",\n'
        '  "track": "NURION Homepage Performance Rig v0.7",\n'
        '  "gate": 1,\n'
        '  "presetCount": 10,\n'
        '  "presets": [\n'
        f'    {{"id": "HOME_IDLE_BREATH", "purpose": "대기{dot}호흡", "loop": true}},\n'
        '    {"id": "HOME_FORMAL_GREETING", "purpose": "정중한 인사", "loop": false},\n'
        '    {"id": "HOME_POINT_PRIMARY_CTA", "purpose": "내 보험 점검하기 버튼 안내", "loop": false},\n'
        '    {"id": "HOME_INTRO_INSURANCE_CORE", "purpose": "보험 분석 영역 소개", "loop": false},\n'
        '    {"id": "HOME_GUIDE_IDENTITY", "purpose": "본인확인 절차 안내", "loop": false},\n'
        f'    {{"id": "HOME_GUIDE_CONSENT_IMPORT", "purpose": "동의{dot}조회 신청 안내", "loop": false}},\n'
        '    {"id": "HOME_WAIT_PROGRESS", "purpose": "진행 중 대기 안내", "loop": true},\n'
        '    {"id": "HOME_GUIDE_RESULTS", "purpose": "결과 확인 안내", "loop": false},\n'
        '    {"id": "HOME_INVITE_ADVISOR", "purpose": "전문가 상담 유도", "loop": false},\n'
        f'    {{"id": "HOME_ERROR_RETRY", "purpose": "오류{dot}재시도 안내", "loop": false}}\n'
        "  ],\n"
        '  "motionSourcePolicy": {\n'
        '    "gate1CreatesAnimation": false,\n'
        '    "futurePresetAuthoring": "NEW_ACTIONS_ONLY",\n'
        '    "copyExistingMeshyActionAsTruth": "DENY",\n'
        '    "videoPerformanceCopy": "V0.8_OUT_OF_SCOPE",\n'
        '    "unsupportedGesture": "ABSTAIN"\n'
        "  },\n"
        '  "production": "NO-GO"\n'
        "}\n"
    )


def main() -> int:
    dots = [
        "\u00b7",  # MIDDLE DOT
        "\u30fb",  # KATAKANA MIDDLE DOT
        "\u2027",  # HYPHENATION POINT
        "\u2219",  # BULLET OPERATOR
        "\uff65",  # HALFWIDTH KATAKANA MIDDLE DOT
        ".",
        "-",
    ]
    candidates: list[tuple[str, bytes, str]] = []
    for dot in dots:
        text = _build_text(dot)
        for nl in ("\n", "\r\n"):
            body = text.replace("\n", nl)
            for trailing in (True, False):
                s = body if trailing else body.rstrip("\r\n")
                b = s.encode("utf-8")
                h = hashlib.sha256(b).hexdigest()
                candidates.append((h, b, f"dot={hex(ord(dot))} nl={nl!r} trail={trailing}"))

        doc = json.loads(text)
        for ensure_ascii in (True, False):
            s = json.dumps(doc, indent=2, ensure_ascii=ensure_ascii) + "\n"
            b = s.encode("utf-8")
            candidates.append(
                (
                    hashlib.sha256(b).hexdigest(),
                    b,
                    f"json.dumps ensure_ascii={ensure_ascii} dot={hex(ord(dot))}",
                )
            )

    hits = [c for c in candidates if c[0] == TARGET]
    print("tried", len(candidates))
    if not hits:
        print("NO_MATCH")
        # print a few hashes for debug
        for h, _b, tag in candidates[:12]:
            print(h, tag)
        return 1

    h, b, tag = hits[0]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(b)
    verify = hashlib.sha256(OUT.read_bytes()).hexdigest()
    print("MATCH", tag)
    print("sha256", verify)
    print("written", OUT)
    return 0 if verify == TARGET else 2


if __name__ == "__main__":
    raise SystemExit(main())
