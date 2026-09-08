#!/usr/bin/env python3
"""Pack ADAPT-02 R2 audit ZIP — self-contained with pinned upstream provenance."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v1/reports_adapt02"
FIX = ROOT / "fast_track/adaptation/fixtures_adapt02"
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
OUT = EV / "NURION-ADAPT-02_skeleton_semantic_proof_R2.zip"

EXCLUDE = {
    "NURION-ADAPT-02_R1_audit_zip_receipt.json",
    "NURION-ADAPT-02_R2_audit_zip_receipt.json",
    "NURION-ADAPT-02_final_zip_sha_EXTERNAL.json",
    "NURION-ADAPT-01_audit_zip_receipt.json",
    "NURION-ADAPT-01_R1_audit_zip_receipt.json",
    "NURION-ADAPT-01_final_zip_sha_EXTERNAL.json",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    # Ensure binding/provenance current
    from tools.build_adapt02_authoritative_binding import main as build_binding

    build_binding()

    ready = {
        "receiptId": "NURION-ADAPT-02_READY_FOR_HUMAN_AUDIT_R2",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-02",
        "revision": "R2",
        "status": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD2-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-03": "LOCKED BY PREDECESSOR",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "blockerFix": "R2 authoritative upstream SHA256 pins + snapshot derivation provenance",
        "finalAuditZipSha256": None,
        "digestSemantics": {
            "payloadCanonicalDigest": "SEE_MANIFEST",
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "authoritativeBodySpecSha256": "PINNED_IN_BINDING_AND_PROVENANCE",
            "authoritativeAxisSha256": "PINNED_IN_BINDING_AND_PROVENANCE",
        },
        "note": "Final ZIP SHA external only. Unpinned snapshot without upstream pins = FAIL CLOSED.",
    }
    (EV / "NURION-ADAPT-02_READY_FOR_HUMAN_AUDIT_receipt.json").write_text(
        json.dumps(ready, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    files: list[tuple[str, Path]] = []
    for name in (
        "NURION_ADAPT02_SKELETON_SEMANTIC_ADAPTATION_CONTRACT_V1.json",
        "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
        "NURION_ADAPT02_BODY_CORE_SNAPSHOT_V1.json",
        "NURION_ADAPT02_AXIS_SNAPSHOT_V1.json",
        "NURION_ADAPTATION_ENGINE_TRACK_V1.json",
    ):
        p = SEM / name
        if p.exists():
            files.append((f"semantic/{name}", p))
    for p in sorted(EV.glob("NURION-ADAPT-02*.json")):
        if p.name in EXCLUDE:
            continue
        files.append((f"evidence/{p.name}", p))
    a01 = EV / "NURION-ADAPT-01_PASS_receipt.json"
    if a01.exists():
        files.append(("evidence/NURION-ADAPT-01_PASS_receipt.json", a01))
    for p in sorted(REP.glob("ADAPT02_report_*.json")):
        files.append((f"reports/{p.name}", p))
    for p in sorted(FIX.iterdir()):
        if p.is_file():
            files.append((f"fixtures/{p.name}", p))
    for rel in [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/authoritative_binding.py",
        "fast_track/adaptation/glb_io.py",
        "fast_track/adaptation/semantic_candidates.py",
        "fast_track/adaptation/classifier.py",
        "fast_track/adaptation/inspector.py",
        "fast_track/adaptation/skeleton_mapping.py",
        "tools/build_adapt01_fixtures.py",
        "tools/build_adapt02_fixtures.py",
        "tools/build_adapt02_authoritative_binding.py",
        "tools/run_adapt02_inspection_proof.py",
        "tools/run_adapt02_independent_proof.py",
        "tools/pack_adapt02_skeleton_proof_zip.py",
    ]:
        p = ROOT / rel
        if p.exists():
            files.append((f"repo/{rel.replace(chr(92), '/')}", p))

    payload_h = hashlib.sha256()
    for arc, path in sorted(files, key=lambda x: x[0]):
        payload_h.update(arc.encode("utf-8"))
        payload_h.update(b"\0")
        payload_h.update(path.read_bytes())
        payload_h.update(b"\0")
    payload_digest = payload_h.hexdigest()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arc, path in files:
            assert ".." not in Path(arc).parts
            zf.write(path, arcname=arc)
        manifest = {
            "schema": "NURION_ADAPT02_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R2",
            "stage": "ADAPT-02",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "AD2-G20": "HUMAN_FINAL_ONLY",
            "ADAPT-03": "LOCKED BY PREDECESSOR",
            "entries": sorted(a for a, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "upstreamProvenance": {
                "bodyCanonicalSpecSha256": "c73b5c540e29fcbf4ef4477c51f869eead9640194cec21110c6d60e55d1f900a",
                "axisRetargetConventionSha256": "19da5a00f4943a144426efaf675d364f64d244773dc60ede7db81be5bb8c6d9a",
                "provenanceReceipt": "evidence/NURION-ADAPT-02_UPSTREAM_PROVENANCE_RECEIPT.json",
            },
            "independentRun": {
                "cmd": "python repo/tools/run_adapt02_independent_proof.py",
                "also": "python repo/tools/run_adapt02_inspection_proof.py",
            },
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    digest = sha256_file(OUT)
    meta = {
        "schema": "NURION_ADAPT02_R2_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R2",
        "zip": str(OUT),
        "finalAuditZipSha256": digest,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD2-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-03": "LOCKED BY PREDECESSOR",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "authoritativeBodySpecSha256": "c73b5c540e29fcbf4ef4477c51f869eead9640194cec21110c6d60e55d1f900a",
        "authoritativeAxisSha256": "19da5a00f4943a144426efaf675d364f64d244773dc60ede7db81be5bb8c6d9a",
        "provenanceNote": "Pins + snapshot digests in binding/provenance; extracted package validates without full upstream files",
    }
    (EV / "NURION-ADAPT-02_R2_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-ADAPT-02_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R2",
                "finalAuditZipSha256": digest,
                "payloadCanonicalDigest": payload_digest,
                "byteLength": OUT.stat().st_size,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
