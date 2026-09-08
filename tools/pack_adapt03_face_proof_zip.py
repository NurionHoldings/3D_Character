#!/usr/bin/env python3
"""Pack ADAPT-03 R1 audit ZIP — self-contained with pinned FACE upstream provenance."""

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
REP = ROOT / "fast_track/working/adaptation_engine_v1/reports_adapt03"
FIX = ROOT / "fast_track/adaptation/fixtures_adapt03"
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
OUT = EV / "NURION-ADAPT-03_face_expression_proof_R1.zip"

EXCLUDE = {
    "NURION-ADAPT-03_R1_audit_zip_receipt.json",
    "NURION-ADAPT-03_final_zip_sha_EXTERNAL.json",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    from tools.build_adapt03_authoritative_binding import main as build_binding
    from tools.run_adapt03_face_adaptation_proof import run_all

    build_binding()
    run_all()

    files: list[tuple[str, Path]] = []
    for name in (
        "NURION_ADAPT03_FACE_EXPRESSION_ADAPTATION_CONTRACT_V1.json",
        "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json",
        "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json",
        "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json",
        "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json",
        "NURION_ADAPTATION_ENGINE_TRACK_V1.json",
        "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
    ):
        p = SEM / name
        if p.exists():
            files.append((f"semantic/{name}", p))
    for p in sorted(EV.glob("NURION-ADAPT-03*.json")):
        if p.name in EXCLUDE:
            continue
        files.append((f"evidence/{p.name}", p))
    for receipt in (
        "NURION-ADAPT-01_PASS_receipt.json",
        "NURION-ADAPT-02_PASS_receipt.json",
    ):
        p = EV / receipt
        if p.exists():
            files.append((f"evidence/{receipt}", p))
    for p in sorted(REP.glob("ADAPT03_report_*.json")):
        files.append((f"reports/{p.name}", p))
    for p in sorted(FIX.iterdir()):
        if p.is_file():
            files.append((f"fixtures/{p.name}", p))
    for rel in [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/authoritative_binding.py",
        "fast_track/adaptation/authoritative_face_binding.py",
        "fast_track/adaptation/glb_io.py",
        "fast_track/adaptation/semantic_candidates.py",
        "fast_track/adaptation/classifier.py",
        "fast_track/adaptation/inspector.py",
        "fast_track/adaptation/skeleton_mapping.py",
        "fast_track/adaptation/face_adaptation.py",
        "tools/build_adapt01_fixtures.py",
        "tools/build_adapt02_fixtures.py",
        "tools/build_adapt03_fixtures.py",
        "tools/build_adapt03_authoritative_binding.py",
        "tools/run_adapt03_face_adaptation_proof.py",
        "tools/run_adapt03_independent_proof.py",
        "tools/pack_adapt03_face_proof_zip.py",
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
            "schema": "NURION_ADAPT03_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R1",
            "stage": "ADAPT-03",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "AD3-G20": "HUMAN_FINAL_ONLY",
            "ADAPT-04": "LOCKED BY PREDECESSOR",
            "entries": sorted(a for a, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "upstreamProvenance": {
                "faceProductLockSha256": "07830e1c34ce79b1d9ff9fc15a8b456ef7e3438d05ae7709d3515c00baebcf06",
                "provenanceReceipt": "evidence/NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json",
            },
            "independentRun": {
                "cmd": "python repo/tools/run_adapt03_independent_proof.py",
                "also": "python repo/tools/run_adapt03_face_adaptation_proof.py",
            },
            "nurionV1Mutation": "NONE",
            "adapt01Mutation": "NONE",
            "adapt02Mutation": "NONE",
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    digest = sha256_file(OUT)
    meta = {
        "schema": "NURION_ADAPT03_R1_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R1",
        "zip": str(OUT),
        "finalAuditZipSha256": digest,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD3-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-04": "LOCKED BY PREDECESSOR",
        "nurionV1Mutation": "NONE",
        "adapt01Mutation": "NONE",
        "adapt02Mutation": "NONE",
    }
    (EV / "NURION-ADAPT-03_R1_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-ADAPT-03_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R1",
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
