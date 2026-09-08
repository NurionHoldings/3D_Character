#!/usr/bin/env python3
"""CR04-GAP-01 independent proof — recompute from Sporty GLB; expanded hardcoding scan."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter
from fast_track.v2_cr02.facial_deformation import (
    _read_f32_vec3,
    _read_f32_vec4,
    _read_u8_vec4,
)
from fast_track.v2_cr03.glb_measure import sha256_file
from fast_track.v2_cr04.audit_paths import resolve_v2_cr04_roots
from fast_track.v2_cr04.facial_region_resolve import (
    resolve_head_joint_local_index,
    select_facial_vertices_resolved,
)
from fast_track.v2_cr04.fasttrack import _morph_index_map_from_mesh, prove_temporal
from fast_track.v2_cr04.gap01_pipeline import expanded_hardcoding_scan
from fast_track.v2_cr04.pins import SECOND_ASSET_SHA, TALKING_ANIMATION_NAME

GAP01_SPEC = "4a8467ad945d3c56d9222075c44ae4cc12e8df5edcd833d4091b046901b903f3"
FACE_DERIVED = "SECOND_ASSET_GAP01_facial_deformation.glb"
TALK_DERIVED = "SECOND_ASSET_GAP01_talking_weights.glb"


def main() -> int:
    roots = resolve_v2_cr04_roots(__file__)
    baseline = Path(roots["baseline"])
    derived_dir = Path(roots["derived"])
    face = derived_dir / FACE_DERIVED
    talk = derived_dir / TALK_DERIVED
    rep = Path(roots["reports"])
    blockers: list[dict] = []
    head = None

    if sha256_file(baseline) != SECOND_ASSET_SHA:
        blockers.append({"code": "G01_SPORTY_PIN"})

    cr01 = run_flexible_adapter(baseline)
    if cr01.get("status") != "PASS":
        blockers.append({"code": "G02_CR01"})
    else:
        gltf, blob, _ = load_gltf_document(baseline)
        assert blob is not None
        skin_joints = list((gltf.get("skins") or [{}])[0].get("joints") or [])
        head = resolve_head_joint_local_index(
            nodes=list(gltf.get("nodes") or []),
            skin_joints=skin_joints,
            nurion_head_name=(cr01.get("mappingView") or {}).get("NURION_head"),
        )
        if head.get("hardcodedIdle15Index21") != "NOT_USED":
            blockers.append({"code": "G03_HARDCODED_21"})
        if head.get("resolver") != "CR01_NURION_head→skin.joints.index":
            blockers.append({"code": "G03_RESOLVER_PROVENANCE"})
        prim = gltf["meshes"][0]["primitives"][0]
        pos = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
        joints = _read_u8_vec4(blob, gltf, prim["attributes"]["JOINTS_0"])
        weights = _read_f32_vec4(blob, gltf, prim["attributes"]["WEIGHTS_0"])
        regions = select_facial_vertices_resolved(
            pos, joints, weights, head["headJointLocalIndex"]
        )
        for key in ("eye_l", "eye_r", "mouth", "jaw"):
            if int(regions[key].sum()) < 5:
                blockers.append({"code": f"G04_REGION:{key}", "count": int(regions[key].sum())})

    if not face.is_file() or not talk.is_file():
        blockers.append({"code": "G05_DERIVED_MISSING"})
    else:
        g, _b, _ = load_gltf_document(talk)
        mmap = _morph_index_map_from_mesh(g["meshes"][0])
        temporal = prove_temporal(talk, mmap)
        if temporal["status"] != "PASS":
            blockers.append({"code": "G10_TEMPORAL", "detail": temporal.get("blockers")})
        anim_names = [a.get("name") for a in (g.get("animations") or [])]
        if TALKING_ANIMATION_NAME not in anim_names:
            blockers.append({"code": "G11_TALKING_MISSING"})
        if not any(n and n != TALKING_ANIMATION_NAME for n in anim_names):
            blockers.append({"code": "G12_BODY_CLIP_MISSING"})

    scan = expanded_hardcoding_scan(Path(roots["repoRoot"]))
    if scan["status"] != "PASS":
        blockers.append({"code": "G15_EXPANDED_HARDCODING", "detail": scan.get("blockers")})
    # Explicit: CR02 Idle_15 SoT remains historical; consume path must not call it
    if not any(
        n.get("disposition") == "HISTORICAL_CR02_CONSUME_ONLY_UNCHANGED" for n in (scan.get("notes") or [])
    ):
        blockers.append({"code": "G16_CR02_HISTORICAL_NOTE_MISSING"})

    gap_track = json.loads(
        (Path(roots["semantic"]) / "NURION_ADAPTATION_ENGINE_V2_CR04_GAP01_TRACK_V1.json").read_text(
            encoding="utf-8"
        )
    )
    if (gap_track.get("humanSpecGate") or {}).get("approvedSpecDigest") != GAP01_SPEC:
        blockers.append({"code": "G02_GAP01_SPEC"})

    matrix = {
        "schema": "NURION_V2_CR04_GAP01_INDEPENDENT_GATE_MATRIX_V1",
        "status": "PASS" if not blockers else "BLOCKED",
        "secondAssetSha256": sha256_file(baseline),
        "facialDerivedSha256": sha256_file(face) if face.is_file() else None,
        "talkingDerivedSha256": sha256_file(talk) if talk.is_file() else None,
        "headResolve": head if cr01.get("status") == "PASS" else None,
        "hardcodingScan": scan.get("status"),
        "hardcodingScanCovers": scan.get("covers"),
        "blockers": blockers,
        "CR04-G20": "HUMAN_FINAL_ONLY",
        "independentRunner": "Sporty GLB recompute + CR01 head resolve + expanded AST hardcoding scan",
        "didNotTrust": "report PASS fields",
    }
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "V2_CR04_GAP01_independent_gate_matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": matrix["status"], "blockers": blockers, "headResolve": matrix.get("headResolve")}, indent=2))
    return 0 if matrix["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
