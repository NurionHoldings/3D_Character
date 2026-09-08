"""Refuse Gate3 if Gate1/2 locked sources or Gate2 parameter hash mutated."""

from __future__ import annotations

import hashlib
from pathlib import Path

GATE1_LOCK = {
    "universal_face_basis.py": "63bc179e68cd03dda345ffc2295abb1fb97e700074deb1888250a13b15f83647",
    "multiview_evidence.py": "1968d12dbb307c6937ac84574bc405055fa5b24d890fc82ba47fdab3ca4fe108",
    "face_basis_validator.py": "324d2e075ee53fefa474831809a6305f05ca13c07ce369255cb8522110081e78",
}
GATE2_LOCK = {
    "flat_eye_placement.py": "9be58dc32209064722b691920593be7835d33e6e4cdf2432b07cfdb4f820580f",
    "flat_eye_validator.py": "e62e203be68687963f15de0b69d7665bd1e8a1543b2af9085a6e76c76fc36719",
    "multiview_depth.py": "6ca7a6f3112aaf70414527f3e11c4c9a0adb439fa2f4c4d4e1317eda8ba73c71",
    "eye_plane_mesh.py": "345939ab55432c610595cf72045f7d654cb4ebed5c887b755964a667f431eb61",
    "parameters.py": "1d8d6c4ced3754d6cf1a28563de6cf23d72bf73c60b8582ef5d8d6cdc472e674",
}
GATE2_PARAM = "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_gate12_locked(root: Path) -> dict:
    root = Path(root)
    report = {"gate1": {}, "gate2": {}, "gate2ParameterHash": None, "ok": True}
    for name, expected in GATE1_LOCK.items():
        h = _sha(root / "nurion_universal_eye" / "gate1" / name)
        report["gate1"][name] = h
        if h != expected:
            report["ok"] = False
            raise RuntimeError(f"GATE1 MUTATION DENY: {name}")
    for name, expected in GATE2_LOCK.items():
        h = _sha(root / "nurion_universal_eye" / "gate2" / name)
        report["gate2"][name] = h
        if h != expected:
            report["ok"] = False
            raise RuntimeError(f"GATE2 MUTATION DENY: {name}")
    from nurion_universal_eye.gate2.parameters import parameter_hash as g2_hash

    g2p = g2_hash()
    report["gate2ParameterHash"] = g2p
    if g2p != GATE2_PARAM:
        report["ok"] = False
        raise RuntimeError(f"GATE2 PARAMETER MUTATION DENY: {g2p}")
    return report
