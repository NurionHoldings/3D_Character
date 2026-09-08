"""Face region separation and eligibility (generation-safe, no GT)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from mathutils import Vector

from ..leak_guard import assert_no_gt_parameters
from ..transform_normalize import WorldMeshView, build_world_mesh_view
from .parameters import FACE_ALPHA1_PARAMETERS
from .spaces import HeadFrame, build_head_frame


EXCLUDE_TOKENS = [t.lower() for t in FACE_ALPHA1_PARAMETERS["region"]["excludeNameTokens"]]
EYEBALL_TOKENS = [t.lower() for t in FACE_ALPHA1_PARAMETERS["region"]["eyeballNameTokens"]]


@dataclass
class FaceRegionResult:
    eligible: bool
    reasonCode: str
    headFrame: Optional[HeadFrame]
    faceVertexIndices: List[int] = field(default_factory=list)
    faceVertexWorld: List[Vector] = field(default_factory=list)
    eyeballObjects: List[str] = field(default_factory=list)
    excludedObjects: List[str] = field(default_factory=list)
    checks: Dict[str, bool] = field(default_factory=dict)
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema": "NURION_FACE_ELIGIBILITY",
            "assetEligible": self.eligible,
            "reasonCode": self.reasonCode,
            "checks": dict(self.checks),
            "eyeballObjects": list(self.eyeballObjects),
            "excludedObjects": list(self.excludedObjects),
            "faceVertexCount": len(self.faceVertexWorld),
            "details": dict(self.details),
        }


def _name_has_token(name: str, tokens: List[str]) -> bool:
    n = name.lower()
    return any(t in n for t in tokens)


def classify_scene_meshes(primary_mesh_name: str) -> Tuple[List[str], List[str], List[str]]:
    """Return (face_candidates, eyeballs, excluded) object names."""
    import bpy

    face_like: List[str] = []
    eyeballs: List[str] = []
    excluded: List[str] = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if _name_has_token(obj.name, EXCLUDE_TOKENS):
            excluded.append(obj.name)
            continue
        if _name_has_token(obj.name, EYEBALL_TOKENS) and obj.name != primary_mesh_name:
            eyeballs.append(obj.name)
            continue
        face_like.append(obj.name)
    return face_like, eyeballs, excluded


def _collect_head_vertices(
    view: WorldMeshView,
    mesh_obj,
    frame: HeadFrame,
    *,
    head_height_ratio: float,
) -> Tuple[List[int], List[Vector]]:
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(deps)
    me = eval_obj.to_mesh()
    try:
        me.transform(eval_obj.matrix_world)
        z_min = float(view.bounds_min.z)
        z_max = float(view.bounds_max.z)
        height = max(z_max - z_min, 1e-6)
        head_z0 = z_max - height * head_height_ratio
        idxs: List[int] = []
        worlds: List[Vector] = []
        for i, v in enumerate(me.vertices):
            p = v.co
            if float(p.z) < head_z0:
                continue
            # Prefer frontal hemisphere in head frame (forward local y >= -small).
            local = frame.to_local(p)
            if float(local.y) < -frame.head_height * 0.15:
                continue
            idxs.append(i)
            worlds.append(p.copy())
        return idxs, worlds
    finally:
        eval_obj.to_mesh_clear()


def evaluate_face_region(
    mesh_obj,
    *,
    view: Optional[WorldMeshView] = None,
    body: Optional[dict] = None,
    forward_axis: str = "+Y",
    **kwargs,
) -> FaceRegionResult:
    assert_no_gt_parameters(**kwargs)
    view = view or build_world_mesh_view(mesh_obj)
    params = FACE_ALPHA1_PARAMETERS["region"]

    height = float((view.bounds_max - view.bounds_min).z)
    head_h = height * float(params["headHeightRatio"])
    head_center = Vector((view.center.x, view.center.y, view.bounds_max.z - head_h * 0.45))
    frame = build_head_frame(
        head_center=head_center,
        forward_axis=forward_axis,
        head_height=head_h,
        body=body,
    )

    face_like, eyeballs, excluded = classify_scene_meshes(mesh_obj.name)
    idxs, worlds = _collect_head_vertices(
        view, mesh_obj, frame, head_height_ratio=float(params["headHeightRatio"])
    )

    checks = {
        "headVolumePresent": head_h > 1e-4,
        "faceVerticesSufficient": len(worlds) >= int(params["minFaceVertexCount"]),
        "frontAxisUsable": frame.forward.length > 0.5,
        "lateralComponentsPresent": False,
        "symmetryPlaneUsable": True,
    }

    if worlds:
        xs = [frame.to_local(p).x for p in worlds]
        left = [x for x in xs if x > 0]
        right = [x for x in xs if x < 0]
        gap = (max(left) - min(right)) if left and right else 0.0
        checks["lateralComponentsPresent"] = bool(left and right and gap >= head_h * float(params["minLateralGapHeadHeight"]))
    else:
        gap = 0.0

    reason = "ELIGIBLE"
    eligible = all(
        [
            checks["headVolumePresent"],
            checks["faceVerticesSufficient"],
            checks["frontAxisUsable"],
            checks["lateralComponentsPresent"],
        ]
    )
    if not checks["faceVerticesSufficient"]:
        reason = "FACE_ASSET_INELIGIBLE"
    elif not checks["lateralComponentsPresent"]:
        reason = "FACE_ASSET_INELIGIBLE"
    elif not checks["frontAxisUsable"]:
        reason = "FACE_ASSET_INELIGIBLE"

    return FaceRegionResult(
        eligible=eligible,
        reasonCode=reason,
        headFrame=frame,
        faceVertexIndices=idxs,
        faceVertexWorld=worlds,
        eyeballObjects=eyeballs,
        excludedObjects=excluded,
        checks=checks,
        details={
            "headHeight": round(head_h, 6),
            "characterHeight": round(height, 6),
            "lateralGap": round(float(gap), 6),
            "faceLikeMeshes": face_like[:20],
            "minFaceVertexCount": int(params["minFaceVertexCount"]),
        },
    )
