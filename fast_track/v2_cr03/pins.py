"""CR03 shared pins / timeline parameters (declared before injection)."""

from __future__ import annotations

APPROVED_SPEC_DIGEST = "3e3885335bcfd8489209a302852230ae6cdd55da89fb8328048f82d8fe4a206c"
CR02_R2_DERIVED_SHA = "1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd"
CR = "V2-CR-03"

# P01 pinned binding (CONSUME ONLY)
MORPH_INDEX_MAP = {
    "VISEME_AA": {"targetIndex": 6, "positionAccessor": 87},
    "VISEME_OH": {"targetIndex": 7, "positionAccessor": 88},
    "VISEME_EE": {"targetIndex": 8, "positionAccessor": 89},
}

REQUIRED_MORPHS = ("VISEME_AA", "VISEME_OH", "VISEME_EE")
TALKING_ANIMATION_NAME = "NURION_TALKING_VISEME_SEQUENCE"

# Deterministic timeline parameters (sequence semantics from SPEC; timings pinned here for P02+)
# Format: (t_seconds, aa, oh, ee)
TALKING_TIMELINE = (
    (0.00, 0.0, 0.0, 0.0),  # NEUTRAL
    (0.10, 1.0, 0.0, 0.0),  # AA
    (0.25, 0.0, 1.0, 0.0),  # OH
    (0.40, 0.0, 0.0, 1.0),  # EE
    (0.55, 0.0, 0.0, 0.0),  # NEUTRAL
)

ACTIVATION_THRESHOLD = 1e-4
RESTORATION_TOLERANCE = 1e-6

COMPONENT_FLOAT = 5126
TYPE_SCALAR = "SCALAR"
MESH_NODE_NAME = "char1"  # Idle_15 skinned mesh node (mesh index 0)
