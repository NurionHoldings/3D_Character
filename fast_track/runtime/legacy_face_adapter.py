"""FAST-HR06 — Legacy PRES_* → NURION FACE Canonical v1 adapter.

Translates existing FAST presentation actuator names into ESSENTIAL_V1
canonical primitives only. Does not implement Korean Lip Sync v2.
Does not rename or delete PRES_* contracts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_NAMING_TABLE = (
    ROOT
    / "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json"
)

PRES_ACTUATORS = (
    "PRES_JawOpen",
    "PRES_Blink_L",
    "PRES_Blink_R",
    "PRES_SmileMild",
    "PRES_Viseme_A",
    "PRES_Viseme_E",
    "PRES_Viseme_O",
    "PRES_Viseme_M",
)

# Hard-locked contract (must match naming table; PRES_Smile rename DENY).
LOCKED_PRES_TO_FACE: dict[str, tuple[str, ...]] = {
    "PRES_JawOpen": ("FACE_mouthOpen",),
    "PRES_Blink_L": ("FACE_eyeBlinkLeft",),
    "PRES_Blink_R": ("FACE_eyeBlinkRight",),
    "PRES_SmileMild": ("FACE_mouthSmileLeft", "FACE_mouthSmileRight"),
    "PRES_Viseme_A": ("FACE_mouthOpen",),
    "PRES_Viseme_E": ("FACE_mouthWiden",),
    "PRES_Viseme_O": ("FACE_mouthPucker",),
    "PRES_Viseme_M": ("FACE_mouthPlosive",),
}


class LegacyFaceAdapterError(ValueError):
    """Fail-closed adapter error."""


class LegacyFaceAdapter:
    """PRES_* runtime contract → FACE Canonical v1 ESSENTIAL primitives."""

    def __init__(self, naming_table_path: Path | None = None):
        path = Path(naming_table_path) if naming_table_path else DEFAULT_NAMING_TABLE
        table = json.loads(path.read_text(encoding="utf-8"))
        self.naming_table_path = path
        self.table = table
        self._tier_by_canonical = {
            row["nurionCanonical"]: row["tier"] for row in table["rows"]
        }
        self.essential_active: frozenset[str] = frozenset(
            name for name, tier in self._tier_by_canonical.items() if tier == "ESSENTIAL_V1"
        )
        self.v11_set: frozenset[str] = frozenset(
            name for name, tier in self._tier_by_canonical.items() if tier == "V1_1"
        )
        self.hold_set: frozenset[str] = frozenset(
            name for name, tier in self._tier_by_canonical.items() if tier == "HOLD"
        )
        contract = table.get("legacyAdapterContract") or {}
        for pres, faces in LOCKED_PRES_TO_FACE.items():
            expected = tuple(contract.get(pres, []))
            if expected != faces:
                raise LegacyFaceAdapterError(
                    f"Naming-table contract mismatch for {pres}: {expected} != {faces}"
                )
            for face in faces:
                if face not in self.essential_active:
                    raise LegacyFaceAdapterError(
                        f"{pres} maps to non-ESSENTIAL target {face}"
                    )
        if contract.get("renamePresSmileMildToPresSmile") != "DENY":
            raise LegacyFaceAdapterError("renamePresSmileMildToPresSmile must be DENY")
        if "PRES_Smile" in LOCKED_PRES_TO_FACE or "PRES_Smile" in contract:
            raise LegacyFaceAdapterError("PRES_Smile creation/rename is DENY")

    @staticmethod
    def clamp_weight(weight: float) -> float:
        return max(0.0, min(1.0, float(weight)))

    def map_pres_to_canonical(
        self,
        pres_weights: dict[str, float],
        *,
        fail_closed_unknown: bool = True,
    ) -> dict[str, float]:
        """Translate PRES weights into ESSENTIAL_V1 FACE weights.

        Colliding targets (e.g. JawOpen + Viseme_A → mouthOpen) use max().
        SmileMild splits symmetrically to L/R with the same clamped weight.
        """
        out: dict[str, float] = {}
        for name, raw in sorted(pres_weights.items()):
            if name not in LOCKED_PRES_TO_FACE:
                if fail_closed_unknown:
                    raise LegacyFaceAdapterError(f"Unknown PRES actuator (fail-closed): {name}")
                continue
            weight = self.clamp_weight(raw)
            if weight <= 0.0:
                continue
            for face in LOCKED_PRES_TO_FACE[name]:
                if face not in self.essential_active:
                    raise LegacyFaceAdapterError(
                        f"Rejected non-ESSENTIAL canonical target from {name}: {face}"
                    )
                out[face] = max(out.get(face, 0.0), weight)
        # Deterministic ordering.
        return {k: out[k] for k in sorted(out)}

    def request_canonical(
        self,
        face_weights: dict[str, float],
    ) -> dict[str, float]:
        """Accept only ESSENTIAL_V1 FACE_* requests; reject V1_1/HOLD/unknown."""
        out: dict[str, float] = {}
        for name, raw in sorted(face_weights.items()):
            tier = self._tier_by_canonical.get(name)
            if tier is None:
                raise LegacyFaceAdapterError(f"Unknown canonical face shape: {name}")
            if tier == "V1_1":
                raise LegacyFaceAdapterError(f"V1_1 canonical not active in HR06: {name}")
            if tier == "HOLD":
                raise LegacyFaceAdapterError(f"HOLD canonical rejected: {name}")
            if tier != "ESSENTIAL_V1":
                raise LegacyFaceAdapterError(f"Unsupported tier {tier} for {name}")
            weight = self.clamp_weight(raw)
            if weight > 0.0:
                out[name] = weight
        return {k: out[k] for k in sorted(out)}

    def snapshot_contract(self) -> dict[str, Any]:
        return {
            "presActuators": list(PRES_ACTUATORS),
            "lockedPresToFace": {k: list(v) for k, v in LOCKED_PRES_TO_FACE.items()},
            "essentialActiveCount": len(self.essential_active),
            "v11Count": len(self.v11_set),
            "holdCount": len(self.hold_set),
            "renamePresSmileMildToPresSmile": "DENY",
            "koreanLipSyncV2InAdapter": "DENY",
            "talkingActivation": "HOLD",
            "namingTable": str(self.naming_table_path),
        }
