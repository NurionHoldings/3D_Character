"""FAST-05A/05C/05D — Presentation state controller."""

from __future__ import annotations

import enum
import json
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from fast_track.runtime.actuator_runtime import ActuatorRuntime, ALL_ACTUATORS
from fast_track.runtime.camera_contract import CameraController, CAM_FULL, CAM_UPPER
from fast_track.runtime.facial_performance import FacialPerformanceRuntime


class PresentationState(enum.Enum):
    FULL_IDLE = "FULL_IDLE"
    MENU_SELECTED = "MENU_SELECTED"
    ZOOM_TO_UPPER = "ZOOM_TO_UPPER"
    EYE_CONTACT_SETTLE = "EYE_CONTACT_SETTLE"
    TALKING = "TALKING"
    NARRATION_END = "NARRATION_END"
    ZOOM_TO_FULL = "ZOOM_TO_FULL"


CANONICAL_ORDER = (
    PresentationState.FULL_IDLE,
    PresentationState.MENU_SELECTED,
    PresentationState.ZOOM_TO_UPPER,
    PresentationState.EYE_CONTACT_SETTLE,
    PresentationState.TALKING,
    PresentationState.NARRATION_END,
    PresentationState.ZOOM_TO_FULL,
    PresentationState.FULL_IDLE,
)


@dataclass
class MenuItem:
    id: str
    label: str
    audio_path: Path
    transcript: str


@dataclass
class TransitionLogEntry:
    cycle: int
    time_sec: float
    from_state: str
    to_state: str
    event: str
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "cycle": self.cycle,
            "timeSec": round(self.time_sec, 4),
            "from": self.from_state,
            "to": self.to_state,
            "event": self.event,
            "detail": self.detail,
        }


@dataclass
class InputGuardResult:
    accepted: bool
    action: str
    reason: str

    def to_dict(self) -> dict:
        return {"accepted": self.accepted, "action": self.action, "reason": self.reason}


