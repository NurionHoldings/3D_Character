"""CR04-GAP-01 — asset-independent facial region resolution (does not patch CR02)."""

from __future__ import annotations

from typing import Any

import numpy as np


def resolve_head_joint_local_index(
    *,
    nodes: list[dict[str, Any]],
    skin_joints: list[int],
    nurion_head_name: str,
) -> dict[str, Any]:
    """Map CR01 NURION_head bone name → skin.joints local index. Fail-closed."""
    if not nurion_head_name:
        raise AssertionError("NURION_head unresolved")
    matches = [i for i, n in enumerate(nodes) if n.get("name") == nurion_head_name]
    if len(matches) != 1:
        raise AssertionError(f"NURION_head node ambiguous/missing: {nurion_head_name!r} count={len(matches)}")
    head_node = matches[0]
    if head_node not in skin_joints:
        raise AssertionError(f"Head node {head_node} not in skin.joints")
    local = skin_joints.index(head_node)
    return {
        "nurionHeadName": nurion_head_name,
        "headNodeIndex": head_node,
        "headJointLocalIndex": local,
        "resolver": "CR01_NURION_head→skin.joints.index",
        "hardcodedIdle15Index21": "NOT_USED",
    }


def select_facial_vertices_resolved(
    pos: np.ndarray,
    joints: np.ndarray,
    weights: np.ndarray,
    head_local_index: int,
) -> dict[str, np.ndarray]:
    """Head-weight + head-local geometry regions. No absolute world FACE_Y_MIN."""
    head_w = np.zeros(len(pos), dtype=np.float32)
    for k in range(4):
        mask = joints[:, k] == head_local_index
        head_w[mask] += weights[mask, k]

    face = head_w >= 0.25
    if not face.any():
        # fail-closed soft fallback only within head-weight distribution (still not absolute Y)
        thr = float(np.percentile(head_w, 90))
        face = head_w >= max(thr, 1e-6)
    if not face.any():
        raise AssertionError("FACE_REGION_EMPTY after head-weight resolve")

    fp = pos[face]
    cy = float(np.median(fp[:, 1]))
    cx = float(np.median(fp[:, 0]))
    cz = float(np.median(fp[:, 2]))
    # head-local vertical span for relative bands
    y_lo = float(np.percentile(fp[:, 1], 5))
    y_hi = float(np.percentile(fp[:, 1], 95))
    y_span = max(y_hi - y_lo, 1e-4)

    eye_band = (
        face
        & (pos[:, 1] > cy + 0.08 * y_span)
        & (pos[:, 1] < cy + 0.55 * y_span)
        & (pos[:, 2] > cz - 0.35 * y_span)
    )
    eye_l = eye_band & (pos[:, 0] > cx + 0.02 * y_span)
    eye_r = eye_band & (pos[:, 0] < cx - 0.02 * y_span)
    mouth = (
        face
        & (pos[:, 1] < cy - 0.08 * y_span)
        & (pos[:, 1] > cy - 0.65 * y_span)
        & (pos[:, 2] > cz - 0.45 * y_span)
    )
    jaw = face & (pos[:, 1] < cy - 0.25 * y_span) & (pos[:, 1] > cy - 0.85 * y_span)
    brow = face & (pos[:, 1] > cy + 0.35 * y_span) & (pos[:, 1] < cy + 0.75 * y_span)
    smile_l = mouth & (pos[:, 0] > cx + 0.08 * y_span)
    smile_r = mouth & (pos[:, 0] < cx - 0.08 * y_span)
    return {
        "face": face,
        "eye_l": eye_l,
        "eye_r": eye_r,
        "mouth": mouth,
        "jaw": jaw,
        "brow": brow,
        "smile_l": smile_l,
        "smile_r": smile_r,
        "centroid": np.array([cx, cy, cz], dtype=np.float32),
        "headLocalYSpan": np.float32(y_span),
    }
