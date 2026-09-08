#!/usr/bin/env python3
"""Build ADAPT-03 fixtures — face-specific GLB scenarios."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(os.environ.get("NURION_ADAPT03_REPO_ROOT") or os.environ.get("NURION_REPO_ROOT") or Path(__file__).resolve().parents[1])
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import write_minimal_glb
from tools.build_adapt01_fixtures import _humanoid_nodes, _mesh_with_morphs
from tools.build_adapt02_fixtures import _nodes_standard, _pack as adapt02_pack

_OUT = os.environ.get("NURION_ADAPT03_FIXTURE_DIR")
if _OUT:
    OUT = Path(_OUT)
elif Path(__file__).resolve().parents[1].name == "repo":
    OUT = Path(__file__).resolve().parents[2] / "fixtures"
else:
    OUT = ROOT / "fast_track" / "adaptation" / "fixtures_adapt03"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _face_glb(
    morphs: list[str],
    *,
    renamed: bool = False,
    prefix: str = "",
    drop_eyes: bool = False,
    drop_jaw: bool = False,
    joint_count: int | None = None,
) -> bytes:
    nodes = _humanoid_nodes(renamed=renamed)
    if drop_eyes:
        nodes = nodes[:20]
        nodes[5].pop("children", None)
    elif drop_jaw:
        nodes[5]["children"] = [20, 21]
    if prefix:
        nodes = [{"name": f"{prefix}{n['name']}", **({k: v for k, v in n.items() if k != 'name'})} for n in nodes]
    nodes[0]["mesh"] = 0
    nodes[0]["skin"] = 0
    jc = joint_count if joint_count is not None else len(nodes)
    gltf = {
        "asset": {"version": "2.0", "generator": "ADAPT03_FIXTURE"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": nodes,
        "meshes": [_mesh_with_morphs(morphs)],
        "skins": [{"name": "Armature", "joints": list(range(jc)), "skeleton": 0}],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
        "extras": {"upAxis": "Y", "forwardAxis": "Z"},
    }
    return write_minimal_glb(gltf, b"\x00\x00\x00\x00")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rich_morphs = [
        "FACE_eyeBlinkLeft",
        "FACE_eyeBlinkRight",
        "FACE_mouthOpen",
        "FACE_mouthSmileLeft",
        "FACE_mouthSmileRight",
        "FACE_browInnerUpLeft",
        "FACE_browInnerUpRight",
        "FACE_mouthPucker",
        "FACE_mouthWiden",
        "FACE_mouthPlosive",
        "viseme_aa",
        "viseme_oh",
        "viseme_ee",
        "mouthFunnel",
    ] + [f"expr_extra_{i}" for i in range(8)]

    jake_morphs = [
        "Brow_Drop_L",
        "Brow_Drop_R",
        "Eye_Blink_L",
        "Eye_Blink_R",
        "Jaw_Open",
        "Mouth_Smile_L",
        "Mouth_Smile_R",
        "Viseme_A",
        "Viseme_O",
        "Viseme_E",
        "Viseme_M",
    ]

    files: dict[str, bytes] = {
        "rich_facial_morphs.glb": _face_glb(rich_morphs),
        "body_minimal_face.glb": _face_glb([], drop_eyes=True, drop_jaw=True),
        "eye_jaw_no_visemes.glb": _face_glb(["eyeBlinkLeft", "eyeBlinkRight", "jawOpen", "mouthSmile"]),
        "blendshape_renamed.glb": _face_glb(jake_morphs),
        "expression_mapping_required.glb": _face_glb(["Smile_L", "Smile_R", "Blink_L", "Blink_R", "Open_Mouth"]),
        "eye_adaptation_required.glb": _face_glb(["blink_left", "blink_right"], renamed=True),
        "talking_augmentation_required.glb": _face_glb(["eyeBlinkLeft", "mouthSmile"], drop_jaw=False),
        "meshy_style.glb": _face_glb(
            ["eyeBlinkLeft", "jawOpen", "mouthSmile"],
            prefix="mixamorig:",
        ),
        "malformed_face_metadata.glb": adapt02_pack(_nodes_standard()),
    }
    # meshy_style uses adapt02 skeleton with prefix — rebuild with morphs on standard nodes
    meshy_nodes = _nodes_standard(prefix="mixamorig:")
    meshy_nodes[0]["mesh"] = 0
    meshy_nodes[0]["skin"] = 0
    gltf_meshy = {
        "asset": {"version": "2.0", "generator": "ADAPT03_MESHY"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": meshy_nodes,
        "meshes": [_mesh_with_morphs(["eyeBlinkLeft", "jawOpen"])],
        "skins": [{"name": "Armature", "joints": list(range(len(meshy_nodes))), "skeleton": 0}],
        "accessors": [
            {"componentType": 5126, "count": 3, "type": "VEC3", "max": [1, 1, 1], "min": [-1, -1, -1]}
        ],
        "bufferViews": [{"buffer": 0, "byteOffset": 0, "byteLength": 4}],
        "buffers": [{"byteLength": 4}],
        "extras": {"upAxis": "Y", "forwardAxis": "Z"},
    }
    files["meshy_style.glb"] = write_minimal_glb(gltf_meshy, b"\x00\x00\x00\x00")

    scenarios = {
        "eye_inversion": {"asset": "rich_facial_morphs.glb", "force": {"invertEyeLaterality": True}},
        "ambiguous_facial": {"asset": "rich_facial_morphs.glb", "force": {"ambiguousFacialControls": True}},
        "head_mismatch": {"asset": "rich_facial_morphs.glb", "force": {"headSemanticUnresolved": True}},
        "adapt01_02_identity_mismatch": {"force": {"adapt01Adapt02IdentityMismatch": True}},
        "source_digest_mismatch": {"asset": "rich_facial_morphs.glb", "force": {"sourceDigestMismatch": True}},
        "expression_conflict": {"asset": "expression_mapping_required.glb", "force": {"expressionMappingConflict": True}},
        "adapt04_augmentation": {"asset": "body_minimal_face.glb"},
        "determinism": {"asset": "rich_facial_morphs.glb"},
        "adapt04_premature": {"asset": "rich_facial_morphs.glb", "force": {"performAdapt04Augmentation": True}},
    }
    (OUT / "SCENARIO_FLAGS.json").write_text(json.dumps(scenarios, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = {"schema": "NURION_ADAPT03_FIXTURE_MANIFEST_V1", "fixtures": {}}
    for name, blob in files.items():
        p = OUT / name
        p.write_bytes(blob)
        manifest["fixtures"][name] = {"sha256": _sha(p), "byteLength": len(blob)}

    (OUT / "FIXTURE_MANIFEST.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(OUT), "count": len(files)}, indent=2))


if __name__ == "__main__":
    main()
