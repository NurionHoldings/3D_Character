"""Normalize CCS Gate1 artifacts to LF and report SHA-256."""
from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EXPECTED = {
    "dist/v0.7/canonical/gate1/V07_CCS_GATE1_TOPOLOGY_CONTRACT.json": "df7f77c009906dc333cada288087cbae3d439e7e0aece06bee062e4731497530",
    "dist/v0.7/canonical/gate1/V07_CCS_GATE1_ASSET_MANIFEST_TEMPLATE.json": "f5e499cf77c0d29af67b11edc7ff9d9eabfb1f249739da0f207e41938eb2d2da",
    "nurion_ccs_gate1/__init__.py": "c08be34c18dbf167e9b5c5f157e6c4b4918454b46e94dd4af0f398a3f3cbe798",
    "nurion_ccs_gate1/topology_contract.py": "f0c66503a8790b4caa5840e1204131d6f83183325d2e931137943741bfcb07c1",
    "tests/test_canonical_gate1.py": "f99a631533f7c83c68e20d55565b59ded259297b51e1406f70140ca64a91c6d6",
}


def main() -> None:
    for rel, expected in EXPECTED.items():
        path = ROOT / rel
        text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
        variants = [text.encode("utf-8"), (text if text.endswith("\n") else text + "\n").encode("utf-8"), text.rstrip("\n").encode("utf-8")]
        matched = False
        for data in variants:
            h = hashlib.sha256(data).hexdigest()
            if h == expected:
                path.write_bytes(data)
                print(f"MATCH {rel} via rewrite")
                matched = True
                break
        if not matched:
            data = (text if text.endswith("\n") else text + "\n").encode("utf-8")
            path.write_bytes(data)
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            print(f"DIFF  {rel}")
            print(f"  expected {expected}")
            print(f"  actual   {h}")


if __name__ == "__main__":
    main()
