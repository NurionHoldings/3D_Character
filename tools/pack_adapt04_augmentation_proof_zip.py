#!/usr/bin/env python3
"""Pack ADAPT-04 R2 audit ZIP — self-contained with ADAPT-03 FACE upstream provenance."""

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
REP = ROOT / "fast_track/working/adaptation_engine_v1/reports_adapt04"
FIX = ROOT / "fast_track/adaptation/fixtures_adapt04"
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
OUT = EV / "NURION-ADAPT-04_auxiliary_rig_proof_R2.zip"

EXCLUDE = {
    "NURION-ADAPT-04_R1_audit_zip_receipt.json",
    "NURION-ADAPT-04_R2_audit_zip_receipt.json",
    "NURION-ADAPT-04_final_zip_sha_EXTERNAL.json",
}

# Immutable upstream audit dependencies — authoritative bytes preserved, not recreated
IMMUTABLE_EVIDENCE = (
    "NURION-ADAPT-01_PASS_receipt.json",
    "NURION-ADAPT-02_PASS_receipt.json",
    "NURION-ADAPT-03_PASS_receipt.json",
    "NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json",
    "NURION-ADAPT-04_UPSTREAM_PROVENANCE_RECEIPT.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    from tools.build_adapt04_authoritative_binding import main as build_binding
    from tools.run_adapt04_augmentation_proof import run_all

    build_binding()
    summary = run_all()

    files: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(arc: str, path: Path) -> None:
        if arc in seen:
            return
        seen.add(arc)
        files.append((arc, path))

    for name in (
        "NURION_ADAPT04_AUXILIARY_RIG_AUGMENTATION_CONTRACT_V1.json",
        "NURION_ADAPT04_REQUIREMENT_BINDING_V1.json",
        "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json",
        "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json",
        "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json",
        "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json",
        "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
        "NURION_ADAPTATION_ENGINE_TRACK_V1.json",
    ):
        p = SEM / name
        if p.exists():
            add(f"semantic/{name}", p)

    for p in sorted(EV.glob("NURION-ADAPT-04*.json")):
        if p.name in EXCLUDE:
            continue
        add(f"evidence/{p.name}", p)

    upstream_pins: dict[str, str] = {}
    for receipt in IMMUTABLE_EVIDENCE:
        p = EV / receipt
        if not p.is_file():
            raise FileNotFoundError(f"required immutable audit dependency missing: {p}")
        add(f"evidence/{receipt}", p)
        upstream_pins[receipt] = sha256_file(p)

    for p in sorted(REP.glob("ADAPT04_report_*.json")):
        add(f"reports/{p.name}", p)
    for p in sorted(FIX.iterdir()):
        if p.is_file():
            add(f"fixtures/{p.name}", p)
    for rel in [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/authoritative_binding.py",
        "fast_track/adaptation/authoritative_face_binding.py",
        "fast_track/adaptation/authoritative_augmentation_binding.py",
        "fast_track/adaptation/boundary_preservation.py",
        "fast_track/adaptation/deformation_binding.py",
        "fast_track/adaptation/eye_augmentation.py",
        "fast_track/adaptation/jaw_mouth_augmentation.py",
        "fast_track/adaptation/expression_augmentation.py",
        "fast_track/adaptation/talking_augmentation.py",
        "fast_track/adaptation/glb_io.py",
        "fast_track/adaptation/semantic_candidates.py",
        "fast_track/adaptation/classifier.py",
        "fast_track/adaptation/inspector.py",
        "fast_track/adaptation/skeleton_mapping.py",
        "fast_track/adaptation/face_adaptation.py",
        "fast_track/adaptation/auxiliary_augmentation.py",
        "tools/build_adapt01_fixtures.py",
        "tools/build_adapt02_fixtures.py",
        "tools/build_adapt03_fixtures.py",
        "tools/build_adapt04_fixtures.py",
        "tools/build_adapt04_authoritative_binding.py",
        "tools/run_adapt04_augmentation_proof.py",
        "tools/run_adapt04_independent_proof.py",
        "tools/pack_adapt04_augmentation_proof_zip.py",
    ]:
        p = ROOT / rel
        if p.exists():
            add(f"repo/{rel.replace(chr(92), '/')}", p)

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
            "schema": "NURION_ADAPT04_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R2",
            "stage": "ADAPT-04",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "AD4-G20": "HUMAN_FINAL_ONLY",
            "ADAPT-05": "LOCKED BY PREDECESSOR",
            "r2Repair": "Include immutable ADAPT-03 upstream provenance receipt for extracted FACE authority verification",
            "immutableUpstreamEvidence": list(IMMUTABLE_EVIDENCE),
            "upstreamEvidenceSha256": upstream_pins,
            "entries": sorted(a for a, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {
                "cmd": "python repo/tools/run_adapt04_independent_proof.py",
                "also": "python repo/tools/run_adapt04_augmentation_proof.py",
            },
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    digest = sha256_file(OUT)
    meta = {
        "schema": "NURION_ADAPT04_R2_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R2",
        "zip": str(OUT),
        "finalAuditZipSha256": digest,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD4-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-05": "LOCKED BY PREDECESSOR",
        "r1Blocker": "PROVENANCE_RECEIPT_MISSING — NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json absent from R1 extracted package",
        "r2Fix": "Immutable ADAPT-03 upstream provenance receipt included in evidence/",
        "adapt03PassReceiptSha256": upstream_pins["NURION-ADAPT-03_PASS_receipt.json"],
        "adapt03UpstreamProvenanceReceiptSha256": upstream_pins["NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json"],
        "adapt04UpstreamProvenanceReceiptSha256": upstream_pins["NURION-ADAPT-04_UPSTREAM_PROVENANCE_RECEIPT.json"],
        "augmentationPlanDigest": summary.get("augmentationPlanDigest"),
        "derivedSemanticDigest": summary.get("derivedSemanticDigest"),
    }
    (EV / "NURION-ADAPT-04_R2_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-ADAPT-04_final_zip_sha_EXTERNAL.json").write_text(
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

    ready = {
        "receiptId": "NURION-ADAPT-04_READY_FOR_HUMAN_AUDIT_R2",
        "revision": "R2",
        "status": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD4-G20": "HUMAN_FINAL_ONLY",
        "ADAPT-05": "LOCKED BY PREDECESSOR",
        "r1HumanAudit": "BLOCKED — extracted runners exit 1 PROVENANCE_RECEIPT_MISSING",
        "r2Fix": "ADAPT-03 upstream provenance receipt packaged",
    }
    (EV / "NURION-ADAPT-04_READY_FOR_HUMAN_AUDIT_receipt.json").write_text(
        json.dumps(ready, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
