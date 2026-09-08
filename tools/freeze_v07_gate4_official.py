"""Official freeze for Gate4 (+ confirm Gate1 continuity / Gate3 remain locked)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
G3 = ROOT / "dist" / "v0.7" / "gate3"
G4 = ROOT / "dist" / "v0.7" / "gate4"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    cont = json.loads((G1 / "V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    if cont.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("Gate1 continuity not PASS")
    cont["LOCKED"] = True
    cont["officialFrozenBaseline"] = True
    cont["officialFreezeRegisteredAt"] = now
    (G1 / "V07_GATE1_BASELINE_CONTINUITY.json").write_text(
        json.dumps(cont, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    g3 = json.loads((G3 / "V07_GATE3_STATUS.json").read_text(encoding="utf-8"))
    if g3.get("parameterHash") != GATE3_HASH or g3.get("V07_GATE3") != "PASS":
        raise SystemExit("Gate3 not PASS/expected hash")
    g3["LOCKED"] = True
    g3["officialFrozenBaseline"] = True
    (G3 / "V07_GATE3_STATUS.json").write_text(json.dumps(g3, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    for name in ("V07_GATE4_STATUS.json", "V07_GATE4_RECEIPT.json"):
        path = G4 / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("parameterHash") != GATE4_HASH:
            raise SystemExit(f"Gate4 hash mismatch: {name}")
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["officialFreezeRegisteredAt"] = now
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    freeze = {
        "schema": "NURION_V07_GATE4_OFFICIAL_FREEZE",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate1BaselineContinuity": "PASS",
        "presetCatalogSha256": PRESET_SHA,
        "V07_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "V07_GATE4": "PASS",
        "parameterHash": GATE4_HASH,
        "weightIntegrity": "PASS",
        "regionSeparation": "PASS",
        "poseSuiteBasic": "PASS",
        "meshyWeightCopy": "DENY",
        "autoFieldRepair": "DENY",
        "sourceZipAndV06Mutation": 0,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "updatedAt": now,
        "next": "V07_GATE5_HOMEPAGE_CONTROL_AND_POSE_VALIDATION",
    }
    (G4 / "V07_GATE4_OFFICIAL_FREEZE.json").write_text(
        json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"freeze": "OK", "gate4Hash": GATE4_HASH}, indent=2))


if __name__ == "__main__":
    main()
