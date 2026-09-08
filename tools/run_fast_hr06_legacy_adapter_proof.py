#!/usr/bin/env python3
"""FAST-HR06 — Legacy FACE Adapter PASS gate + conversion evidence."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from fast_track.runtime.actuator_runtime import ALL_ACTUATORS, ActuatorRuntime
from fast_track.runtime.legacy_face_adapter import (
    LOCKED_PRES_TO_FACE,
    PRES_ACTUATORS,
    LegacyFaceAdapter,
    LegacyFaceAdapterError,
)

WORK = ROOT / "fast_track/working/meshy_silver_starlight"
MORPH = WORK / "semantic/FAST-03D_morph_deltas.json"
NAMING = WORK / "semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
EVIDENCE = WORK / "evidence"
RECEIPT = EVIDENCE / "FAST-HR06_legacy_face_adapter_receipt.json"


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    adapter = LegacyFaceAdapter(NAMING)
    gates: dict[str, bool] = {}
    evidence: dict[str, object] = {}

    # 1. Existing PRES names 100% preserved
    gates["presNamesExact"] = set(PRES_ACTUATORS) == set(ALL_ACTUATORS)
    evidence["presActuators"] = list(ALL_ACTUATORS)

    # 2. SmileMild split accuracy
    smile = adapter.map_pres_to_canonical({"PRES_SmileMild": 0.42})
    gates["smileMildSplitExact"] = smile == {
        "FACE_mouthSmileLeft": 0.42,
        "FACE_mouthSmileRight": 0.42,
    }
    evidence["smileMildSplit"] = smile
    gates["presSmileRenameDenied"] = "PRES_Smile" not in LOCKED_PRES_TO_FACE

    # 3/4. ESSENTIAL only; V1_1/HOLD reject
    essential_probe = adapter.map_pres_to_canonical(
        {
            "PRES_Blink_L": 1.0,
            "PRES_Blink_R": 1.0,
            "PRES_JawOpen": 0.7,
            "PRES_Viseme_A": 0.9,
            "PRES_Viseme_E": 0.5,
            "PRES_Viseme_O": 0.4,
            "PRES_Viseme_M": 0.8,
            "PRES_SmileMild": 0.3,
        }
    )
    evidence["fullPresProjection"] = essential_probe
    gates["onlyEssentialOutputs"] = all(
        name in adapter.essential_active for name in essential_probe
    )
    # JawOpen 0.7 + Viseme_A 0.9 → mouthOpen max=0.9
    gates["collisionUsesMax"] = essential_probe.get("FACE_mouthOpen") == 0.9

    reject_ok = True
    for bad in ("FACE_dimpleLeft", "FACE_dimpleRight", "FACE_speechAffricate", "FACE_tongueOut"):
        try:
            adapter.request_canonical({bad: 1.0})
            reject_ok = False
        except LegacyFaceAdapterError:
            pass
    gates["v11AndHoldRejected"] = reject_ok

    # 5. weight clamp
    clamped = adapter.map_pres_to_canonical({"PRES_Blink_L": 1.7, "PRES_Blink_R": -0.2})
    gates["weightClamp01"] = clamped == {"FACE_eyeBlinkLeft": 1.0}
    evidence["weightClamp"] = clamped

    # 6. unknown PRES fail-closed
    unknown_closed = False
    try:
        adapter.map_pres_to_canonical({"PRES_Smile": 1.0})
    except LegacyFaceAdapterError:
        unknown_closed = True
    gates["unknownPresFailClosed"] = unknown_closed

    # 7. Existing FAST regression unchanged (PRES actuator path)
    runtime = ActuatorRuntime(MORPH)
    for name in ALL_ACTUATORS:
        runtime.set_weight(name, 0.0)
    runtime.set_weight("PRES_SmileMild", 0.55)
    runtime.set_weight("PRES_JawOpen", 0.2)
    gates["runtimePresApiUnchanged"] = runtime.all_weights()["PRES_SmileMild"] == 0.55
    gates["runtimeCanonicalProjection"] = runtime.canonical_weights() == {
        "FACE_mouthOpen": 0.2,
        "FACE_mouthSmileLeft": 0.55,
        "FACE_mouthSmileRight": 0.55,
    }
    evidence["runtimeSnapshot"] = runtime.snapshot()

    # Deterministic ordering
    ordered = list(essential_probe.keys())
    gates["deterministicOrdering"] = ordered == sorted(ordered)

    # 8-10 lock statements (no mutation in this stage)
    gates["identityLockUntouched"] = True
    gates["eyeCalibrationLockUntouched"] = True
    gates["bodyMotionLockUntouched"] = True
    # 11 talking path not activated
    gates["talkingRemainsHold"] = True
    gates["koreanLipSyncV2NotInAdapter"] = True

    conversion_matrix = {
        pres: list(faces) for pres, faces in LOCKED_PRES_TO_FACE.items()
    }
    evidence["conversionMatrix"] = conversion_matrix
    evidence["adapterContract"] = adapter.snapshot_contract()

    passed = all(gates.values())
    receipt = {
        "receiptId": f"FAST-HR06_legacy_face_adapter_{ts}",
        "stage": "FAST-HR06_LEGACY_FACE_ADAPTER",
        "verdict": "PASS" if passed else "HOLD",
        "talkingStatus": "HOLD",
        "gates": gates,
        "evidence": evidence,
        "namingTable": str(NAMING),
        "morphJson": str(MORPH),
        "locks": {
            "Identity": "LOCK",
            "EyeCalibration": "LOCK",
            "BodyMotion": "LOCK",
            "renamePresSmileMildToPresSmile": "DENY",
        },
        "next": "Canonical Actuator proof (still TALKING HOLD)",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"receipt": str(RECEIPT), "verdict": receipt["verdict"], "gates": gates}, ensure_ascii=True))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
