"""Left/right and anatomical chain constraints for corrected landmarks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from mathutils import Vector

from .landmark_engine import LandmarkPoint
from .sources import ESTIMATED, GEOMETRY_CORRECTED


ARM_CHAINS = (("shoulder.L", "elbow.L", "wrist.L"), ("shoulder.R", "elbow.R", "wrist.R"))
LEG_CHAINS = (("hip.L", "knee.L", "ankle.L"), ("hip.R", "knee.R", "ankle.R"))


@dataclass
class ConstraintReport:
    left_right_swaps: List[str] = field(default_factory=list)
    rejected_outside: List[str] = field(default_factory=list)
    rejected_chain: List[str] = field(default_factory=list)
    symmetry_applied: List[str] = field(default_factory=list)
    forced_review: List[str] = field(default_factory=list)


def _length(a: Vector, b: Vector) -> float:
    return (a - b).length


def detect_left_right_swaps(landmarks: Dict[str, LandmarkPoint], center_x: float) -> List[str]:
    swaps: List[str] = []
    pairs = [
        ("shoulder.L", "shoulder.R"),
        ("elbow.L", "elbow.R"),
        ("wrist.L", "wrist.R"),
        ("hip.L", "hip.R"),
        ("knee.L", "knee.R"),
        ("ankle.L", "ankle.R"),
    ]
    for left, right in pairs:
        if left not in landmarks or right not in landmarks:
            continue
        # Convention: +X is character left.
        if landmarks[left].position.x < landmarks[right].position.x:
            swaps.append(f"{left}/{right}")
    _ = center_x
    return swaps


def apply_symmetry_correction(
    landmarks: Dict[str, LandmarkPoint],
    center_x: float,
    pairs: Tuple[Tuple[str, str], ...] = (
        ("shoulder.L", "shoulder.R"),
        ("elbow.L", "elbow.R"),
        ("wrist.L", "wrist.R"),
        ("hip.L", "hip.R"),
        ("knee.L", "knee.R"),
        ("ankle.L", "ankle.R"),
    ),
) -> List[str]:
    """Soft L/R Y/Z averaging when both are GEOMETRY_CORRECTED.

    X is NOT remapped to a shared offset — equalizing stance width was collapsing
    medial limbs (especially ankle.R / knee.R) and dominating max-error.
    """
    applied: List[str] = []
    _ = center_x
    for left, right in pairs:
        if left not in landmarks or right not in landmarks:
            continue
        lp = landmarks[left]
        rp = landmarks[right]
        if lp.source != GEOMETRY_CORRECTED or rp.source != GEOMETRY_CORRECTED:
            continue
        # Extremities: skip symmetry entirely (feet/hands are often mesh-asymmetric).
        if left.startswith(("ankle.", "wrist.")):
            continue
        avg_y = 0.5 * (lp.position.y + rp.position.y)
        avg_z = 0.5 * (lp.position.z + rp.position.z)
        lp.position = Vector((lp.position.x, avg_y, avg_z))
        rp.position = Vector((rp.position.x, avg_y, avg_z))
        if lp.evidence is not None:
            lp.evidence["symmetryApplied"] = True
            lp.evidence["symmetryMode"] = "YZ_ONLY"
        if rp.evidence is not None:
            rp.evidence["symmetryApplied"] = True
            rp.evidence["symmetryMode"] = "YZ_ONLY"
        applied.extend([left, right])
    return applied


def validate_chain_lengths(
    landmarks: Dict[str, LandmarkPoint],
    height: float,
) -> List[str]:
    """Reject abnormal chain segment lengths relative to character height."""
    rejected: List[str] = []
    # Reasonable segment ratios of total height.
    limits = {
        ("shoulder", "elbow"): (0.08, 0.35),
        ("elbow", "wrist"): (0.08, 0.35),
        ("hip", "knee"): (0.12, 0.45),
        ("knee", "ankle"): (0.12, 0.45),
    }

    def check(a: str, b: str, key: Tuple[str, str]) -> None:
        if a not in landmarks or b not in landmarks:
            return
        if landmarks[a].source != GEOMETRY_CORRECTED and landmarks[b].source != GEOMETRY_CORRECTED:
            return
        lo, hi = limits[key]
        seg = _length(landmarks[a].position, landmarks[b].position)
        if seg < height * lo or seg > height * hi:
            rejected.append(f"{a}->{b}")

    for shoulder, elbow, wrist in ARM_CHAINS:
        check(shoulder, elbow, ("shoulder", "elbow"))
        check(elbow, wrist, ("elbow", "wrist"))
    for hip, knee, ankle in LEG_CHAINS:
        check(hip, knee, ("hip", "knee"))
        check(knee, ankle, ("knee", "ankle"))
    return rejected


def revert_to_estimated(
    current: Dict[str, LandmarkPoint],
    estimated: Dict[str, LandmarkPoint],
    names: List[str],
) -> None:
    for name in names:
        base = name.split("->")[0] if "->" in name else name
        targets = [base]
        if "->" in name:
            targets = name.split("->")
        for key in targets:
            if key in estimated:
                prev = estimated[key]
                current[key] = LandmarkPoint(
                    name=prev.name,
                    position=prev.position.copy(),
                    source=ESTIMATED,
                    confidence=prev.confidence,
                    side=prev.side,
                    evidence={"reverted": True, "reason": "chain_or_outside_reject"},
                )
