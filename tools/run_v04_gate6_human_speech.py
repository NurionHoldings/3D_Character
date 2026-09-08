"""
v0.4 Gate 6 — Human Speech Quality Validation.

Consumes frozen Gate5A/5B only. No parameter tuning.
Human WAV files are local evidence (hashes recorded); do not pack into install ZIP.

Usage:
  py -3 tools/run_v04_gate6_human_speech.py
  py -3 tools/run_v04_gate6_human_speech.py --manifest dist/v0.4/gate6/HUMAN_SPEECH_MANIFEST.json
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "dist" / "v0.4" / "gate6"
DEFAULT_MANIFEST = DEFAULT_OUT / "HUMAN_SPEECH_MANIFEST.json"


def _parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--write-template", action="store_true", help="Force rewrite template manifest")
    return p.parse_args(argv)


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv=None) -> int:
    args = _parse(argv if argv is not None else sys.argv[1:])
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    manifest_path = Path(args.manifest)
    if not manifest_path.is_absolute():
        manifest_path = ROOT / manifest_path

    sys.path.insert(0, str(ROOT))
    from nurion_v04_face_rig.gate6.manifest import write_template_manifest
    from nurion_v04_face_rig.gate6.measure import run_gate6_measurement
    from nurion_v04_face_rig.gate6.parameters import GATE6_PARAMETERS, parameter_hash

    inbox_audio = out_dir / "inbox" / "audio"
    inbox_audio.mkdir(parents=True, exist_ok=True)
    (out_dir / "inbox" / "README.txt").write_text(
        "Place human WAV PCM 16-bit mono 16/48kHz files here.\n"
        "File names must match HUMAN_SPEECH_MANIFEST.json audio fields.\n"
        "Do not strip silence, time-stretch, or denoise.\n"
        "Human audio is validation evidence only — exclude from install ZIP.\n",
        encoding="utf-8",
    )

    if args.write_template or not manifest_path.exists():
        write_template_manifest(manifest_path, audio_dir_rel="inbox/audio")

    result = run_gate6_measurement(manifest_path, runs=args.runs)

    # Working/input manifest: keep template editable when waiting; write evidence copy always
    if result["decision"].get("verdict") == "WAITING_FOR_INPUT":
        write_template_manifest(manifest_path, audio_dir_rel="inbox/audio")
        write_template_manifest(out_dir / "HUMAN_SPEECH_MANIFEST.TEMPLATE.json", audio_dir_rel="inbox/audio")
        _write(out_dir / "HUMAN_SPEECH_MANIFEST.EVIDENCE.json", result["manifest"])
    else:
        _write(out_dir / "HUMAN_SPEECH_MANIFEST.json", result["manifest"])

    _write(out_dir / "HUMAN_ALIGNMENT_REPORT.json", result["alignmentReport"])
    _write(out_dir / "HUMAN_LIPSYNC_REPORT.json", result["lipsyncReport"])
    _write(out_dir / "LOW_CONFIDENCE_REVIEW.json", result["lowConfidenceReview"])
    _write(out_dir / "GATE6_DECISION.json", result["decision"])

    # optional frozen timelines for cross-asset replay (local only)
    timelines = result.get("timelines") or {}
    if timelines:
        tdir = out_dir / "human_gate4_timelines"
        for uid, doc in timelines.items():
            _write(tdir / f"{uid}.json", doc)

    status = {
        "schema": "NURION_V04_GATE6_STATUS",
        "gate": "6",
        "name": "HUMAN_SPEECH_QUALITY_VALIDATION",
        "V04_GATE6": result["decision"].get("verdict"),
        "parameterHash": parameter_hash(),
        "gate5aParameterHash": GATE6_PARAMETERS["gate5aParameterHash"],
        "gate5bParameterHash": GATE6_PARAMETERS["gate5bParameterHash"],
        "gate1to5Mutation": "DENY",
        "parameterTuning": "DENY",
        "asr": "INACTIVE",
        "microphone": "HOLD",
        "realTime": "HOLD",
        "fullExpressionIntegration": GATE6_PARAMETERS["fullExpressionIntegration"],
        "excludeHumanAudioFromInstallZip": True,
        "artifacts": {
            "manifest": "HUMAN_SPEECH_MANIFEST.json",
            "alignment": "HUMAN_ALIGNMENT_REPORT.json",
            "lipsync": "HUMAN_LIPSYNC_REPORT.json",
            "lowConfidence": "LOW_CONFIDENCE_REVIEW.json",
            "decision": "GATE6_DECISION.json",
        },
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(out_dir / "V04_GATE6_STATUS.json", status)
    _write(DEFAULT_OUT / "V04_GATE6_LATEST.json", status)

    print(
        json.dumps(
            {
                "V04_GATE6": result["decision"].get("verdict"),
                "reason": result["decision"].get("reason"),
                "parameterHash": parameter_hash(),
                "gate1to5Hash": result.get("hashes", {}).get("gate1to5"),
                "next": result["decision"].get("next"),
                "inbox": str(inbox_audio).replace("\\", "/"),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    verdict = result["decision"].get("verdict")
    if verdict == "WAITING_FOR_INPUT":
        return 0
    if verdict in ("PASS", "PASS_WITH_LIMITATIONS"):
        return 0
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
