"""Refuse Gate6 if Gate1–5 locked sources/params mutated."""

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
GATE4A_LOCK = {
    "parameters.py": "0245ba619f11793d234e28f38fcea851e99991165ecd71ec16f11cf5948cd573",
    "lock_guard.py": "35432d0015f208d6081a466ff28217d6d72966ffaf4357fe9a8b676987c223a9",
    "safe_ellipse.py": "02cb3dd9ae9e185b9dc5a8340d09d902dfb69bc47e92e472a882fd68fba9c975",
    "gaze_meshes.py": "c41338c7f06a3e15732284d9ae33752fcbfc2f0e6c9f0d3bd82c1f82e3fd3eff",
    "gaze_motion.py": "644a5869748b2a48aa5182f3ac3176fc4adc08a2789437e1bbbd49364580564b",
    "gaze_validator.py": "b6299b8f6268763f3afd91b73d5bf7979cbde92f1a71f41fa29e6678c3eb5bdf",
    "__init__.py": "fcf440305394303f2de06d846b44921baeda9f7787009eed4063cdc199bb71ab",
}
GATE4B_LOCK = {
    "parameters.py": "dbbba4be389cadcbb27011e058acebcdc8201fe74fd8e98ad3f13c4d1f9b4cd5",
    "lock_guard.py": "bcfb657d074dbe5c89008f4c344a02e5187f5e0a02dc4ad3d9c5c6e7c9a95fa0",
    "capability.py": "247f79e1c40c079590ce310cae67247b6fb533578a30c1a16c829e822f1cc9f5",
    "lid_proxy.py": "f6e3bc1e219b7fe2c4f87104f863aac266b55f28e704f150c8aad3122e2cb35c",
    "blink_motion.py": "fed1385d0ec72f86955ed68cd3635ba382f533ec1122582b6a24b4f09e327f1c",
    "blink_validator.py": "e12c1dbf5b4635dac59a4347d21ed02c3bc24bc72656b5b798b846c69a485f7c",
    "__init__.py": "fc51fe7a1c9bed17132bc8c3e218630e366f896a7d7f18359d7991e555671aa3",
}
GATE5_LOCK = {
    "parameters.py": "ee415963d9e2a991426eb6bc1a4019a90767e58018348f2ed2b58f0b38aebff8",
    "lock_guard.py": "f83bf4ad8dbb4f1cc740e9f752da71a50fdfddf927b34f53c8e1284f4934db83",
    "expression_recipes.py": "f511daac850457f9d9a07058e180dcd5417f592a825fcd858460463279fbd9f6",
    "expression_matching.py": "5fbd3184c88b10109ec103ba15929ed349f600e369d290301cfc442619910715",
    "expression_validator.py": "3ac1a3707ab4cd86e77d7b39b848b7091e2ea29525310d8091a4eddb65e50c45",
    "__init__.py": "84ea0a95260a9ef8015d500694d5072edf47c0ea76f0f85017a6cc921b83a402",
}
GATE2_PARAM = "ac799e4fedc8d84bd110dc54ee3789122a4018ad33d244327aec7d882ca595b5"
GATE3_PARAM = "9d8056d16641af8d0d9e211c19408f4124a5784b6e20c4d2999bcf6e1f894e2f"
GATE4A_PARAM = "6a834ee878e0d466cfba9cd67e8408f6e737400693cc6f60dd751979b6b01c35"
GATE4B_PARAM = "44b94103939a483583f239dfd944956499fd93c9bc535a38c5e0e59b28428a61"
GATE5_PARAM = "4672cc7973b3367ca4d01eeed66879125a1b15b7ac18130cbff34ab351c3203e"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assert_gate12345_locked(root: Path) -> dict:
    root = Path(root)
    report = {"ok": True}
    for label, mapping, folder in (
        ("gate1", GATE1_LOCK, "gate1"),
        ("gate2", GATE2_LOCK, "gate2"),
        ("gate3", GATE3_LOCK, "gate3"),
        ("gate4a", GATE4A_LOCK, "gate4a"),
        ("gate4b", GATE4B_LOCK, "gate4b"),
        ("gate5", GATE5_LOCK, "gate5"),
    ):
        report[label] = {}
        for name, expected in mapping.items():
            h = _sha(root / "nurion_universal_eye" / folder / name)
            report[label][name] = h
            if h != expected:
                raise RuntimeError(f"{label.upper()} MUTATION DENY: {name}")

    from nurion_universal_eye.gate2.parameters import parameter_hash as g2_hash
    from nurion_universal_eye.gate3.parameters import parameter_hash as g3_hash
    from nurion_universal_eye.gate4a.parameters import parameter_hash as g4a_hash
    from nurion_universal_eye.gate4b.parameters import parameter_hash as g4b_hash
    from nurion_universal_eye.gate5.parameters import parameter_hash as g5_hash

    hashes = {
        "gate2ParameterHash": g2_hash(),
        "gate3ParameterHash": g3_hash(),
        "gate4aParameterHash": g4a_hash(),
        "gate4bParameterHash": g4b_hash(),
        "gate5ParameterHash": g5_hash(),
    }
    report.update(hashes)
    expected = {
        "gate2ParameterHash": GATE2_PARAM,
        "gate3ParameterHash": GATE3_PARAM,
        "gate4aParameterHash": GATE4A_PARAM,
        "gate4bParameterHash": GATE4B_PARAM,
        "gate5ParameterHash": GATE5_PARAM,
    }
    for k, exp in expected.items():
        if hashes[k] != exp:
            raise RuntimeError(f"{k.upper()} MUTATION DENY: {hashes[k]}")
    return report
