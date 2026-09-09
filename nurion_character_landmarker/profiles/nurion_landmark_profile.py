"""NURION Character Profile read/write (nurion-character-profile.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.landmark_engine import LandmarkPoint
from ..core.sources import ESTIMATED
from .profile_contract import MAX_PROFILE_BYTES, ContractViolation, normalize_and_validate

SCHEMA = "NURION_CHARACTER_PROFILE"
PROFILE_VERSION = "0.2.0-alpha.2"
DEFAULT_FILENAME = "nurion-character-profile.json"


@dataclass
class NurionCharacterProfile:
    character_id: str
    character_height: float
    forward_axis: str
    floor_z: float
    landmarks: List[dict] = field(default_factory=list)
    measurements: Dict[str, Any] = field(default_factory=dict)
    center: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    width: float = 0.0
    schema: str = SCHEMA
    version: str = PROFILE_VERSION

    def to_dict(self) -> dict:
        return {
            "schema": self.schema,
            "version": self.version,
            "characterId": self.character_id,
            "characterHeight": self.character_height,
            "width": self.width,
            "center": self.center,
            "forwardAxis": self.forward_axis,
            "floorZ": self.floor_z,
            "measurements": self.measurements,
            "landmarks": self.landmarks,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "NurionCharacterProfile":
        doc = normalize_and_validate(data)
        landmarks = doc["landmarks"]
        return cls(
            schema=doc["schema"],
            version=doc["version"],
            character_id=doc["characterId"],
            character_height=float(doc["characterHeight"]),
            width=float(doc["width"]),
            center=[float(v) for v in doc["center"]],
            forward_axis=doc["forwardAxis"],
            floor_z=float(doc["floorZ"]),
            measurements=dict(doc.get("measurements", {})),
            landmarks=landmarks,
        )

    def landmark_points(self) -> Dict[str, LandmarkPoint]:
        result: Dict[str, LandmarkPoint] = {}
        for entry in self.landmarks:
            point = LandmarkPoint.from_profile_entry(entry)
            if point.name == "unknown":
                continue
            result[point.name] = point
        return result


def save_profile(profile: NurionCharacterProfile, path: str | Path) -> Path:
    target = Path(path)
    if target.is_dir() or str(path).endswith(("/", "\\")):
        target = target / DEFAULT_FILENAME
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")

    document = normalize_and_validate(profile.to_dict())
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_profile(path: str | Path) -> NurionCharacterProfile:
    try:
        source = Path(path)
        if source.stat().st_size > MAX_PROFILE_BYTES:
            raise ContractViolation("PROFILE_INPUT_TOO_LARGE")
        data = json.loads(source.read_text(encoding="utf-8"))
    except OverflowError as exc:
        raise ContractViolation("PROFILE_INPUT_INVALID") from exc
    return NurionCharacterProfile.from_dict(data)


def default_export_path(directory: Optional[str] = None) -> Path:
    base = Path(directory) if directory else Path.home() / "Documents" / "NURION"
    return base / DEFAULT_FILENAME


def measurements_payload(measurements) -> Dict[str, Any]:
    """Serialize CharacterMeasurements with source tags."""
    if measurements is None:
        return {}
    return {
        "height": {"value": measurements.height.value, "source": measurements.height.source},
        "width": {"value": measurements.width.value, "source": measurements.width.source},
        "depth": {"value": measurements.depth.value, "source": measurements.depth.source},
        "center": {"value": list(measurements.center), "source": measurements.center_source},
        "floorZ": {"value": measurements.floor_position.value, "source": measurements.floor_position.source},
        "shoulderWidth": {
            "value": measurements.shoulder_width.value,
            "source": measurements.shoulder_width.source,
            "note": measurements.shoulder_width.note,
        },
        "hipWidth": {
            "value": measurements.hip_width.value,
            "source": measurements.hip_width.source,
            "note": measurements.hip_width.note,
        },
        "armLength": {
            "value": measurements.arm_length.value,
            "source": measurements.arm_length.source,
            "note": measurements.arm_length.note,
        },
        "legLength": {
            "value": measurements.leg_length.value,
            "source": measurements.leg_length.source,
            "note": measurements.leg_length.note,
        },
        "forwardAxis": {
            "value": measurements.forward_axis,
            "source": measurements.forward_axis_source,
        },
    }
