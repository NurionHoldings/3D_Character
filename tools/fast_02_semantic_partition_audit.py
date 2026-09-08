#!/usr/bin/env python3
"""FAST-02 read-only Semantic Mesh Partition & Head-Neck Interface Audit."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any

import numpy as np

COMPONENT_TYPE = {
    5120: ("b", 1, np.int8),
    5121: ("B", 1, np.uint8),
    5122: ("h", 2, np.int16),
    5123: ("H", 2, np.uint16),
    5125: ("I", 4, np.uint32),
    5126: ("f", 4, np.float32),
}

TYPE_COMPONENTS = {
    "SCALAR": 1,
    "VEC2": 2,
    "VEC3": 3,
    "VEC4": 4,
    "MAT2": 4,
    "MAT3": 9,
    "MAT4": 16,
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_glb(path: Path) -> tuple[dict[str, Any], bytes]:
    data = path.read_bytes()
    if data[:4] != b"glTF":
        raise ValueError(f"Not a GLB file: {path}")
    version, total_len = struct.unpack_from("<II", data, 4)
    if version != 2:
        raise ValueError(f"Unsupported glTF version: {version}")
    offset = 12
    gltf: dict[str, Any] | None = None
    bin_blob = b""
    while offset + 8 <= len(data):
        chunk_len, chunk_type = struct.unpack_from("<I4s", data, offset)
        offset += 8
        chunk = data[offset : offset + chunk_len]
        offset += chunk_len
        if chunk_type == b"JSON":
            gltf = json.loads(chunk.decode("utf-8"))
        elif chunk_type == b"BIN\x00":
            bin_blob = chunk
    if gltf is None:
        raise ValueError("GLB missing JSON chunk")
    return gltf, bin_blob


def read_accessor(gltf: dict[str, Any], bin_blob: bytes, accessor_index: int) -> np.ndarray:
    accessor = gltf["accessors"][accessor_index]
    bv = gltf["bufferViews"][accessor["bufferView"]]
    ctype = accessor["componentType"]
    _, comp_size, np_dtype = COMPONENT_TYPE[ctype]
    ncomp = TYPE_COMPONENTS[accessor["type"]]
    count = accessor["count"]
    start = bv.get("byteOffset", 0) + accessor.get("byteOffset", 0)
    stride = bv.get("byteStride", comp_size * ncomp)
    if stride == comp_size * ncomp:
        end = start + count * comp_size * ncomp
        raw = bin_blob[start:end]
        arr = np.frombuffer(raw, dtype=np_dtype)
        return arr.reshape(count, ncomp) if ncomp > 1 else arr
    out = np.empty((count, ncomp), dtype=np.float64)
    for i in range(count):
        row_start = start + i * stride
        raw = bin_blob[row_start : row_start + comp_size * ncomp]
        out[i] = np.frombuffer(raw, dtype=np_dtype).reshape(ncomp)
    return out


def node_world_matrix(gltf: dict[str, Any], node_index: int, cache: dict[int, np.ndarray]) -> np.ndarray:
    if node_index in cache:
        return cache[node_index]
    node = gltf["nodes"][node_index]
    if "matrix" in node:
        local = np.array(node["matrix"], dtype=np.float64).reshape(4, 4).T
    else:
        local = np.eye(4, dtype=np.float64)
        t = node.get("translation", [0, 0, 0])
        r = node.get("rotation", [0, 0, 0, 1])
        s = node.get("scale", [1, 1, 1])
        tx, ty, tz = t
        qx, qy, qz, qw = r
        sx, sy, sz = s
        xx, yy, zz = qx * qx, qy * qy, qz * qz
        xy, xz, yz = qx * qy, qx * qz, qy * qz
        wx, wy, wz = qw * qx, qw * qy, qw * qz
        rot = np.array(
            [
                [1 - 2 * (yy + zz), 2 * (xy - wz), 2 * (xz + wy), 0],
                [2 * (xy + wz), 1 - 2 * (xx + zz), 2 * (yz - wx), 0],
                [2 * (xz - wy), 2 * (yz + wx), 1 - 2 * (xx + yy), 0],
                [0, 0, 0, 1],
            ],
            dtype=np.float64,
        )
        scale = np.diag([sx, sy, sz, 1.0])
        local = rot @ scale
        local[0:3, 3] = [tx, ty, tz]
    parent_indices = [
        i for i, n in enumerate(gltf["nodes"]) if node_index in n.get("children", [])
    ]
    if parent_indices:
        parent = node_world_matrix(gltf, parent_indices[0], cache)
        world = parent @ local
    else:
        world = local
    cache[node_index] = world
    return world


def joint_name_matches(name: str, tokens: tuple[str, ...]) -> bool:
    lower = name.lower()
    return any(tok in lower for tok in tokens)


def classify_bone_role(name: str) -> str:
    lower = name.lower()
    if any(x in lower for x in ("jaw", "mandible")):
        return "jaw"
    if any(x in lower for x in ("eye", "eyeball", "pupil")) and "lid" not in lower and "brow" not in lower:
        return "eye"
    if any(x in lower for x in ("lid", "eyelid")):
        return "eyelid"
    if any(x in lower for x in ("head", "skull")) and "end" not in lower and "front" not in lower:
        return "head"
    if "neck" in lower:
        return "neck"
    if any(x in lower for x in ("face", "mouth", "lip", "tongue", "cheek", "brow")):
        return "facial"
    return "body"


def dominant_region(weights: np.ndarray, joint_indices: np.ndarray, joint_roles: dict[int, str]) -> str:
    if weights.size == 0:
        return "unweighted"
    order = np.argsort(-weights)
    for idx in order:
        if weights[idx] <= 0:
            break
        role = joint_roles.get(int(joint_indices[idx]), "body")
        if role in ("head", "facial"):
            return "head"
        if role == "neck":
            return "neck"
    top_role = joint_roles.get(int(joint_indices[order[0]]), "body")
    if top_role == "neck":
        return "neck"
    if top_role in ("head", "facial"):
        return "head"
    return "body"


def audit_glb(glb_path: Path) -> dict[str, Any]:
    gltf, bin_blob = load_glb(glb_path)
    scenes = gltf.get("scenes", [])
    nodes = gltf.get("nodes", [])
    meshes = gltf.get("meshes", [])
    skins = gltf.get("skins", [])
    materials = gltf.get("materials", [])
    textures = gltf.get("textures", [])
    images = gltf.get("images", [])
    animations = gltf.get("animations", [])

    scene_graph: list[dict[str, Any]] = []
    for si, scene in enumerate(scenes):
        for root in scene.get("nodes", []):
            scene_graph.extend(walk_nodes(gltf, root, parent=None, path=[f"scene[{si}]"]))

    morph_summary = {"meshCountWithMorphTargets": 0, "totalMorphTargets": 0, "names": []}
    for mesh_idx, mesh in enumerate(meshes):
        morphs = mesh.get("primitives", [{}])[0].get("targets", [])
        if morphs:
            morph_summary["meshCountWithMorphTargets"] += 1
            morph_summary["totalMorphTargets"] += len(morphs)
            morph_summary["names"].append({"meshIndex": mesh_idx, "meshName": mesh.get("name"), "targetCount": len(morphs)})

    skin_reports: list[dict[str, Any]] = []
    joint_hierarchy: list[dict[str, Any]] = []
    bone_capability = {
        "headBones": [],
        "neckBones": [],
        "jawBones": [],
        "eyeBones": [],
        "eyelidBones": [],
        "facialBones": [],
        "totalJoints": 0,
    }
    roles_by_skin_joint: dict[int, str] = {}
    head_neck_interface = {
        "seamVertexCount": 0,
        "neckDominantVertexCount": 0,
        "headDominantVertexCount": 0,
        "mixedHeadNeckVertexCount": 0,
        "headBoneIndex": None,
        "neckBoneIndex": None,
        "seamYSpreadInHeadSpace": None,
    }

    for skin_idx, skin in enumerate(skins):
        joint_node_indices = skin.get("joints", [])
        joint_names = [nodes[j].get("name", f"joint_{j}") for j in joint_node_indices]
        bone_capability["totalJoints"] = max(bone_capability["totalJoints"], len(joint_names))
        for ji, jn in enumerate(joint_names):
            role = classify_bone_role(jn)
            roles_by_skin_joint[ji] = role
            entry = {"skinIndex": skin_idx, "jointIndex": ji, "nodeIndex": joint_node_indices[ji], "name": jn, "role": role}
            joint_hierarchy.append(entry)
            if role == "head":
                bone_capability["headBones"].append(jn)
                if head_neck_interface["headBoneIndex"] is None:
                    head_neck_interface["headBoneIndex"] = ji
            elif role == "neck":
                bone_capability["neckBones"].append(jn)
                if head_neck_interface["neckBoneIndex"] is None:
                    head_neck_interface["neckBoneIndex"] = ji
            elif role == "jaw":
                bone_capability["jawBones"].append(jn)
            elif role == "eye":
                bone_capability["eyeBones"].append(jn)
            elif role == "eyelid":
                bone_capability["eyelidBones"].append(jn)
            elif role == "facial":
                bone_capability["facialBones"].append(jn)

        skin_reports.append(
            {
                "skinIndex": skin_idx,
                "name": skin.get("name"),
                "jointCount": len(joint_node_indices),
                "jointNames": joint_names,
                "skeletonRoot": skin.get("skeleton"),
            }
        )

        if "inverseBindMatrices" in skin and joint_node_indices:
            ibm = read_accessor(gltf, bin_blob, skin["inverseBindMatrices"]).reshape(-1, 4, 4)
            head_ji = head_neck_interface["headBoneIndex"]
            neck_ji = head_neck_interface["neckBoneIndex"]
            if head_ji is not None and neck_ji is not None:
                head_world = np.linalg.inv(ibm[head_ji])
                head_space_y: list[float] = []
                mixed = 0
                neck_dom = 0
                head_dom = 0
                seam = 0
                for mesh in meshes:
                    for prim in mesh.get("primitives", []):
                        attrs = prim.get("attributes", {})
                        if "POSITION" not in attrs or "JOINTS_0" not in attrs or "WEIGHTS_0" not in attrs:
                            continue
                        pos = read_accessor(gltf, bin_blob, attrs["POSITION"]).astype(np.float64)
                        joints = read_accessor(gltf, bin_blob, attrs["JOINTS_0"]).astype(np.int32)
                        weights_raw = read_accessor(gltf, bin_blob, attrs["WEIGHTS_0"]).astype(np.float64)
                        row_sum = weights_raw.sum(axis=1, keepdims=True)
                        row_sum[row_sum == 0] = 1.0
                        weights = weights_raw / row_sum
                        for vi in range(pos.shape[0]):
                            w = weights[vi]
                            j = joints[vi]
                            head_w = float(w[j == head_ji].sum()) if np.any(j == head_ji) else 0.0
                            neck_w = float(w[j == neck_ji].sum()) if np.any(j == neck_ji) else 0.0
                            role = dominant_region(w, j, roles_by_skin_joint)
                            if role == "neck":
                                neck_dom += 1
                            elif role == "head":
                                head_dom += 1
                            if head_w > 0.15 and neck_w > 0.15:
                                mixed += 1
                            if head_w > 0.05 and neck_w > 0.05:
                                seam += 1
                                p4 = np.array([pos[vi, 0], pos[vi, 1], pos[vi, 2], 1.0])
                                hs = head_world @ p4
                                head_space_y.append(float(hs[1]))
                head_neck_interface.update(
                    {
                        "seamVertexCount": seam,
                        "neckDominantVertexCount": neck_dom,
                        "headDominantVertexCount": head_dom,
                        "mixedHeadNeckVertexCount": mixed,
                        "seamYSpreadInHeadSpace": {
                            "min": min(head_space_y) if head_space_y else None,
                            "max": max(head_space_y) if head_space_y else None,
                            "span": (max(head_space_y) - min(head_space_y)) if len(head_space_y) > 1 else 0.0,
                        },
                    }
                )

    mesh_reports: list[dict[str, Any]] = []
    all_partition_counts = {"head": 0, "neck": 0, "body": 0, "unweighted": 0}

    for mesh_idx, mesh in enumerate(meshes):
        for prim_idx, prim in enumerate(mesh.get("primitives", [])):
            attrs = prim.get("attributes", {})
            pos = read_accessor(gltf, bin_blob, attrs["POSITION"]) if "POSITION" in attrs else None
            joints = read_accessor(gltf, bin_blob, attrs["JOINTS_0"]).astype(np.int32) if "JOINTS_0" in attrs else None
            weights_raw = read_accessor(gltf, bin_blob, attrs["WEIGHTS_0"]) if "WEIGHTS_0" in attrs else None
            uv = read_accessor(gltf, bin_blob, attrs["TEXCOORD_0"]) if "TEXCOORD_0" in attrs else None
            n_verts = int(pos.shape[0]) if pos is not None else 0
            tri_count = 0
            if "indices" in prim:
                idx = read_accessor(gltf, bin_blob, prim["indices"]).astype(np.int64)
                tri_count = int(len(idx) // 3)

            partition = {"head": 0, "neck": 0, "body": 0, "unweighted": 0}
            if joints is not None and weights_raw is not None:
                weights = weights_raw.astype(np.float64)
                row_sum = weights.sum(axis=1, keepdims=True)
                row_sum[row_sum == 0] = 1.0
                weights = weights / row_sum
                for vi in range(n_verts):
                    region = dominant_region(weights[vi], joints[vi], roles_by_skin_joint)
                    partition[region] += 1
                for k in partition:
                    all_partition_counts[k] += partition[k]

            mesh_reports.append(
                {
                    "meshIndex": mesh_idx,
                    "meshName": mesh.get("name"),
                    "primitiveIndex": prim_idx,
                    "vertexCount": n_verts,
                    "triangleCount": tri_count,
                    "hasNormals": "NORMAL" in attrs,
                    "hasUV": uv is not None,
                    "materialIndex": prim.get("material"),
                    "mode": prim.get("mode", 4),
                    "skinBindingPresent": joints is not None and weights_raw is not None,
                    "semanticPartitionVertexCounts": partition,
                }
            )

    material_reports: list[dict[str, Any]] = []
    embedded_textures: list[dict[str, Any]] = []
    for mi, mat in enumerate(materials):
        pbr = mat.get("pbrMetallicRoughness", {})
        base_tex = pbr.get("baseColorTexture")
        mat_entry = {
            "materialIndex": mi,
            "name": mat.get("name"),
            "baseColorTextureIndex": base_tex.get("index") if base_tex else None,
            "baseColorFactor": pbr.get("baseColorFactor"),
            "metallicFactor": pbr.get("metallicFactor"),
            "roughnessFactor": pbr.get("roughnessFactor"),
            "emissiveTextureIndex": (mat.get("emissiveTexture") or {}).get("index"),
            "normalTextureIndex": (mat.get("normalTexture") or {}).get("index"),
            "occlusionTextureIndex": (mat.get("occlusionTexture") or {}).get("index"),
        }
        material_reports.append(mat_entry)

    for ii, img in enumerate(images):
        embedded_textures.append(
            {
                "imageIndex": ii,
                "name": img.get("name"),
                "mimeType": img.get("mimeType"),
                "bufferViewIndex": img.get("bufferView"),
                "uri": img.get("uri"),
                "embedded": img.get("bufferView") is not None,
            }
        )

    animation_reports = [
        {
            "animationIndex": ai,
            "name": anim.get("name"),
            "channelCount": len(anim.get("channels", [])),
            "samplerCount": len(anim.get("samplers", [])),
        }
        for ai, anim in enumerate(animations)
    ]

    facial_capability = {
        "morphTargetsPresent": morph_summary["totalMorphTargets"] > 0,
        "morphTargetCount": morph_summary["totalMorphTargets"],
        "jawBonePresent": len(bone_capability["jawBones"]) > 0,
        "eyeBonePresent": len(bone_capability["eyeBones"]) > 0,
        "eyelidBonePresent": len(bone_capability["eyelidBones"]) > 0,
        "facialBonePresent": len(bone_capability["facialBones"]) > 0,
        "talkingCapableAsIs": False,
        "blinkCapableAsIs": False,
        "eyeContactCapableAsIs": False,
        "lipSyncCapableAsIs": False,
    }

    # Path classification logic — A preferred over B over C
    single_mesh = len(meshes) == 1
    object_separated = len(meshes) > 1 or any(
        n.get("mesh") is not None for n in nodes if n.get("mesh") is not None
    )
    head_share = all_partition_counts["head"] / max(sum(all_partition_counts.values()), 1)
    neck_share = all_partition_counts["neck"] / max(sum(all_partition_counts.values()), 1)
    seam_ratio = head_neck_interface["seamVertexCount"] / max(all_partition_counts["head"] + all_partition_counts["neck"], 1)

    path_scores = {
        "A_FACE_SURFACE_IDENTITY_ADAPT": 0,
        "B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK": 0,
        "C_HEAD_REPLACEMENT_REQUIRED": 0,
    }
    path_rationale: list[str] = []

    if bone_capability["headBones"] and bone_capability["neckBones"]:
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] += 2
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 2
        path_rationale.append("Head and neck bones present in base biped rig.")
    if all_partition_counts["head"] > 0 and all_partition_counts["neck"] > 0:
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] += 2
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 1
        path_rationale.append("Semantic vertex partition identifies distinct head and neck weight regions.")
    if not morph_summary["totalMorphTargets"]:
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] -= 1
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] -= 0
        path_rationale.append("No morph targets — viseme/expression must be ADDed regardless of path.")
    if not bone_capability["jawBones"]:
        path_rationale.append("No jaw bone — talking requires ADD jaw rig/proxy.")
    if single_mesh and not object_separated:
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 1
        path_scores["C_HEAD_REPLACEMENT_REQUIRED"] += 1
        path_rationale.append("Single unified mesh (char1) — head/face not object-separated; geometry edit or replacement required for identity shape.")
    if seam_ratio > 0.05:
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] += 1
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] += 2
        path_rationale.append(f"Head-neck seam band detected ({head_neck_interface['seamVertexCount']} vertices) — favors preserving neck interface (B).")
    else:
        path_rationale.append("Limited explicit head-neck weight overlap — surface projection may still be viable (A).")

    # A viable if head region identifiable + rig kept + identity mappable to face surface without full head topo swap
    if head_share >= 0.02 and not morph_summary["totalMorphTargets"]:
        # without morphs, A still possible via texture/normal projection + minimal ADD bones — prefer A if seam clean
        path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] += 1

    ordered = sorted(path_scores.items(), key=lambda kv: (-kv[1], kv[0]))
    recommended_path = ordered[0][0]
    if recommended_path.startswith("A"):
        path_label = "A — FACE_SURFACE_IDENTITY_ADAPT"
    elif recommended_path.startswith("B"):
        path_label = "B — HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"
    else:
        path_label = "C — HEAD_REPLACEMENT_REQUIRED"

    # Tie-break toward A then B per constitution
    if path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] == path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"]:
        path_label = "A — FACE_SURFACE_IDENTITY_ADAPT"
        recommended_path = "A_FACE_SURFACE_IDENTITY_ADAPT"
    elif (
        path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"] >= path_scores["C_HEAD_REPLACEMENT_REQUIRED"]
        and path_scores["A_FACE_SURFACE_IDENTITY_ADAPT"] < path_scores["B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"]
    ):
        path_label = "B — HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"
        recommended_path = "B_HEAD_IDENTITY_ADAPT_WITH_EXISTING_NECK"

    keep_adapt_add_replace = {
        "KEEP": [
            "24-joint biped skeleton (Hips→…→neck→Head)",
            "Body/clothes/hair silhouette mesh regions (body-weighted vertices)",
            "Existing body skin weights and animations (7 GLB clips)",
            "Embedded single material + UV + PNG texture",
            "Presentation motions: Idle/Wave/Bow/Walk/Run",
        ],
        "ADAPT": [
            "Head-neck interface seam (circumference/orientation/scale alignment)",
            "Face surface region within head-weighted vertices for NURION identity mapping",
            "UV layout in face island (if identity uses texture projection first)",
        ],
        "ADD": [
            "Jaw bone or jaw proxy + minimal mouth viseme shapes",
            "Eye L/R bones or eye aim rig",
            "Eyelid L/R or blink blendshapes",
            "Minimal facial shape keys for talking/blink (none present in source)",
            "Semantic mesh partition metadata (HEAD/NECK/BODY) before any cut",
        ],
        "REPLACE": [
            "Only if A/B fail validation: head geometry block (not body/hair/clothes)",
            "Not selected in FAST-02 — deferred to FAST-03+ unless partition proves A/B infeasible",
        ],
    }

    if recommended_path == "C_HEAD_REPLACEMENT_REQUIRED":
        keep_adapt_add_replace["REPLACE"] = [
            "Head geometry region (topology swap) while preserving neck seam + body skinning",
            "Deferred from A/B due to single-mesh topology/rig constraints",
        ]

    shortest_path = [
        "FAST-02 partition evidence (this receipt) — read-only, mutation=0",
        "FAST-03 Semantic region separation (HEAD_SKIN vs HAIR vs BODY) on mirror working copy",
        f"FAST-03 Identity apply via {path_label.split('—')[0].strip()} path",
        "FAST-03 ADD jaw/eyes/eyelids + minimal mouth shapes",
        "FAST-04 Lip sync + blink + eye contact wiring",
        "FAST-05 Presentation state machine (FULL/UPPER, menu-driven)",
        "FAST-06 Integration → WORKING PRESENTATION CHARACTER v0",
    ]

    return {
        "auditId": "FAST-02",
        "auditType": "SEMANTIC_MESH_PARTITION_HEAD_NECK_INTERFACE",
        "mode": "MIRROR_MODE_2_READ_ONLY",
        "mutationPolicy": {"glb": 0, "mesh": 0, "skeleton": 0, "material": 0, "animation": 0},
        "canonicalGlb": str(glb_path),
        "sceneNodeGraph": scene_graph,
        "meshPrimitives": mesh_reports,
        "skins": skin_reports,
        "jointHierarchy": joint_hierarchy,
        "semanticPartition": {
            "method": "dominant_skin_weight_role",
            "vertexCounts": all_partition_counts,
            "headVertexShare": round(head_share, 4),
            "neckVertexShare": round(neck_share, 4),
        },
        "headNeckInterface": head_neck_interface,
        "materials": material_reports,
        "embeddedTextures": embedded_textures,
        "morphTargets": morph_summary,
        "animations": animation_reports,
        "facialJawEyeEyelidCapability": facial_capability,
        "pathClassification": {
            "priorityOrder": ["A", "B", "C"],
            "scores": path_scores,
            "recommendedPath": recommended_path,
            "recommendedPathLabel": path_label,
            "rationale": path_rationale,
        },
        "keepAdaptAddReplaceMatrix": keep_adapt_add_replace,
        "shortestUserIdentityToTalkingCharacterPath": shortest_path,
        "objectSeparation": {
            "meshCount": len(meshes),
            "singleUnifiedMesh": single_mesh,
            "bodyHeadHairClothesObjectSeparated": not single_mesh,
        },
    }


def walk_nodes(
    gltf: dict[str, Any], node_index: int, parent: int | None, path: list[str]
) -> list[dict[str, Any]]:
    node = gltf["nodes"][node_index]
    name = node.get("name", f"node_{node_index}")
    entry = {
        "nodeIndex": node_index,
        "name": name,
        "path": "/".join(path + [name]),
        "parentNodeIndex": parent,
        "meshIndex": node.get("mesh"),
        "skinIndex": node.get("skin"),
        "childNodeIndices": node.get("children", []),
    }
    out = [entry]
    for child in node.get("children", []):
        out.extend(walk_nodes(gltf, child, node_index, path + [name]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="FAST-02 semantic partition read-only audit")
    parser.add_argument("--glb", type=Path, required=True)
    parser.add_argument("--source-zip", type=Path, required=True)
    parser.add_argument("--mirror-zip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    source_hash = sha256_file(args.source_zip)
    mirror_hash = sha256_file(args.mirror_zip)
    glb_hash = sha256_file(args.glb)

    if source_hash != mirror_hash:
        print("ERROR: mirror zip SHA-256 mismatch", file=sys.stderr)
        return 2

    audit = audit_glb(args.glb)
    receipt = {
        "receiptId": f"FAST-02_semantic_partition_audit_{ts}",
        "timestampUtc": ts,
        "lane": "FAST_PRODUCT",
        "stage": "FAST-02",
        "verdict": "AUDIT_COMPLETE_READ_ONLY",
        "contract": {
            "sourceZipReadOnly": True,
            "mirrorOnlyExtract": True,
            "formalBaselineTouch": False,
            "arkaonInsuranceClassification": "FAST_INTAKE_SOURCE_REFERENCE_ONLY",
        },
        "integrity": {
            "sourceZipSha256": source_hash,
            "mirrorZipSha256": mirror_hash,
            "mirrorMatchesSource": True,
            "canonicalGlbSha256": glb_hash,
            "canonicalGlbPath": str(args.glb),
        },
        "audit": audit,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "receipt": str(args.out),
                "recommendedPath": audit["pathClassification"]["recommendedPathLabel"].replace("\u2014", "-"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
