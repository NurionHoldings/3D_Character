"""Cleanup pass for NURION DerivedHead — normals, boundaries, neck, geometry separation."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    ParsedObj,
    _boundary_loops,
    mesh_quality,
    parse_obj,
    sha256_file,
    transfer_correspondence,
    write_obj,
)

SKIN_GROUP = "NurionHeadSkin"
RIG_PREFIXES = ("joint-", "helper-")

NECK_SPIKE_Y_MAX = 5.65
NECK_SPIKE_ASPECT = 2.5


@dataclass
class CleanupResult:
    skin: ParsedObj
    rig: ParsedObj
    meta: dict[str, Any]
    boundary_map: dict[str, Any]
    quality_before: dict[str, Any]
    quality_after: dict[str, Any]
    old_to_new: dict[int, int]
    correspondence: dict[str, Any]


def _face_normal(V: np.ndarray, ids: list[int]) -> np.ndarray:
    if len(ids) < 3:
        return np.zeros(3)
    a, b, c = V[ids[0]], V[ids[1]], V[ids[2]]
    n = np.cross(b - a, c - a)
    nn = float(np.linalg.norm(n))
    return n / nn if nn > 1e-12 else np.zeros(3)


def _face_aspect(V: np.ndarray, ids: list[int]) -> float:
    lens = []
    n = len(ids)
    for i in range(n):
        lens.append(float(np.linalg.norm(V[ids[i]] - V[ids[(i + 1) % n]])))
    return max(lens) / max(min(lens), 1e-8)


def _edge_key(a: int, b: int) -> tuple[int, int]:
    return (min(a, b), max(a, b))


def _orient_faces_consistent(mesh: ParsedObj, seed_face: int | None = None) -> tuple[ParsedObj, dict[str, Any]]:
    """Propagate winding so adjacent faces agree; flip when needed."""
    V = mesh.verts
    faces = [list(face) for face in mesh.faces]
    n_faces = len(faces)
    if n_faces == 0:
        return mesh, {"flippedFaces": 0, "seedFace": None}

    edge_to_faces: dict[tuple[int, int], list[tuple[int, int, int]]] = defaultdict(list)
    for fi, face in enumerate(faces):
        ids = [vi for vi, _ in face]
        m = len(ids)
        for i in range(m):
            a, b = ids[i], ids[(i + 1) % m]
            edge_to_faces[_edge_key(a, b)].append((fi, a, b))

    if seed_face is None:
        # Forehead-ish: highest Y centroid among quads
        best = 0
        best_y = -1e9
        for fi, face in enumerate(faces):
            ids = [vi for vi, _ in face]
            cy = float(V[ids, 1].mean())
            if cy > best_y:
                best_y = cy
                best = fi
        seed_face = best

    center = V.mean(axis=0)
    seed_ids = [vi for vi, _ in faces[seed_face]]
    seed_c = V[seed_ids].mean(axis=0)
    seed_n = _face_normal(V, seed_ids)
    out_ref = seed_c - center
    out_ref_n = float(np.linalg.norm(out_ref))
    if out_ref_n > 1e-9:
        out_ref = out_ref / out_ref_n
        if float(np.dot(seed_n, out_ref)) < 0:
            faces[seed_face] = [(seed_ids[i], faces[seed_face][i][1]) for i in reversed(range(len(faces[seed_face])))]

    visited = [False] * n_faces
    stack = [seed_face]
    visited[seed_face] = True
    flipped = 0

    while stack:
        fi = stack.pop()
        ids = [vi for vi, _ in faces[fi]]
        for i in range(len(ids)):
            a, b = ids[i], ids[(i + 1) % len(ids)]
            ek = _edge_key(a, b)
            for fj, aj, bj in edge_to_faces.get(ek, []):
                if fj == fi or visited[fj]:
                    continue
                # fi uses edge a->b; fj should use b->a for consistent orientation
                fj_ids = [vi for vi, _ in faces[fj]]
                consistent = False
                for k in range(len(fj_ids)):
                    if fj_ids[k] == b and fj_ids[(k + 1) % len(fj_ids)] == a:
                        consistent = True
                        break
                if not consistent:
                    faces[fj] = [(fj_ids[i], faces[fj][i][1]) for i in reversed(range(len(faces[fj])))]
                    flipped += 1
                visited[fj] = True
                stack.append(fj)

    oriented = ParsedObj(mesh.verts, mesh.uvs, faces, list(mesh.face_groups))
    return oriented, {"flippedFaces": flipped, "seedFace": seed_face, "visitedFaces": int(sum(visited))}


def _classify_loop(loop_idx: int, loop: list[tuple[int, int]], V: np.ndarray) -> dict[str, Any]:
    verts = sorted({a for e in loop for a in e})
    pts = V[verts]
    c = pts.mean(axis=0)
    ext = pts.max(axis=0) - pts.min(axis=0)
    cy, cz, cx = float(c[1]), float(c[2]), float(c[0])
    edge_count = len(loop)

    if cy < 6.05 and ext[1] > 0.35:
        loop_id = "BND_NECK_CUT"
        role = "NECK_TERMINATION"
    elif abs(cx) > 0.25 and cy > 7.05:
        side = "RIGHT" if cx > 0 else "LEFT"
        loop_id = f"BND_EYELASH_{side}_{'UPPER' if cy > 7.28 else 'LOWER'}"
        role = "EYELASH_HELPER_BOUNDARY"
    elif abs(cx) > 0.25 and cy > 7.0:
        side = "RIGHT" if cx > 0 else "LEFT"
        loop_id = f"BND_EYE_SOCKET_{side}"
        role = "EYE_SOCKET_RIM"
    elif cz < 0.75 and abs(cx) < 0.25:
        loop_id = "BND_NOSE_NOSTRIL"
        role = "NOSTRIL_OPENING"
    elif cy > 6.62 and cz > 1.45 and abs(cx) < 0.35:
        loop_id = "BND_ORAL_OPENING_OUTER"
        role = "ORAL_CAVITY_PRIMARY"
    elif cy > 6.62 and cz > 1.1 and abs(cx) < 0.35:
        loop_id = "BND_ORAL_OPENING_INNER"
        role = "ORAL_CAVITY_INNER_RING"
    elif cy < 6.75 and cz > 0.9:
        loop_id = "BND_ORAL_JAW_LINE"
        role = "ORAL_ADJACENT"
    else:
        loop_id = f"BND_UNCLASSIFIED_{loop_idx:02d}"
        role = "REVIEW_REQUIRED"

    return {
        "loopIndex": loop_idx,
        "loopId": loop_id,
        "role": role,
        "edgeCount": edge_count,
        "vertexCount": len(verts),
        "centroid": [float(c[0]), float(c[1]), float(c[2])],
        "extent": [float(ext[0]), float(ext[1]), float(ext[2])],
        "oralCavityBoundary": loop_id.startswith("BND_ORAL_OPENING_OUTER"),
        "qaVisible": loop_id != "BND_ORAL_OPENING_INNER",
    }


def _build_boundary_map(mesh: ParsedObj) -> dict[str, Any]:
    loops = _boundary_loops(mesh)
    entries = [_classify_loop(i, loop, mesh.verts) for i, loop in enumerate(loops)]
    oral = [e for e in entries if e["loopId"].startswith("BND_ORAL_OPENING")]
    return {
        "schema": "NURION_V07_DERIVED_HEAD_BOUNDARY_LOOP_MAP_V1",
        "loopCount": len(entries),
        "entries": entries,
        "oralPrimaryLoopId": "BND_ORAL_OPENING_OUTER",
        "oralLoopsDetected": [e["loopId"] for e in oral],
        "nonOralLoops": [e["loopId"] for e in entries if not e["loopId"].startswith("BND_ORAL")],
    }


def _remove_neck_spike_faces(skin: ParsedObj) -> tuple[ParsedObj, dict[str, Any]]:
    loops = _boundary_loops(skin)
    if len(loops) < 4:
        return skin, {"removedFaces": 0, "reason": "NO_NECK_LOOP"}
    neck_idx = min(range(len(loops)), key=lambda i: float(skin.verts[[a for e in loops[i] for a in e], 1].mean()))
    neck_edges = {_edge_key(a, b) for a, b in loops[neck_idx]}

    kept_faces: list[list[tuple[int, int | None]]] = []
    kept_groups: list[str | None] = []
    removed = 0
    V = skin.verts
    for face, g in zip(skin.faces, skin.face_groups):
        ids = [vi for vi, _ in face]
        touched = any(
            _edge_key(ids[i], ids[(i + 1) % len(ids)]) in neck_edges for i in range(len(ids))
        )
        if touched:
            ymin = float(V[ids, 1].min())
            aspect = _face_aspect(V, ids)
            if ymin <= NECK_SPIKE_Y_MAX and aspect >= NECK_SPIKE_ASPECT:
                removed += 1
                continue
        kept_faces.append(face)
        kept_groups.append(g)

    out = ParsedObj(skin.verts, skin.uvs, kept_faces, kept_groups)
    return out, {"removedFaces": removed, "neckLoopIndex": neck_idx}


def _split_skin_rig(mesh: ParsedObj) -> tuple[ParsedObj, ParsedObj]:
    skin_faces: list[list[tuple[int, int | None]]] = []
    skin_groups: list[str | None] = []
    rig_faces: list[list[tuple[int, int | None]]] = []
    rig_groups: list[str | None] = []

    for face, g in zip(mesh.faces, mesh.face_groups):
        if g == SKIN_GROUP:
            skin_faces.append(face)
            skin_groups.append(g)
        elif g and (g.startswith("joint-") or g.startswith("helper-")):
            rig_faces.append(face)
            rig_groups.append(g)

    skin = ParsedObj(mesh.verts, mesh.uvs, skin_faces, skin_groups)
    rig = ParsedObj(mesh.verts, mesh.uvs, rig_faces, rig_groups)
    return skin, rig


def _compact_mesh(mesh: ParsedObj) -> tuple[ParsedObj, dict[int, int]]:
    used: set[int] = set()
    for face in mesh.faces:
        for vi, _ in face:
            used.add(vi)
    old_sorted = sorted(used)
    old_to_new = {old: i for i, old in enumerate(old_sorted)}
    new_verts = mesh.verts[old_sorted]

    vert_uv: dict[int, int] = {}
    new_uvs: list[list[float]] = []
    if len(mesh.uvs):
        for old in old_sorted:
            vert_uv[old] = len(new_uvs)
            new_uvs.append([0.0, 0.0])

    new_faces: list[list[tuple[int, int | None]]] = []
    for face in mesh.faces:
        nf = []
        for vi, ti in face:
            nvi = old_to_new[vi]
            if ti is not None and len(mesh.uvs):
                if ti < len(mesh.uvs):
                    vert_uv_idx = vert_uv.get(vi)
                    if vert_uv_idx is not None:
                        new_uvs[vert_uv_idx] = [float(mesh.uvs[ti, 0]), float(mesh.uvs[ti, 1])]
                nti = vert_uv.get(vi)
            else:
                nti = ti
            nf.append((nvi, nti))
        new_faces.append(nf)

    compact = ParsedObj(
        new_verts,
        np.asarray(new_uvs, np.float64) if new_uvs else mesh.uvs,
        new_faces,
        list(mesh.face_groups),
    )
    return compact, old_to_new


def cleanup_derived_head(
    mesh: ParsedObj,
    correspondence: dict | None = None,
) -> CleanupResult:
    quality_before = mesh_quality(mesh)
    boundary_before_full = _build_boundary_map(mesh)

    skin, rig = _split_skin_rig(mesh)
    skin, neck_meta = _remove_neck_spike_faces(skin)
    skin, orient_meta = _orient_faces_consistent(skin)
    skin, skin_old_to_new = _compact_mesh(skin)
    rig, _rig_map = _compact_mesh(rig)

    boundary_skin = _build_boundary_map(skin)
    boundary_after = dict(boundary_before_full)
    boundary_after["skinOnlyLoopCount"] = boundary_skin["loopCount"]
    boundary_after["skinOnlyLoops"] = boundary_skin["entries"]
    boundary_after["note"] = (
        "Primary 10-loop classification is on full v0 derived mesh; "
        "skin-only QA mesh exposes oral/nose/neck loops after rig separation."
    )

    quality_after = mesh_quality(skin)

    corr_before = correspondence or {}
    transferred = (
        transfer_correspondence(corr_before, skin_old_to_new) if corr_before else {}
    )

    meta = {
        "skinGroup": SKIN_GROUP,
        "rigGroups": sorted({g for g in rig.face_groups if g}),
        "geometrySeparation": "SKIN_VS_RIG_COMPLETE",
        "removedFloatingSquaresPolicy": "RIG_ONLY_NOT_QA_SKIN",
        "neckCleanup": neck_meta,
        "normalRecompute": orient_meta,
        "qualityBefore": quality_before,
        "qualityAfter": quality_after,
        "boundaryLoopCountBefore": boundary_before_full["loopCount"],
        "boundaryLoopCountAfterFullMesh": boundary_before_full["loopCount"],
        "boundaryLoopCountSkinOnly": boundary_skin["loopCount"],
        "correspondenceBefore": {
            "lostMappings": corr_before.get("lostMappings"),
            "typeCounts": corr_before.get("typeCounts"),
        },
        "correspondenceAfter": {
            "lostMappings": transferred.get("lostMappings"),
            "typeCounts": transferred.get("typeCounts"),
        },
        "correspondenceDelta": {
            "lostMappingsDelta": (transferred.get("lostMappings") or 0) - (corr_before.get("lostMappings") or 0),
            "unsupportedDelta": (transferred.get("typeCounts") or {}).get("UNSUPPORTED", 0)
            - (corr_before.get("typeCounts") or {}).get("UNSUPPORTED", 0),
        },
    }

    return CleanupResult(
        skin=skin,
        rig=rig,
        meta=meta,
        boundary_map=boundary_after,
        quality_before=quality_before,
        quality_after=quality_after,
        old_to_new=skin_old_to_new,
        correspondence=transferred,
    )


def write_cleanup_bundle(
    out_dir: Path,
    skin: ParsedObj,
    rig: ParsedObj,
    boundary_map: dict,
    meta: dict,
    transferred: dict,
    before_sha: str,
    header_base: list[str],
) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    skin_path = out_dir / "NURION_DerivedHead_v1_skin.obj"
    rig_path = out_dir / "NURION_DerivedHead_v1_rig_helpers.obj"
    qa_path = out_dir / "NURION_DerivedHead_v1_qa_skin.obj"

    skin_header = header_base + [
        "# Cleanup: skin-only NurionHeadSkin — QA gray/wireframe target",
        f"# PriorDerivedSha256: {before_sha}",
    ]
    rig_header = header_base + [
        "# Cleanup: rig helpers and joints — excluded from neutral gray skin QA",
        "# Oral helpers here are used only for mouth-open QA pass",
        f"# PriorDerivedSha256: {before_sha}",
    ]
    qa_header = header_base + [
        "# Cleanup: alias of v1 skin for QA rerender entry",
        f"# PriorDerivedSha256: {before_sha}",
    ]

    write_obj(skin_path, skin, skin_header)
    write_obj(rig_path, rig, rig_header)
    write_obj(qa_path, skin, qa_header)

    def _write_json(p: Path, v: dict) -> None:
        p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    _write_json(out_dir / "BOUNDARY_LOOP_MAP.json", boundary_map)
    _write_json(out_dir / "CLEANUP_META.json", meta)
    _write_json(out_dir / "MESH_QUALITY.json", meta["qualityAfter"])
    _write_json(out_dir / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json", transferred)

    return {
        "skin": str(skin_path),
        "rig": str(rig_path),
        "qaSkin": str(qa_path),
        "skinSha256": sha256_file(skin_path),
        "rigSha256": sha256_file(rig_path),
        "qaSkinSha256": sha256_file(qa_path),
    }


def load_and_cleanup(path: Path, corr_path: Path | None = None) -> CleanupResult:
    mesh = parse_obj(path)
    corr = json.loads(corr_path.read_text(encoding="utf-8")) if corr_path and corr_path.is_file() else {}
    return cleanup_derived_head(mesh, corr)
