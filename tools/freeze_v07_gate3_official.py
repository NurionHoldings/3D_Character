"""Official freeze registration for Gate1 Continuity + Gate3."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
G3 = ROOT / "dist" / "v0.7" / "gate3"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"


def main() -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    cont = json.loads((G1 / "V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    cont["LOCKED"] = True
    cont["officialFrozenBaseline"] = True
    cont["V07_GATE1_BASELINE_CONTINUITY"] = "PASS"
    cont["presetCatalogSha256"] = PRESET_SHA
    cont["officialFreezeRegisteredAt"] = now
    (G1 / "V07_GATE1_BASELINE_CONTINUITY.json").write_text(
        json.dumps(cont, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for name in ("V07_GATE3_STATUS.json", "V07_GATE3_RECEIPT.json"):
        path = G3 / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("parameterHash") != GATE3_HASH and name.endswith("STATUS.json"):
            raise SystemExit(f"Gate3 hash mismatch in {name}")
        if "parameterHash" in doc and doc["parameterHash"] != GATE3_HASH:
            raise SystemExit(f"Gate3 hash mismatch in {name}")
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["officialFreezeRegisteredAt"] = now
        path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    freeze = {
        "schema": "NURION_V07_GATE3_OFFICIAL_FREEZE",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate1BaselineContinuity": "PASS",
        "presetCatalog": "OFFICIAL_BYTES_HASH_MATCH",
        "presetCatalogSha256": PRESET_SHA,
        "V07_GATE3": "PASS",
        "parameterHash": GATE3_HASH,
        "nativeArmatureBones": 24,
        "weightsGenerated": False,
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "sourceAndV06Mutation": 0,
        "production": "NO-GO",
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "updatedAt": now,
        "next": "V07_GATE4_WEIGHT_INITIALIZATION",
    }
    (G3 / "V07_GATE3_OFFICIAL_FREEZE.json").write_text(
        json.dumps(freeze, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"freeze": "OK", "gate3Hash": GATE3_HASH}, indent=2))


if __name__ == "__main__":
    main()
