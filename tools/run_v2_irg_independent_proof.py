#!/usr/bin/env python3
"""V2-IRG independent proof — recompute digests; do not trust report PASS.

Works in MONOREPO and EXTRACTED_AUDIT_ZIP layouts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.v2_cr03.glb_measure import canonical_sha256, sha256_file
from fast_track.v2_irg import pins as P
from fast_track.v2_irg.audit_paths import resolve_v2_irg_roots
from fast_track.v2_irg.hc01_regression_scan import expanded_hardcoding_scan


def _resolve_pin_file(pkg: Path, *, extracted: bool, monorepo_rel: str, extracted_rel: str) -> Path:
    if extracted:
        return pkg / extracted_rel
    return pkg / monorepo_rel


def main() -> int:
    roots = resolve_v2_irg_roots(__file__)
    sem = Path(roots["semantic"])
    ev = Path(roots["evidence"])
    rep = Path(roots["reports"])
    pkg = Path(roots["packageRoot"])
    extracted = bool(roots.get("extracted"))
    blockers: list[dict] = []

    track = json.loads((sem / "NURION_ADAPTATION_ENGINE_V2_IRG_TRACK_V1.json").read_text(encoding="utf-8"))
    if (track.get("humanSpecGate") or {}).get("approvedSpecDigest") != P.APPROVED_SPEC_DIGEST:
        blockers.append({"code": "G02_SPEC"})
    if sha256_file(sem / "NURION_ADAPTATION_ENGINE_V2_INTEGRATION_RELEASE_GATE_SPEC_R1.json") != P.APPROVED_SPEC_DIGEST:
        blockers.append({"code": "SPEC_DIGEST_MISMATCH"})

    pin_files = [
        (
            "derived_cr02/Idle_15_R2_facial_deformation.glb",
            "derived/Idle_15_R2_facial_deformation.glb",
            P.CR02_DERIVED,
        ),
        (
            "derived_cr03/Idle_15_CR03_talking_weights.glb",
            "derived/Idle_15_CR03_talking_weights.glb",
            P.CR03_DERIVED,
        ),
        (
            "assets_cr04/SECOND_ASSET_BASELINE.glb",
            "assets/SECOND_ASSET_BASELINE.glb",
            P.CR04_SECOND,
        ),
        (
            "derived_cr04/SECOND_ASSET_GAP01_facial_deformation.glb",
            "derived/SECOND_ASSET_GAP01_facial_deformation.glb",
            P.CR04_FACIAL,
        ),
        (
            "derived_cr04/SECOND_ASSET_GAP01_talking_weights.glb",
            "derived/SECOND_ASSET_GAP01_talking_weights.glb",
            P.CR04_TALKING,
        ),
    ]
    for mono, ext, expected in pin_files:
        path = _resolve_pin_file(pkg, extracted=extracted, monorepo_rel=mono, extracted_rel=ext)
        if not path.is_file() or sha256_file(path) != expected:
            blockers.append({"code": "UPSTREAM_DIGEST_MISMATCH", "file": str(path.name), "layout": "extracted" if extracted else "monorepo"})

    for name in (
        "NURION-V2-CR01_R2_HUMAN_PASS_receipt.json",
        "NURION-V2-CR02_R2_HUMAN_PASS_receipt.json",
        "NURION-V2-CR03_R2_HUMAN_PASS_receipt.json",
        "NURION-V2-CR04_R3_HUMAN_PASS_receipt.json",
        "NURION-V2-CR04_R3_CONSUME_ONLY_SEAL.json",
    ):
        if not (ev / name).is_file():
            blockers.append({"code": "MISSING_HUMAN_PASS_RECEIPT", "file": name})

    manifest = sem / "NURION_ADAPTATION_ENGINE_V2_RELEASE_MANIFEST.json"
    candidate = sem / "NURION_ADAPTATION_ENGINE_V2_RELEASE_CANDIDATE.json"
    if not manifest.is_file() or not candidate.is_file():
        blockers.append({"code": "PROOF_PACKAGE_INCOMPLETE"})
    else:
        m = json.loads(manifest.read_text(encoding="utf-8"))
        if not m.get("releaseDigest"):
            blockers.append({"code": "NONDETERMINISTIC_RELEASE_IDENTITY"})

    # Scan packaged repo tree (extracted: package/repo; monorepo: repoRoot)
    scan_root = Path(roots["repoRoot"])
    scan = expanded_hardcoding_scan(scan_root)
    if scan.get("status") != "PASS":
        blockers.append({"code": "HC01_REGRESSION", "detail": scan.get("blockers")})
    if not any(
        n.get("disposition") == "HISTORICAL_CR02_CONSUME_ONLY_UNCHANGED" for n in (scan.get("notes") or [])
    ):
        blockers.append({"code": "HC01_HISTORICAL_NOTE_MISSING"})

    matrix = {
        "schema": "NURION_V2_IRG_INDEPENDENT_GATE_MATRIX_V1",
        "status": "PASS" if not blockers else "BLOCKED",
        "approvedSpecDigest": P.APPROVED_SPEC_DIGEST,
        "layout": "EXTRACTED_AUDIT_ZIP" if extracted else "MONOREPO",
        "blockers": blockers,
        "engineV2": "NOT_OPEN",
        "V2-RG-G20": "HUMAN_FINAL_ONLY",
        "independentRunner": "pin/digest recompute + HC-01 scan — does not trust report PASS",
    }
    rep.mkdir(parents=True, exist_ok=True)
    (rep / "V2_IRG_independent_gate_matrix.json").write_text(
        json.dumps(matrix, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({"status": matrix["status"], "blockers": blockers, "layout": matrix["layout"]}, indent=2))
    return 0 if matrix["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
