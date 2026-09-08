"""
v0.4 Gate 5A — Offline Speech Alignment (FORCED_ALIGNMENT).

No Blender required. Gate 5B remains HOLD.

Usage:
  py -3 tools/run_v04_gate5a_speech_alignment.py --label tennis --role DEVELOPMENT
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate5a"


def _parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--label", default="tennis")
    p.add_argument("--role", default="DEVELOPMENT", choices=["DEVELOPMENT", "CROSS_VALIDATION", "REFERENCE"])
    p.add_argument("--out-dir", default="")
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--audio-dir", default="")
    p.add_argument("--manifest", default="", help="Optional JSON list of {id,audio,transcript,language,sourceKind}")
    return p.parse_args(argv)


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    args = _parse(argv if argv is not None else sys.argv[1:])
    out_dir = Path(args.out_dir) if args.out_dir else DEFAULT_OUT / args.label
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate5a.fixtures import ensure_synthetic_fixtures
    from nurion_v04_face_rig.gate5a.integration import run_gate5a
    from nurion_v04_face_rig.gate5a.parameters import GATE5A_PARAMETERS, parameter_hash

    if args.manifest:
        jobs = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    else:
        audio_dir = Path(args.audio_dir) if args.audio_dir else DEFAULT_OUT / "fixtures" / "audio"
        if not audio_dir.is_absolute():
            audio_dir = ROOT / audio_dir
        jobs = ensure_synthetic_fixtures(audio_dir)
        _write(DEFAULT_OUT / "fixtures" / "MANIFEST.json", {"schema": "NURION_V04_GATE5A_FIXTURE_MANIFEST", "items": jobs})

    result = run_gate5a(jobs, runs=args.runs)

    align_dir = out_dir / "alignments"
    g4_dir = out_dir / "gate4_timelines"
    for jid, doc in result.alignments.items():
        _write(align_dir / f"{jid}.json", doc)
    for jid, doc in result.gate4_timelines.items():
        _write(g4_dir / f"{jid}.json", doc)

    _write(out_dir / "GATE5A_PROFILE.json", result.profile)
    _write(out_dir / "GATE5A_VALIDATION.json", result.validation)

    status = {
        "schema": "NURION_V04_GATE5A_STATUS",
        "gate": "5A",
        "name": "OFFLINE_SPEECH_ALIGNMENT",
        "V04_GATE5A": result.verdict,
        "role": args.role,
        "asset": args.label,
        "parameterHash": parameter_hash(),
        "gates": result.validation.get("gates"),
        "fails": result.validation.get("fails"),
        "notes": result.notes,
        "alignerModel": GATE5A_PARAMETERS["alignerModel"],
        "alignerModelVersion": GATE5A_PARAMETERS["alignerModelVersion"],
        "koreanPronunciationRuleset": GATE5A_PARAMETERS["koreanPronunciationRuleset"],
        "audioDecoder": GATE5A_PARAMETERS["audioDecoder"],
        "normalizationPolicy": GATE5A_PARAMETERS["normalizationPolicy"],
        "gate5b": "HOLD",
        "microphone": "INACTIVE",
        "realTimeStreaming": "HOLD",
        "sourceCharacterMutation": "DENY",
        "gate1to4Mutation": "DENY",
        "utteranceCount": len(jobs),
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "artifacts": {
            "profile": "GATE5A_PROFILE.json",
            "validation": "GATE5A_VALIDATION.json",
            "alignments": "alignments/",
            "gate4Timelines": "gate4_timelines/",
        },
    }
    _write(out_dir / "V04_GATE5A_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE5A_LATEST.json", status)

    if result.verdict == "PASS" and args.role == "DEVELOPMENT" and args.label == "tennis":
        freeze = {
            "schema": "NURION_V04_GATE5A_PARAM_TEMP_FREEZE",
            "status": "TEMP_FROZEN_AFTER_TENNIS_DEV_PASS",
            "parameterHash": parameter_hash(),
            "parameterChange": "DENY_UNTIL_CV_COMPLETE",
            "tennis": "PASS",
            "gate5b": "HOLD",
            "alignerModel": GATE5A_PARAMETERS["alignerModel"],
            "alignerModelVersion": GATE5A_PARAMETERS["alignerModelVersion"],
            "koreanPronunciationRuleset": GATE5A_PARAMETERS["koreanPronunciationRuleset"],
            "audioDecoder": GATE5A_PARAMETERS["audioDecoder"],
            "normalizationPolicy": GATE5A_PARAMETERS["normalizationPolicy"],
            "next": "TENNIS_GATE5B_OR_CAPTAIN_AFTER_5B_PLAN",
            "frozenAt": datetime.now(timezone.utc).isoformat(),
        }
        _write(DEFAULT_OUT / "GATE5A_PARAM_TEMP_FREEZE.json", freeze)

    print(
        json.dumps(
            {
                "V04_GATE5A": result.verdict,
                "parameterHash": parameter_hash(),
                "gates": result.validation.get("gates"),
                "fails": result.validation.get("fails"),
                "gate5b": "HOLD",
                "notes": result.notes,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if result.verdict == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
