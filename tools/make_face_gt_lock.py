"""Create face-ground-truth.lock.json next to a GT JSON (Alpha1 ZIP untouched).

Includes GT SHA-256 plus eye-center resolution method / fit evidence hashes when available.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EYE_REPORT = ROOT / "dist" / "v0.3" / "face" / "reports" / "eye-center-resolution.json"
ALPHA1_CORE = {
    "eye.center.L",
    "eye.center.R",
    "eye.inner.L",
    "eye.inner.R",
    "eye.outer.L",
    "eye.outer.R",
    "nose.tip",
    "mouth.center",
    "mouth.corner.L",
    "mouth.corner.R",
    "chin",
    "ear.center.L",
    "ear.center.R",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("gt_json", type=Path)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--eye-report", type=Path, default=DEFAULT_EYE_REPORT)
    p.add_argument(
        "--allow-unresolved-eyes",
        action="store_true",
        help="Allow lock for diagnostic GT even if eye centers are not resolvable (marks officialAlpha1Gate=false).",
    )
    args = p.parse_args()
    gt = args.gt_json
    if not gt.exists():
        raise SystemExit(f"missing {gt}")

    doc = json.loads(gt.read_text(encoding="utf-8"))
    annotated = [
        e
        for e in doc.get("landmarks", [])
        if e.get("annotated")
        and e.get("positionWorld")
        and e["positionWorld"][0] is not None
        and e.get("name") in ALPHA1_CORE
    ]
    digest = sha256_file(gt)

    eye_block = {
        "EYE_CENTER_RESOLUTION": "UNKNOWN",
        "gtMethod": None,
        "evidenceSha256": None,
        "evidenceFile": None,
        "officialAlpha1GateAllowed": False,
    }
    if args.eye_report.exists():
        eye = json.loads(args.eye_report.read_text(encoding="utf-8"))
        evidence = eye.get("evidence") or {}
        evidence_sha = eye.get("evidenceSha256") or sha256_text(
            json.dumps(evidence, sort_keys=True, separators=(",", ":"))
        )
        resolution = eye.get("EYE_CENTER_RESOLUTION", "FAIL")
        eye_block = {
            "EYE_CENTER_RESOLUTION": resolution,
            "gtMethod": "VISIBLE_EYEBALL_SURFACE_FIT",
            "reasonCode": eye.get("reasonCode"),
            "evidenceSha256": evidence_sha,
            "evidenceSha256Length": 64,
            "evidenceFile": str(args.eye_report.as_posix()),
            "perLandmark": {
                k: {
                    "accepted": (evidence.get(k) or {}).get("accepted"),
                    "sampleCount": (evidence.get(k) or {}).get("sampleCount"),
                    "fitResidualMm": (evidence.get(k) or {}).get("fitResidualMm"),
                    "radiusMm": (evidence.get(k) or {}).get("radiusMm"),
                }
                for k in ("eye.center.L", "eye.center.R")
            },
            "officialAlpha1GateAllowed": resolution == "PASS",
        }
        if resolution != "PASS" and not args.allow_unresolved_eyes:
            raise SystemExit(
                "EYE_CENTER_RESOLUTION != PASS — refuse official GT lock. "
                "Use --allow-unresolved-eyes only for diagnostic (non-gate) locks."
            )

    lock = {
        "schema": "NURION_FACE_GT_LOCK",
        "gtFile": gt.name,
        "sha256": digest,
        "sha256Length": 64,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "landmarkCount": len(annotated),
        "coordinateSpaces": ["WORLD", "HEAD_LOCAL"],
        "predictionHiddenDuringAnnotation": True,
        "snapToPrediction": False,
        "frozen": True,
        "eyeCenter": eye_block,
        "ThirteenPointGtEligibility": (
            "PASS" if eye_block.get("officialAlpha1GateAllowed") and len(annotated) >= 13 else "FAIL"
        ),
        "note": (
            "Do not edit GT after lock. New edits require a new file + new hash. "
            "Official Alpha1 quality PASS requires EYE_CENTER_RESOLUTION=PASS and 13 annotated core points."
        ),
    }
    out = args.out or gt.with_name(gt.stem + ".lock.json")
    if gt.name == "face-ground-truth.json":
        out = gt.with_name("face-ground-truth.lock.json")
    out.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(lock, indent=2, ensure_ascii=False))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
