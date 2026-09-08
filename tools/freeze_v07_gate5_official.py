"""Official freeze for Gate5 (+ confirm Continuity / Gate3–4 remain locked)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
G3 = ROOT / "dist" / "v0.7" / "gate3"
G4 = ROOT / "dist" / "v0.7" / "gate4"
G5 = ROOT / "dist" / "v0.7" / "gate5"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    cont = json.loads((G1 / "V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    if cont.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("continuity not PASS")
    cont["LOCKED"] = True
    cont["officialFrozenBaseline"] = True
    (G1 / "V07_GATE1_BASELINE_CONTINUITY.json").write_text(
        json.dumps(cont, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for path, expected, key in [
        (G3 / "V07_GATE3_STATUS.json", GATE3_HASH, "V07_GATE3"),
        (G4 / "V07_GATE4_STATUS.json", GATE4_HASH, "V07_GATE4"),
        (G5 / "V07_GATE5_STATUS.json", GATE5_HASH, "V07_GATE5"),
    ]:
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("parameterHash") != expected or doc.get(key) != "PASS":
            raise SystemExit(f"freeze precheck failed: {path.name}")
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["officialFreezeRegisteredAt"] = now
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Mark UI 0.0px interpretation note on Gate5 evidence if present
    ev_path = G5 / "V07_GATE5_CONTROL_POSE_EVIDENCE.json"
    if ev_path.is_file():
        ev = json.loads(ev_path.read_text(encoding="utf-8"))
        ev["uiTargetZeroPxInterpretation"] = (
            "CONSTRAINT_COMPUTED_ALIGNMENT_ONLY_NOT_VISUAL_NATURALNESS_OR_JOINT_ACCURACY_EVIDENCE"
        )
        ev_path.write_text(json.dumps(ev, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    freeze = {
        "schema": "NURION_V07_GATE5_OFFICIAL_FREEZE",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate1BaselineContinuity": "PASS",
        "presetCatalogSha256": PRESET_SHA,
        "V07_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "V07_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "V07_GATE5": "PASS",
        "parameterHash": GATE5_HASH,
        "controlDeformSeparation": "PASS",
        "gesturesPoseSuiteUiTarget": "PASS",
        "uiTargetZeroPxInterpretation": "CONSTRAINT_COMPUTED_ALIGNMENT_ONLY_NOT_VISUAL_NATURALNESS_OR_JOINT_ACCURACY_EVIDENCE",
        "sourceGate34V06Mutation": 0,
        "manualCorrection": 0,
        "assetSpecificTuning": 0,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "updatedAt": now,
        "next": "V07_GATE6_HOMEPAGE_PRESET_AUTHORING",
    }
    (G5 / "V07_GATE5_OFFICIAL_FREEZE.json").write_text(
        json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if (G5 / "V07_GATE5_RECEIPT.json").is_file():
        rec = json.loads((G5 / "V07_GATE5_RECEIPT.json").read_text(encoding="utf-8"))
        rec["LOCKED"] = True
        rec["officialFrozenBaseline"] = True
        rec["officialFreezeRegisteredAt"] = now
        (G5 / "V07_GATE5_RECEIPT.json").write_text(
            json.dumps(rec, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    print(json.dumps({"freeze": "OK", "gate5Hash": GATE5_HASH}, indent=2))


if __name__ == "__main__":
    main()
