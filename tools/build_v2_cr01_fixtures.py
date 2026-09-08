#!/usr/bin/env python3
"""Build V2-CR-01 synthetic fixtures — topology rules + counter-fixtures (no Idle_15 hardcoding)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import write_minimal_glb

OUT = Path(os.environ.get("NURION_V2_CR01_FIXTURE_DIR", str(ROOT / "fast_track/v2_cr01/fixtures")))


def _node(name: str, children: list[int] | None = None) -> dict:
    n: dict = {"name": name}
    if children:
        n["children"] = children
    return n


def _glb(nodes: list[dict], joints: list[int]) -> bytes:
    # skin requires inverseBindMatrices accessor — use empty stub for structure-only fixtures
    gltf = {
        "asset": {"version": "2.0", "generator": "NURION_V2_CR01_FIXTURE"},
        "scenes": [{"nodes": [0]}],
        "scene": 0,
        "nodes": nodes,
        "skins": [{"joints": joints, "skeleton": joints[0] if joints else 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "accessors": [
            {"componentType": 5126, "count": 1, "type": "VEC3", "max": [0, 0, 0], "min": [0, 0, 0], "bufferView": 0}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 12}],
        "buffers": [{"byteLength": 12}],
    }
    # attach mesh to a leaf for validity if needed — not required for adapter
    return write_minimal_glb(gltf, b"\x00" * 12)


def meshy_style_idle15_topology() -> bytes:
    """Meshy-like: Hips>Spine02>Spine01>Spine>{LShoulder,RShoulder,neck>Head} — NOT a name lookup table."""
    # indices:
    # 0 Armature
    # 1 Hips
    # 2 LeftUpLeg 3 LeftLeg 4 LeftFoot
    # 5 RightUpLeg 6 RightLeg 7 RightFoot
    # 8 Spine02 9 Spine01 10 Spine
    # 11 LeftShoulder 12 LeftArm 13 LeftForeArm 14 LeftHand
    # 15 RightShoulder 16 RightArm 17 RightForeArm 18 RightHand
    # 19 neck 20 Head
    nodes = [
        _node("Armature", [1]),
        _node("Hips", [2, 5, 8]),
        _node("LeftUpLeg", [3]),
        _node("LeftLeg", [4]),
        _node("LeftFoot"),
        _node("RightUpLeg", [6]),
        _node("RightLeg", [7]),
        _node("RightFoot"),
        _node("Spine02", [9]),
        _node("Spine01", [10]),
        _node("Spine", [11, 15, 19]),
        _node("LeftShoulder", [12]),
        _node("LeftArm", [13]),
        _node("LeftForeArm", [14]),
        _node("LeftHand"),
        _node("RightShoulder", [16]),
        _node("RightArm", [17]),
        _node("RightForeArm", [18]),
        _node("RightHand"),
        _node("neck", [20]),
        _node("Head"),
    ]
    joints = list(range(1, 21))
    return _glb(nodes, joints)


def counter_spine_name_without_shoulders() -> bytes:
    """Bone named 'Spine' exists but shoulders attach elsewhere — must NOT become chest."""
    # 0 Armature 1 Hips 2 ChestReal (shoulders) 3 FakeSpine (named Spine, no shoulders)
    # 4 LeftShoulder 5 RightShoulder 6 neck 7 Head
    # 8 LeftUpLeg 9 RightUpLeg
    nodes = [
        _node("Armature", [1]),
        _node("Hips", [2, 3, 8, 9]),
        _node("TorsoAttach", [4, 5, 6]),  # real chest by topology
        _node("Spine"),  # misleading name — sibling, no shoulders
        _node("LeftShoulder"),
        _node("RightShoulder"),
        _node("neck", [7]),
        _node("Head"),
        _node("LeftUpLeg"),
        _node("RightUpLeg"),
    ]
    joints = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    return _glb(nodes, joints)


def counter_ambiguous_shoulder_side() -> bytes:
    """Two shoulders without L/R side tokens — must BLOCK SHOULDER_SIDE_AMBIGUOUS (no guessing)."""
    nodes = [
        _node("Armature", [1]),
        _node("Hips", [2, 3, 8]),
        _node("LeftUpLeg"),
        _node("RightUpLeg"),
        _node("Torso", [4, 5, 6]),
        _node("ShoulderA"),
        _node("ShoulderB"),
        _node("neck", [7]),
        _node("Head"),
    ]
    joints = list(range(1, 9))
    return _glb(nodes, joints)


def counter_multiple_pelvis() -> bytes:
    """Two pelvis-class nodes with bilateral legs — must BLOCK MULTIPLE_PELVIS_CANDIDATES."""
    nodes = [
        _node("Armature", [1]),
        _node("Hips", [2, 3, 4]),
        _node("LeftUpLeg"),
        _node("RightUpLeg"),
        _node("Pelvis", [5, 6]),
        _node("LeftUpLeg2"),
        _node("RightUpLeg2"),
        _node("Torso", [7, 8, 9]),
        _node("LeftShoulder"),
        _node("RightShoulder"),
        _node("neck", [10]),
        _node("Head"),
    ]
    joints = list(range(1, 12))
    return _glb(nodes, joints)


def counter_multiple_head() -> bytes:
    """Multiple Head bones with no unique torso/pelvis descendant — must BLOCK MULTIPLE_HEAD_CANDIDATES."""
    nodes = [
        _node("Armature", [1, 7, 8]),
        _node("Hips", [2, 3, 4]),
        _node("LeftUpLeg"),
        _node("RightUpLeg"),
        _node("Torso", [5, 6]),
        _node("LeftShoulder"),
        _node("RightShoulder"),
        _node("Head"),
        _node("Head"),
    ]
    joints = list(range(1, 9))
    return _glb(nodes, joints)


def exact_nurion_like() -> bytes:
    nodes = [
        _node("Armature", [1]),
        _node("Hips", [2, 10, 14]),
        _node("Spine01", [3]),
        _node("Chest", [4, 7, 18]),
        _node("LeftShoulder", [5]),
        _node("LeftArm", [6]),
        _node("LeftForeArm", []),
        _node("RightShoulder", [8]),
        _node("RightArm", [9]),
        _node("RightForeArm", []),
        _node("LeftUpLeg", [11]),
        _node("LeftLeg", [12]),
        _node("LeftFoot", [13]),
        _node("LeftToeBase"),
        _node("RightUpLeg", [15]),
        _node("RightLeg", [16]),
        _node("RightFoot", [17]),
        _node("RightToeBase"),
        _node("neck", [19]),
        _node("Head"),
    ]
    # fix children with hands
    nodes[6] = _node("LeftForeArm", [20])
    nodes[9] = _node("RightForeArm", [21])
    nodes.append(_node("LeftHand"))
    nodes.append(_node("RightHand"))
    joints = list(range(1, len(nodes)))
    return _glb(nodes, joints)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    required = [
        "meshy_style_topology.glb",
        "counter_spine_name_no_shoulders.glb",
        "exact_named_chest.glb",
        "counter_ambiguous_shoulder_side.glb",
        "counter_multiple_pelvis.glb",
        "counter_multiple_head.glb",
    ]
    if all((OUT / name).is_file() for name in required):
        # Rebuild when fixture builders change — force with NURION_V2_CR01_FORCE_FIXTURES=1
        if os.environ.get("NURION_V2_CR01_FORCE_FIXTURES") != "1":
            manifest = {"schema": "NURION_V2_CR01_FIXTURE_MANIFEST_V1", "fixtures": {}, "source": "PREPACKAGED"}
            for name in required:
                manifest["fixtures"][name] = {"bytes": (OUT / name).stat().st_size}
            (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"ok": True, "out": str(OUT), "count": len(required), "prepackaged": True}, indent=2))
            return

    fixtures = {
        "meshy_style_topology.glb": meshy_style_idle15_topology(),
        "counter_spine_name_no_shoulders.glb": counter_spine_name_without_shoulders(),
        "exact_named_chest.glb": exact_nurion_like(),
        "counter_ambiguous_shoulder_side.glb": counter_ambiguous_shoulder_side(),
        "counter_multiple_pelvis.glb": counter_multiple_pelvis(),
        "counter_multiple_head.glb": counter_multiple_head(),
    }
    manifest = {"schema": "NURION_V2_CR01_FIXTURE_MANIFEST_V1", "fixtures": {}}
    for name, data in fixtures.items():
        p = OUT / name
        p.write_bytes(data)
        manifest["fixtures"][name] = {"bytes": len(data), "role": name}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(fixtures)}, indent=2))


if __name__ == "__main__":
    main()
