"""Human speech manifest load / validate / template."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Tuple

from .parameters import GATE6_PARAMETERS

RECOMMENDED_ITEMS = [
    {"id": "word_보험", "transcript": "보험", "type": "WORD", "rate": "NORMAL", "emotion": "NEUTRAL"},
    {"id": "word_분석", "transcript": "분석", "type": "WORD", "rate": "NORMAL", "emotion": "NEUTRAL"},
    {"id": "word_상담", "transcript": "상담", "type": "WORD", "rate": "NORMAL", "emotion": "NEUTRAL"},
    {"id": "word_확인", "transcript": "확인", "type": "WORD", "rate": "NORMAL", "emotion": "NEUTRAL"},
    {"id": "greet_안녕하세요", "transcript": "안녕하세요", "type": "GREETING", "rate": "NORMAL", "emotion": "FRIENDLY"},
    {
        "id": "guide_보험분석",
        "transcript": "고객님의 보험을 분석해 드릴게요",
        "type": "GUIDE",
        "rate": "NORMAL",
        "emotion": "NEUTRAL",
    },
    {
        "id": "aba_가입내용확인",
        "transcript": "고객님의 보험 가입 내용을 확인하겠습니다",
        "type": "ABA",
        "rate": "NORMAL",
        "emotion": "NEUTRAL",
    },
    {
        "id": "pause_확인후안내",
        "transcript": "확인 후, 점검 결과를 안내해 드리겠습니다",
        "type": "PAUSE",
        "rate": "NORMAL",
        "emotion": "NEUTRAL",
    },
    {
        "id": "slow_보험분석",
        "transcript": "고객님의 보험을 분석해 드릴게요",
        "type": "RATE",
        "rate": "SLOW_0_75",
        "emotion": "NEUTRAL",
    },
    {
        "id": "fast_보험분석",
        "transcript": "고객님의 보험을 분석해 드릴게요",
        "type": "RATE",
        "rate": "FAST_1_25",
        "emotion": "NEUTRAL",
    },
    {
        "id": "emotion_친절",
        "transcript": "고객님의 보험을 분석해 드릴게요",
        "type": "EMOTION",
        "rate": "NORMAL",
        "emotion": "FRIENDLY",
    },
    {
        "id": "emotion_공감",
        "transcript": "고객님의 보험을 분석해 드릴게요",
        "type": "EMOTION",
        "rate": "NORMAL",
        "emotion": "EMPATHY",
    },
    {
        "id": "long_보험안내",
        "transcript": "안녕하세요. 고객님의 보험 가입 내용을 확인한 뒤 점검 결과를 안내해 드리겠습니다.",
        "type": "LONG",
        "rate": "NORMAL",
        "emotion": "NEUTRAL",
    },
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_template_manifest(path: Path, audio_dir_rel: str = "inbox/audio") -> Dict:
    items = []
    for rec in RECOMMENDED_ITEMS:
        items.append(
            {
                **rec,
                "audio": f"{audio_dir_rel}/{rec['id']}.wav",
                "language": "ko-KR",
                "speakerId": "SPEAKER_01",
                "sourceKind": "HUMAN",
                "notes": "",
            }
        )
    doc = {
        "schema": "NURION_V04_GATE6_HUMAN_SPEECH_MANIFEST",
        "version": "0.4.0-gate6",
        "status": "TEMPLATE_AWAITING_HUMAN_WAV",
        "speakerCount": 1,
        "language": "ko-KR",
        "recordingPolicy": {
            "format": "WAV_PCM",
            "bits": 16,
            "channels": 1,
            "sampleRatePreferredHz": 48000,
            "sampleRatesAccepted": GATE6_PARAMETERS["acceptedSampleRates"],
            "forbidSilenceStrip": True,
            "forbidTimeStretch": True,
            "forbidDenoise": True,
            "transcriptMustMatchSpeech": True,
            "excludeFromInstallZip": True,
        },
        "minimums": {
            "utterances": GATE6_PARAMETERS["minUtterances"],
            "totalSpeechMs": GATE6_PARAMETERS["minTotalSpeechMs"],
        },
        "items": items,
        "instructions": [
            "inbox/audio/ 에 동일 파일명의 사람 음성 WAV를 배치한다.",
            "대본과 실제 발화가 일치해야 한다.",
            "준비되면 tools/run_v04_gate6_human_speech.py --manifest <this file> 실행.",
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return doc


def load_manifest(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_items(manifest: Dict, manifest_path: Path) -> Tuple[List[Dict], List[str]]:
    """Return resolved items with absolute audio paths; collect ASSET_INVALID reasons."""
    base = manifest_path.parent
    errors: List[str] = []
    resolved: List[Dict] = []
    for item in manifest.get("items") or []:
        audio_rel = item.get("audio") or ""
        audio_path = Path(audio_rel)
        if not audio_path.is_absolute():
            audio_path = (base / audio_rel).resolve()
        row = dict(item)
        row["audioPath"] = audio_path
        if not audio_path.exists():
            errors.append(f"MISSING_AUDIO:{item.get('id')}:{audio_rel}")
            row["present"] = False
        else:
            row["present"] = True
            row["audioSha256"] = sha256_file(audio_path)
        if not (item.get("transcript") or "").strip():
            errors.append(f"MISSING_TRANSCRIPT:{item.get('id')}")
        if item.get("sourceKind") and item.get("sourceKind") != "HUMAN":
            errors.append(f"NOT_HUMAN_SOURCE:{item.get('id')}:{item.get('sourceKind')}")
        resolved.append(row)
    return resolved, errors
