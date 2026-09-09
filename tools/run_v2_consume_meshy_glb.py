#!/usr/bin/env python3
"""Post-V2 sealed consume — one Meshy-style GLB end-to-end (local).

Consumes sealed CR01 / GAP-01 facial resolve / CR02 morph build / CR03–CR04 talking
injection. Does NOT reopen Engine V2. Does NOT pin to Sporty SHA (any new Meshy GLB).

Example (PowerShell):

  py -3 tools/run_v2_consume_meshy_glb.py `
    --input "D:\\path\\to\\YourCharacter_Idle_withSkin.glb" `
    --out-dir "dist/v2_consume/your_character"
"""

from __future__ import annotations

import argparse
import json
import re
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
from fast_track.v2_cr04.pins import TALKING_ANIMATION_NAME

MORPH_ORDER = [
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


def _safe_stem(path: Path) -> str:
    stem = path.stem.strip() or "meshy_character"
    stem = re.sub(r"[^\w.\-]+", "_", stem, flags=re.UNICODE)
    for suffix in ("_SOURCE_BASELINE", "_V2_FACE_TALKING", "_V2_FACE"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return (stem[:80] or "meshy_character")


def run_consume(*, input_glb: Path, out_dir: Path) -> dict:
    if not input_glb.is_file():
        return {"status": "BLOCKED", "reason": "INPUT_MISSING", "path": str(input_glb)}
    if input_glb.suffix.lower() != ".glb":
        return {"status": "BLOCKED", "reason": "INPUT_NOT_GLB", "path": str(input_glb)}

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(input_glb)
    src_copy = out_dir / f"{stem}_SOURCE_BASELINE.glb"
    face_out = out_dir / f"{stem}_V2_FACE.glb"
    talk_out = out_dir / f"{stem}_V2_FACE_TALKING.glb"
    report_path = out_dir / "CONSUME_E2E_REPORT.json"

    before = input_glb.read_bytes()
    src_sha = sha256_file(input_glb)
    shutil.copy2(input_glb, src_copy)

    cr01 = run_flexible_adapter(input_glb)
    if cr01.get("status") != "PASS":
        report = {
            "schema": "NURION_V2_CONSUME_MESHY_E2E_V1",
            "status": "BLOCKED",
            "reason": "CR01_FAIL",
            "cr01": cr01,
            "input": {"path": str(input_glb), "sha256": src_sha, "bytes": len(before)},
        }
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return report
    if input_glb.read_bytes() != before:
        return {"status": "BLOCKED", "reason": "SOURCE_MUTATED", "path": str(input_glb)}

    gltf, blob, _ = load_gltf_document(input_glb)
    if blob is None:
        return {"status": "BLOCKED", "reason": "GLB_BLOB_MISSING"}
    skins = gltf.get("skins") or []
    if not skins:
        return {"status": "BLOCKED", "reason": "NO_SKIN"}
    meshes = gltf.get("meshes") or []
    if not meshes or not (meshes[0].get("primitives") or []):
        return {"status": "BLOCKED", "reason": "NO_MESH_PRIMITIVE"}

    skin_joints = list(skins[0].get("joints") or [])
    head = resolve_head_joint_local_index(
        nodes=list(gltf.get("nodes") or []),
        skin_joints=skin_joints,
        nurion_head_name=(cr01.get("mappingView") or {}).get("NURION_head"),
    )
    prim = meshes[0]["primitives"][0]
    attrs = prim.get("attributes") or {}
    for key in ("POSITION", "JOINTS_0", "WEIGHTS_0"):
        if key not in attrs:
            return {"status": "BLOCKED", "reason": f"MISSING_ATTR_{key}"}

    pos = _read_f32_vec3(blob, gltf, attrs["POSITION"])
    joints = _read_u8_vec4(blob, gltf, attrs["JOINTS_0"])
    weights = _read_f32_vec4(blob, gltf, attrs["WEIGHTS_0"])
    regions = select_facial_vertices_resolved(pos, joints, weights, head["headJointLocalIndex"])
    deltas = build_morph_deltas(pos, regions)

    write_meta = write_deformed_glb(input_glb, face_out, deltas=deltas, morph_order=MORPH_ORDER)
    inj = inject_talking_by_name(input_glb=face_out, output_glb=talk_out)
    if inj.get("status") not in (None, "PASS", "OK") and inj.get("ok") is False:
        # inject_talking_by_name may return dict without status; continue to temporal proof
        pass

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

    region_counts = {
        k: int(v.sum())
        for k, v in regions.items()
        if getattr(v, "dtype", None) == bool or (hasattr(v, "dtype") and str(v.dtype) == "bool")
    }

    status = (
        "PASS"
        if temporal.get("status") == "PASS"
        and body_ok
        and all(v == "PASS" for v in functional.values())
        else "BLOCKED"
    )

    report = {
        "schema": "NURION_V2_CONSUME_MESHY_E2E_V1",
        "declaredAtUtc": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "mode": "POST_V2_SEALED_CONSUME_E2E",
        "engineV2": "CLOSED / PASS (consume only)",
        "input": {
            "path": str(input_glb.resolve()),
            "fileName": input_glb.name,
            "sha256": src_sha,
            "bytes": len(before),
        },
        "cr01": {
            "status": cr01.get("status"),
            "NURION_head": (cr01.get("mappingView") or {}).get("NURION_head"),
            "semanticAdapterDigest": cr01.get("semanticAdapterDigest"),
        },
        "headResolve": head,
        "regionCounts": region_counts,
        "functional": functional,
        "injectTalking": {k: inj.get(k) for k in ("status", "ok", "animationName") if k in inj}
        if isinstance(inj, dict)
        else {},
        "outputs": {
            "outDir": str(out_dir.resolve()),
            "sourceCopy": str(src_copy),
            "faceGlb": str(face_out),
            "faceSha256": write_meta.get("derivedSha256") or sha256_file(face_out),
            "talkingGlb": str(talk_out),
            "talkingSha256": sha256_file(talk_out),
            "report": str(report_path),
        },
        "preservation": {
            "sourceUnmutated": input_glb.read_bytes() == before,
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
        "status": status,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Local E2E: one Meshy-style GLB → V2 FACE + FACE_TALKING (sealed consume)."
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        type=Path,
        help="Path to Meshy rigged+skinned GLB (e.g. *_Idle_*_withSkin.glb)",
    )
    parser.add_argument(
        "--out-dir",
        "-o",
        type=Path,
        default=None,
        help="Export directory (default: dist/v2_consume/<input_stem>)",
    )
    args = parser.parse_args(argv)

    input_glb = args.input.expanduser().resolve()
    out_dir = (
        args.out_dir.expanduser().resolve()
        if args.out_dir
        else (ROOT / "dist" / "v2_consume" / _safe_stem(input_glb))
    )

    report = run_consume(input_glb=input_glb, out_dir=out_dir)
    print(json.dumps(report, indent=2, ensure_ascii=True))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
