#!/usr/bin/env python3
"""Adapter registry: one RetargetEngine + many DonorSkeletonProfile loaders."""

from __future__ import annotations

from pathlib import Path

from fast_track.runtime.retarget.engine import RetargetEngine
from fast_track.runtime.retarget.profile import DonorSkeletonProfile, load_profile

ROOT = Path(r"d:\NURION Character Landmarker")
PROFILE_DIR = ROOT / "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles"

# Profile ids — stable registration keys (not Canonical bone names)
PROFILE_MJN_LEGACY = "mjn_legacy_v1"
PROFILE_JAKE_CC = "jake_cc_v1"

_PROFILE_FILES = {
    PROFILE_MJN_LEGACY: PROFILE_DIR / "mjn_legacy_profile_v1.json",
    PROFILE_JAKE_CC: PROFILE_DIR / "jake_cc_profile_v1.json",
}


class RetargetAdapterRegistry:
    """
    RetargetAdapter
    ├── MJNLegacy (profile)
    ├── JakeCC (profile)
    └── future donor profiles

    Algorithms stay in RetargetEngine; adapters are profiles only.
    """

    def __init__(self, engine: RetargetEngine | None = None) -> None:
        self.engine = engine or RetargetEngine()
        self._profiles: dict[str, DonorSkeletonProfile] = {}

    def register_file(self, profile_id: str, path: Path) -> DonorSkeletonProfile:
        prof = load_profile(path)
        if prof.profile_id != profile_id:
            raise ValueError(f"profile_id mismatch: {prof.profile_id} != {profile_id}")
        self._profiles[profile_id] = prof
        return prof

    def register_defaults(self) -> None:
        for pid, path in _PROFILE_FILES.items():
            self.register_file(pid, path)

    def get(self, profile_id: str) -> DonorSkeletonProfile:
        if profile_id not in self._profiles:
            raise KeyError(profile_id)
        return self._profiles[profile_id]

    def list_ids(self) -> list[str]:
        return sorted(self._profiles)
