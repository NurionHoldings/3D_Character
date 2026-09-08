"""Verify v0.7 Gate 1 baseline continuity (official artifact SHA-256 MATCH)."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
OFFICIAL = {
    "V07_GATE1_CONTRACT.json": "aa6fdbc11f8a92485c9727d58ebb2c141cc7e156d6c7d6148d8f7b2180be9ac8",
    "V07_GATE1_QUALITY_GATES.json": "35e0965c3481140e4236670971e6f93d161ccacc9bbe59ca70a1e913223d54ec",
    "V07_HOMEPAGE_PRESET_CATALOG.json": "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071",
    "V07_GATE1_CONTRACT.md": "4a669759f09941b1b9c512899c4263164d58a560a0ee2c6f10fa5f2499b7398b",
}
GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for c in iter(lambda: f.read(1024 * 1024), b""):
            h.update(c)
    return h.hexdigest()


def main() -> int:
    matches = {}
    for name, expected in OFFICIAL.items():
        path = G1 / name
        actual = _sha(path) if path.is_file() else None
        matches[name] = {
            "expected": expected,
            "actual": actual,
            "result": "MATCH" if actual == expected else "HASH_MISMATCH",
        }
    all_match = all(v["result"] == "MATCH" for v in matches.values())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    doc = {
        "schema": "NURION_V07_GATE1_BASELINE_CONTINUITY",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 1,
        "parameterHash": GATE1_HASH,
        "V07_GATE1_BASELINE_CONTINUITY": "PASS" if all_match else "HOLD_BASELINE_CONTINUITY",
        "artifactContinuity": matches,
        "presetCatalogRestoredFromOfficialBytes": True,
        "recomputedHashMustNotReplaceOfficial": True,
        "updatedAt": now,
    }
    (G1 / "V07_GATE1_BASELINE_CONTINUITY.json").write_text(
        json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    # Refresh lock workspace hashes to MATCH state without changing official hashes
    lock_path = G1 / "V07_GATE1_BASELINE_LOCK.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    lock["artifactHashes"] = dict(OFFICIAL)
    lock["workspaceRegisteredArtifactHashes"] = {k: v["actual"] for k, v in matches.items()}
    lock["artifactHashMatchOfficial"] = {k: v["result"] == "MATCH" for k, v in matches.items()}
    lock["baselineContinuity"] = "PASS" if all_match else "HOLD_BASELINE_CONTINUITY"
    lock["baselineMutation"] = "DENY"
    lock["continuityVerifiedAt"] = now
    lock_path.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(json.dumps({"continuity": doc["V07_GATE1_BASELINE_CONTINUITY"], "matches": {k: v["result"] for k, v in matches.items()}}, indent=2))
    return 0 if all_match else 1


if __name__ == "__main__":
    raise SystemExit(main())
