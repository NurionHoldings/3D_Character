"""Refuse Gate4A if Gate1–3 locked sources/params mutated."""

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
GATE3_LOCK = {
    "convex_conversion.py": "806962bfb16119d6cb290972d8f39da16605a23259dcc884ee50b9c50d31f0ed",
    "convex_validator.py": "4c433051400c81c88d5240138d571aff72ffcbbee96c8096e201c1e8a7e3d22e",
    "eye_dome_mesh.py": "fc85c013794ddd73820d9a132537aa264df6a81ff8eff8a0d4d95c2fe0758427",
    "parameters.py": "0dea9094e43aa79e502b4016e8f08a3771d6346868f3a744eb4e43902c964cb1",
    "lock_guard.py": "810c27cc619a294bc5790265c6c958faab219125242a4a00bb63a51d621d6ebc",
}
GATE2_PARAM = "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5"
GATE3_PARAM = "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_gate123_locked(root: Path) -> dict:
    root = Path(root)
    report = {"ok": True}
    for label, mapping, folder in (
        ("gate1", GATE1_LOCK, "gate1"),
        ("gate2", GATE2_LOCK, "gate2"),
        ("gate3", GATE3_LOCK, "gate3"),
    ):
        report[label] = {}
        for name, expected in mapping.items():
            h = _sha(root / "nurion_universal_eye" / folder / name)
            report[label][name] = h
            if h != expected:
                raise RuntimeError(f"{label.upper()} MUTATION DENY: {name}")
    from nurion_universal_eye.gate2.parameters import parameter_hash as g2_hash
    from nurion_universal_eye.gate3.parameters import parameter_hash as g3_hash

    g2p, g3p = g2_hash(), g3_hash()
    report["gate2ParameterHash"] = g2p
    report["gate3ParameterHash"] = g3p
    if g2p != GATE2_PARAM:
        raise RuntimeError(f"GATE2 PARAMETER MUTATION DENY: {g2p}")
    if g3p != GATE3_PARAM:
        raise RuntimeError(f"GATE3 PARAMETER MUTATION DENY: {g3p}")
    return report
