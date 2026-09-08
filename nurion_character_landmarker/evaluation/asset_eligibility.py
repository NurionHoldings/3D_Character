"""Asset Eligibility Gate — evaluation-only validity of mesh↔GT pairing.

GT bones may be read here solely to decide whether an asset may enter quality
evaluation. This module must never be called from landmark generation paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..core.leak_guard import note_gt_access
from ..core.transform_normalize import WorldMeshView, build_world_mesh_view
from .gt_bones import collect_gt_landmarks


# Structural reachability thresholds for Alpha3 ankle gates (cm).
ANKLE_GATE_CM = 10.0
DEFAULT_FOOT_Z_MAX = 0.12


REASON_MESH_GT_MISMATCH = "MESH_GT_MISMATCH"
REASON_MISSING_LATERAL_COMPONENT = "MISSING_LATERAL_COMPONENT"
REASON_TRANSFORM_INCONSISTENT = "TRANSFORM_INCONSISTENT"
REASON_REST_POSE_MIX = "REST_POSE_MIX"
REASON_OK = "ELIGIBLE"


@dataclass
class AssetEligibilityResult:
    assetEligible: bool
    reasonCode: str
    blockedJoints: List[str] = field(default_factory=list)
    evaluationExcluded: List[str] = field(default_factory=list)
    evaluationAllowed: bool = False
    autoRigAllowed: bool = False
    checks: Dict[str, bool] = field(default_factory=dict)
    details: Dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "schema": "NURION_ASSET_ELIGIBILITY",
            "assetEligible": self.assetEligible,
            "reasonCode": self.reasonCode,
            "blockedJoints": list(self.blockedJoints),
            "evaluationExcluded": list(self.evaluationExcluded),
            "evaluationAllowed": self.evaluationAllowed,
            "autoRigAllowed": self.autoRigAllowed,
            "checks": dict(self.checks),
            "details": dict(self.details),
        }


def _world_space_consistent(mesh_obj, arm_obj) -> Tuple[bool, dict]:
    """Mesh and armature must both expose usable world transforms (same space)."""
    mm = mesh_obj.matrix_world.copy()
    am = arm_obj.matrix_world.copy()
    # Allow independent object transforms; require both to be finite/invertible.
    try:
        _ = mm.inverted()
        _ = am.inverted()
        ok = True
    except Exception:
        ok = False
    detail = {
        "meshMatrixDet": round(float(mm.determinant()), 6),
        "armMatrixDet": round(float(am.determinant()), 6),
        "meshLocation": [round(float(x), 6) for x in mesh_obj.location],
        "armLocation": [round(float(x), 6) for x in arm_obj.location],
    }
    return ok, detail


def _rest_pose_consistent(arm_obj) -> Tuple[bool, dict]:
    """Detect Rest/Pose mix. GT readers use rest local heads; prefer REST mode."""
    note_gt_access("asset_eligibility:rest_pose_check")
    pose_position = getattr(arm_obj.data, "pose_position", "REST")
    max_delta = 0.0
    if arm_obj.pose is not None:
        for pb in arm_obj.pose.bones:
            t = pb.matrix_basis.to_translation().length
            max_delta = max(max_delta, float(t))
            e = pb.matrix_basis.to_euler()
            max_delta = max(max_delta, abs(float(e.x)) + abs(float(e.y)) + abs(float(e.z)))
    # PASS when armature is in REST, or POSE bones are effectively identity.
    ok = (str(pose_position) == "REST") or (max_delta < 1e-4)
    detail = {
        "posePosition": str(pose_position),
        "maxPoseDelta": round(max_delta, 6),
        "preferred": "REST",
        "gtUsesRestLocalHeads": True,
    }
    return ok, detail


def _foot_clusters(
    view: WorldMeshView,
    mesh_obj,
    *,
    center_x: float,
    z_max: float,
) -> Tuple[List[Vector], List[Vector], dict]:
    """Collect low vertices on L/R halves in world space."""
    import bpy

    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = mesh_obj.evaluated_get(deps)
    me = eval_obj.to_mesh()
    try:
        me.transform(eval_obj.matrix_world)
        left: List[Vector] = []
        right: List[Vector] = []
        for vert in me.vertices:
            p = vert.co
            if float(p.z) > z_max:
                continue
            if float(p.x) >= center_x:
                left.append(p.copy())
            else:
                right.append(p.copy())
    finally:
        eval_obj.to_mesh_clear()

    def _mean(pts: List[Vector]) -> Optional[List[float]]:
        if not pts:
            return None
        c = Vector((0.0, 0.0, 0.0))
        for p in pts:
            c += p
        c /= float(len(pts))
        return [round(float(c.x), 4), round(float(c.y), 4), round(float(c.z), 4)]

    detail = {
        "leftCount": len(left),
        "rightCount": len(right),
        "leftMean": _mean(left),
        "rightMean": _mean(right),
        "leftXRange": (
            [round(min(p.x for p in left), 4), round(max(p.x for p in left), 4)] if left else None
        ),
        "rightXRange": (
            [round(min(p.x for p in right), 4), round(max(p.x for p in right), 4)] if right else None
        ),
        "zMax": z_max,
    }
    return left, right, detail


def _lateral_components_ok(left: List[Vector], right: List[Vector], center_x: float, height: float) -> Tuple[bool, dict]:
    min_count = 50
    ok_counts = len(left) >= min_count and len(right) >= min_count
    if not ok_counts:
        return False, {"minCount": min_count, "leftCount": len(left), "rightCount": len(right)}
    l_mean_x = sum(p.x for p in left) / len(left)
    r_mean_x = sum(p.x for p in right) / len(right)
    # Centers must lie on opposite sides of the symmetry plane with a gap.
    gap = abs(l_mean_x - r_mean_x)
    opposite = l_mean_x > center_x and r_mean_x < center_x
    min_gap = height * 0.04
    ok = opposite and gap >= min_gap
    return ok, {
        "leftMeanX": round(l_mean_x, 4),
        "rightMeanX": round(r_mean_x, 4),
        "gap": round(gap, 4),
        "minGap": round(min_gap, 4),
        "oppositeSides": opposite,
    }


def _best_inside_error_cm(cluster: List[Vector], gt_pos: Vector) -> Optional[float]:
    if not cluster:
        return None
    # Use cluster mean lifted slightly above sole as the best wearable-foot center.
    c = Vector((0.0, 0.0, 0.0))
    for p in cluster:
        c += p
    c /= float(len(cluster))
    c.z += 0.03
    return float((c - gt_pos).length * 100.0)


def evaluate_asset_eligibility(
    mesh_obj,
    arm_obj,
    *,
    view: Optional[WorldMeshView] = None,
    ankle_gate_cm: float = ANKLE_GATE_CM,
    foot_z_max: Optional[float] = None,
) -> AssetEligibilityResult:
    """
    Evaluation-only gate. Uses GT bone positions solely for asset validity.

    Does not generate landmarks and must not be invoked inside generation_scope
    for production of coordinates (callers should run this in evaluation phase).
    """
    note_gt_access("evaluate_asset_eligibility")
    mesh_view = view or build_world_mesh_view(mesh_obj)
    height = float(mesh_view.dimensions.z)
    center_x = float(mesh_view.center.x)
    z_max = foot_z_max if foot_z_max is not None else max(DEFAULT_FOOT_Z_MAX, height * 0.08)

    checks: Dict[str, bool] = {}
    details: Dict = {"height": round(height, 4), "centerX": round(center_x, 4)}

    world_ok, world_detail = _world_space_consistent(mesh_obj, arm_obj)
    checks["worldTransformUsable"] = world_ok
    details["worldTransform"] = world_detail

    rest_ok, rest_detail = _rest_pose_consistent(arm_obj)
    checks["restPoseConsistent"] = rest_ok
    details["restPose"] = rest_detail

    left, right, cluster_detail = _foot_clusters(mesh_view, mesh_obj, center_x=center_x, z_max=z_max)
    details["footClusters"] = cluster_detail
    lat_ok, lat_detail = _lateral_components_ok(left, right, center_x, height)
    checks["lateralComponentsPresent"] = len(left) >= 50 and len(right) >= 50
    checks["lateralCentersOpposite"] = bool(lat_detail.get("oppositeSides"))
    checks["lateralGapAdequate"] = lat_ok
    details["lateral"] = lat_detail

    gt = collect_gt_landmarks(arm_obj, ["ankle.L", "ankle.R", "knee.L", "knee.R", "hip.L", "hip.R"])
    blocked: List[str] = []
    joint_errors: Dict[str, dict] = {}
    for key, cluster in (("ankle.L", left), ("ankle.R", right)):
        if key not in gt:
            blocked.append(key)
            joint_errors[key] = {"missingGt": True}
            continue
        gt_pos = Vector(gt[key]["position"])
        err = _best_inside_error_cm(cluster, gt_pos)
        xs = [p.x for p in cluster] if cluster else []
        reachable = err is not None and err < ankle_gate_cm
        joint_errors[key] = {
            "bestInsideError_cm": None if err is None else round(err, 3),
            "gateCm": ankle_gate_cm,
            "gateReachableInsideMesh": reachable,
            "meshXRange": [round(min(xs), 4), round(max(xs), 4)] if xs else None,
            "gt": gt[key]["position"],
            "bone": gt[key].get("bone"),
        }
        if not reachable:
            blocked.append(key)

    checks["gtInsideMeshReachable"] = len(blocked) == 0
    details["jointReachability"] = joint_errors

    # Aggregate reason. Prefer MESH_GT_MISMATCH when joint reachability fails —
    # that is the structural quality-gate blocker class (e.g. Wither fixture).
    if blocked:
        reason = REASON_MESH_GT_MISMATCH
    elif not world_ok:
        reason = REASON_TRANSFORM_INCONSISTENT
    elif not rest_ok:
        reason = REASON_REST_POSE_MIX
    elif not checks["lateralComponentsPresent"] or not checks["lateralCentersOpposite"]:
        reason = REASON_MISSING_LATERAL_COMPONENT
    else:
        reason = REASON_OK

    eligible = reason == REASON_OK and all(
        [
            checks.get("worldTransformUsable", False),
            checks.get("restPoseConsistent", False),
            checks.get("lateralComponentsPresent", False),
            checks.get("lateralCentersOpposite", False),
            checks.get("lateralGapAdequate", False),
            checks.get("gtInsideMeshReachable", False),
        ]
    )

    return AssetEligibilityResult(
        assetEligible=eligible,
        reasonCode=reason,
        blockedJoints=sorted(set(blocked)),
        evaluationExcluded=sorted(set(blocked)),
        evaluationAllowed=eligible,
        # Eligibility alone never auto-confirms a rig in alpha.
        autoRigAllowed=False,
        checks=checks,
        details=details,
    )
