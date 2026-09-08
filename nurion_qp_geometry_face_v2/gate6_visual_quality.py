"""Automated minimum visual quality gate for Gate 6 identity-grade packs."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def _stats(path: Path) -> dict[str, float]:
    arr = np.asarray(Image.open(path).convert("RGB"), dtype=np.float32)
    return {
        "mean": float(arr.mean()),
        "std": float(arr.std()),
        "darkFrac": float((arr.mean(axis=2) < 25.0).mean()),
        "bytes": float(path.stat().st_size),
    }


def evaluate_identity_visual_quality(
    *,
    render_paths: dict[str, Path],
    albedo_meta: dict[str, Any] | None,
    has_eyeballs: bool,
    has_photo_texture: bool,
    mesh_vertex_count: int,
    compare_path: Path | None = None,
) -> dict[str, Any]:
    reasons: list[str] = []
    checks: dict[str, Any] = {
        "hasEyeballs": has_eyeballs,
        "hasPhotoTexture": has_photo_texture,
        "meshVertexCount": mesh_vertex_count,
    }

    if not has_eyeballs:
        reasons.append("EYEBALL_STRUCTURE_MISSING")
    if not has_photo_texture:
        reasons.append("PHOTO_TEXTURE_MISSING")

    view_stats = {}
    for view, path in render_paths.items():
        if not path.is_file():
            reasons.append(f"RENDER_MISSING_{view.upper()}")
            continue
        st = _stats(path)
        view_stats[view] = st
        if st["bytes"] < 20_000:
            reasons.append(f"RENDER_TOO_SMALL_{view.upper()}")
        if st["std"] < 12.0:
            reasons.append(f"RENDER_LOW_CONTRAST_{view.upper()}")
        if st["darkFrac"] > 0.55:
            reasons.append(f"RENDER_MOSTLY_DARK_HOLES_{view.upper()}")
        # Over-smooth blob / wrong UV often shows very high mean luminance with weak edges
        arr = np.asarray(Image.open(path).convert("L"), dtype=np.float32)
        gy, gx = np.gradient(arr)
        edge = float(np.mean(np.hypot(gx, gy)))
        view_stats[view]["edgeMean"] = edge
        if edge < 4.0:
            reasons.append(f"RENDER_TOO_SMOOTH_BLOB_{view.upper()}")

    checks["views"] = view_stats

    if compare_path is not None and compare_path.is_file():
        # Heuristic: right half (render) should not be near-uniform pastel blob vs left photo.
        cmp_img = np.asarray(Image.open(compare_path).convert("RGB"), dtype=np.float32)
        h, w, _ = cmp_img.shape
        right = cmp_img[:, w // 2 :, :]
        if float(right.std()) < 18.0:
            reasons.append("COMPARE_RENDER_NEAR_UNIFORM")

    # Honest: MediaPipe 478 surface alone is still limited for eyelid/lip volume.
    if mesh_vertex_count < 400:
        reasons.append("MESH_DENSITY_MARGINAL_FOR_IDENTITY_STRUCTURES")

    hard = [r for r in reasons if r.startswith("RENDER_MISSING") or r == "PHOTO_TEXTURE_MISSING"]
    structural = [r for r in reasons if "BLOB" in r or "UNIFORM" in r or "DARK_HOLES" in r]

    if hard:
        verdict = "ABSTAIN"
    elif structural:
        verdict = "IDENTITY_REVIEW_NOT_READY"
    elif reasons:
        verdict = "IDENTITY_REVIEW_NOT_READY"
    else:
        # Automated gate may only clear technical minimum; human judgment still required.
        verdict = "IDENTITY_VISUAL_QUALITY_GATE_PASS_TECHNICAL_MINIMUM"

    return {
        "schema": "NURION_V07_QP_GF_FACE_V2_GATE6_VISUAL_QUALITY_GATE_V1",
        "verdict": verdict,
        "reasons": reasons,
        "checks": checks,
        "humanReviewAllowed": verdict == "IDENTITY_VISUAL_QUALITY_GATE_PASS_TECHNICAL_MINIMUM",
        "humanJudgmentStillRequired": True,
        "production": "NO-GO",
    }
