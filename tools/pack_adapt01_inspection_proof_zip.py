#!/usr/bin/env python3
"""Pack ADAPT-01 R1 human audit ZIP — self-contained; final ZIP SHA is EXTERNAL ONLY."""

from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
EV = ROOT / "fast_track/working/adaptation_engine_v1/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v1/reports"
FIX = ROOT / "fast_track/adaptation/fixtures"
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
OUT = EV / "NURION-ADAPT-01_intake_inspection_proof_R1.zip"

# Must NOT be packed into the ZIP (final SHA lives only outside).
EXCLUDE_EVIDENCE_NAMES = {
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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    # Pre-pack READY receipt: no final ZIP SHA embedded
    ready = {
        "receiptId": "NURION-ADAPT-01_READY_FOR_HUMAN_AUDIT_R1",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-01",
        "revision": "R1",
        "status": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "AD1-G16": "HUMAN_FINAL_ONLY",
        "ADAPT-02": "NOT_STARTED",
        "nurionV1Mutation": "NONE",
        "blockerFix": {
            "B1": "Removed fast_track.runtime dependency; local canonical_sha256 only",
            "B2": "Final audit ZIP SHA is EXTERNAL_ONLY — not embedded inside ZIP payload",
        },
        "digestSemantics": {
            "payloadCanonicalDigest": "SEE_MANIFEST_FIELD_payloadCanonicalDigest",
            "finalAuditZipSha256": "EXTERNAL_ONLY — NURION-ADAPT-01_R1_audit_zip_receipt.json beside ZIP",
            "r0Mismatch": (
                "R0 recorded e3a7… inside READY while submitted ZIP was 161676… "
                "(self-referential re-pack). Corrected in R1."
            ),
        },
        "auditZipRel": "NURION-ADAPT-01_intake_inspection_proof_R1.zip",
        "finalAuditZipSha256": None,
        "note": "Do not treat null finalAuditZipSha256 inside ZIP as failure — see external receipt.",
    }
    (EV / "NURION-ADAPT-01_READY_FOR_HUMAN_AUDIT_receipt.json").write_text(
        json.dumps(ready, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    files: list[tuple[str, Path]] = []
    for p in sorted(SEM.glob("*.json")):
        files.append((f"semantic/{p.name}", p))
    for p in sorted(EV.glob("NURION-ADAPT-01*.json")):
        if p.name in EXCLUDE_EVIDENCE_NAMES:
            continue
        files.append((f"evidence/{p.name}", p))
    for p in sorted(REP.glob("ADAPT01_report_*.json")):
        files.append((f"reports/{p.name}", p))
    for p in sorted(FIX.iterdir()):
        if p.is_file():
            files.append((f"fixtures/{p.name}", p))
    for rel in [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/glb_io.py",
        "fast_track/adaptation/semantic_candidates.py",
        "fast_track/adaptation/classifier.py",
        "fast_track/adaptation/inspector.py",
        "tools/build_adapt01_fixtures.py",
        "tools/run_adapt01_inspection_proof.py",
        "tools/run_adapt01_independent_proof.py",
        "tools/pack_adapt01_inspection_proof_zip.py",
    ]:
        p = ROOT / rel
        if p.exists():
            files.append((f"repo/{rel.replace(chr(92), '/')}", p))

    # Payload digest = ordered concatenation of arcname + file bytes (pre-zip)
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
            assert not arc.startswith("/") and ".." not in Path(arc).parts
            zf.write(path, arcname=arc)
        manifest = {
            "schema": "NURION_ADAPT01_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R1",
            "stage": "ADAPT-01",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "AD1-G16": "HUMAN_FINAL_ONLY",
            "ADAPT-02": "NOT_STARTED",
            "entries": sorted(a for a, _ in files),
            "nurionV1Mutation": "NONE",
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {
                "fromExtractRoot": "python repo/tools/run_adapt01_independent_proof.py",
                "also": "python repo/tools/run_adapt01_inspection_proof.py",
                "requires": "stdlib + packaged repo/fast_track/adaptation only",
            },
            "digestSemantics": {
                "payloadCanonicalDigest": "pre-zip sealed payload identity",
                "finalAuditZipSha256": "computed after ZIP seal; recorded only in external receipt",
            },
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    digest = sha256_file(OUT)
    meta = {
        "schema": "NURION_ADAPT01_R1_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R1",
        "zip": str(OUT),
        "zipRel": "fast_track/working/adaptation_engine_v1/evidence/NURION-ADAPT-01_intake_inspection_proof_R1.zip",
        "finalAuditZipSha256": digest,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD1-G16": "HUMAN_FINAL_ONLY",
        "ADAPT-02": "NOT_STARTED",
        "nurionV1Mutation": "NONE",
        "provenanceNote": (
            "finalAuditZipSha256 is authoritative and EXTERNAL to the ZIP. "
            "Inside-ZIP READY.finalAuditZipSha256 is null by design (no self-hash)."
        ),
        "r0MismatchCorrected": {
            "r0EmbeddedReadySha": "e3a7aeb0ef0c92078206127dfa22b802427315f03d44f0b48c877ae8458186cc",
            "r0SubmittedZipSha": "161676ea894e891921182dcaa9daff92b09c3c18b227e21f569f1f4cc5027be9",
            "cause": "READY updated after pack then re-packed; embedded SHA could not equal final ZIP",
            "r1Rule": "Never embed final ZIP SHA inside ZIP payload files",
        },
    }
    (EV / "NURION-ADAPT-01_R1_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    # Convenience alias for auditors
    (EV / "NURION-ADAPT-01_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "finalAuditZipSha256": digest,
                "payloadCanonicalDigest": payload_digest,
                "zip": str(OUT),
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
