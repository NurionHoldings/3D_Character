"""
v0.4 Gate 5A.2 — Human Speech Alignment Improvement.

Does not mutate Gate5A.1 locked baseline or Gate5B parameters.

Usage:
  py -3 tools/run_v04_gate5a2_improvement.py
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "v0.4" / "gate5a2"


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _parse(argv):
    p = argparse.ArgumentParser()
    p.add_argument("--out-dir", default=str(OUT))
    p.add_argument("--runs", type=int, default=3)
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(argv if argv is not None else sys.argv[1:])
    out = Path(args.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    sys.path.insert(0, str(ROOT))

    from nurion_v04_face_rig.gate5a.fixtures import ensure_synthetic_fixtures
    from nurion_v04_face_rig.gate5a.parameters import parameter_hash as h5a1
    from nurion_v04_face_rig.gate5a2.integration import run_jobs
    from nurion_v04_face_rig.gate5a2.parameters import GATE5A1_FROZEN, GATE5A2_PARAMETERS, parameter_hash

    # 1) synthetic fixtures (recreate if missing)
    synth_dir = ROOT / "dist" / "v0.4" / "gate5a" / "fixtures" / "audio"
    synth_jobs = ensure_synthetic_fixtures(synth_dir)
    for j in synth_jobs:
        j["sourceKind"] = "SYNTHETIC"

    synth = run_jobs(synth_jobs, runs=args.runs)
    synth_verdict = "PASS" if synth["verdict"] in ("PASS", "PASS_WITH_LIMITATIONS") and synth["gates"]["LOW_CONFIDENCE_OVERDRIVE"] == 0 else "FAIL"

    # 2) human 4-clip from gate6 inbox
    human_manifest = ROOT / "dist" / "v0.4" / "gate6" / "HUMAN_SPEECH_MANIFEST.json"
    human_jobs = []
    if human_manifest.exists():
        man = json.loads(human_manifest.read_text(encoding="utf-8"))
        for item in man.get("items") or []:
            ap = ROOT / "dist" / "v0.4" / "gate6" / item["audio"] if not Path(item["audio"]).is_absolute() else Path(item["audio"])
            # manifest audio is relative to gate6 dir
            ap = (ROOT / "dist" / "v0.4" / "gate6" / item["audio"]).resolve()
            if ap.exists():
                human_jobs.append(
                    {
                        "id": item["id"],
                        "audio": str(ap),
                        "transcript": item["transcript"],
                        "language": item.get("language", "ko-KR"),
                        "sourceKind": "HUMAN",
                    }
                )
    human = run_jobs(human_jobs, runs=args.runs) if human_jobs else {"verdict": "SKIP", "gates": {}, "fails": ["NO_HUMAN"], "items": [], "timelines": {}}

    human_verdict = human.get("verdict")
    if human_jobs and human["gates"].get("LOW_CONFIDENCE_OVERDRIVE", 1) == 0 and human_verdict in ("PASS", "PASS_WITH_LIMITATIONS"):
        human_ok = True
    else:
        human_ok = False if human_jobs else False

    overall = "PASS"
    fails = []
    if h5a1() != GATE5A1_FROZEN:
        overall = "FAIL"
        fails.append("GATE5A1_HASH")
    if synth_verdict != "PASS":
        overall = "FAIL"
        fails.append("SYNTHETIC_REGRESSION")
    if human_jobs:
        if not human_ok:
            overall = "FAIL"
            fails.append("HUMAN_4CLIP")
        elif human_verdict == "PASS_WITH_LIMITATIONS" and overall == "PASS":
            overall = "PASS_WITH_LIMITATIONS"
    else:
        fails.append("HUMAN_4CLIP_MISSING")
        overall = "FAIL"

    # write artifacts (branch dir only — never overwrite gate5a locked outputs)
    for label, bundle in (("synthetic", synth), ("human", human)):
        if not bundle.get("items"):
            continue
        bdir = out / label
        for it in bundle["items"]:
            _write(bdir / "alignments" / f"{it['id']}.json", it["alignment"])
        for uid, tl in (bundle.get("timelines") or {}).items():
            _write(bdir / "gate4_timelines" / f"{uid}.json", tl)
        _write(
            bdir / "REPORT.json",
            {
                "schema": f"NURION_V04_GATE5A2_{label.upper()}_REPORT",
                "verdict": bundle.get("verdict"),
                "gates": bundle.get("gates"),
                "fails": bundle.get("fails"),
                "notes": bundle.get("notes"),
                "itemSummaries": [
                    {
                        "id": i["id"],
                        "overdrive": i["overdrive"],
                        "breathAsPhoneme": i["breathAsPhoneme"],
                        "lipsyncMetrics": i["lipsyncMetrics"],
                        "determinism3x": i["determinism3x"],
                    }
                    for i in bundle["items"]
                ],
            },
        )

    decision = {
        "schema": "NURION_V04_GATE5A2_DECISION",
        "verdict": overall,
        "fails": fails,
        "syntheticRegression": synth_verdict,
        "human4Clip": human_verdict if human_jobs else "MISSING",
        "gates": {
            "SYNTHETIC_REGRESSION": synth_verdict,
            "HUMAN_4CLIP_ALIGNMENT": human_verdict if human_jobs else "MISSING",
            "LOW_CONFIDENCE_OVERDRIVE": (synth.get("gates", {}).get("LOW_CONFIDENCE_OVERDRIVE", 0) or 0)
            + (human.get("gates", {}).get("LOW_CONFIDENCE_OVERDRIVE", 0) or 0),
            "BREATH_AS_PHONEME": (synth.get("gates", {}).get("BREATH_AS_PHONEME", 0) or 0)
            + (human.get("gates", {}).get("BREATH_AS_PHONEME", 0) or 0),
            "GATE5B_CONTRACT_COMPATIBILITY": "PASS"
            if (synth.get("gates", {}).get("LOW_CONFIDENCE_OVERDRIVE", 0) or 0)
            + (human.get("gates", {}).get("LOW_CONFIDENCE_OVERDRIVE", 0) or 0)
            == 0
            else "FAIL",
            "GATE5A1_HASH": "UNCHANGED" if h5a1() == GATE5A1_FROZEN else "CHANGED",
            "DETERMINISM_3X": "PASS"
            if synth.get("gates", {}).get("DETERMINISM_3X") == "PASS"
            and (not human_jobs or human.get("gates", {}).get("DETERMINISM_3X") == "PASS")
            else "FAIL",
        },
        "parameterHash": parameter_hash(),
        "gate5a1ParameterHash": GATE5A1_FROZEN,
        "gate5bParameterHash": GATE5A2_PARAMETERS["gate5bParameterHash"],
        "alignerModel": GATE5A2_PARAMETERS["alignerModel"],
        "alignerModelVersion": GATE5A2_PARAMETERS["alignerModelVersion"],
        "parameterTuningOnLockedBaseline": "DENY",
        "gate6": "HOLD",
        "gate7": "HOLD",
        "next": "TEMP_FREEZE_5A2_THEN_INSURANCE_HUMAN_SET" if overall in ("PASS", "PASS_WITH_LIMITATIONS") else "CONTINUE_5A2_FIX",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(out / "GATE5A2_DECISION.json", decision)

    if overall in ("PASS", "PASS_WITH_LIMITATIONS"):
        _write(
            out / "GATE5A2_PARAM_TEMP_FREEZE.json",
            {
                "schema": "NURION_V04_GATE5A2_PARAM_TEMP_FREEZE",
                "status": "TEMP_FROZEN_AFTER_SYNTH_AND_HUMAN4_PASS",
                "parameterHash": parameter_hash(),
                "gate5a1ParameterHash": GATE5A1_FROZEN,
                "gate5a1Mutation": "DENY",
                "verdict": overall,
                "next": "INSURANCE_HUMAN_10_15_FOR_GATE6",
                "frozenAt": datetime.now(timezone.utc).isoformat(),
            },
        )

    print(json.dumps({"V04_GATE5A2": overall, "parameterHash": parameter_hash(), "fails": fails, "gates": decision["gates"]}, indent=2, ensure_ascii=False))
    return 0 if overall in ("PASS", "PASS_WITH_LIMITATIONS") else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
