"""NURION-owned parametric head mesh (not MediaPipe 854, not research 3DMM)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .parametric_face_v0 import ParametricFit


def build_nurion_parametric_head(
    fit: ParametricFit,
    *,
    nu: int = 64,
    nv: int = 48,
) -> tuple[np.ndarray, list[tuple[int, int, int]], np.ndarray]:
    """Return vertices (N,3), triangles, uvs (N,2) for a denser NURION head.

    Topology is NURION-owned ellipsoid with eye sockets, nose bump, lip band.
    """
    r = fit.geometry_ratios
    fw = float(r.get("FACE_WIDTH_TO_LENGTH", 0.75))
    nose_r = float(r.get("NOSE_LENGTH_TO_FACE_LENGTH", 0.3))
    mouth_r = float(r.get("MOUTH_WIDTH_TO_FACE_WIDTH", 0.4))
    iod_r = float(r.get("INTEROCULAR_TO_FACE_WIDTH", 0.35))

    sx = 0.55 * (0.75 + 0.5 * fw)
    sy = 0.48
    sz = 0.70 * (1.15 - 0.25 * fw)

    verts: list[list[float]] = []
    uvs: list[list[float]] = []
    for j in range(nv + 1):
        v = j / nv
        phi = v * np.pi  # 0..pi
        for i in range(nu):
            u = i / nu
            theta = u * 2.0 * np.pi
            x = sx * np.sin(phi) * np.cos(theta)
            y = -sy * np.sin(phi) * np.sin(theta)  # front toward -Y
            z = sz * np.cos(phi)
            # eye sockets (front hemisphere)
            if 0.32 < v < 0.48 and (abs(u - 0.22) < 0.05 or abs(u - 0.78) < 0.05):
                y += 0.035
                z -= 0.01
            # nose bump
            if 0.45 < v < 0.62 and (u < 0.06 or u > 0.94):
                y -= 0.06 * (0.6 + nose_r)
                x *= 0.85
            # mouth indent
            if 0.62 < v < 0.72 and (u < 0.08 * mouth_r / 0.4 + 0.02 or u > 1.0 - (0.08 * mouth_r / 0.4 + 0.02)):
                y += 0.02
            # cheek width
            if 0.45 < v < 0.7:
                x *= 0.95 + 0.15 * fw
            verts.append([float(x), float(y), float(z)])
            uvs.append([u, 1.0 - v])

    tris: list[tuple[int, int, int]] = []
    for j in range(nv):
        for i in range(nu):
            a = j * nu + i
            b = j * nu + (i + 1) % nu
            c = (j + 1) * nu + i
            d = (j + 1) * nu + (i + 1) % nu
            tris.append((a, c, b))
            tris.append((b, c, d))

    # Eye socket depth push using iod
    eye_sep = 0.18 * (0.7 + iod_r)
    v = np.asarray(verts, dtype=np.float64)
    for sign, u0 in ((-1.0, 0.22), (1.0, 0.78)):
        # find nearest verts to eye target
        target = np.array([sign * eye_sep, -sy * 0.85, sz * 0.18], dtype=np.float64)
        d = np.linalg.norm(v - target, axis=1)
        idx = np.where(d < 0.09)[0]
        v[idx, 1] += 0.04  # deepen socket toward camera? front is -Y so +Y is back
        v[idx, 1] = v[idx, 1] + 0.03

    return v, tris, np.asarray(uvs, dtype=np.float64)


def write_obj_with_uv(
    path: Path,
    vertices: np.ndarray,
    triangles: list[tuple[int, int, int]],
    uvs: np.ndarray,
) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NURION_PARAMETRIC_FACE_V0 head",
        "# commercialClearance=NURION_OWNED",
        "mtllib nurion_face.mtl",
        "usemtl FaceAlbedo",
    ]
    for x, y, z in vertices:
        lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
    for u, vv in uvs:
        lines.append(f"vt {u:.8f} {vv:.8f}")
    for a, b, c in triangles:
        lines.append(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"vertexCount": int(len(vertices)), "triangleCount": int(len(triangles)), "path": str(path)}
