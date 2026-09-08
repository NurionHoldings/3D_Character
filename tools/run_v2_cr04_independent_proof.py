#!/usr/bin/env python3
"""CR04 independent proof — recompute from GLB; do not trust report PASS."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr03.glb_measure import sha256_file
from fast_track.v2_cr04.audit_paths import resolve_v2_cr04_roots
from fast_track.v2_cr04.fasttrack import hardcoding_scan, prove_temporal, _morph_index_map_from_mesh
from fast_track.v2_cr04.pins import APPROVED_SPEC_DIGEST, SECOND_ASSET_SHA, TALKING_ANIMATION_NAME
from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.v2_cr01.flexible_adapter import run_flexible_adapter


def main() -> int:
    roots = resolve_v2_cr04_roots(__file__)
    baseline = Path(roots["baseline"])
    derived = Path(roots["derived"]) / "SECOND_ASSET_CR03_talking_weights.glb"
    rep = Path(roots["reports"])
    blockers = []

    if sha256_file(baseline) != SECOND_ASSET_SHA:
        blockers.append({"code": "G01_SECOND_ASSET_SHA"})

    cr01 = run_flexible_adapter(baseline)
    if cr01.get("status") != "PASS":
        blockers.append({"code": "G02_CR01"})

    if not derived.is_file():
        blockers.append({"code": "G03_DERIVED_MISSING"})
        matrix = {"status": "BLOCKED", "blockers": blockers}
        rep.mkdir(parents=True, exist_ok=True)
        (rep / "V2_CR04_independent_gate_matrix.json").write_text(
            json.dumps(matrix, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(matrix, indent=2))
        return 1

    g, b, _ = load_gltf_document(derived)
    mmap = _morph_index_map_from_mesh(g["meshes"][0])
    temporal = prove_temporal(derived, mmap)
    if temporal["status"] != "PASS":
        blockers.append({"code": "G10_TEMPORAL", "detail": temporal.get("blockers")})

    anim_names = [a.get("name") for a in (g.get("animations") or [])]
    if TALKING_ANIMATION_NAME not in anim_names:
        blockers.append({"code": "G11_TALKING_MISSING"})
    if not any(n and n != TALKING_ANIMATION_NAME for n in anim_names):
        blockers.append({"code": "G12_BODY_CLIP_MISSING"})

    scan = hardcoding_scan(Path(roots["repoRoot"]))
    if scan["status"] != "PASS":
        blockers.append({"code": "G15_HARDCODING", "detail": scan.get("blockers")})

    track = json.loads(
        (Path(roots["semantic"]) / "NURION_ADAPTATION_ENGINE_V2_CR04_TRACK_V1.json").read_text(
            encoding="utf-8"
        )
    )
    if (track.get("humanSpecGate") or {}).get("approvedSpecDigest") != APPROVED_SPEC_DIGEST:
        blockers.append({"code": "G02_SPEC"})

    matrix = {
        "schema": "NURION_V2_CR04_INDEPENDENT_GATE_MATRIX_V1",
        "status": "PASS" if not blockers else "BLOCKED",
        "secondAssetSha256": sha256_file(baseline),
        "derivedSha256": sha256_file(derived),
        "runtimeProofDigest": temporal.get("runtimeProofDigest"),
        "cr01Digest": cr01.get("semanticAdapterDigest"),
        "hardcodingScan": scan.get("status"),
        "blockers": blockers,
        "CR04-G20": "HUMAN_FINAL_ONLY",
        "independentRunner": "GLB recompute + hardcoding scan — does not trust report PASS",
    }
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "V2_CR04_independent_gate_matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": matrix["status"], "blockers": blockers}, indent=2))
    return 0 if matrix["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
