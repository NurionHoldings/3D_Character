#!/usr/bin/env python3
"""Build ADAPT-02 fixtures (GLBs + force-flag scenarios). Does not touch NURION V1 / ADAPT-01 SoT."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT02_REPO_ROOT") or os.environ.get("NURION_REPO_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import write_minimal_glb

_OUT = os.environ.get("NURION_ADAPT02_FIXTURE_DIR")
if _OUT:
    OUT = Path(_OUT)
elif Path(__file__).resolve().parents[1].name == "repo":
    OUT = Path(__file__).resolve().parents[2] / "fixtures"
else:
    OUT = ROOT / "fast_track" / "adaptation" / "fixtures_adapt02"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _nodes_standard(prefix: str = "", intermediary: bool = False) -> list[dict]:
    # Mixamo-style uses prefix "mixamorig:"
    def n(name: str) -> str:
        return f"{prefix}{name}" if prefix else name

    names = [
        n("Root"),
        n("Hips"),
        n("Spine"),
        n("Spine1") if intermediary else n("Chest"),
        n("Neck"),
        n("Head"),
        n("LeftShoulder"),
        n("LeftArm"),
        n("LeftForeArm"),
        n("LeftHand"),
        n("RightShoulder"),
        n("RightArm"),
        n("RightForeArm"),
        n("RightHand"),
        n("LeftUpLeg"),
        n("LeftLeg"),
        n("LeftFoot"),
        n("RightUpLeg"),
        n("RightLeg"),
        n("RightFoot"),
    ]
    if intermediary:
        # insert Chest after Spine1
        names = [
            n("Root"),
            n("Hips"),
            n("Spine"),
            n("SpineMid"),  # intermediary helper
            n("Chest"),
            n("Neck"),
            n("Head"),
            n("LeftShoulder"),
            n("LeftArm"),
            n("LeftForeArm"),
            n("LeftHand"),
            n("RightShoulder"),
            n("RightArm"),
            n("RightForeArm"),
            n("RightHand"),
            n("LeftUpLeg"),
            n("LeftLeg"),
            n("LeftFoot"),
            n("RightUpLeg"),
            n("RightLeg"),
            n("RightFoot"),
        ]
        children = {
            0: [1],
            1: [2, 15, 18],
            2: [3],
            3: [4],
            4: [5, 7, 11],
            5: [6],
            7: [8],
            8: [9],
            9: [10],
            11: [12],
            12: [13],
            13: [14],
            15: [16],
            16: [17],
            18: [19],
            19: [20],
        }
    else:
        children = {
            0: [1],
            1: [2, 14, 17],
            2: [3],
            3: [4, 6, 10],
            4: [5],
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
        node: dict = {"name": name}
        if i in children:
            node["children"] = children[i]
        nodes.append(node)
    return nodes


def _pack(nodes: list[dict], *, extras: dict | None = None, joint_count: int | None = None) -> bytes:
    nodes = [dict(n) for n in nodes]
    nodes[0]["mesh"] = 0
    nodes[0]["skin"] = 0
    jc = joint_count if joint_count is not None else len(nodes)
    gltf = {
        "asset": {"version": "2.0", "generator": "ADAPT02_FIXTURE"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [{"name": "Body", "primitives": [{"attributes": {"POSITION": 0}}]}],
        "skins": [{"name": "Armature", "joints": list(range(jc)), "skeleton": 0}],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
        "extras": extras or {"upAxis": "Y", "forwardAxis": "Z"},
    }
    return write_minimal_glb(gltf, b"\x00\x00\x00\x00")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files: dict[str, bytes] = {
        "canonical_humanoid.glb": _pack(_nodes_standard()),
        "mixamo_style.glb": _pack(_nodes_standard(prefix="mixamorig:")),
        "intermediary_helpers.glb": _pack(_nodes_standard(intermediary=True)),
        "axis_z_up_adapter.glb": _pack(_nodes_standard(), extras={"upAxis": "Z", "forwardAxis": "-Y"}),
    }
    # Reuse ADAPT-01 renamed builder via import
    from tools.build_adapt01_fixtures import build_renamed_bones, build_body_no_face, build_malformed

    files["renamed_nonstandard.glb"] = build_renamed_bones()
    files["body_no_face_ok.glb"] = build_body_no_face()
    files["malformed.bin"] = build_malformed()

    # incompatible: cyclic hierarchy
    bad = _nodes_standard()
    bad[1]["children"] = [2, 0]  # hips -> spine and root (cycle-ish with root->hips)
    files["incompatible_hierarchy.glb"] = _pack(bad)

    scenarios = {
        "ambiguous_arm": {"note": "force via proof flags", "force": {"impossibleArmInLeg": True}},
        "laterality_inversion": {"force": {"invertLaterality": True}},
        "root_pelvis_ambiguity": {"force": {"rootPelvisSame": True}},
        "missing_limb": {"force": {"missingLimb": True}},
        "digest_mismatch": {"force": {"digestMismatch": True}},
        "malformed_adapt01": {"force": {"malformedAdapt01": True}},
        "retarget_blocked": {"force": {"retargetBlocked": True}},
        "axis_adapter": {"asset": "axis_z_up_adapter.glb", "force": {"axisMismatchAdapter": True}},
    }
    (OUT / "SCENARIO_FLAGS.json").write_text(json.dumps(scenarios, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {"schema": "NURION_ADAPT02_FIXTURE_MANIFEST_V1", "fixtures": {}}
    for name, blob in files.items():
        p = OUT / name
        p.write_bytes(blob)
        manifest["fixtures"][name] = {"sha256": _sha(p), "byteLength": len(blob)}
    man = OUT / "FIXTURE_MANIFEST.json"
    man.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(files)}, indent=2))


if __name__ == "__main__":
    main()
