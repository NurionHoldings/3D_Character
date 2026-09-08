"""End-to-end Alpha2 Meshy Eye Proxy + Procedural Eyeball pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters
from ..transform_normalize import WorldMeshView, build_world_mesh_view
from .eye_proxy import EyeProxyResult, build_eye_proxy
from .procedural_eyeball import ProceduralEyeballResult, create_procedural_eyeballs
from .region import FaceRegionResult, evaluate_face_region


@dataclass
class EyeProxyPipelineResult:
    region: FaceRegionResult
    proxy: EyeProxyResult
    eyeballs: ProceduralEyeballResult
    landmarks: Dict[str, LandmarkPoint] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": "NURION_EYE_PROXY_PIPELINE_RESULT",
            "eligibleFaceRegion": self.region.eligible,
            "reasonCode": self.region.reasonCode,
            "surfaceCount": len(self.proxy.surface),
            "centerCount": len(self.proxy.centers),
            "eyeballObjects": dict(self.eyeballs.objects),
            "radiiM": {k: round(v, 6) for k, v in self.proxy.radii.items()},
            "notes": list(self.notes) + list(self.proxy.notes) + list(self.eyeballs.notes),
            "centers": {
                k: {
                    "position": [round(float(p.position.x), 6), round(float(p.position.y), 6), round(float(p.position.z), 6)],
                    "source": p.source,
                    "evidence": p.evidence,
                }
                for k, p in self.proxy.centers.items()
            },
        }


def run_eye_proxy_pipeline(
    mesh_obj,
    *,
    view: Optional[WorldMeshView] = None,
    body: Optional[dict] = None,
    forward_axis: str = "+Y",
    create_meshes: bool = True,
    **kwargs,
) -> EyeProxyPipelineResult:
    assert_no_gt_parameters(**kwargs)
    view = view or build_world_mesh_view(mesh_obj)
    region = evaluate_face_region(mesh_obj, view=view, body=body, forward_axis=forward_axis)
    proxy = build_eye_proxy(view, region)
    eyeballs = ProceduralEyeballResult()
    if create_meshes and region.headFrame is not None and proxy.centers:
        eyeballs = create_procedural_eyeballs(proxy, region.headFrame)
    landmarks = proxy.all_landmarks()
    notes = []
    if len(proxy.centers) < 2:
        notes.append("Eye proxy incomplete — both eyes required")
    return EyeProxyPipelineResult(
        region=region,
        proxy=proxy,
        eyeballs=eyeballs,
        landmarks=landmarks,
        notes=notes,
    )
