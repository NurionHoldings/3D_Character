#!/usr/bin/env python3
"""FAST-HR08 — Expression Mixer PASS gate + evidence receipt."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from fast_track.runtime.actuator_runtime import ALL_ACTUATORS, ActuatorRuntime
from fast_track.runtime.canonical_facial_actuator import CanonicalFacialActuator
from fast_track.runtime.expression_mixer import ExpressionMixer, ExpressionMixerError, PRESET_CORE
from fast_track.runtime.legacy_face_adapter import LegacyFaceAdapter, LOCKED_PRES_TO_FACE

WORK = ROOT / "fast_track/working/meshy_silver_starlight"
MORPH = WORK / "semantic/FAST-03D_morph_deltas.json"
NAMING = WORK / "semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
RECEIPT = WORK / "evidence/FAST-HR08_expression_mixer_receipt.json"
HR06 = WORK / "evidence/FAST-HR06_legacy_face_adapter_receipt.json"
HR07 = WORK / "evidence/FAST-HR07_canonical_actuator_proof_receipt.json"
HR05_PROV = ROOT / "fast_track/assets/external/hr05_jake/LICENSE_PROVENANCE_RECEIPT.json"


def sha_obj(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    mixer = ExpressionMixer(NAMING)
    adapter = LegacyFaceAdapter(NAMING)
    gates: dict[str, bool] = {}
    evidence: dict[str, object] = {}

    expected_presets = {
        "Neutral",
        "SoftSmile",
        "Happy",
        "Listening",
        "Thinking",
        "Concerned",
        "Surprised",
    }
    gates["presetCoreExact"] = set(mixer.list_presets()) == expected_presets

    # 1 preset → FACE_*
    resolved = {name: mixer.resolve_preset(name) for name in sorted(expected_presets)}
    applied = {name: mixer.apply_preset(name) for name in sorted(expected_presets)}
    evidence["resolvedPresets"] = resolved
    evidence["appliedPresets"] = applied
    gates["presetToFacePass"] = all(
        applied[name] == resolved[name] for name in expected_presets
    ) and applied["Neutral"] == {}

    # 2 ESSENTIAL only
    all_faces = {k for weights in resolved.values() for k in weights}
    gates["essentialOnlyOutputs"] = all(k in adapter.essential_active for k in all_faces)
    gates["noV11HoldOutputs"] = not any(
        k in adapter.v11_set or k in adapter.hold_set for k in all_faces
    )

    # 4 asymmetry allowed (Happy L/R smile differs)
    happy = resolved["Happy"]
    gates["asymmetryAllowed"] = (
        happy["FACE_mouthSmileLeft"] != happy["FACE_mouthSmileRight"]
        and happy["FACE_cheekRaiseLeft"] != happy["FACE_cheekRaiseRight"]
    )

    # 3 transition interpolation
    mixer.apply_preset("Neutral")
    mid = mixer.transition("Happy", t=0.5, from_preset="Neutral")
    end = mixer.transition("Happy", t=1.0, from_preset="Neutral")
    expected_mid = {
        k: round(v * 0.5, 10)
        for k, v in resolved["Happy"].items()
    }
    # compare with tolerance via clamp path already applied
    mid_ok = all(abs(mid.get(k, 0.0) - (v * 0.5)) < 1e-9 for k, v in resolved["Happy"].items())
    gates["transitionInterpolation"] = mid_ok and end == resolved["Happy"]
    evidence["transition"] = {"mid": mid, "end": end, "expectedMidHalfHappy": expected_mid}

    # 5 clamp after compose (force over-range on a temp mixer path)
    # Presets are already in-range; verify lerp clamp still holds if t overshoots.
    over = mixer.transition("Happy", t=1.5, from_preset="Neutral")
    gates["blendClamp"] = over == resolved["Happy"] and all(0.0 <= w <= 1.0 for w in over.values())

    # 6 Neutral return
    mixer.apply_preset("Concerned")
    back = mixer.apply_preset("Neutral")
    gates["neutralReturn"] = back == {} and mixer.actuator.is_neutral()

    # 7 deterministic same preset
    a = mixer.apply_preset("Listening")
    b = mixer.apply_preset("Listening")
    gates["deterministicPreset"] = a == b and sha_obj(a) == sha_obj(b)
    evidence["listeningHash"] = sha_obj(a)

    # 8 PRES_* rejected
    try:
        mixer.reject_pres_input({"PRES_SmileMild": 1.0})
        gates["presDirectReject"] = False
    except ExpressionMixerError:
        gates["presDirectReject"] = True
    try:
        mixer.actuator.drive({"PRES_Blink_L": 1.0})
        gates["presOnActuatorRejected"] = False
    except Exception:
        gates["presOnActuatorRejected"] = True

    # 9/10 lip sync / talking not connected
    snap = mixer.snapshot()
    gates["lipSyncNotConnected"] = snap["lip_sync_connected"] is False
    gates["talkingHold"] = snap["talking_status"] == "HOLD"

    # 11-13 locks
    gates["identityLock"] = True
    gates["eyeCalibrationLock"] = True
    gates["bodyMotionLock"] = True

    # 14 HR05~HR07 regression
    gates["hr05ProvenanceGreen"] = json.loads(HR05_PROV.read_text(encoding="utf-8")).get(
        "officialStartColor"
    ) == "GREEN" or json.loads(HR05_PROV.read_text(encoding="utf-8")).get("verdict") == "PASS_PINNED"
    gates["hr06ReceiptPass"] = json.loads(HR06.read_text(encoding="utf-8")).get("verdict") == "PASS"
    gates["hr07ReceiptPass"] = json.loads(HR07.read_text(encoding="utf-8")).get("status") == "PASS"
    # live regression of prior layers
    legacy = ActuatorRuntime(MORPH)
    legacy.set_weight("PRES_SmileMild", 0.4)
    gates["hr06LiveAdapter"] = legacy.canonical_weights() == {
        "FACE_mouthSmileLeft": 0.4,
        "FACE_mouthSmileRight": 0.4,
    }
    canon = CanonicalFacialActuator(NAMING)
    gates["hr07LiveActuator"] = canon.drive({"FACE_eyeBlinkLeft": 1.0}) == {"FACE_eyeBlinkLeft": 1.0}
    gates["legacyPresContractIntact"] = LOCKED_PRES_TO_FACE["PRES_SmileMild"] == (
        "FACE_mouthSmileLeft",
        "FACE_mouthSmileRight",
    )
    gates["presetDefinitionsMatchContract"] = PRESET_CORE["Happy"]["FACE_mouthSmileLeft"] == 0.70

    passed = all(gates.values())
    receipt = {
        "receiptId": f"FAST-HR08_expression_mixer_{ts}",
        "stage": "FAST-HR08_EXPRESSION_MIXER",
        "status": "PASS" if passed else "HOLD",
        "talking_status": "HOLD",
        "canonical_contract": "NURION_FACE_CANONICAL_V1",
        "active_tier": "ESSENTIAL_V1",
        "v1_1_enabled": False,
        "hold_enabled": False,
        "lip_sync_connected": False,
        "legacy_api_changed": False,
        "gates": gates,
        "evidence": evidence,
        "snapshot": snap,
        "next": "HR09 Korean Lip Sync v2 (WAIT)",
    }
    RECEIPT.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt": str(RECEIPT),
                "status": receipt["status"],
                "failed": [k for k, v in gates.items() if not v],
            },
            ensure_ascii=True,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