class PresentationStateController:
    """Event-driven presentation UX state machine — ONE character instance."""

    EYE_CONTACT_SETTLE_SEC = 0.35

    def __init__(
        self,
        character_instance_id: str,
        morph_json: Path,
        menus: list[MenuItem],
        zoom_duration: float = 0.85,
    ):
        self.character_instance_id = character_instance_id
        self.morph_json = morph_json
        self.menus = {m.id: m for m in menus}
        self.state = PresentationState.FULL_IDLE
        self.camera = CameraController(zoom_duration)
        self.transition_log: list[TransitionLogEntry] = []
        self.input_guard_log: list[dict] = []
        self.cycle_index = 0
        self.global_time = 0.0
        self._selected_menu: MenuItem | None = None
        self._facial: FacialPerformanceRuntime | None = None
        self._talking_elapsed = 0.0
        self._eye_settle_elapsed = 0.0
        self._narration_complete_fired = False
        self._neutral_verified = False
        self.actuators = ActuatorRuntime(morph_json)

    def _log(self, to_state: PresentationState, event: str, **detail: Any) -> None:
        entry = TransitionLogEntry(
            cycle=self.cycle_index,
            time_sec=self.global_time,
            from_state=self.state.value,
            to_state=to_state.value,
            event=event,
            detail=detail,
        )
        self.transition_log.append(entry)
        self.state = to_state

    def input_guard(self, menu_id: str) -> InputGuardResult:
        if self.state == PresentationState.FULL_IDLE:
            result = InputGuardResult(True, "ACCEPT", "FULL_IDLE")
        else:
            result = InputGuardResult(False, "IGNORE", "BUSY")
        self.input_guard_log.append(
            {
                "cycle": self.cycle_index,
                "timeSec": round(self.global_time, 4),
                "state": self.state.value,
                "menuId": menu_id,
                **result.to_dict(),
            }
        )
        return result

    def handle_menu_click(self, menu_id: str) -> bool:
        guard = self.input_guard(menu_id)
        if not guard.accepted:
            return False
        if menu_id not in self.menus:
            return False
        self.cycle_index += 1
        self._selected_menu = self.menus[menu_id]
        self._log(
            PresentationState.MENU_SELECTED,
            "MENU_CLICK",
            menuId=menu_id,
            label=self._selected_menu.label,
        )
        self.camera.begin_zoom_to_upper()
        self._log(PresentationState.ZOOM_TO_UPPER, "BEGIN_ZOOM_TO_UPPER", target="CAM_UPPER")
        return True

    def tick(self, dt: float) -> dict[str, Any]:
        self.global_time += dt
        snapshot: dict[str, Any] = {
            "timeSec": round(self.global_time, 4),
            "state": self.state.value,
            "camera": self.camera.state().to_dict(),
            "cycle": self.cycle_index,
            "characterInstanceId": self.character_instance_id,
        }

        if self.state == PresentationState.ZOOM_TO_UPPER:
            if self.camera.tick(dt):
                self._log(PresentationState.EYE_CONTACT_SETTLE, "ZOOM_COMPLETE", camera="CAM_UPPER")
                self._eye_settle_elapsed = 0.0

        elif self.state == PresentationState.EYE_CONTACT_SETTLE:
            self._eye_settle_elapsed += dt
            if self._eye_settle_elapsed >= self.EYE_CONTACT_SETTLE_SEC:
                menu = self._selected_menu
                assert menu is not None
                self._facial = FacialPerformanceRuntime(self.morph_json, menu.audio_path, menu.transcript)
                self._talking_elapsed = 0.0
                self._narration_complete_fired = False
                self._log(
                    PresentationState.TALKING,
                    "BEGIN_TALKING",
                    menuId=menu.id,
                    eyeContactSettleSec=self.EYE_CONTACT_SETTLE_SEC,
                )

        elif self.state == PresentationState.TALKING:
            self._talking_elapsed += dt
            assert self._facial is not None
            t_audio = self._talking_elapsed
            weights = self._facial.sample(t_audio)
            for k, w in weights.items():
                self.actuators.set_weight(k, w)
            snapshot["facialWeights"] = weights
            if t_audio >= self._facial.duration and not self._narration_complete_fired:
                self._narration_complete_fired = True
                self._log(
                    PresentationState.NARRATION_END,
                    "NARRATION_COMPLETE",
                    authoritative="audio_duration",
                    audioDurationSec=self._facial.duration,
                )
                self.actuators.reset_all()
                self._neutral_verified = self.actuators.is_neutral(tol=0.0)
                self._log(
                    PresentationState.NARRATION_END,
                    "NEUTRAL_RESET",
                    pass_=self._neutral_verified,
                    contract="POST_NARRATION_NEUTRAL_PARITY_EXACT_ZERO",
                )
                self.camera.begin_zoom_to_full()
                self._log(PresentationState.ZOOM_TO_FULL, "BEGIN_ZOOM_TO_FULL", target="CAM_FULL")

        elif self.state == PresentationState.ZOOM_TO_FULL:
            # ensure weights stay neutral during zoom-out
            self.actuators.reset_all()
            if self.camera.tick(dt):
                self._log(PresentationState.FULL_IDLE, "ZOOM_OUT_COMPLETE", camera="CAM_FULL")
                self._selected_menu = None
                self._facial = None

        snapshot["weightsNeutral"] = self.actuators.is_neutral(tol=0.0)
        return snapshot

    def run_until_idle(self, dt: float = 1.0 / 60.0, max_steps: int = 20000) -> list[dict]:
        frames: list[dict] = []
        steps = 0
        while steps < max_steps:
            frames.append(self.tick(dt))
            if self.state == PresentationState.FULL_IDLE and self.cycle_index > 0:
                # need at least one tick after returning to idle
                if frames[-1].get("event") == "ZOOM_OUT_COMPLETE" or (
                    len(self.transition_log) >= 2
                    and self.transition_log[-1].event == "ZOOM_OUT_COMPLETE"
                ):
                    break
            steps += 1
            if self.state == PresentationState.FULL_IDLE and steps > 100 and self.cycle_index == 0:
                break
        return frames

    def run_cycle(self, menu_id: str, dt: float = 1.0 / 60.0) -> list[dict]:
        if not self.handle_menu_click(menu_id):
            return []
        frames: list[dict] = []
        max_steps = 20000
        for _ in range(max_steps):
            fr = self.tick(dt)
            frames.append(fr)
            if self.state == PresentationState.FULL_IDLE and self.transition_log[-1].event == "ZOOM_OUT_COMPLETE":
                break
        return frames

    def export_log(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "characterInstanceId": self.character_instance_id,
                    "transitions": [e.to_dict() for e in self.transition_log],
                    "inputGuard": self.input_guard_log,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
