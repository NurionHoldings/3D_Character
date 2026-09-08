#!/usr/bin/env python3
"""Post-V2 sealed consume demo — run Human-PASS V2 chain on Sporty pin GLB.

Does NOT reopen V2. Consumes sealed CR01/GAP-01/CR03 mechanisms only.
Output: dist/v2_final_demo/
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter
from fast_track.v2_cr02.facial_deformation import (
    _read_f32_vec3,
    _read_f32_vec4,
    _read_u8_vec4,
    build_morph_deltas,
    measure_cycle,
    write_deformed_glb,
)
from fast_track.v2_cr03.glb_measure import base_skin_digests, sha256_file
from fast_track.v2_cr04.facial_region_resolve import (
    resolve_head_joint_local_index,
    select_facial_vertices_resolved,
)
from fast_track.v2_cr04.fasttrack import inject_talking_by_name, prove_temporal, _morph_index_map_from_mesh
from fast_track.v2_cr04.pins import SECOND_ASSET_SHA, TALKING_ANIMATION_NAME

OUT = ROOT / "dist" / "v2_final_demo"
SRC = ROOT / "fast_track/working/adaptation_engine_v2/assets_cr04/SECOND_ASSET_BASELINE.glb"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    src_sha = sha256_file(SRC)
    if src_sha != SECOND_ASSET_SHA:
        print(json.dumps({"status": "BLOCKED", "reason": "SOURCE_PIN_MISMATCH", "got": src_sha}, indent=2))
        return 1

    before = SRC.read_bytes()
    cr01 = run_flexible_adapter(SRC)
    if cr01.get("status") != "PASS":
        print(json.dumps({"status": "BLOCKED", "cr01": cr01}, indent=2))
        return 1
    if SRC.read_bytes() != before:
        print(json.dumps({"status": "BLOCKED", "reason": "SOURCE_MUTATED"}, indent=2))
        return 1

    gltf, blob, _ = load_gltf_document(SRC)
    assert blob is not None
    skin_joints = list((gltf.get("skins") or [{}])[0].get("joints") or [])
    head = resolve_head_joint_local_index(
        nodes=list(gltf.get("nodes") or []),
        skin_joints=skin_joints,
        nurion_head_name=(cr01.get("mappingView") or {}).get("NURION_head"),
    )
    prim = gltf["meshes"][0]["primitives"][0]
    pos = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    joints = _read_u8_vec4(blob, gltf, prim["attributes"]["JOINTS_0"])
    weights = _read_f32_vec4(blob, gltf, prim["attributes"]["WEIGHTS_0"])
    regions = select_facial_vertices_resolved(pos, joints, weights, head["headJointLocalIndex"])
    deltas = build_morph_deltas(pos, regions)
    morph_order = [
        "Blink_L",
        "Blink_R",
        "Jaw_Mouth",
        "EXPR_SMILE",
        "EXPR_BROW_UP",
        "EXPR_FROWN",
        "VISEME_AA",
        "VISEME_OH",
        "VISEME_EE",
    ]

    face_out = OUT / "Sporty_V2_FACE.glb"
    talk_out = OUT / "Sporty_V2_FACE_TALKING.glb"
    write_meta = write_deformed_glb(SRC, face_out, deltas=deltas, morph_order=morph_order)
    inj = inject_talking_by_name(input_glb=face_out, output_glb=talk_out)
    g_talk, b_talk, _ = load_gltf_document(talk_out)
    assert b_talk is not None
    mmap = _morph_index_map_from_mesh(g_talk["meshes"][0])
    temporal = prove_temporal(talk_out, mmap)
    body_ok = base_skin_digests(blob, gltf) == base_skin_digests(b_talk, g_talk)
    anims = [a.get("name") for a in (g_talk.get("animations") or [])]

    functional = {
        name: measure_cycle(pos, deltas, name, {name: 1.0}).get("functionalTest")
        for name in ("Blink_L", "Blink_R", "Jaw_Mouth", "VISEME_AA", "VISEME_OH", "VISEME_EE")
    }

    # also copy sealed Idle_15 talking product for reference
    idle_talk = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr03/Idle_15_CR03_talking_weights.glb"
    if idle_talk.is_file():
        shutil.copy2(idle_talk, OUT / "Idle15_V2_FACE_TALKING_SEALED.glb")

    shutil.copy2(SRC, OUT / "Sporty_SOURCE_BASELINE.glb")

    report = {
        "schema": "NURION_V2_FINAL_DEMO_RESULT_V1",
        "declaredAtUtc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "mode": "POST_V2_SEALED_CONSUME_DEMO",
        "engineV2": "CLOSED / PASS (consume only)",
        "input": {
            "file": "Sporty_Studio_Portrait Idle_15_withSkin (SECOND_ASSET_BASELINE.glb)",
            "sha256": src_sha,
            "bytes": len(before),
        },
        "cr01": {
            "status": cr01.get("status"),
            "NURION_head": (cr01.get("mappingView") or {}).get("NURION_head"),
            "semanticAdapterDigest": cr01.get("semanticAdapterDigest"),
        },
        "headResolve": head,
        "regionCounts": {k: int(v.sum()) for k, v in regions.items() if getattr(v, "dtype", None) == bool},
        "functional": functional,
        "outputs": {
            "faceGlb": str(face_out),
            "faceSha256": write_meta.get("derivedSha256") or sha256_file(face_out),
            "talkingGlb": str(talk_out),
            "talkingSha256": sha256_file(talk_out),
        },
        "preservation": {
            "sourceUnmutated": SRC.read_bytes() == before,
            "bodySkinDigestMatch": body_ok,
            "animations": anims,
            "talkingClipPresent": TALKING_ANIMATION_NAME in anims,
        },
        "temporal": {
            "status": temporal.get("status"),
            "runtimeProofDigest": temporal.get("runtimeProofDigest"),
            "stateDistinctness": temporal.get("stateDistinctness"),
            "restoration": temporal.get("restoration"),
        },
        "status": "PASS"
        if temporal.get("status") == "PASS" and body_ok and all(v == "PASS" for v in functional.values())
        else "BLOCKED",
    }
    (OUT / "FINAL_DEMO_REPORT.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
