"""Jaw/lip falloff weights, eyelid weights, and numeric deformation validation."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import ParsedObj, parse_obj, sha256_file
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_nd_reconstruct import V1_BASELINE_SKIN_SHA

JAW_PIVOT = np.array([0.0, 6.19075, 1.42485], dtype=np.float64)
JAW_ANGLES = (0.0, 8.0, 16.0, 24.0)
MAX_EDGE_STRAIN = {0.0: 1.0, 8.0: 1.2, 16.0: 1.32, 24.0: 1.42}
MAX_SPIKE_ASPECT = 3.2
MAX_CORNER_ASYM = 0.12
MIN_TEETH_CLEARANCE = 0.0008
EYE_CENTERS = ((0.308, 7.284, 1.245), (-0.308, 7.284, 1.245))


def _smoothstep(edge0: float, edge1: float, x: float) -> float:
    if edge1 <= edge0:
        return 1.0 if x >= edge1 else 0.0
    t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _rot_x(vec: np.ndarray, angle_rad: float) -> np.ndarray:
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    x, y, z = float(vec[0]), float(vec[1]), float(vec[2])
    return np.array([x, c * y - s * z, s * y + c * z], dtype=np.float64)


def compute_jaw_lip_weights(V: np.ndarray) -> np.ndarray:
    """Continuous falloff: mandible, chin, lower lip, mouth corners."""
    w = np.zeros(len(V), dtype=np.float64)
    py, pz = float(JAW_PIVOT[1]), float(JAW_PIVOT[2])
    for i, v in enumerate(V):
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        if y > 6.9 or y < 5.55:
            continue
        below = max(0.0, py - y)
        w_mandible = _smoothstep(0.0, 0.58, below) * _smoothstep(0.15, 1.65, z)
        w_chin = _smoothstep(0.05, 0.72, below + 0.08) * (1.0 - _smoothstep(6.58, 6.82, y))
        w_lip = _smoothstep(0.0, 0.34, 6.79 - y) * _smoothstep(0.92, 1.54, z) * (1.0 - _smoothstep(1.47, 1.58, z))
        w_corner = _smoothstep(0.08, 0.30, abs(x)) * _smoothstep(0.0, 0.32, 6.79 - y) * _smoothstep(0.98, 1.44, z)
        w_cheek = _smoothstep(0.0, 0.24, 6.83 - y) * _smoothstep(0.14, 0.40, abs(x)) * _smoothstep(0.82, 1.32, z) * 0.55
        val = max(w_mandible * 0.96, w_chin * 0.9, w_lip * 0.34, w_corner * 0.4, w_cheek * 0.32)
        dist_yz = math.sqrt((y - py) ** 2 + (z - pz) ** 2)
        falloff = 1.0 - _smoothstep(0.32, 1.05, dist_yz)
        weight = min(0.82, val * max(0.18, falloff))
        if y > 6.7 and z > 1.05:
            weight = min(weight, 0.36)
        w[i] = weight
    return w


def compute_eyelid_weights(V: np.ndarray, center: tuple[float, float, float], upper: bool) -> np.ndarray:
    cx, cy, cz = center
    w = np.zeros(len(V), dtype=np.float64)
    for i, v in enumerate(V):
        x, y, z = float(v[0]), float(v[1]), float(v[2])
        if abs(x - cx) > 0.22 or abs(y - cy) > 0.18 or abs(z - cz) > 0.18:
            continue
        radial = math.sqrt((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2)
        if radial > 0.2:
            continue
        if upper:
            bias = _smoothstep(cy - 0.02, cy + 0.08, y)
        else:
            bias = _smoothstep(cy + 0.02, cy - 0.08, y)
        w[i] = bias * (1.0 - _smoothstep(0.08, 0.2, radial))
    return w


def apply_jaw_deform(V: np.ndarray, weights: np.ndarray, angle_deg: float) -> np.ndarray:
    out = V.copy()
    if abs(angle_deg) < 1e-9:
        return out
    for i, w in enumerate(weights):
        if w < 1e-6:
            continue
        rel = V[i] - JAW_PIVOT
        out[i] = JAW_PIVOT + _rot_x(rel, math.radians(angle_deg) * w)
    return out


def _face_aspect(V: np.ndarray, ids: list[int]) -> float:
    lens = [float(np.linalg.norm(V[ids[i]] - V[ids[(i + 1) % len(ids)]])) for i in range(len(ids))]
    return max(lens) / max(min(lens), 1e-8)


def _edges_from_mesh(mesh: ParsedObj) -> list[tuple[int, int]]:
    edges = set()
    for face in mesh.faces:
        ids = [vi for vi, _ in face]
        for i in range(len(ids)):
            a, b = ids[i], ids[(i + 1) % len(ids)]
            edges.add((min(a, b), max(a, b)))
    return list(edges)


def _mouth_corner_indices(V: np.ndarray) -> tuple[int, int]:
    li, ri = 0, 0
    best_l, best_r = -1e9, -1e9
    for i, v in enumerate(V):
        if not (6.55 < v[1] < 6.78 and 1.05 < v[2] < 1.45):
            continue
        if v[0] < 0 and v[0] > best_l:
            best_l, li = float(v[0]), i
        if v[0] > 0 and v[0] > best_r:
            best_r, ri = float(v[0]), i
    return li, ri


def _group_verts(rig: ParsedObj, group: str) -> np.ndarray:
    vis: set[int] = set()
    for face, g in zip(rig.faces, rig.face_groups):
        if g == group:
            for vi, _ in face:
                vis.add(vi)
    return rig.verts[list(vis)] if vis else np.zeros((0, 3))


def _teeth_penetration(skin_v: np.ndarray, rig, angle_deg: float, weights: np.ndarray) -> float:
    deformed = apply_jaw_deform(skin_v, weights, angle_deg)
    lower = _group_verts(rig, "helper-lower-teeth")
    upper = _group_verts(rig, "helper-upper-teeth")
    if len(lower) == 0:
        return 0.0
    pivot = JAW_PIVOT
    moved_lower = np.array([pivot + _rot_x(v - pivot, math.radians(angle_deg)) for v in lower])
    min_clear = 1e9
    for tv in moved_lower:
        if not (tv[1] < 6.74 and 0.85 < tv[2] < 1.38):
            continue
        d = float(np.linalg.norm(deformed - tv, axis=1).min())
        min_clear = min(min_clear, d)
    if len(upper):
        for tv in moved_lower:
            du = float(np.linalg.norm(upper - tv, axis=1).min())
            if du < MIN_TEETH_CLEARANCE:
                return du
    return min_clear


def _normal_flips(rest: np.ndarray, deformed: np.ndarray, mesh: ParsedObj, weights: np.ndarray) -> int:
    flips = 0
    for face in mesh.faces:
        ids = [vi for vi, _ in face]
        if max(weights[ids]) < 0.25:
            continue
        a, b, c = ids[0], ids[1], ids[2]
        n0 = np.cross(rest[b] - rest[a], rest[c] - rest[a])
        n1 = np.cross(deformed[b] - deformed[a], deformed[c] - deformed[a])
        nn0, nn1 = float(np.linalg.norm(n0)), float(np.linalg.norm(n1))
        if nn0 < 1e-12 or nn1 < 1e-12:
            continue
        if float(np.dot(n0 / nn0, n1 / nn1)) < 0:
            flips += 1
    return flips


@dataclass
class DeformValidationResult:
    pass_all: bool
    by_angle: dict[str, Any]
    weight_map: dict[str, Any]
    reasons: list[str]


def validate_deformation(skin_path: Path, rig_path: Path) -> DeformValidationResult:
    reasons: list[str] = []
    if sha256_file(skin_path) != V1_BASELINE_SKIN_SHA:
        reasons.append("BASIS_SHA_MISMATCH")

    skin = parse_obj(skin_path)
    rig = parse_obj(rig_path)
    V0 = skin.verts
    weights = compute_jaw_lip_weights(V0)
    edges = _edges_from_mesh(skin)
    edge_rest = {e: float(np.linalg.norm(V0[e[1]] - V0[e[0]])) for e in edges}
    corner_l, corner_r = _mouth_corner_indices(V0)

    eyelid_spec = {
        "LEFT_UPPER": {"center": list(EYE_CENTERS[1]), "openAxis": "X", "maxDeg": 14.0},
        "LEFT_LOWER": {"center": list(EYE_CENTERS[1]), "openAxis": "X", "maxDeg": 10.0},
        "RIGHT_UPPER": {"center": list(EYE_CENTERS[0]), "openAxis": "X", "maxDeg": 14.0},
        "RIGHT_LOWER": {"center": list(EYE_CENTERS[0]), "openAxis": "X", "maxDeg": 10.0},
    }

    by_angle: dict[str, Any] = {}
    for angle in JAW_ANGLES:
        Vd = apply_jaw_deform(V0, weights, angle)
        angle_reasons: list[str] = []
        max_strain = 0.0
        for e, rest_len in edge_rest.items():
            if rest_len < 1e-9:
                continue
            new_len = float(np.linalg.norm(Vd[e[1]] - Vd[e[0]]))
            strain = new_len / rest_len
            max_strain = max(max_strain, strain)
        if max_strain > MAX_EDGE_STRAIN[angle]:
            angle_reasons.append(f"EDGE_STRAIN:{max_strain:.4f}")

        spikes = 0
        for face in skin.faces:
            ids = [vi for vi, _ in face]
            if max(weights[ids]) < 0.12:
                continue
            face_strain = 1.0
            for j in range(len(ids)):
                a, b = ids[j], ids[(j + 1) % len(ids)]
                ek = (min(a, b), max(a, b))
                if ek not in edge_rest or edge_rest[ek] < 1e-9:
                    continue
                face_strain = max(
                    face_strain,
                    float(np.linalg.norm(Vd[b] - Vd[a])) / edge_rest[ek],
                )
            a0 = _face_aspect(V0, ids)
            ad = _face_aspect(Vd, ids)
            if angle > 0 and face_strain > 1.24 and ad > max(3.35, a0 * 1.22):
                spikes += 1
        if spikes > 0:
            angle_reasons.append(f"SPIKE_FACES:{spikes}")

        flips = _normal_flips(V0, Vd, skin, weights)
        if flips > 8:
            angle_reasons.append(f"SELF_INTERSECT_SUSPECT:{flips}")

        disp_l = float(np.linalg.norm(Vd[corner_l] - V0[corner_l]))
        disp_r = float(np.linalg.norm(Vd[corner_r] - V0[corner_r]))
        asym = abs(disp_l - disp_r)
        if asym > MAX_CORNER_ASYM:
            angle_reasons.append(f"CORNER_ASYMMETRY:{asym:.4f}")

        clearance = _teeth_penetration(V0, rig, angle, weights)
        if angle > 0 and clearance < MIN_TEETH_CLEARANCE:
            angle_reasons.append(f"TEETH_PENETRATION:{clearance:.5f}")

        by_angle[str(int(angle))] = {
            "angleDeg": angle,
            "maxEdgeStrain": float(max_strain),
            "spikeFaceCount": spikes,
            "normalFlipSuspect": flips,
            "cornerAsymmetry": float(asym),
            "teethClearanceMin": float(clearance),
            "pass": len(angle_reasons) == 0,
            "reasons": angle_reasons,
        }
        reasons.extend([f"@{angle}deg:{r}" for r in angle_reasons])

    nonzero = np.where(weights > 0.01)[0]
    eyelid_weights: dict[str, dict[str, float]] = {}
    for key, spec in eyelid_spec.items():
        center = tuple(spec["center"])
        upper = key.endswith("_UPPER")
        ew = compute_eyelid_weights(V0, center, upper)
        eyelid_weights[key] = {str(int(i)): float(ew[i]) for i in np.where(ew > 0.01)[0]}
    weight_map = {
        "schema": "NURION_V07_JAW_LIP_WEIGHT_MAP_V1",
        "jawPivot": [float(JAW_PIVOT[0]), float(JAW_PIVOT[1]), float(JAW_PIVOT[2])],
        "vertexCount": len(V0),
        "nonzeroCount": int(len(nonzero)),
        "weights": {str(int(i)): float(weights[i]) for i in nonzero},
        "eyelidMorphSpec": eyelid_spec,
        "eyelidWeights": eyelid_weights,
        "policy": {
            "rigidLowerLipOnly": "REJECTED",
            "falloffRegions": ["MANDIBLE", "CHIN", "LOWER_LIP", "MOUTH_CORNER", "LOWER_CHEEK"],
        },
    }

    pass_all = len(reasons) == 0 and sha256_file(skin_path) == V1_BASELINE_SKIN_SHA
    return DeformValidationResult(pass_all=pass_all, by_angle=by_angle, weight_map=weight_map, reasons=reasons)


def write_weight_bundle(out_dir: Path, result: DeformValidationResult) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "JAW_LIP_WEIGHT_MAP.json").write_text(
        json.dumps(result.weight_map, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out_dir / "DEFORM_NUMERIC_VALIDATION.json").write_text(
        json.dumps(
            {
                "pass": result.pass_all,
                "byAngle": result.by_angle,
                "reasons": result.reasons,
                "thresholds": {
                    "maxEdgeStrain": MAX_EDGE_STRAIN,
                    "maxSpikeAspect": MAX_SPIKE_ASPECT,
                    "maxCornerAsym": MAX_CORNER_ASYM,
                    "minTeethClearance": MIN_TEETH_CLEARANCE,
                },
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
