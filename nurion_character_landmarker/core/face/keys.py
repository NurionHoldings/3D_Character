"""Face landmark key registry for v0.3a."""

from __future__ import annotations

from typing import List

# Full planned face set (GT annotation template).
FACE_LANDMARK_KEYS_FULL: List[str] = [
    "face.center",
    "head.top",
    "chin",
    "jaw.L",
    "jaw.R",
    "eye.center.L",
    "eye.center.R",
    "eye.inner.L",
    "eye.inner.R",
    "eye.outer.L",
    "eye.outer.R",
    "eyelid.upper.L",
    "eyelid.upper.R",
    "eyelid.lower.L",
    "eyelid.lower.R",
    "iris.visualCenter.L",
    "iris.visualCenter.R",
    "brow.inner.L",
    "brow.inner.R",
    "brow.center.L",
    "brow.center.R",
    "brow.outer.L",
    "brow.outer.R",
    "nose.bridge",
    "nose.tip",
    "nostril.L",
    "nostril.R",
    "mouth.center",
    "mouth.corner.L",
    "mouth.corner.R",
    "lip.upper",
    "lip.lower",
    "ear.center.L",
    "ear.center.R",
    "ear.top.L",
    "ear.top.R",
    "ear.bottom.L",
    "ear.bottom.R",
]

# Alias used in docs / GT tooling.
FACE_LANDMARK_KEYS = list(FACE_LANDMARK_KEYS_FULL)

# v0.3a Alpha1 direction-validation core set (13).
ALPHA1_CORE_KEYS: List[str] = [
    "eye.center.L",
    "eye.center.R",
    "eye.inner.L",
    "eye.inner.R",
    "eye.outer.L",
    "eye.outer.R",
    "nose.tip",
    "mouth.center",
    "mouth.corner.L",
    "mouth.corner.R",
    "chin",
    "ear.center.L",
    "ear.center.R",
]

# v0.3a-alpha.2 Meshy Eye Proxy — human-confirmable surface GT (+ derived eye.center).
ALPHA2_EYE_SURFACE_KEYS: List[str] = [
    "eye.inner.L",
    "eye.inner.R",
    "eye.outer.L",
    "eye.outer.R",
    "eyelid.upper.L",
    "eyelid.upper.R",
    "eyelid.lower.L",
    "eyelid.lower.R",
    "iris.visualCenter.L",
    "iris.visualCenter.R",
]

ALPHA2_DERIVED_EYE_CENTER_KEYS: List[str] = [
    "eye.center.L",
    "eye.center.R",
]

# Alpha2 facial detail (later).
ALPHA2_DETAIL_KEYS: List[str] = [
    "eyelid.upper.L",
    "eyelid.upper.R",
    "eyelid.lower.L",
    "eyelid.lower.R",
    "brow.inner.L",
    "brow.inner.R",
    "brow.center.L",
    "brow.center.R",
    "brow.outer.L",
    "brow.outer.R",
    "lip.upper",
    "lip.lower",
    "nose.bridge",
    "nostril.L",
    "nostril.R",
    "jaw.L",
    "jaw.R",
    "ear.top.L",
    "ear.top.R",
    "ear.bottom.L",
    "ear.bottom.R",
    "face.center",
    "head.top",
]
