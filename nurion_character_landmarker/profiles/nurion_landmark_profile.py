"""NURION Character Profile read/write (nurion-character-profile.json)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..core.landmark_engine import LandmarkPoint
from ..core.sources import ESTIMATED

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
        raw_landmarks = data.get("landmarks", [])
        landmarks = _normalize_landmarks(raw_landmarks)
        return cls(
            schema=data.get("schema", SCHEMA),
            version=data.get("version", PROFILE_VERSION),
            character_id=data.get("characterId", "character-001"),
            character_height=float(data.get("characterHeight", 0.0)),
            width=float(data.get("width", 0.0)),
            center=[float(v) for v in data.get("center", [0.0, 0.0, 0.0])],
            forward_axis=data.get("forwardAxis", "-Y"),
            floor_z=float(data.get("floorZ", 0.0)),
            measurements=dict(data.get("measurements", {})),
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


def _normalize_landmarks(raw: Any) -> List[dict]:
    """Accept list-of-objects (v0.1) or legacy dict name→[x,y,z]."""
    if isinstance(raw, dict):
        out = []
        for name, value in raw.items():
            if isinstance(value, dict):
                entry = dict(value)
                entry.setdefault("name", name)
                out.append(LandmarkPoint.from_profile_entry(entry).to_profile_entry())
            else:
                point = LandmarkPoint.from_profile_entry(value)
                point.name = name
                out.append(point.to_profile_entry())
        return out

    if isinstance(raw, list):
        out = []
        for item in raw:
            if isinstance(item, dict):
                out.append(LandmarkPoint.from_profile_entry(item).to_profile_entry())
        return out

    return []


def save_profile(profile: NurionCharacterProfile, path: str | Path) -> Path:
    target = Path(path)
    if target.is_dir() or str(path).endswith(("/", "\\")):
        target = target / DEFAULT_FILENAME
    if target.suffix.lower() != ".json":
        target = target.with_suffix(".json")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(profile.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def load_profile(path: str | Path) -> NurionCharacterProfile:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
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
