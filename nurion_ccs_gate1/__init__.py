"""Official NURION Canonical Character System Gate 1 validator."""

from .topology_contract import load_json, validate_asset_manifest

__all__ = ["load_json", "validate_asset_manifest"]
__version__ = "0.7.0-gate1"
