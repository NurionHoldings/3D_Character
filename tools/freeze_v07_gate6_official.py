"""Official freeze for Gate6 (+ Continuity / Gate3–5 remain locked)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
G6 = ROOT / "dist" / "v0.7" / "gate6"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
GATE6_HASH = "adca66246f5a2066fe9652a2129355e72787fd223f42c58be5a770db5ecc736b"
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

    for name in ("V07_GATE6_STATUS.json", "V07_GATE6_RECEIPT.json"):
        path = G6 / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("parameterHash") != GATE6_HASH:
            raise SystemExit(f"Gate6 hash mismatch: {name}")
        if name.endswith("STATUS.json") and doc.get("V07_GATE6") != "PASS":
            raise SystemExit("Gate6 not PASS")
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["officialFreezeRegisteredAt"] = now
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    freeze = {
        "schema": "NURION_V07_GATE6_OFFICIAL_FREEZE",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate1BaselineContinuity": "PASS",
        "presetCatalogSha256": PRESET_SHA,
        "V07_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "V07_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "V07_GATE5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "V07_GATE6": "PASS",
        "parameterHash": GATE6_HASH,
        "homepageActions10": "INDEPENDENT_CREATED",
        "meshyActionCopy": "DENY",
        "loopDriftCollapseMix": 0,
        "v06Handoff": "CREATED",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "production": "NO-GO",
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "updatedAt": now,
        "next": "V07_GATE7_HOLDOUT_AND_DETERMINISM",
    }
    (G6 / "V07_GATE6_OFFICIAL_FREEZE.json").write_text(
        json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"freeze": "OK", "gate6Hash": GATE6_HASH}, indent=2))


if __name__ == "__main__":
    main()
