"""NURION-owned parametric head V1.1 — true depth priors, continuous UV, 478 as 2D only.

Commercial clearance: NURION-owned topology (not MediaPipe tessellation as render surface).
MediaPipe Z is never used as mesh depth.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


# MediaPipe landmark indices used only as 2D fitting targets
MP = {
    "L_EYE": 33,
    "R_EYE": 263,
    "NOSE": 1,
    "CHIN": 152,
    "FOREHEAD": 10,
    "MOUTH_L": 61,
    "MOUTH_R": 291,
    "L_BROW": 70,
    "R_BROW": 300,
}


@dataclass(frozen=True)
class ParametricHeadFit:
    vertices: np.ndarray  # (N,3) template depth space
    triangles: list[tuple[int, int, int]]
    uvs: np.ndarray  # (N,2) continuous cylindrical
    correspondences: dict[str, int]  # feature -> vertex index
    params: dict[str, float]
    disclosures: tuple[str, ...]


def _build_template(nu: int = 80, nv: int = 64) -> tuple[np.ndarray, list[tuple[int, int, int]], np.ndarray, dict[str, int]]:
    """Parametric depth head — not flat photo-ellipsoid; not MediaPipe 854."""
    sx, sy, sz = 0.50, 0.52, 0.66
    verts: list[list[float]] = []
    uvs: list[list[float]] = []
    for j in range(nv + 1):
        v = j / nv
        phi = v * np.pi
        for i in range(nu):
            u = i / nu
            theta = u * 2.0 * np.pi - np.pi  # front theta≈0 → -Y
            x = sx * np.sin(phi) * np.sin(theta)
            y = -sy * np.sin(phi) * np.cos(theta)
            z = sz * np.cos(phi)
            front_dist = min(u, 1.0 - u)  # 0 at geometric front seam

            # Eye sockets deep into head (+Y)
            eye_u = min(abs(u - 0.30), abs(u - 0.70))
            if 0.34 < v < 0.48 and eye_u < 0.06:
                y += 0.085 * (1.0 - eye_u / 0.06)
                z += 0.01
            if 0.30 < v < 0.36 and eye_u < 0.08:
                y -= 0.035  # brow toward camera

            # Nose bridge → tip (strong -Y)
            if 0.40 < v < 0.62 and front_dist < 0.10:
                bridge = 1.0 - front_dist / 0.10
                along = max(0.0, 1.0 - abs((v - 0.52) / 0.12))
                y -= 0.16 * bridge * max(0.35, along)
                if 0.50 < v < 0.58:
                    x *= 0.78 + 0.12 * (front_dist / 0.10)
                if 0.55 < v < 0.60 and front_dist < 0.045:
                    y -= 0.025

            # Cheeks
            cheek = min(abs(u - 0.22), abs(u - 0.78))
            if 0.44 < v < 0.58 and 0.04 < cheek < 0.12:
                y -= 0.035

            # Lips forward + oral recess
            if 0.58 < v < 0.66 and front_dist < 0.11:
                y -= 0.055 * (1.0 - front_dist / 0.11)
            if 0.62 < v < 0.68 and front_dist < 0.07:
                y += 0.045

            # Jaw + chin depth
            if v > 0.70:
                taper = (v - 0.70) / 0.30
                x *= 1.0 - 0.32 * taper
                if front_dist < 0.14 and v > 0.78:
                    y -= 0.05 * (1.0 - front_dist / 0.14) * taper
                    z -= 0.04 * taper
            if v > 0.90:
                x *= 0.50
                y *= 0.72

            verts.append([x, y, z])
            uvs.append([(u + 0.5) % 1.0, 1.0 - v])

    tris: list[tuple[int, int, int]] = []
    for j in range(nv):
        for i in range(nu):
            a = j * nu + i
            b = j * nu + (i + 1) % nu
            c = (j + 1) * nu + i
            d = (j + 1) * nu + (i + 1) % nu
            tris.append((a, c, b))
            tris.append((b, c, d))

    V = np.asarray(verts, dtype=np.float64)

    def nearest(target: np.ndarray) -> int:
        return int(np.linalg.norm(V - target, axis=1).argmin())

    corr = {
        "L_EYE": nearest(np.array([-0.16, -0.32, 0.10])),
        "R_EYE": nearest(np.array([0.16, -0.32, 0.10])),
        "NOSE": nearest(np.array([0.0, -0.62, -0.02])),
        "CHIN": nearest(np.array([0.0, -0.42, -0.58])),
        "FOREHEAD": nearest(np.array([0.0, -0.40, 0.48])),
        "MOUTH_L": nearest(np.array([-0.10, -0.45, -0.28])),
        "MOUTH_R": nearest(np.array([0.10, -0.45, -0.28])),
        "L_BROW": nearest(np.array([-0.14, -0.42, 0.20])),
        "R_BROW": nearest(np.array([0.14, -0.42, 0.20])),
        "LIP_UPPER": nearest(np.array([0.0, -0.50, -0.24])),
        "LIP_LOWER": nearest(np.array([0.0, -0.48, -0.32])),
    }
    return V, tris, np.asarray(uvs, dtype=np.float64), corr


def depth_order_metrics(fit: ParametricHeadFit) -> dict[str, float]:
    """Front = -Y. Expect nose tip more forward (smaller Y) than lips than mid-cheek baseline."""
    V = fit.vertices
    c = fit.correspondences
    nose_y = float(V[c["NOSE"], 1])
    lip_y = float(0.5 * (V[c["LIP_UPPER"], 1] + V[c["LIP_LOWER"], 1]))
    chin_y = float(V[c["CHIN"], 1])
    cheek_y = float(0.5 * (V[c["MOUTH_L"], 1] + V[c["MOUTH_R"], 1]))
    return {
        "noseY": nose_y,
        "lipY": lip_y,
        "chinY": chin_y,
        "cheekY": cheek_y,
        "noseForwardOfLips": float(nose_y < lip_y),
        "lipsForwardOfChinPlane": float(lip_y <= chin_y + 0.08),
        "noseForwardOfCheek": float(nose_y < cheek_y),
    }


def fit_parametric_head_from_478(landmarks_raw: np.ndarray, *, polish: bool = False) -> ParametricHeadFit:
    """Fit template using 2D landmark constraints only. Never uses MP Z as depth."""
    lm = np.asarray(landmarks_raw, dtype=np.float64)
    if lm.shape != (478, 3):
        raise ValueError("LANDMARKS_MUST_BE_478x3")

    V0, tris, uvs, corr = _build_template()
    feat_ids = [k for k in corr if k in MP]
    src = np.array([V0[corr[k]] for k in feat_ids], dtype=np.float64)
    dst = np.array([lm[MP[k], :2].copy() for k in feat_ids], dtype=np.float64)

    src2 = np.column_stack([src[:, 0], -src[:, 2]])
    src_c = src2.mean(axis=0)
    dst_c = dst.mean(axis=0)
    src_z = src2 - src_c
    dst_z = dst - dst_c
    s = float(np.linalg.norm(dst_z) / (np.linalg.norm(src_z) + 1e-8))
    H = src_z.T @ dst_z
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    t = dst_c - s * (R @ src_c)

    V = V0.copy()
    predicted = (s * (R @ src2.T)).T + t
    residual = dst - predicted
    for i, k in enumerate(feat_ids):
        idx = corr[k]
        dx = residual[i, 0] / max(s, 1e-6)
        dz = -residual[i, 1] / max(s, 1e-6)
        strength = 0.35 if not polish else 0.22
        V[idx, 0] += dx * strength
        V[idx, 2] += dz * strength
        d = np.linalg.norm(V0 - V0[idx], axis=1)
        w = np.exp(-(d**2) / (2 * 0.08**2))
        w[idx] = 0
        V[:, 0] += w * dx * strength * 0.25
        V[:, 2] += w * dz * strength * 0.25

    if polish:
        mirrored = V.copy()
        mirrored[:, 0] *= -1.0
        V = 0.9 * V + 0.1 * mirrored

    iod = float(np.linalg.norm(lm[263, :2] - lm[33, :2])) + 1e-8
    face_len = float(np.linalg.norm(lm[152, :2] - lm[10, :2])) + 1e-8
    fw = float(np.linalg.norm(lm[454, :2] - lm[234, :2])) / face_len
    V[:, 0] *= 0.85 + 0.35 * min(max(fw, 0.55), 0.95)
    V[:, 2] *= 0.95 + 0.1 * (face_len / (iod * 2.2))

    params = {
        "scale2d": float(s),
        "rotDet": float(np.linalg.det(R)),
        "tx": float(t[0]),
        "ty": float(t[1]),
        "iod": float(iod),
        "faceWidthToLength": float(fw),
        "polish": float(polish),
        "triangleCount": float(len(tris)),
        "vertexCount": float(len(V)),
    }
    return ParametricHeadFit(
        vertices=V,
        triangles=tris,
        uvs=uvs,
        correspondences=corr,
        params=params,
        disclosures=(
            "NURION_PARAMETRIC_HEAD_V1_OWNED",
            "MEDIAPIPE_478_CONSTRAINT_ONLY",
            "MEDIAPIPE_Z_NOT_USED_AS_DEPTH",
            "CONTINUOUS_CYLINDRICAL_UV",
            "NOT_DIRECT_FACEMESH_RENDER",
            "TRUE_PARAMETRIC_DEPTH_PRIORS_V1_1",
        ),
    )


def write_obj(path: Path, fit: ParametricHeadFit) -> dict[str, Any]:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# NURION_PARAMETRIC_HEAD_V1_1", "o NurionParametricHeadV1"]
    for x, y, z in fit.vertices:
        lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
    for u, v in fit.uvs:
        lines.append(f"vt {u:.8f} {v:.8f}")
    for a, b, c in fit.triangles:
        lines.append(f"f {a+1}/{a+1} {b+1}/{b+1} {c+1}/{c+1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "vertexCount": int(len(fit.vertices)),
        "triangleCount": int(len(fit.triangles)),
        "correspondences": fit.correspondences,
        "params": fit.params,
        "disclosures": list(fit.disclosures),
        "depthOrder": depth_order_metrics(fit),
    }
