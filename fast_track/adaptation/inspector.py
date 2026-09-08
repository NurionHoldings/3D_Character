"""ADAPT-01 read-only character intake & inspection."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fast_track.adaptation.classifier import classify_adaptation
from fast_track.adaptation.glb_io import ParseError, load_gltf_document
from fast_track.adaptation.semantic_candidates import detect_semantic_candidates

REPORT_SCHEMA = "NURION_ADAPT01_INSPECTION_REPORT_V1"

VISEME_HINTS = (
    "viseme",
    "mouthopen",
    "mouthsmile",
    "jawopen",
    "aa",
    "oh",
    "ou",
    "ee",
    "ih",
    "sil",
    "ch",
    "dd",
    "ff",
    "kk",
    "nn",
    "pp",
    "rr",
    "ss",
    "th",
    "e",
    "i",
    "o",
    "u",
)

FACIAL_BONE_HINTS = (
    "brow",
    "eyelid",
    "lip",
    "cheek",
    "nose",
    "mouth",
    "face",
    "orbit",
    "lid",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_dumps(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def canonical_sha256(obj: Any) -> str:
    return hashlib.sha256(canonical_dumps(obj).encode("utf-8")).hexdigest()


def inspect_character(
    path: Path | str,
    *,
    character_id: str | None = None,
    read_only_assert: bool = True,
) -> dict[str, Any]:
    """
    IMPORT → INSPECT → CLASSIFY → REPORT.
    Never mutates the source file. Auto-repair DENY.
    """
    path = Path(path)
    before = None
    if path.is_file() and read_only_assert:
        before = path.read_bytes()

    issues: list[dict[str, Any]] = []
    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "characterId": character_id or path.stem,
        "parseStatus": "PENDING",
        "sourceAsset": {
            "path": str(path),
            "exists": path.is_file(),
            "sha256": None,
            "byteLength": None,
            "suffix": path.suffix.lower() if path.suffix else None,
        },
        "issues": issues,
    }

    if not path.is_file():
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "ASSET_MISSING",
                "message": f"file not found: {path}",
            }
        )
        report["parseStatus"] = "FAILED"
        report["adaptationClassification"] = classify_adaptation(report)
        report["reportCanonicalSha256"] = canonical_sha256(_stable_report(report))
        return report

    digest = sha256_file(path)
    report["sourceAsset"]["sha256"] = digest
    report["sourceAsset"]["byteLength"] = path.stat().st_size

    suffix = path.suffix.lower()
    if suffix == ".fbx":
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "FORMAT_RESERVED_NOT_IMPLEMENTED",
                "message": "FBX reserved but not implemented in ADAPT-01; do not fake support",
            }
        )
        report["parseStatus"] = "FAILED"
        report["sourceAsset"]["format"] = "fbx"
        report["sourceAsset"]["supported"] = False
        report["adaptationClassification"] = classify_adaptation(report)
        report["reportCanonicalSha256"] = canonical_sha256(_stable_report(report))
        _assert_unchanged(path, before, read_only_assert)
        return report

    try:
        gltf, _bin, fmt = load_gltf_document(path)
    except ParseError as e:
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "PARSE_FAILURE",
                "message": str(e),
            }
        )
        report["parseStatus"] = "FAILED"
        report["adaptationClassification"] = classify_adaptation(report)
        report["reportCanonicalSha256"] = canonical_sha256(_stable_report(report))
        _assert_unchanged(path, before, read_only_assert)
        return report

    report["parseStatus"] = "OK"
    report["sourceAsset"]["format"] = fmt
    report["sourceAsset"]["supported"] = True

    nodes = list(gltf.get("nodes") or [])
    meshes = list(gltf.get("meshes") or [])
    materials = list(gltf.get("materials") or [])
    textures = list(gltf.get("textures") or [])
    images = list(gltf.get("images") or [])
    skins = list(gltf.get("skins") or [])
    animations = list(gltf.get("animations") or [])
    scenes = list(gltf.get("scenes") or [])
    asset = dict(gltf.get("asset") or {})

    # Scene inventory
    node_inventory = []
    for i, n in enumerate(nodes):
        node_inventory.append(
            {
                "index": i,
                "name": n.get("name"),
                "mesh": n.get("mesh"),
                "skin": n.get("skin"),
                "children": list(n.get("children") or []),
                "hasTranslation": "translation" in n,
                "hasRotation": "rotation" in n,
                "hasScale": "scale" in n,
                "hasMatrix": "matrix" in n,
            }
        )

    cyclic = _detect_cycles(nodes)
    if cyclic:
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "CYCLIC_HIERARCHY",
                "message": f"cyclic node relationships: {cyclic}",
            }
        )

    report["scene"] = {
        "sceneCount": len(scenes),
        "defaultScene": gltf.get("scene"),
        "nodeCount": len(nodes),
        "nodes": node_inventory,
        "assetGenerator": asset.get("generator"),
        "assetVersion": asset.get("version"),
        "cyclicHierarchy": bool(cyclic),
    }

    # Meshes
    morph_total = 0
    morph_names: list[str] = []
    mesh_entries = []
    for mi, mesh in enumerate(meshes):
        prims = mesh.get("primitives") or []
        target_count = 0
        for p in prims:
            targets = p.get("targets") or []
            target_count += len(targets)
        extras = mesh.get("extras") or {}
        names = extras.get("targetNames") or []
        if isinstance(names, list):
            morph_names.extend(str(x) for x in names)
        morph_total += target_count
        mesh_entries.append(
            {
                "index": mi,
                "name": mesh.get("name"),
                "primitiveCount": len(prims),
                "morphTargetCount": target_count,
                "targetNamesDeclared": list(names) if isinstance(names, list) else [],
            }
        )

    report["meshes"] = {
        "count": len(meshes),
        "entries": mesh_entries,
        "status": "DETECTED" if meshes else "NOT_DETECTED",
    }
    if not meshes:
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "NO_USABLE_MESH",
                "message": "no meshes present",
            }
        )

    report["materials"] = {
        "count": len(materials),
        "names": [m.get("name") for m in materials],
        "status": "DETECTED" if materials else "NOT_DETECTED",
    }
    report["textures"] = {
        "textureCount": len(textures),
        "imageCount": len(images),
        "status": "DETECTED" if textures or images else "NOT_DETECTED",
    }

    # Skeleton / skins
    joint_indices: list[int] = []
    skin_entries = []
    invalid_joints = []
    for si, skin in enumerate(skins):
        joints = [j for j in (skin.get("joints") or []) if isinstance(j, int)]
        for j in joints:
            if j < 0 or j >= len(nodes):
                invalid_joints.append({"skin": si, "joint": j})
        joint_indices.extend(joints)
        skin_entries.append(
            {
                "index": si,
                "name": skin.get("name"),
                "jointCount": len(joints),
                "joints": joints,
                "skeletonRoot": skin.get("skeleton"),
            }
        )
    if invalid_joints:
        issues.append(
            {
                "severity": "BLOCKER",
                "code": "INVALID_SKIN_JOINT_REFERENCES",
                "message": f"invalid joint refs: {invalid_joints[:8]}",
            }
        )

    unique_joints = sorted(set(joint_indices))
    report["skeleton"] = {
        "skinsDetected": bool(skins),
        "skinCount": len(skins),
        "skins": skin_entries,
        "jointCount": len(unique_joints),
        "jointIndices": unique_joints,
        "status": "DETECTED" if skins and unique_joints else "NOT_DETECTED",
    }
    report["skinning"] = {
        "status": "DETECTED" if skins else "NOT_DETECTED",
        "skinnedMeshNodes": [
            i for i, n in enumerate(nodes) if isinstance(n.get("skin"), int)
        ],
    }

    # Hierarchy edges for joints
    hierarchy_edges = []
    for i, n in enumerate(nodes):
        for c in n.get("children") or []:
            if isinstance(c, int):
                hierarchy_edges.append(
                    {
                        "parentIndex": i,
                        "parentName": n.get("name"),
                        "childIndex": c,
                        "childName": (nodes[c].get("name") if 0 <= c < len(nodes) else None),
                    }
                )
    report["skeleton"]["hierarchyEdgeCount"] = len(hierarchy_edges)
    report["skeleton"]["hierarchyEdgesSample"] = hierarchy_edges[:64]

    sem = detect_semantic_candidates(nodes, skins)
    report["semanticBoneCandidates"] = sem

    # FACE / expression
    facial_bone_hits = []
    for i, n in enumerate(nodes):
        nm = str(n.get("name") or "").lower()
        if any(h in nm for h in FACIAL_BONE_HINTS):
            # exclude generic "face" root alone with low specificity — still record
            facial_bone_hits.append({"nodeIndex": i, "name": n.get("name")})

    face_bones_status = "DETECTED" if len(facial_bone_hits) >= 2 else (
        "AMBIGUOUS" if facial_bone_hits else "NOT_DETECTED"
    )
    report["faceCapabilities"] = {
        "facialBones": {
            "status": face_bones_status,
            "count": len(facial_bone_hits),
            "samples": facial_bone_hits[:20],
        },
        "blendshapesDetected": morph_total > 0,
    }

    # Eyes / jaw from semantic candidates
    cands = sem.get("candidates") or {}
    report["eyeCapabilities"] = {
        "leftEyeBone": _cap_from_candidate(cands.get("eye_L")),
        "rightEyeBone": _cap_from_candidate(cands.get("eye_R")),
    }
    report["jawCapabilities"] = {
        "bone": _cap_from_candidate(cands.get("jaw")),
    }

    viseme_hits = [n for n in morph_names if _looks_viseme(n)]
    # Also scan target-less morph count as expression capability
    blend_status = "DETECTED" if morph_total > 0 else "NOT_DETECTED"
    report["expressionCapabilities"] = {
        "blendshapes": {"status": blend_status},
        "blendshapeCount": morph_total,
        "targetNames": morph_names[:128],
        "targetNamesTruncated": len(morph_names) > 128,
    }
    talking_status = "DETECTED" if viseme_hits or (
        morph_total >= 10 and any(_looks_viseme(n) for n in morph_names)
    ) else ("AMBIGUOUS" if morph_total >= 5 else "NOT_DETECTED")
    report["talkingCapabilities"] = {
        "visemeCandidates": {
            "status": talking_status,
            "matchedNames": viseme_hits[:32],
        }
    }

    report["animationCapabilities"] = {
        "status": "DETECTED" if animations else "NOT_DETECTED",
        "clipCount": len(animations),
        "clips": [
            {
                "index": i,
                "name": a.get("name"),
                "channelCount": len(a.get("channels") or []),
                "samplerCount": len(a.get("samplers") or []),
            }
            for i, a in enumerate(animations)
        ],
    }

    report["axisAndScale"] = _observe_axis_scale(gltf, nodes, asset)

    # Classification
    report["adaptationClassification"] = classify_adaptation(report)

    report["preservation"] = {
        "mode": "READ_ONLY",
        "autoRepair": "DENY",
        "sourceBytesUnchanged": True,
        "mutationsApplied": [],
    }
    report["nurionV1Boundary"] = {
        "mutation": "NONE",
        "consume": "REFERENCE_ONLY",
        "productPipeline": "CLOSED / PASS / CONSUME ONLY",
    }

    report["reportCanonicalSha256"] = canonical_sha256(_stable_report(report))
    _assert_unchanged(path, before, read_only_assert)
    return report


def _cap_from_candidate(block: dict[str, Any] | None) -> dict[str, Any]:
    if not block:
        return {"status": "NOT_DETECTED"}
    status = block.get("status") or "NOT_DETECTED"
    sel = block.get("selected")
    out: dict[str, Any] = {"status": status}
    if sel:
        out["observedSourceNodeName"] = sel.get("observedSourceNodeName")
        out["nodeIndex"] = sel.get("nodeIndex")
        out["confidence"] = sel.get("confidence")
        out["reason"] = sel.get("reason")
    return out


def _looks_viseme(name: str) -> bool:
    n = re.sub(r"[^a-z0-9]", "", name.lower())
    return any(h in n for h in VISEME_HINTS)


def _detect_cycles(nodes: list[dict[str, Any]]) -> list[int]:
    children = {
        i: [c for c in (n.get("children") or []) if isinstance(c, int)]
        for i, n in enumerate(nodes)
    }
    visiting: set[int] = set()
    visited: set[int] = set()
    cyclic_nodes: list[int] = []

    def dfs(u: int) -> None:
        if u in visited:
            return
        if u in visiting:
            cyclic_nodes.append(u)
            return
        visiting.add(u)
        for v in children.get(u, []):
            if 0 <= v < len(nodes):
                dfs(v)
        visiting.discard(u)
        visited.add(u)

    for i in range(len(nodes)):
        dfs(i)
    return sorted(set(cyclic_nodes))


def _observe_axis_scale(
    gltf: dict[str, Any], nodes: list[dict[str, Any]], asset: dict[str, Any]
) -> dict[str, Any]:
    scales = []
    for n in nodes:
        if "scale" in n and isinstance(n["scale"], list) and len(n["scale"]) == 3:
            scales.append(n["scale"])
    extras = gltf.get("extras") or {}
    return {
        "assetVersion": asset.get("version"),
        "generator": asset.get("generator"),
        "gltfExtrasKeys": sorted(extras.keys()) if isinstance(extras, dict) else [],
        "nodeScaleSamples": scales[:16],
        "upAxis": extras.get("upAxis") or extras.get("UP_AXIS") or "NOT_DECLARED",
        "forwardAxis": extras.get("forwardAxis") or extras.get("FORWARD_AXIS") or "NOT_DECLARED",
        "status": "OBSERVED",
        "note": "Axis inferred only from declared extras; silent invention DENY",
    }


def _stable_report(report: dict[str, Any]) -> dict[str, Any]:
    """Strip volatile absolute path for digest stability across relocation optional — keep sha/identity."""
    clone = json.loads(json.dumps(report))
    # Keep path but digest excludes reportCanonicalSha256 field itself
    clone.pop("reportCanonicalSha256", None)
    return clone


def _assert_unchanged(path: Path, before: bytes | None, enabled: bool) -> None:
    if not enabled or before is None:
        return
    after = path.read_bytes()
    if after != before:
        raise RuntimeError(f"ADAPT-01 preservation violation: source bytes changed: {path}")
