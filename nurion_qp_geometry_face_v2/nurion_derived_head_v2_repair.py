"""NURION DerivedHead v2 — conservative oral / eye / neck boundary repair."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from nurion_qp_geometry_face_v2.nurion_derived_head_cleanup import (
    SKIN_GROUP,
    _compact_mesh,
    _edge_key,
    _face_aspect,
    _orient_faces_consistent,
)
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import (
    ParsedObj,
    _boundary_loops,
    mesh_quality,
    parse_obj,
    sha256_file,
    transfer_correspondence,
    write_obj,
)

LIP_SPIKE_ASPECT = 3.8
NECK_Y_MAX = 5.78
NECK_ASPECT = 1.75
EYE_OPEN_RADIUS = 0.06
EYE_CENTERS = ((0.34, 7.28, 1.36), (-0.34, 7.28, 1.36))


@dataclass
class RepairResult:
    skin: ParsedObj
    oral_tongue: ParsedObj
    oral_teeth_upper: ParsedObj
    oral_teeth_lower: ParsedObj
    rig_joints: ParsedObj
    boundary_map: dict[str, Any]
    meta: dict[str, Any]
    quality_before: dict[str, Any]
    quality_after: dict[str, Any]
    old_to_new: dict[int, int]
    correspondence: dict[str, Any]


def _remove_faces(faces, groups, drop: set[int]):
    kept_f, kept_g = [], []
    for fi, (face, g) in enumerate(zip(faces, groups)):
        if fi not in drop:
            kept_f.append(face)
            kept_g.append(g)
    return kept_f, kept_g


def _remove_lip_spikes(skin: ParsedObj) -> tuple[ParsedObj, int]:
    V = skin.verts
    drop: set[int] = set()
    for fi, face in enumerate(skin.faces):
        ids = [vi for vi, _ in face]
        cy = float(V[ids, 1].mean())
        cz = float(V[ids, 2].mean())
        if 6.35 < cy < 6.88 and cz > 1.05 and _face_aspect(V, ids) >= LIP_SPIKE_ASPECT:
            drop.add(fi)
    faces, groups = _remove_faces(skin.faces, skin.face_groups, drop)
    return ParsedObj(skin.verts, skin.uvs, faces, groups), len(drop)


def _repair_neck(skin: ParsedObj) -> tuple[ParsedObj, dict[str, Any]]:
    loops = _boundary_loops(skin)
    if not loops:
        return skin, {"removedFaces": 0}
    neck_idx = min(range(len(loops)), key=lambda i: float(skin.verts[[a for e in loops[i] for a in e], 1].mean()))
    neck_edges = {_edge_key(a, b) for a, b in loops[neck_idx]}
    V = skin.verts
    drop: set[int] = set()
    for fi, face in enumerate(skin.faces):
        ids = [vi for vi, _ in face]
        touched = any(_edge_key(ids[i], ids[(i + 1) % len(ids)]) in neck_edges for i in range(len(ids)))
        if touched and float(V[ids, 1].min()) <= NECK_Y_MAX and _face_aspect(V, ids) >= NECK_ASPECT:
            drop.add(fi)
    faces, groups = _remove_faces(skin.faces, skin.face_groups, drop)
    return ParsedObj(skin.verts, skin.uvs, faces, groups), {"removedFaces": len(drop), "neckLoopIndexBefore": neck_idx}


def _open_eye_sockets_minimal(skin: ParsedObj) -> tuple[ParsedObj, int]:
    V = skin.verts
    drop: set[int] = set()
    for fi, face in enumerate(skin.faces):
        ids = [vi for vi, _ in face]
        for ex, ey, ez in EYE_CENTERS:
            if all(float(np.linalg.norm(V[vi] - np.array([ex, ey, ez]))) < EYE_OPEN_RADIUS for vi in ids):
                drop.add(fi)
                break
    faces, groups = _remove_faces(skin.faces, skin.face_groups, drop)
    return ParsedObj(skin.verts, skin.uvs, faces, groups), len(drop)


def _loop_stats(loop: list[tuple[int, int]], V: np.ndarray) -> dict[str, Any]:
    verts = sorted({a for e in loop for a in e})
    pts = V[verts]
    c = pts.mean(axis=0)
    ext = pts.max(axis=0) - pts.min(axis=0)
    return {
        "edgeCount": len(loop),
        "vertexCount": len(verts),
        "centroid": [float(c[0]), float(c[1]), float(c[2])],
        "extent": [float(ext[0]), float(ext[1]), float(ext[2])],
        "meanX": float(c[0]),
        "meanY": float(c[1]),
        "meanZ": float(c[2]),
        "verts": verts,
    }


def _entry_base(i: int, stats: dict[str, Any], loop_id: str, role: str, **extra) -> dict[str, Any]:
    return {
        "loopIndex": i,
        "loopId": loop_id,
        "role": role,
        "edgeCount": stats["edgeCount"],
        "vertexCount": stats["vertexCount"],
        "centroid": stats["centroid"],
        "extent": stats["extent"],
        "skinBoundary": True,
        "eyelashHelperExcluded": True,
        **extra,
    }


def _build_skin_boundary_map(mesh: ParsedObj) -> dict[str, Any]:
    loops = _boundary_loops(mesh)
    V = mesh.verts
    entries: list[dict[str, Any]] = []
    assigned: set[int] = set()

    oral_like = []
    for i, loop in enumerate(loops):
        stats = _loop_stats(loop, V)
        if stats["meanY"] > 6.55 and stats["meanZ"] > 1.0 and abs(stats["meanX"]) < 0.38:
            oral_like.append((i, stats))
    oral_like.sort(key=lambda x: x[1]["meanZ"], reverse=True)
    oral_outer = oral_inner = 0
    if oral_like:
        i, stats = oral_like[0]
        entries.append(_entry_base(i, stats, "BND_ORAL_OPENING_OUTER", "ORAL_CAVITY_OUTER"))
        assigned.add(i)
        oral_outer = 1
    if len(oral_like) > 1:
        i, stats = oral_like[1]
        entries.append(_entry_base(i, stats, "BND_ORAL_OPENING_INNER", "ORAL_CAVITY_INNER"))
        assigned.add(i)
        oral_inner = 1

    for i, loop in enumerate(loops):
        if i in assigned:
            continue
        stats = _loop_stats(loop, V)
        if stats["meanY"] < 6.08 and stats["extent"][1] > 0.3:
            entries.append(_entry_base(i, stats, "BND_NECK_CUT", "NECK_TERMINATION"))
            assigned.add(i)
            continue
        if 6.62 < stats["meanY"] < 6.95 and 0.48 < stats["meanZ"] < 0.82 and abs(stats["meanX"]) < 0.28:
            left = [v for v in stats["verts"] if V[v, 0] < -0.015]
            right = [v for v in stats["verts"] if V[v, 0] > 0.015]
            if len(left) >= 8:
                c = V[left].mean(axis=0)
                entries.append(
                    _entry_base(
                        i,
                        stats,
                        "BND_NOSTRIL_LEFT",
                        "NOSTRIL_OPENING_LEFT",
                        physicalLoopShared=True,
                        partitionVertexCount=len(left),
                        centroid=[float(c[0]), float(c[1]), float(c[2])],
                    )
                )
            if len(right) >= 8:
                c = V[right].mean(axis=0)
                entries.append(
                    _entry_base(
                        i,
                        stats,
                        "BND_NOSTRIL_RIGHT",
                        "NOSTRIL_OPENING_RIGHT",
                        physicalLoopShared=True,
                        partitionVertexCount=len(right),
                        centroid=[float(c[0]), float(c[1]), float(c[2])],
                    )
                )
            assigned.add(i)
            continue

    for side, x_sign in (("RIGHT", 1), ("LEFT", -1)):
        side_loops = []
        for i, loop in enumerate(loops):
            if i in assigned:
                continue
            stats = _loop_stats(loop, V)
            if stats["meanY"] > 7.0 and (stats["meanX"] * x_sign) > 0.1:
                side_loops.append((i, stats))
        side_loops.sort(key=lambda x: (-x[1]["meanY"], -x[1]["edgeCount"]))
        if side_loops:
            i, stats = side_loops[0]
            entries.append(_entry_base(i, stats, f"BND_EYELID_{side}_UPPER", "EYE_SOCKET_UPPER_RIM"))
            assigned.add(i)
            upper = [v for v in stats["verts"] if V[v, 1] >= stats["meanY"] - 0.002]
            lower = [v for v in stats["verts"] if V[v, 1] < stats["meanY"] - 0.002]
            if len(lower) >= 3:
                c = V[lower].mean(axis=0)
                entries.append(
                    {
                        "loopIndex": i,
                        "loopId": f"BND_EYELID_{side}_LOWER",
                        "role": "EYE_SOCKET_LOWER_RIM",
                        "edgeCount": stats["edgeCount"],
                        "vertexCount": len(lower),
                        "centroid": [float(c[0]), float(c[1]), float(c[2])],
                        "extent": stats["extent"],
                        "skinBoundary": True,
                        "eyelashHelperExcluded": True,
                        "derivedFrom": "EYE_LOOP_VERTEX_PARTITION",
                        "partitionVertexCount": len(lower),
                    }
                )
            elif len(upper) >= 3:
                assigned.discard(i)
                entries.pop()
                entries.append(_entry_base(i, stats, f"BND_EYELID_{side}_UPPER", "EYE_SOCKET_UPPER_RIM"))
                assigned.add(i)
        if len(side_loops) > 1:
            i, stats = side_loops[1]
            entries.append(_entry_base(i, stats, f"BND_EYELID_{side}_LOWER", "EYE_SOCKET_LOWER_RIM"))
            assigned.add(i)

    loop_ids = [e["loopId"] for e in entries]
    return {
        "schema": "NURION_V07_DERIVED_HEAD_BOUNDARY_LOOP_MAP_V2",
        "scope": "SKIN_ONLY_EYELASH_HELPER_EXCLUDED",
        "physicalLoopCount": len(loops),
        "semanticEntryCount": len(entries),
        "uniqueLoopIdCount": len(set(loop_ids)),
        "duplicateLoopIds": [k for k, v in Counter(loop_ids).items() if v > 1],
        "entries": entries,
        "loopCount": len(entries),
        "oralOuterLoops": oral_outer,
        "oralInnerLoops": oral_inner,
        "expectedOralOuter": 1,
        "expectedOralInner": 1,
    }


def _extract_rig_group(rig: ParsedObj, group_name: str, out_name: str) -> ParsedObj:
    faces, groups = [], []
    for face, g in zip(rig.faces, rig.face_groups):
        if g == group_name:
            faces.append(face)
            groups.append(out_name)
    return ParsedObj(rig.verts, rig.uvs, faces, groups)


def _extract_rig_joints(rig: ParsedObj) -> ParsedObj:
    faces, groups = [], []
    for face, g in zip(rig.faces, rig.face_groups):
        if g and g.startswith("joint-"):
            faces.append(face)
            groups.append(g)
    return ParsedObj(rig.verts, rig.uvs, faces, groups)


def repair_derived_head_v2(
    skin: ParsedObj,
    rig: ParsedObj,
    correspondence: dict | None = None,
) -> RepairResult:
    quality_before = mesh_quality(skin)
    steps: dict[str, Any] = {}

    work = skin
    work, n = _remove_lip_spikes(work)
    steps["lipSpikesRemoved"] = n
    work, neck_meta = _repair_neck(work)
    steps["neckRepair"] = neck_meta
    work, n_eye = _open_eye_sockets_minimal(work)
    steps["eyeSocketFacesRemoved"] = n_eye
    work, orient_meta = _orient_faces_consistent(work)
    steps["normalRecompute"] = orient_meta
    work, old_to_new = _compact_mesh(work)

    boundary_map = _build_skin_boundary_map(work)
    quality_after = mesh_quality(work)
    corr_before = correspondence or {}
    transferred = transfer_correspondence(corr_before, old_to_new) if corr_before else {}

    meta = {
        "repairVersion": "v2_conservative",
        "steps": steps,
        "geometryIsolation": {
            "skin": SKIN_GROUP,
            "oralCavity": "NURION_DerivedHead_v2_oral_tongue.obj",
            "teethUpper": "NURION_DerivedHead_v2_oral_teeth_upper.obj",
            "teethLower": "NURION_DerivedHead_v2_oral_teeth_lower.obj",
        },
        "qualityBefore": quality_before,
        "qualityAfter": quality_after,
        "boundaryPhysicalLoopsBefore": quality_before.get("boundaryLoopCount"),
        "boundaryPhysicalLoopsAfter": quality_after.get("boundaryLoopCount"),
        "correspondenceBefore": {
            "lostMappings": corr_before.get("lostMappings"),
            "typeCounts": corr_before.get("typeCounts"),
        },
        "correspondenceAfter": {
            "lostMappings": transferred.get("lostMappings"),
            "typeCounts": transferred.get("typeCounts"),
        },
        "correspondenceDelta": {
            "remappingNewLoss": max(
                0,
                (transferred.get("lostMappings") or 0) - (corr_before.get("lostMappings") or 0),
            ),
            "unsupportedDelta": (transferred.get("typeCounts") or {}).get("UNSUPPORTED", 0)
            - (corr_before.get("typeCounts") or {}).get("UNSUPPORTED", 0),
        },
    }

    return RepairResult(
        skin=work,
        oral_tongue=_extract_rig_group(rig, "helper-tongue", "NurionOralTongue"),
        oral_teeth_upper=_extract_rig_group(rig, "helper-upper-teeth", "NurionOralTeethUpper"),
        oral_teeth_lower=_extract_rig_group(rig, "helper-lower-teeth", "NurionOralTeethLower"),
        rig_joints=_extract_rig_joints(rig),
        boundary_map=boundary_map,
        meta=meta,
        quality_before=quality_before,
        quality_after=quality_after,
        old_to_new=old_to_new,
        correspondence=transferred,
    )


def write_v2_bundle(out_dir: Path, result: RepairResult, before_sha: str, header_base: list[str]) -> dict[str, str]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "skin": out_dir / "NURION_DerivedHead_v2_skin.obj",
        "oralTongue": out_dir / "NURION_DerivedHead_v2_oral_tongue.obj",
        "oralTeethUpper": out_dir / "NURION_DerivedHead_v2_oral_teeth_upper.obj",
        "oralTeethLower": out_dir / "NURION_DerivedHead_v2_oral_teeth_lower.obj",
        "rigJoints": out_dir / "NURION_DerivedHead_v2_rig_joints.obj",
    }
    write_obj(paths["skin"], result.skin, header_base + [f"# PriorV1SkinSha256: {before_sha}"])
    write_obj(paths["oralTongue"], result.oral_tongue, header_base + ["# Isolated tongue"])
    write_obj(paths["oralTeethUpper"], result.oral_teeth_upper, header_base + ["# Isolated upper teeth"])
    write_obj(paths["oralTeethLower"], result.oral_teeth_lower, header_base + ["# Isolated lower teeth"])
    write_obj(paths["rigJoints"], result.rig_joints, header_base + ["# Joints for mouth-open pivot"])

    def _wj(p: Path, v: dict) -> None:
        p.write_text(json.dumps(v, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    _wj(out_dir / "BOUNDARY_LOOP_MAP.json", result.boundary_map)
    _wj(out_dir / "REPAIR_META.json", result.meta)
    _wj(out_dir / "MESH_QUALITY.json", result.quality_after)
    _wj(out_dir / "MEDIAPIPE_478_CORRESPONDENCE_DERIVED.json", result.correspondence)
    return {"skinSha256": sha256_file(paths["skin"]), "paths": {k: str(v) for k, v in paths.items()}}


def load_v1_and_repair(v1_dir: Path, corr_path: Path | None = None) -> RepairResult:
    skin = parse_obj(v1_dir / "NURION_DerivedHead_v1_skin.obj")
    rig = parse_obj(v1_dir / "NURION_DerivedHead_v1_rig_helpers.obj")
    corr = json.loads(corr_path.read_text(encoding="utf-8")) if corr_path and corr_path.is_file() else {}
    return repair_derived_head_v2(skin, rig, corr)
