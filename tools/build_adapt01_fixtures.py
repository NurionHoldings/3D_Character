#!/usr/bin/env python3
"""Build deterministic ADAPT-01 fixtures (synthetic GLBs). Does not touch NURION V1."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT01_REPO_ROOT") or os.environ.get("NURION_REPO_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import write_minimal_glb

_OUT_ENV = os.environ.get("NURION_ADAPT01_FIXTURE_DIR")
if _OUT_ENV:
    OUT = Path(_OUT_ENV)
elif Path(__file__).resolve().parents[1].name == "repo":
    OUT = Path(__file__).resolve().parents[2] / "fixtures"
else:
    OUT = ROOT / "fast_track" / "adaptation" / "fixtures"


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def _mesh_with_morphs(names: list[str]) -> dict:
    targets = [{"POSITION": 0} for _ in names]  # accessor index placeholder unused by inspector count
    return {
        "name": "BodyMesh",
        "extras": {"targetNames": names},
        "primitives": [
            {
                "attributes": {"POSITION": 0},
                "targets": targets,
            }
        ],
    }


def _humanoid_nodes(renamed: bool = False) -> list[dict]:
    # indices: 0 Root, 1 Pelvis, 2 Spine, 3 Chest, 4 Neck, 5 Head,
    # 6 ClavL, 7 UArmL, 8 LArmL, 9 HandL,
    # 10 ClavR, 11 UArmR, 12 LArmR, 13 HandR,
    # 14 ThighL, 15 CalfL, 16 FootL,
    # 17 ThighR, 18 CalfR, 19 FootR,
    # 20 EyeL, 21 EyeR, 22 Jaw
    if renamed:
        names = [
            "CharacterRoot",
            "HipBone",
            "Back_01",
            "Thorax",
            "NeckLink",
            "Cranium",
            "L_Collar",
            "L_UpperLimb",
            "L_ForeLimb",
            "L_Palm",
            "R_Collar",
            "R_UpperLimb",
            "R_ForeLimb",
            "R_Palm",
            "L_UpperLeg",
            "L_Shin",
            "L_Ankle",
            "R_UpperLeg",
            "R_Shin",
            "R_Ankle",
            "Oculus_L",
            "Oculus_R",
            "ChinBone",
        ]
    else:
        names = [
            "Root",
            "Hips",
            "Spine",
            "Chest",
            "Neck",
            "Head",
            "LeftShoulder",
            "LeftArm",
            "LeftForeArm",
            "LeftHand",
            "RightShoulder",
            "RightArm",
            "RightForeArm",
            "RightHand",
            "LeftUpLeg",
            "LeftLeg",
            "LeftFoot",
            "RightUpLeg",
            "RightLeg",
            "RightFoot",
            "LeftEye",
            "RightEye",
            "Jaw",
        ]
    children = {
        0: [1],
        1: [2, 14, 17],
        2: [3],
        3: [4, 6, 10],
        4: [5],
        5: [20, 21, 22],
        6: [7],
        7: [8],
        8: [9],
        10: [11],
        11: [12],
        12: [13],
        14: [15],
        15: [16],
        17: [18],
        18: [19],
    }
    nodes = []
    for i, name in enumerate(names):
        n: dict = {"name": name}
        if i in children:
            n["children"] = children[i]
        nodes.append(n)
    return nodes


def build_rigged_with_face() -> bytes:
    nodes = _humanoid_nodes(False)
    nodes[0]["mesh"] = 0
    nodes[0]["skin"] = 0
    morphs = [
        "eyeBlinkLeft",
        "eyeBlinkRight",
        "jawOpen",
        "mouthSmile",
        "viseme_aa",
        "viseme_oh",
        "viseme_ou",
        "viseme_ee",
        "viseme_sil",
        "browInnerUp",
        "mouthFunnel",
        "cheekPuff",
    ] + [f"expr_{i}" for i in range(20)]
    gltf = {
        "asset": {"version": "2.0", "generator": "ADAPT01_FIXTURE"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [_mesh_with_morphs(morphs)],
        "skins": [{"name": "Armature", "joints": list(range(23)), "skeleton": 0}],
        "animations": [
            {
                "name": "Idle",
                "channels": [{"sampler": 0, "target": {"node": 1, "path": "rotation"}}],
                "samplers": [{"input": 0, "output": 1, "interpolation": "LINEAR"}],
            }
        ],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]},
            {"componentType": 5126, "count": 2, "type": "SCALAR"},
            {"componentType": 5126, "count": 2, "type": "VEC4"},
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
        "materials": [{"name": "BodyMat"}],
        "extras": {"upAxis": "Y", "forwardAxis": "Z"},
    }
    return write_minimal_glb(gltf, b"\x00\x00\x00\x00")


def build_body_no_face() -> bytes:
    nodes = _humanoid_nodes(False)[:20]  # drop eyes/jaw
    # fix head children
    nodes[5].pop("children", None)
    nodes[0]["mesh"] = 0
    nodes[0]["skin"] = 0
    gltf = {
        "asset": {"version": "2.0", "generator": "ADAPT01_FIXTURE"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "BodyOnly",
                "primitives": [{"attributes": {"POSITION": 0}}],
            }
        ],
        "skins": [{"name": "Armature", "joints": list(range(20)), "skeleton": 0}],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
        "materials": [{"name": "BodyMat"}],
    }
    return write_minimal_glb(gltf, b"\x00\x00\x00\x00")


def build_renamed_bones() -> bytes:
    nodes = _humanoid_nodes(True)
    nodes[0]["mesh"] = 0
    nodes[0]["skin"] = 0
    gltf = {
        "asset": {"version": "2.0", "generator": "ADAPT01_FIXTURE_RENAMED"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [
            {
                "name": "BodyMesh",
                "primitives": [{"attributes": {"POSITION": 0}}],
            }
        ],
        "skins": [{"name": "Skin", "joints": list(range(23)), "skeleton": 0}],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
    }
    return write_minimal_glb(gltf, b"\x00\x00\x00\x00")


def build_malformed() -> bytes:
    # Bad magic / truncated
    return b"NOTGLTF????\x00\x00"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {
        "positive_rigged_with_face.glb": build_rigged_with_face(),
        "body_compatible_missing_face.glb": build_body_no_face(),
        "renamed_nonstandard_bones.glb": build_renamed_bones(),
        "malformed_not_glb.bin": build_malformed(),
        "unsupported_fake.fbx": b"Kaydara FBX Binary  \x00fake",
    }
    manifest = {"schema": "NURION_ADAPT01_FIXTURE_MANIFEST_V1", "fixtures": {}}
    for name, blob in files.items():
        p = OUT / name
        p.write_bytes(blob)
        manifest["fixtures"][name] = {
            "sha256": _sha(p),
            "byteLength": len(blob),
        }
    # empty / no mesh glb
    empty = write_minimal_glb(
        {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": [0]}],
            "nodes": [{"name": "Empty"}],
        }
    )
    ep = OUT / "no_mesh.glb"
    ep.write_bytes(empty)
    manifest["fixtures"][ep.name] = {"sha256": _sha(ep), "byteLength": len(empty)}

    man_path = OUT / "FIXTURE_MANIFEST.json"
    man_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "manifestSha256": _sha(man_path)}, indent=2))


if __name__ == "__main__":
    main()
