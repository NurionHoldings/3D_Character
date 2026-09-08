import hashlib
from pathlib import Path

exp = "c08be34c18dbf167e9b5c5f157e6c4b4918454b46e94dd4af0f398a3f3cbe798"
path = Path(__file__).resolve().parents[1] / "nurion_ccs_gate1" / "__init__.py"

lines = [
    '"""Official NURION Canonical Character System Gate 1 validator."""',
    "",
    "from .topology_contract import load_json, validate_asset_manifest",
    "",
    '__all__ = ["load_json", "validate_asset_manifest"]',
    '__version__ = "0.7.0-gate1"',
]
body = "\n".join(lines)
variants = [
    body,
    body + "\n",
    body + "\n\n",
    body.replace("\n", "\r\n"),
    body.replace("\n", "\r\n") + "\r\n",
]
for data in (v.encode("utf-8") for v in variants):
    h = hashlib.sha256(data).hexdigest()
    print(("MATCH" if h == exp else "diff"), h, len(data))
    if h == exp:
        path.write_bytes(data)
        print("restored", path)
        break
else:
    raise SystemExit("could not reproduce official __init__.py hash")
