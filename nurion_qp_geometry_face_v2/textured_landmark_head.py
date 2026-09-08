"""Build textured identity head from 478 landmarks with image-space UVs.

Uses MediaPipe tessellation (Apache-2.0) + photo albedo. Not a research 3DMM.
Does not claim photoreal PASS by itself — quality gate decides.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .dense_identity_draft import TRIANGLES, _to_metric
from .parametric_face_v0 import ParametricFit


def build_textured_landmark_head(
    landmarks_raw: np.ndarray,
    *,
    polish: bool = False,
) -> tuple[np.ndarray, list[tuple[int, int, int]], np.ndarray, dict[str, Any]]:
    lm = np.asarray(landmarks_raw, dtype=np.float64)
    if lm.shape != (478, 3):
        raise ValueError("LANDMARKS_MUST_BE_478x3")
    verts = _to_metric(lm)
    if polish:
        # mild symmetric blend on X only
        mirrored = verts.copy()
        mirrored[:, 0] *= -1.0
        verts = 0.88 * verts + 0.12 * mirrored
    # UV in image normalized space so full-frame albedo maps 1:1 to landmarks
    uvs = np.column_stack([lm[:, 0], 1.0 - lm[:, 1]])
    meta = {
        "vertexCount": 478,
        "triangleCount": len(TRIANGLES),
        "uvSource": "LANDMARK_IMAGE_XY",
        "topology": "MEDIAPIPE_FACEMESH_TESSELATION_APACHE_2_0",
        "modelId": "NURION_PARAMETRIC_FACE_V0_TEXTURED_LANDMARK_HEAD",
    }
    return verts, list(TRIANGLES), uvs, meta


def write_obj_mtl(
    obj_path: Path,
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    uvs: np.ndarray,
    albedo_name: str = "albedo_full.png",
) -> dict[str, Any]:
    obj_path = Path(obj_path)
    obj_path.parent.mkdir(parents=True, exist_ok=True)
    mtl_path = obj_path.with_suffix(".mtl")
    mtl_path.write_text(
        "\n".join(
            [
                "newmtl FaceAlbedo",
                "Ka 1.000 1.000 1.000",
                "Kd 1.000 1.000 1.000",
                "d 1.0",
                f"map_Kd {albedo_name}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    lines = [
        "# NURION Gate6 textured landmark head",
        f"mtllib {mtl_path.name}",
        "usemtl FaceAlbedo",
    ]
    for x, y, z in vertices:
        lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
    for u, v in uvs:
        lines.append(f"vt {u:.8f} {v:.8f}")
    for a, b, c in triangles:
        lines.append(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}")
    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "vertexCount": int(len(vertices)),
        "triangleCount": int(len(triangles)),
        "obj": str(obj_path),
        "mtl": str(mtl_path),
    }


def eye_centers_metric(landmarks_raw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    verts = _to_metric(np.asarray(landmarks_raw, dtype=np.float64))
    return verts[33].copy(), verts[263].copy()
