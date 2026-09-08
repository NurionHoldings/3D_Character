"""Assert Gate1–6 locks unchanged for integrated regression."""

from __future__ import annotations

from pathlib import Path

from ..gate6.lock_guard import assert_gate12345_locked
from ..gate6.parameters import parameter_hash as g6_hash
from .parameters import GATE7A_PARAMETERS


def assert_all_gate_params_locked(root: Path) -> dict:
    root = Path(root)
    report = assert_gate12345_locked(root)
    g6 = g6_hash()
    report["gate6ParameterHash"] = g6
    expected = GATE7A_PARAMETERS["requiredGateParams"]
    mapping = {
        "gate2": report["gate2ParameterHash"],
        "gate3": report["gate3ParameterHash"],
        "gate4a": report["gate4aParameterHash"],
        "gate4b": report["gate4bParameterHash"],
        "gate5": report["gate5ParameterHash"],
        "gate6": g6,
    }
    for key, exp in expected.items():
        if mapping[key] != exp:
            raise RuntimeError(f"GATE PARAM CHANGE DENY: {key} {mapping[key]} != {exp}")
    report["gateParamChange"] = 0
    return report


def required_pipeline_objects() -> list:
    objs = []
    for side in ("L", "R"):
        objs.extend(
            [
                f"NURION_EyePlane.{side}",
                f"NURION_EyeDome.{side}",
                f"NURION_DiagnosticIris.{side}",
                f"NURION_DiagnosticPupil.{side}",
                f"NURION_GazeSafeEllipse.{side}",
                f"NURION_UpperLidProxy.{side}",
                f"NURION_LowerLidProxy.{side}",
                f"NURION_LimbalRing.{side}",
                f"NURION_Catchlight.{side}",
            ]
        )
    objs.extend(
        [
            "NURION_GazeControl",
            "NURION_BlinkControl",
            "NURION_ExpressionControl",
            "NURION_BeautyControl",
        ]
    )
    return objs
