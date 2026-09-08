"""Derive NURION Head Base from pinned hm08 — topology/oral cavity only, no renders."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

EXPECTED_HM08_SHA = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
EXP_G5 = "6b19a231bfddff5014532bf2527a3cdce5a2a574b8dad97e8c88014ef351d31d"


@dataclass
class ParsedObj:
    verts: np.ndarray
    uvs: np.ndarray
    faces: list[list[tuple[int, int | None]]]  # (vi, ti)
    face_groups: list[str | None]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_obj(path: Path) -> ParsedObj:
    verts: list[list[float]] = []
    uvs: list[list[float]] = []
    faces: list[list[tuple[int, int | None]]] = []
    face_groups: list[str | None] = []
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append([float(a[1]), float(a[2]), float(a[3])])
        elif line.startswith("vt "):
            a = line.split()
            uvs.append([float(a[1]), float(a[2])])
        elif line.startswith("g ") or line.startswith("o "):
            current = line[2:].strip()
        elif line.startswith("f "):
            idxs = []
            for t in line.split()[1:]:
                p = t.split("/")
                vi = int(p[0]) - 1
                ti = int(p[1]) - 1 if len(p) > 1 and p[1] else None
                idxs.append((vi, ti))
            faces.append(idxs)
            face_groups.append(current)
    return ParsedObj(np.asarray(verts, np.float64), np.asarray(uvs, np.float64) if uvs else np.zeros((0, 2)), faces, face_groups)


def derive_head(
    src: ParsedObj,
    regions: dict[str, list[int]],
) -> tuple[ParsedObj, dict[str, Any], dict[int, int]]:
    """Extract head+neck+helpers, cut oral opening, keep sockets/loops."""
    keep_groups = {
        "helper-l-eye",
        "helper-r-eye",
        "helper-l-eyelashes-1",
        "helper-l-eyelashes-2",
        "helper-r-eyelashes-1",
        "helper-r-eyelashes-2",
        "helper-tongue",
        "helper-upper-teeth",
        "helper-lower-teeth",
        "joint-jaw",
        "joint-mouth",
        "joint-l-eye",
        "joint-r-eye",
        "joint-l-upperlid",
        "joint-l-lowerlid",
        "joint-r-upperlid",
        "joint-r-lowerlid",
        "joint-neck",
        "joint-head",
        "joint-head-2",
        "joint-tongue-1",
        "joint-tongue-2",
        "joint-tongue-3",
        "joint-tongue-4",
    }
    head_set = set(regions.get("HEAD_ALL") or [])
    neck_set = set(regions.get("NECK") or [])
    body_keep = head_set | neck_set
    lips = set(regions.get("LIPS") or [])
    oral_helpers = set(regions.get("ORAL") or [])

    selected: list[tuple[list[tuple[int, int | None]], str | None]] = []
    for face, g in zip(src.faces, src.face_groups):
        vis = [vi for vi, _ in face]
        if g and g != "body" and g in keep_groups:
            selected.append((face, g))
            continue
        if g == "body" or g is None:
            if vis and all(vi in body_keep for vi in vis):
                selected.append((face, "NurionHeadSkin"))

    V = src.verts
    lip_faces_removed = 0
    kept: list[tuple[list[tuple[int, int | None]], str | None]] = []
    if lips:
        lip_ys = V[list(lips), 1]
        mid_y = float(np.median(lip_ys))
        upper_lip = {i for i in lips if V[i, 1] >= mid_y}
        lower_lip = {i for i in lips if V[i, 1] < mid_y}
        for face, g in selected:
            vis = [vi for vi, _ in face]
            if g != "NurionHeadSkin":
                kept.append((face, g))
                continue
            u = sum(1 for vi in vis if vi in upper_lip)
            lo = sum(1 for vi in vis if vi in lower_lip)
            if u > 0 and lo > 0 and all(vi in lips for vi in vis):
                lip_faces_removed += 1
                continue
            if all(vi in lips for vi in vis):
                ys = V[vis, 1]
                if float(ys.max() - ys.min()) < 0.06 and abs(float(ys.mean()) - mid_y) < 0.05:
                    lip_faces_removed += 1
                    continue
            kept.append((face, g))
    else:
        kept = selected

    used: set[int] = set()
    for face, _g in kept:
        for vi, _ti in face:
            used.add(vi)
    used |= oral_helpers
    used |= set(regions.get("HELPER_L_EYE") or [])
    used |= set(regions.get("HELPER_R_EYE") or [])

    old_sorted = sorted(used)
    old_to_new = {old: i for i, old in enumerate(old_sorted)}
    new_verts = V[old_sorted]

    # Build UVs: prefer source vt; fallback frontal per vertex
    new_uvs: list[list[float]] = []
    vert_uv_index: dict[int, int] = {}
    xs, ys = new_verts[:, 0], new_verts[:, 1]
    x0, x1 = float(xs.min()), float(xs.max())
    y0, y1 = float(ys.min()), float(ys.max())

    def ensure_uv_for_vert(nvi: int, ti: int | None) -> int:
        if nvi in vert_uv_index:
            return vert_uv_index[nvi]
        if ti is not None and len(src.uvs) and 0 <= ti < len(src.uvs):
            new_uvs.append([float(src.uvs[ti, 0]), float(src.uvs[ti, 1])])
        else:
            x, y = float(new_verts[nvi, 0]), float(new_verts[nvi, 1])
            new_uvs.append([(x - x0) / max(x1 - x0, 1e-8), (y - y0) / max(y1 - y0, 1e-8)])
        vert_uv_index[nvi] = len(new_uvs) - 1
        return vert_uv_index[nvi]

    faces_out: list[list[tuple[int, int | None]]] = []
    groups_out: list[str | None] = []
    for face, g in kept:
        nf = []
        for vi, ti in face:
            nvi = old_to_new[vi]
            nti = ensure_uv_for_vert(nvi, ti)
            nf.append((nvi, nti))
        faces_out.append(nf)
        groups_out.append(g)

    derived = ParsedObj(new_verts, np.asarray(new_uvs, np.float64), faces_out, groups_out)
    boundary = _boundary_loops(derived)
    meta = {
        "sourceFacesKept": len(kept),
        "oralFacesRemoved": lip_faces_removed,
        "vertexCount": int(len(derived.verts)),
        "faceCount": int(len(derived.faces)),
        "groups": sorted({g for g in derived.face_groups if g}),
        "boundaryLoopCount": len(boundary),
        "boundaryEdgeCount": sum(len(loop) for loop in boundary),
        "oldToNewCount": len(old_to_new),
        "jawRegionKept": len(set(regions.get("JAW") or []) & used),
        "neckRegionKept": len(set(regions.get("NECK") or []) & used),
        "earRegionKept": len(set(regions.get("EAR") or []) & used),
        "noseRegionKept": len(set(regions.get("NOSE") or []) & used),
        "eyelidRegionKept": len(set(regions.get("EYELID") or []) & used),
    }
    return derived, meta, old_to_new


def _boundary_loops(mesh: ParsedObj) -> list[list[tuple[int, int]]]:
    edge = Counter()
    for face in mesh.faces:
        ids = [vi for vi, _ in face]
        n = len(ids)
        for i in range(n):
            a, b = ids[i], ids[(i + 1) % n]
            e = (min(a, b), max(a, b))
            edge[e] += 1
    bounds = [e for e, c in edge.items() if c == 1]
    adj: dict[int, list[int]] = defaultdict(list)
    for a, b in bounds:
        adj[a].append(b)
        adj[b].append(a)
    seen_e = set()
    loops = []
    for a, b in bounds:
        e0 = (min(a, b), max(a, b))
        if e0 in seen_e:
            continue
        loop = []
        prev, cur = a, b
        start = a
        for _ in range(len(bounds) + 2):
            e = (min(prev, cur), max(prev, cur))
            if e in seen_e and loop:
                break
            seen_e.add(e)
            loop.append((prev, cur))
            nxts = [x for x in adj[cur] if x != prev]
            if not nxts:
                break
            prev, cur = cur, nxts[0]
            if cur == start:
                e = (min(prev, cur), max(prev, cur))
                seen_e.add(e)
                loop.append((prev, cur))
                break
        if loop:
            loops.append(loop)
    return loops


def mesh_quality(mesh: ParsedObj) -> dict[str, Any]:
    V = mesh.verts
    # duplicate verts
    # round to grid
    keyed = {}
    dup_pairs = 0
    for i, v in enumerate(V):
        k = (round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6))
        if k in keyed:
            dup_pairs += 1
        else:
            keyed[k] = i

    edge_faces: dict[tuple[int, int], list[int]] = defaultdict(list)
    face_normals = []
    flipped_suspect = 0
    nonmanifold = 0
    for fi, face in enumerate(mesh.faces):
        ids = [vi for vi, _ in face]
        if len(ids) < 3:
            continue
        a, b, c = V[ids[0]], V[ids[1]], V[ids[2]]
        n = np.cross(b - a, c - a)
        nn = float(np.linalg.norm(n))
        if nn < 1e-12:
            face_normals.append(np.zeros(3))
        else:
            face_normals.append(n / nn)
        n_ids = len(ids)
        for i in range(n_ids):
            e = (min(ids[i], ids[(i + 1) % n_ids]), max(ids[i], ids[(i + 1) % n_ids]))
            edge_faces[e].append(fi)

    for e, fis in edge_faces.items():
        if len(fis) > 2:
            nonmanifold += 1
        elif len(fis) == 2:
            n0, n1 = face_normals[fis[0]], face_normals[fis[1]]
            # adjacent faces should have consistent orientation along shared edge — soft check via normal angle
            if float(np.dot(n0, n1)) < -0.98:
                flipped_suspect += 1

    # UV continuity: per-vertex UV variance across loops
    uv_break = 0.0
    if len(mesh.uvs):
        acc: dict[int, list[tuple[float, float]]] = defaultdict(list)
        for face in mesh.faces:
            for vi, ti in face:
                if ti is None:
                    continue
                acc[vi].append((float(mesh.uvs[ti, 0]), float(mesh.uvs[ti, 1])))
        for samples in acc.values():
            if len(samples) < 2:
                continue
            xs = [s[0] for s in samples]
            ys = [s[1] for s in samples]
            # allow seam wrap at 0/1
            span_u = min(max(xs) - min(xs), 1.0 - (max(xs) - min(xs)))
            # simpler: raw span; seams expected on head back
            span_u = max(xs) - min(xs)
            span_v = max(ys) - min(ys)
            if span_u > 0.25 or span_v > 0.25:
                uv_break = max(uv_break, span_u, span_v)

    boundary = _boundary_loops(mesh)
    quads = sum(1 for f in mesh.faces if len(f) == 4)
    tris = sum(1 for f in mesh.faces if len(f) == 3)
    return {
        "duplicateVertexPairsApprox": dup_pairs,
        "nonManifoldEdges": nonmanifold,
        "flippedAdjacentSuspect": flipped_suspect,
        "uvDiscontinuityMaxSpan": float(uv_break),
        "boundaryLoopCount": len(boundary),
        "quadCount": quads,
        "triCount": tris,
        "hasOralBoundary": len(boundary) >= 1,
        "passSoft": nonmanifold == 0 and dup_pairs < 50 and flipped_suspect < 20,
    }


def transfer_correspondence(corr: dict, old_to_new: dict[int, int]) -> dict[str, Any]:
    entries = []
    type_counts: Counter = Counter()
    lost = 0
    for e in corr.get("entries") or []:
        et = e.get("type")
        if et == "UNSUPPORTED":
            entries.append(dict(e))
            type_counts["UNSUPPORTED"] += 1
            continue
        ne = {"mpIndex": e.get("mpIndex"), "type": et, "region": e.get("region"), "transferredFromHm08": True}
        ok = True
        if et == "VERTEX":
            v = e.get("vertex")
            if v not in old_to_new:
                ok = False
            else:
                ne["vertex"] = old_to_new[v]
        elif et == "EDGE":
            edge = e.get("edge") or []
            if len(edge) != 2 or edge[0] not in old_to_new or edge[1] not in old_to_new:
                ok = False
            else:
                ne["edge"] = [old_to_new[edge[0]], old_to_new[edge[1]]]
                ne["t"] = e.get("t")
        elif et == "FACE_BARYCENTRIC":
            face = e.get("face") or []
            if len(face) != 3 or any(v not in old_to_new for v in face):
                ok = False
            else:
                ne["face"] = [old_to_new[v] for v in face]
                ne["barycentric"] = e.get("barycentric")
        else:
            ok = False
        if not ok:
            lost += 1
            ne = {
                "mpIndex": e.get("mpIndex"),
                "type": "UNSUPPORTED",
                "reason": "LOST_IN_HEAD_EXTRACTION_OR_ORAL_CUT",
                "prior": et,
            }
            type_counts["UNSUPPORTED"] += 1
        else:
            type_counts[et] += 1
        entries.append(ne)
    return {
        "schema": "NURION_V07_DERIVED_HEAD_MEDIAPIPE_478_CORRESPONDENCE_V1",
        "forcedSingleVertexMapping": "DENY",
        "typeCounts": dict(type_counts),
        "lostMappings": lost,
        "entries": entries,
    }


def write_obj(path: Path, mesh: ParsedObj, header: list[str]) -> None:
    lines = list(header)
    lines.append("o NurionDerivedHeadV0")
    for x, y, z in mesh.verts:
        lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")
    for u, v in mesh.uvs:
        lines.append(f"vt {u:.8f} {v:.8f}")
    current = None
    for face, g in zip(mesh.faces, mesh.face_groups):
        if g != current:
            lines.append(f"g {g or 'NurionHead'}")
            current = g
        toks = []
        for vi, ti in face:
            if ti is None:
                toks.append(f"{vi+1}")
            else:
                toks.append(f"{vi+1}/{ti+1}")
        lines.append("f " + " ".join(toks))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
