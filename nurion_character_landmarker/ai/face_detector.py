"""Face landmark detection facade — v0.3a geometry + multiview fusion."""

from __future__ import annotations

from typing import Dict, Optional

from ..core.character_analyzer import CharacterAnalysis
from ..core.face.correct import FaceCorrectionResult, correct_face_landmarks
from ..core.landmark_engine import LandmarkPoint
from ..core.measurement_engine import CharacterMeasurements


def detect_face(
    analysis: CharacterAnalysis,
    measurements: CharacterMeasurements,
    body: Optional[Dict[str, LandmarkPoint]] = None,
    mesh_obj=None,
) -> Dict[str, LandmarkPoint]:
    """
    Run v0.3a face correction when mesh is available; otherwise return empty.

    Callers should prefer detect_face_corrected() for eligibility + notes.
    """
    result = detect_face_corrected(analysis, measurements, body=body, mesh_obj=mesh_obj)
    return result.landmarks


def detect_face_corrected(
    analysis: CharacterAnalysis,
    measurements: CharacterMeasurements,
    body: Optional[Dict[str, LandmarkPoint]] = None,
    mesh_obj=None,
) -> FaceCorrectionResult:
    import bpy

    obj = mesh_obj
    if obj is None:
        obj = bpy.data.objects.get(analysis.object_name)
    if obj is None or obj.type != "MESH":
        from ..core.face.region import FaceRegionResult

        return FaceCorrectionResult(
            landmarks={},
            region=FaceRegionResult(eligible=False, reasonCode="FACE_ASSET_INELIGIBLE", headFrame=None),
            missing=[],
            notes=["No mesh object for face detection"],
        )
    return correct_face_landmarks(
        obj,
        body=body,
        forward_axis=measurements.forward_axis,
        core_only=True,
    )
