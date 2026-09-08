"""In-memory session state shared by operators and UI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .core.character_analyzer import CharacterAnalysis
from .core.landmark_engine import LandmarkPoint, LandmarkSet
from .core.measurement_engine import CharacterMeasurements


@dataclass
class SessionState:
    character_name: str = ""
    analysis: Optional[CharacterAnalysis] = None
    measurements: Optional[CharacterMeasurements] = None
    landmarks: LandmarkSet = field(default_factory=LandmarkSet)
    last_messages: List[str] = field(default_factory=list)
    low_confidence: List[str] = field(default_factory=list)
    validation_issues: List[str] = field(default_factory=list)
    last_profile_path: str = ""

    def all_landmarks(self) -> Dict[str, LandmarkPoint]:
        merged = dict(self.landmarks.body)
        merged.update(self.landmarks.face)
        return merged

    def set_message(self, message: str) -> None:
        self.last_messages = [message]


SESSION = SessionState()
