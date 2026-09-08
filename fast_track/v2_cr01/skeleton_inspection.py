"""CR01-P01 — Real Skeleton Inspection (read-only)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import ParseError, load_gltf_document
from fast_track.adaptation.inspector import canonical_sha256, sha256_file

REPORT_SCHEMA = "NURION_V2_CR01_SKELETON_INSPECTION_V1"


def _parent_map(nodes: list[dict[str, Any]]) -> dict[int, int | None]:
    parent: dict[int, int | None] = {i: None for i in range(len(nodes))}
    for i, n in enumerate(nodes):
        for c in n.get("children") or []:
            if isinstance(c, int) and 0 <= c < len(nodes):
                parent[c] = i
    return parent


def _skin_joint_set(gltf: dict[str, Any]) -> set[int]:
    out: set[int] = set()
    for skin in gltf.get("skins") or []:
        for j in skin.get("joints") or []:
            if isinstance(j, int):
                out.add(j)
    return out


def inspect_skeleton(path: Path | str) -> dict[str, Any]:
    """Extract deterministic skeleton graph without mutating source."""
    path = Path(path)
    before = path.read_bytes() if path.is_file() else None
    source_sha = sha256_file(path) if path.is_file() else None

    blockers: list[dict[str, Any]] = []
    try:
        gltf, _bin, fmt = load_gltf_document(path)
    except ParseError as e:
        return {
            "schema": REPORT_SCHEMA,
            "stage": "CR01-P01",
            "status": "BLOCKED",
            "blockers": [{"code": "SKELETON_EXTRACTION_FAILED", "message": str(e)}],
            "sourceIdentity": {"path": str(path), "sha256": source_sha},
            "sourcePreservation": {"bytesUnchanged": True},
        }

    nodes = gltf.get("nodes") or []
    parent = _parent_map(nodes)
    skin_joints = _skin_joint_set(gltf)

    node_records = []
    for i, n in enumerate(nodes):
        children = [c for c in (n.get("children") or []) if isinstance(c, int)]
        node_records.append(
            {
                "index": i,
                "name": n.get("name"),
                "parentIndex": parent.get(i),
                "childIndices": children,
                "isSkinJoint": i in skin_joints,
            }
        )

    roots = [i for i in range(len(nodes)) if parent.get(i) is None]
    cycles = _detect_cycles(parent, len(nodes))
    if cycles:
        blockers.append({"code": "CYCLIC_SKELETON", "cycles": cycles})

    after = path.read_bytes() if path.is_file() else None
    preserved = before is not None and before == after

    skeleton_core = {
        "format": fmt,
        "nodeCount": len(nodes),
        "skinJointCount": len(skin_joints),
        "rootIndices": roots,
        "nodes": node_records,
        "parentMap": {str(k): v for k, v in parent.items()},
        "skinJoints": sorted(skin_joints),
    }
    source_skeleton_digest = canonical_sha256(
        {
            "nodeCount": skeleton_core["nodeCount"],
            "nodes": [
                {
                    "index": r["index"],
                    "name": r["name"],
                    "parentIndex": r["parentIndex"],
                    "childIndices": r["childIndices"],
                    "isSkinJoint": r["isSkinJoint"],
                }
                for r in node_records
            ],
            "skinJoints": skeleton_core["skinJoints"],
        }
    )

    status = "BLOCKED" if blockers else "PASS"
    return {
        "schema": REPORT_SCHEMA,
        "stage": "CR01-P01",
        "status": status,
        "sourceIdentity": {
            "path": str(path),
            "sha256": source_sha,
            "byteLength": len(before) if before is not None else None,
        },
        "sourceSkeletonDigest": source_skeleton_digest,
        "skeleton": skeleton_core,
        "blockers": blockers,
        "sourcePreservation": {
            "bytesUnchanged": preserved,
            "sourceAssetSha256": source_sha,
        },
    }


def _detect_cycles(parent: dict[int, int | None], n: int) -> list[list[int]]:
    cycles: list[list[int]] = []
    for start in range(n):
        seen: list[int] = []
        cur: int | None = start
        while cur is not None:
            if cur in seen:
                cycles.append(seen[seen.index(cur) :] + [cur])
                break
            seen.append(cur)
            cur = parent.get(cur)
    # unique cycle signatures
    uniq = []
    sigs = set()
    for c in cycles:
        sig = tuple(sorted(set(c)))
        if sig not in sigs and len(sig) > 1:
            sigs.add(sig)
            uniq.append(c)
    return uniq
