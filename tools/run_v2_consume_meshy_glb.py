#!/usr/bin/env python3
"""Post-V2 sealed consume — one Meshy-style GLB end-to-end (local).

Consumes sealed CR01 / GAP-01 facial resolve / CR02 morph build / CR03–CR04 talking
injection. Does NOT reopen Engine V2. Does NOT pin to Sporty SHA (any new Meshy GLB).

Fail-closed: missing input, non-GLB, size/header, OUTPUT_ALREADY_EXISTS, talking inject
failure, missing GLB blob after talking, and source mutation all return BLOCKED.

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
import struct
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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
from fast_track.v2_cr04.fasttrack import (
    _morph_index_map_from_mesh,
    inject_talking_by_name,
    prove_temporal,
)
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

# Align with Post-V2 FBX import ceiling (docs/REPRODUCIBLE_RUNTIME.md).
MAX_INPUT_BYTES = 512 * 1024 * 1024
GLB_MAGIC = b"glTF"
GLB_VERSION = 2
SCHEMA = "NURION_V2_CONSUME_MESHY_E2E_V1"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_stem(path: Path) -> str:
    stem = path.stem.strip() or "meshy_character"
    stem = re.sub(r"[^\w.\-]+", "_", stem, flags=re.UNICODE)
    for suffix in ("_SOURCE_BASELINE", "_V2_FACE_TALKING", "_V2_FACE"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem[:80] or "meshy_character"


def _input_meta(input_glb: Path, *, sha256: str | None = None, nbytes: int | None = None) -> dict[str, Any]:
    """Public-safe input identity (no absolute paths)."""
    meta: dict[str, Any] = {"fileName": input_glb.name}
    if sha256 is not None:
        meta["sha256"] = sha256
    if nbytes is not None:
        meta["bytes"] = nbytes
    return meta


def _write_report(report_path: Path | None, report: dict[str, Any]) -> dict[str, Any]:
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def _blocked(
    reason: str,
    *,
    report_path: Path | None = None,
    input_glb: Path | None = None,
    extra: dict[str, Any] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "declaredAtUtc": _utc(),
        "mode": "POST_V2_SEALED_CONSUME_E2E",
        "engineV2": "CLOSED / PASS (consume only)",
        "status": "BLOCKED",
        "reason": reason,
    }
    if input_glb is not None:
        report["input"] = _input_meta(input_glb)
    if extra:
        report.update(extra)
    if write and report_path is not None:
        return _write_report(report_path, report)
    return report


def validate_glb_header(data: bytes) -> str | None:
    """Return a BLOCKED reason code, or None if header looks like glTF 2 GLB."""
    if len(data) < 12:
        return "INVALID_GLB_HEADER"
    magic = data[:4]
    if magic != GLB_MAGIC:
        return "INVALID_GLB_HEADER"
    version = struct.unpack_from("<I", data, 4)[0]
    if version != GLB_VERSION:
        return "UNSUPPORTED_GLB_VERSION"
    length = struct.unpack_from("<I", data, 8)[0]
    if length != len(data):
        return "INVALID_GLB_LENGTH"
    return None


def _talking_inject_failed(inj: Any) -> str | None:
    if not isinstance(inj, dict):
        return "TALKING_INJECT_FAIL"
    if inj.get("ok") is False:
        return "TALKING_INJECT_FAIL"
    status = inj.get("status")
    if status is not None and status not in ("PASS", "OK"):
        return "TALKING_INJECT_FAIL"
    if not inj.get("derivedSha256"):
        return "TALKING_INJECT_FAIL"
    return None


def run_consume(*, input_glb: Path, out_dir: Path) -> dict[str, Any]:
    report_path = out_dir / "CONSUME_E2E_REPORT.json"

    if not input_glb.is_file():
        # Do not create out_dir / overwrite anything for missing input.
        return _blocked("INPUT_MISSING", input_glb=input_glb, write=False)

    if input_glb.suffix.lower() != ".glb":
        return _blocked("INPUT_NOT_GLB", input_glb=input_glb, write=False)

    size = input_glb.stat().st_size
    if size <= 0:
        return _blocked("INPUT_EMPTY", input_glb=input_glb, write=False)
    if size > MAX_INPUT_BYTES:
        return _blocked(
            "INPUT_TOO_LARGE",
            input_glb=input_glb,
            write=False,
            extra={"input": _input_meta(input_glb, nbytes=size), "maxInputBytes": MAX_INPUT_BYTES},
        )

    header = input_glb.read_bytes()[:12]
    # Re-read full only after collision checks; validate header from prefix + size field.
    # Length field must match full file size — read just enough then compare declared length.
    if len(header) < 12:
        return _blocked("INVALID_GLB_HEADER", input_glb=input_glb, write=False)
    # Validate magic/version from prefix; length against st_size without loading whole file yet.
    if header[:4] != GLB_MAGIC:
        return _blocked("INVALID_GLB_HEADER", input_glb=input_glb, write=False)
    version = struct.unpack_from("<I", header, 4)[0]
    if version != GLB_VERSION:
        return _blocked("UNSUPPORTED_GLB_VERSION", input_glb=input_glb, write=False)
    declared = struct.unpack_from("<I", header, 8)[0]
    if declared != size:
        return _blocked("INVALID_GLB_LENGTH", input_glb=input_glb, write=False)

    stem = _safe_stem(input_glb)
    src_copy = out_dir / f"{stem}_SOURCE_BASELINE.glb"
    face_out = out_dir / f"{stem}_V2_FACE.glb"
    talk_out = out_dir / f"{stem}_V2_FACE_TALKING.glb"
    outputs = [src_copy, face_out, talk_out, report_path]
    existing = [p.name for p in outputs if p.exists()]
    if existing:
        return _blocked(
            "OUTPUT_ALREADY_EXISTS",
            input_glb=input_glb,
            write=False,
            extra={"existingOutputs": existing},
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    before = input_glb.read_bytes()
    header_reason = validate_glb_header(before)
    if header_reason:
        return _blocked(header_reason, report_path=report_path, input_glb=input_glb)

    src_sha = sha256_file(input_glb)
    shutil.copy2(input_glb, src_copy)

    cr01 = run_flexible_adapter(input_glb)
    if cr01.get("status") != "PASS":
        return _blocked(
            "CR01_FAIL",
            report_path=report_path,
            input_glb=input_glb,
            extra={
                "input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before)),
                "cr01": {"status": cr01.get("status")},
            },
        )
    if input_glb.read_bytes() != before:
        return _blocked(
            "SOURCE_MUTATED",
            report_path=report_path,
            input_glb=input_glb,
            extra={"input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before))},
        )

    gltf, blob, _ = load_gltf_document(input_glb)
    if blob is None:
        return _blocked("GLB_BLOB_MISSING", report_path=report_path, input_glb=input_glb)
    skins = gltf.get("skins") or []
    if not skins:
        return _blocked("NO_SKIN", report_path=report_path, input_glb=input_glb)
    meshes = gltf.get("meshes") or []
    if not meshes or not (meshes[0].get("primitives") or []):
        return _blocked("NO_MESH_PRIMITIVE", report_path=report_path, input_glb=input_glb)

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
            return _blocked(f"MISSING_ATTR_{key}", report_path=report_path, input_glb=input_glb)

    pos = _read_f32_vec3(blob, gltf, attrs["POSITION"])
    joints = _read_u8_vec4(blob, gltf, attrs["JOINTS_0"])
    weights = _read_f32_vec4(blob, gltf, attrs["WEIGHTS_0"])
    regions = select_facial_vertices_resolved(pos, joints, weights, head["headJointLocalIndex"])
    deltas = build_morph_deltas(pos, regions)

    write_meta = write_deformed_glb(input_glb, face_out, deltas=deltas, morph_order=MORPH_ORDER)

    try:
        inj = inject_talking_by_name(input_glb=face_out, output_glb=talk_out)
    except Exception as exc:  # noqa: BLE001 — fail-closed boundary for sealed consume
        return _blocked(
            "TALKING_INJECT_FAIL",
            report_path=report_path,
            input_glb=input_glb,
            extra={
                "input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before)),
                "talkingErrorType": type(exc).__name__,
            },
        )

    fail = _talking_inject_failed(inj)
    if fail or not talk_out.is_file():
        return _blocked(
            "TALKING_INJECT_FAIL",
            report_path=report_path,
            input_glb=input_glb,
            extra={
                "input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before)),
                "injectTalking": {
                    k: inj.get(k)
                    for k in ("status", "ok", "derivedSha256")
                    if isinstance(inj, dict) and k in inj
                },
            },
        )

    try:
        g_talk, b_talk, _ = load_gltf_document(talk_out)
    except Exception as exc:  # noqa: BLE001
        return _blocked(
            "TALKING_GLB_LOAD_FAIL",
            report_path=report_path,
            input_glb=input_glb,
            extra={"talkingErrorType": type(exc).__name__},
        )
    if b_talk is None:
        return _blocked("TALKING_BLOB_MISSING", report_path=report_path, input_glb=input_glb)

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

    source_ok = input_glb.read_bytes() == before
    if not source_ok:
        return _blocked(
            "SOURCE_MUTATED",
            report_path=report_path,
            input_glb=input_glb,
            extra={"input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before))},
        )

    status = (
        "PASS"
        if temporal.get("status") == "PASS"
        and body_ok
        and all(v == "PASS" for v in functional.values())
        and TALKING_ANIMATION_NAME in anims
        else "BLOCKED"
    )

    report: dict[str, Any] = {
        "schema": SCHEMA,
        "declaredAtUtc": _utc(),
        "mode": "POST_V2_SEALED_CONSUME_E2E",
        "engineV2": "CLOSED / PASS (consume only)",
        "input": _input_meta(input_glb, sha256=src_sha, nbytes=len(before)),
        "cr01": {
            "status": cr01.get("status"),
            "NURION_head": (cr01.get("mappingView") or {}).get("NURION_head"),
            "semanticAdapterDigest": cr01.get("semanticAdapterDigest"),
        },
        "headResolve": head,
        "regionCounts": region_counts,
        "functional": functional,
        "injectTalking": {
            k: inj.get(k) for k in ("derivedSha256", "talkingAnimationIndex", "timelineDigest") if k in inj
        },
        "outputs": {
            "sourceCopy": src_copy.name,
            "faceGlb": face_out.name,
            "faceSha256": write_meta.get("derivedSha256") or sha256_file(face_out),
            "talkingGlb": talk_out.name,
            "talkingSha256": sha256_file(talk_out),
            "report": report_path.name,
        },
        "preservation": {
            "sourceUnmutated": True,
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
    if status != "PASS":
        report["reason"] = "POST_TALKING_GATES_FAIL"
    return _write_report(report_path, report)


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
