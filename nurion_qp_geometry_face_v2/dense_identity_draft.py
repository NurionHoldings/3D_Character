"""Build dense identity face drafts from 478 landmarks (Gate 5).

Uses offline-pinned MediaPipe Face Mesh tesselation. Does not claim photoreal
quality or automatic identity PASS.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np

from . import face_mesh_connections as fmc


REGION_SETS = {
    "EYES": frozenset(i for e in fmc.FACEMESH_LEFT_EYE | fmc.FACEMESH_RIGHT_EYE for i in e),
    "EYELIDS": frozenset(
        i for e in (fmc.FACEMESH_LEFT_EYE | fmc.FACEMESH_RIGHT_EYE | fmc.FACEMESH_LEFT_EYEBROW | fmc.FACEMESH_RIGHT_EYEBROW) for i in e
    ),
    "NOSE": frozenset(i for e in fmc.FACEMESH_NOSE for i in e),
    "NOSE_ALAE": frozenset({48, 64, 98, 97, 2, 326, 327, 294, 278, 344, 440, 275, 45, 220, 115}),
    "LIPS": frozenset(i for e in fmc.FACEMESH_LIPS for i in e),
    "MOUTH": frozenset(i for e in fmc.FACEMESH_LIPS for i in e) | {13, 14, 17, 0, 267, 269, 270, 409, 291, 61},
    "JAWLINE": frozenset(i for e in fmc.FACEMESH_FACE_OVAL for i in e),
}


def _triangles_from_edges(edges: Iterable[tuple[int, int]]) -> list[tuple[int, int, int]]:
    adj: dict[int, set[int]] = {}
    edge_set = set()
    for a, b in edges:
        a, b = int(a), int(b)
        edge_set.add((a, b) if a < b else (b, a))
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    tris: set[tuple[int, int, int]] = set()
    for a, b in edge_set:
        for c in adj[a].intersection(adj[b]):
            tri = tuple(sorted((a, b, c)))
            if len(set(tri)) == 3:
                tris.add(tri)  # type: ignore[arg-type]
    return sorted(tris)  # type: ignore[return-value]


TRIANGLES = _triangles_from_edges(fmc.FACEMESH_TESSELATION)


@dataclass(frozen=True)
class DenseIdentityDraft:
    mode: str
    vertices: np.ndarray  # (478, 3)
    triangles: tuple[tuple[int, int, int], ...]
    expressed_regions: tuple[str, ...]
    disclosures: tuple[str, ...]

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)


def _validate_landmarks(landmarks: np.ndarray) -> np.ndarray:
    arr = np.asarray(landmarks, dtype=np.float64)
    if arr.shape != (478, 3) or not np.isfinite(arr).all():
        raise ValueError("LANDMARKS_MUST_BE_478x3_FINITE")
    return arr.copy()


def _to_metric(landmarks: np.ndarray) -> np.ndarray:
    """Convert normalized face landmarks to a stable metric frame (IOD=1)."""
    left, right = landmarks[33], landmarks[263]
    iod = float(np.linalg.norm(right[:2] - left[:2]))
    if iod <= 1e-8:
        raise ValueError("DEGENERATE_INTEROCULAR_DISTANCE")
    mid = (left + right) * 0.5
    out = (landmarks - mid) / iod
    # Blender-friendly: X right, Y depth forward(-), Z up
    # MediaPipe: x right, y down, z toward camera (approx). Remap:
    remapped = np.empty_like(out)
    remapped[:, 0] = out[:, 0]
    remapped[:, 1] = out[:, 2]
    remapped[:, 2] = -out[:, 1]
    return remapped


def _mild_polish(vertices: np.ndarray) -> np.ndarray:
    """Mild symmetry + neighbor smooth — preview proxy, not photoreal beauty."""
    v = vertices.copy()
    # Reflect-average on X for mild symmetry (keeps Z/Y).
    mirrored = v.copy()
    mirrored[:, 0] *= -1.0
    # MediaPipe indices are not perfect left-right pairs for all verts; use soft blend to mirror of nearest-x.
    # Safer: only blend with exact sign flip of each point's X about midline (same index approximation).
    v = 0.85 * v + 0.15 * mirrored
    # one-ring laplacian using triangle adjacency
    acc = np.zeros_like(v)
    w = np.zeros((len(v), 1), dtype=np.float64)
    for a, b, c in TRIANGLES:
        for i, j in ((a, b), (b, c), (c, a)):
            acc[i] += v[j]
            w[i] += 1.0
            acc[j] += v[i]
            w[j] += 1.0
    w = np.maximum(w, 1.0)
    lap = acc / w
    return 0.7 * v + 0.3 * lap


def expressed_regions_present(vertices: np.ndarray) -> list[str]:
    present = []
    for name, idxs in REGION_SETS.items():
        pts = vertices[list(idxs)]
        if pts.shape[0] >= 3 and float(np.linalg.norm(pts.std(axis=0))) > 1e-6:
            present.append(name)
    return present


def build_dense_identity_draft(landmarks: np.ndarray, mode: str = "NATURAL") -> DenseIdentityDraft:
    mode = mode.upper()
    if mode not in ("NATURAL", "POLISHED"):
        raise ValueError("MODE_MUST_BE_NATURAL_OR_POLISHED")
    lm = _validate_landmarks(landmarks)
    verts = _to_metric(lm)
    if mode == "POLISHED":
        verts = _mild_polish(verts)
    regions = expressed_regions_present(verts)
    required = ["EYES", "EYELIDS", "NOSE", "NOSE_ALAE", "LIPS", "MOUTH", "JAWLINE"]
    missing = [r for r in required if r not in regions]
    if missing:
        raise ValueError(f"REQUIRED_REGIONS_MISSING:{missing}")
    disclosures = (
        "DENSE_IDENTITY_FACE_DRAFT_NOT_PHOTOREAL_CLAIM",
        "AUTOMATIC_IDENTITY_SIMILARITY_PASS_DENIED",
        "LOW_POLY_CANONICAL_PROXY_NOT_USED_AS_IDENTITY_EVIDENCE",
        "GEOMETRY_FIRST_478_LANDMARK_SURFACE",
    )
    if mode == "POLISHED":
        disclosures = disclosures + ("POLISHED_IS_MILD_SYMMETRY_SMOOTH_PROXY_ONLY",)
    return DenseIdentityDraft(
        mode=mode,
        vertices=verts,
        triangles=tuple(TRIANGLES),
        expressed_regions=tuple(regions),
        disclosures=disclosures,
    )


def write_obj(draft: DenseIdentityDraft, path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# NURION GF Face v2 Gate5 dense identity draft",
        f"# mode={draft.mode}",
        f"# regions={','.join(draft.expressed_regions)}",
        "# photorealAutomaticPass=DENY",
    ]
    for x, y, z in draft.vertices:
        lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
    for a, b, c in draft.triangles:
        lines.append(f"f {a + 1} {b + 1} {c + 1}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_region_sidecar(draft: DenseIdentityDraft, path: Path) -> None:
    import json

    path = Path(path)
    doc = {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE5_REGION_SIDECAR_V1",
        "mode": draft.mode,
        "vertexCount": draft.vertex_count,
        "triangleCount": draft.triangle_count,
        "expressedRegions": list(draft.expressed_regions),
        "regionIndices": {k: sorted(v) for k, v in REGION_SETS.items()},
        "disclosures": list(draft.disclosures),
        "photorealAutomaticPass": "DENY",
        "production": "NO-GO",
    }
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
