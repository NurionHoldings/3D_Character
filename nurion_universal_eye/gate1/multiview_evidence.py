"""
Gate 1 multiview evidence cameras / optional OpenGL stills.

Views: FRONT, LEFT_30, LEFT_60, LEFT_90, RIGHT_30, RIGHT_60, RIGHT_90.
Does not generate visual eyes.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List, Optional

from mathutils import Matrix, Vector

from .universal_face_basis import HeadAxes, UniversalFaceBasis, _v3

EVIDENCE_VIEWS = (
    ("FRONT", 0.0),
    ("LEFT_30", 30.0),
    ("LEFT_60", 60.0),
    ("LEFT_90", 90.0),
    ("RIGHT_30", -30.0),
    ("RIGHT_60", -60.0),
    ("RIGHT_90", -90.0),
)


def _cam_matrix(axes: HeadAxes, yaw_deg: float, distance: float) -> Matrix:
    """Look-at head origin from yaw around up axis (0 = front / -forward)."""
    yaw = math.radians(yaw_deg)
    # Camera sits in front of face; yaw positive → character left (world +right).
    offset = (
        -axes.forward * math.cos(yaw) * distance
        + axes.right * math.sin(yaw) * distance
        + axes.up * (axes.head_height * 0.05)
    )
    loc = axes.origin + offset
    # Camera -Z looks toward origin.
    direction = (axes.origin - loc).normalized()
    up = axes.up
    right = direction.cross(up)
    if right.length < 1e-8:
        right = axes.right.copy()
    right.normalize()
    up = right.cross(direction).normalized()
    # Blender camera: local -Z forward, +Y up, +X right
    # columns: right, up, -direction, location
    return Matrix(
        (
            (right.x, up.x, -direction.x, loc.x),
            (right.y, up.y, -direction.y, loc.y),
            (right.z, up.z, -direction.z, loc.z),
            (0.0, 0.0, 0.0, 1.0),
        )
    )


def build_evidence_plan(basis: UniversalFaceBasis) -> List[dict]:
    if basis.axes is None:
        return []
    dist = max(basis.head_height * 2.8, 0.35)
    plan = []
    for name, yaw in EVIDENCE_VIEWS:
        mat = _cam_matrix(basis.axes, yaw, dist)
        plan.append(
            {
                "view": name,
                "yawDeg": yaw,
                "distance": round(float(dist), 6),
                "cameraLocation": _v3(mat.translation),
                "lookAt": _v3(basis.axes.origin),
                "matrixWorld": [round(float(mat[i][j]), 6) for i in range(4) for j in range(4)],
            }
        )
    return plan


def render_multiview_evidence(
    basis: UniversalFaceBasis,
    out_dir: Path,
    *,
    do_render: bool = True,
    resolution: int = 512,
) -> Dict:
    """Create evidence cameras and optionally render stills. Never mutates character mesh."""
    import bpy

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    plan = build_evidence_plan(basis)
    rendered: List[dict] = []

    # Ensure REST pose if armature present.
    for arm in [o for o in bpy.data.objects if o.type == "ARMATURE"]:
        arm.data.pose_position = "REST"
    bpy.context.view_layer.update()

    # Hide any NURION visual leftovers if present (should not exist in Gate 1).
    for obj in list(bpy.data.objects):
        if obj.name.startswith("NURION_Eyeball") or obj.name.startswith("NURION_Visual"):
            obj.hide_set(True)
            obj.hide_render = True

    scene = bpy.context.scene
    scene.render.resolution_x = resolution
    scene.render.resolution_y = resolution
    scene.render.image_settings.file_format = "PNG"

    for item in plan:
        cam_data = bpy.data.cameras.new(name=f"NURION_GATE1_{item['view']}")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = max(basis.head_height * 1.6, 0.25)
        cam_obj = bpy.data.objects.new(f"NURION_GATE1_CAM_{item['view']}", cam_data)
        bpy.context.collection.objects.link(cam_obj)
        # Reconstruct matrix
        flat = item["matrixWorld"]
        mat = Matrix(
            (
                (flat[0], flat[1], flat[2], flat[3]),
                (flat[4], flat[5], flat[6], flat[7]),
                (flat[8], flat[9], flat[10], flat[11]),
                (flat[12], flat[13], flat[14], flat[15]),
            )
        )
        cam_obj.matrix_world = mat
        entry = dict(item)
        entry["cameraObject"] = cam_obj.name
        path = out_dir / f"evidence_{item['view'].lower()}.png"
        entry["imagePath"] = str(path).replace("\\", "/")
        entry["rendered"] = False
        if do_render:
            scene.camera = cam_obj
            scene.render.filepath = str(path)
            try:
                bpy.ops.render.render(write_still=True)
                entry["rendered"] = path.exists()
            except Exception as exc:  # noqa: BLE001 — evidence soft-fail
                entry["renderError"] = str(exc)
                entry["rendered"] = False
        rendered.append(entry)

    return {
        "schema": "NURION_GATE1_MULTIVIEW_EVIDENCE",
        "version": "0.3.0-alpha.3-gate1",
        "viewCount": len(rendered),
        "views": rendered,
        "visualEyeGenerated": False,
        "manualGtUsed": False,
    }
