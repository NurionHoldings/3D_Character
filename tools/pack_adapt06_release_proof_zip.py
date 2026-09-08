#!/usr/bin/env python3
"""Pack ADAPT-06 R1 audit ZIP — adapted character release seal."""

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
REP06 = ROOT / "fast_track/working/adaptation_engine_v1/reports_adapt06"
REP05 = ROOT / "fast_track/working/adaptation_engine_v1/reports_adapt05"
FIX = ROOT / "fast_track/adaptation/fixtures_adapt06"
SEM = ROOT / "fast_track/working/adaptation_engine_v1/semantic"
OUT = EV / "NURION-ADAPT-06_release_proof_R1.zip"

EXCLUDE = {
    "NURION-ADAPT-06_R1_audit_zip_receipt.json",
    "NURION-ADAPT-06_final_zip_sha_EXTERNAL.json",
}

IMMUTABLE_EVIDENCE = (
    "NURION-ADAPT-01_PASS_receipt.json",
    "NURION-ADAPT-02_PASS_receipt.json",
    "NURION-ADAPT-03_PASS_receipt.json",
    "NURION-ADAPT-03_UPSTREAM_PROVENANCE_RECEIPT.json",
    "NURION-ADAPT-04_PASS_receipt.json",
    "NURION-ADAPT-04_UPSTREAM_PROVENANCE_RECEIPT.json",
    "NURION-ADAPT-05_PASS_receipt.json",
    "NURION-ADAPT-05_UPSTREAM_PROVENANCE_RECEIPT.json",
    "NURION-ADAPT-05_CANONICAL_QUALIFICATION_SEAL.json",
    "NURION-ADAPT-06_UPSTREAM_PROVENANCE_RECEIPT.json",
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    from tools.build_adapt06_authoritative_binding import main as build_binding
    from tools.run_adapt06_release_proof import run_all

    build_binding()
    summary = run_all()

    seal_path = EV / "NURION-ADAPT-06_CANONICAL_RELEASE_SEAL.json"
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    for key in (
        "releaseReportDigest",
        "finalReleaseDigest",
        "candidateSha256",
        "qualificationReportDigest",
        "runtimeCompatibilityDigest",
        "adapt05HandoffDigest",
    ):
        if summary.get("canonicalSeal", {}).get(key) != seal.get(key):
            raise SystemExit(f"seal mismatch before pack: {key}")
    g19 = (summary.get("gates") or {}).get("AD6-G19") or {}
    if g19.get("releaseReportDigest") != seal["releaseReportDigest"]:
        raise SystemExit("G19 seal mismatch before pack")

    files: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(arc: str, path: Path) -> None:
        if arc in seen or not path.is_file():
            return
        seen.add(arc)
        files.append((arc, path))

    for name in (
        "NURION_ADAPT06_ADAPTED_CHARACTER_RELEASE_CONTRACT_V1.json",
        "NURION_ADAPT06_RELEASE_AUTHORITY_BINDING_V1.json",
        "NURION_ADAPT05_RUNTIME_QUALIFICATION_CONTRACT_V1.json",
        "NURION_ADAPT05_RUNTIME_AUTHORITY_BINDING_V1.json",
        "NURION_ADAPT04_REQUIREMENT_BINDING_V1.json",
        "NURION_ADAPT04_AUXILIARY_RIG_AUGMENTATION_CONTRACT_V1.json",
        "NURION_ADAPT03_CANONICAL_FACE_BINDING_V1.json",
        "NURION_ADAPT03_FACE_SEMANTIC_SNAPSHOT_V1.json",
        "NURION_ADAPT03_ATTACHMENT_SNAPSHOT_V1.json",
        "NURION_ADAPT03_EYE_TALKING_SNAPSHOT_V1.json",
        "NURION_ADAPT02_CANONICAL_BODY_BINDING_V1.json",
        "NURION_ADAPTATION_ENGINE_TRACK_V1.json",
    ):
        add(f"semantic/{name}", SEM / name)

    for p in sorted(EV.glob("NURION-ADAPT-06*.json")):
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

    for p in sorted(REP06.glob("ADAPT06_report_*.json")):
        add(f"reports/{p.name}", p)
    add("reports/ADAPT05_report_canonical_qualified.json", REP05 / "ADAPT05_report_canonical_qualified.json")

    for p in sorted(FIX.iterdir()):
        if p.is_file():
            add(f"fixtures/{p.name}", p)

    for rel in [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/authoritative_binding.py",
        "fast_track/adaptation/authoritative_face_binding.py",
        "fast_track/adaptation/authoritative_augmentation_binding.py",
        "fast_track/adaptation/authoritative_runtime_qualification_binding.py",
        "fast_track/adaptation/authoritative_release_binding.py",
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
        "fast_track/adaptation/structural_qualifier.py",
        "fast_track/adaptation/face_capability_qualifiers.py",
        "fast_track/adaptation/runtime_compatibility_qualifiers.py",
        "fast_track/adaptation/qualification_classifier.py",
        "fast_track/adaptation/adapt06_handoff.py",
        "fast_track/adaptation/runtime_qualification.py",
        "fast_track/adaptation/character_release.py",
        "fast_track/adaptation/release_classifier.py",
        "tools/build_adapt01_fixtures.py",
        "tools/build_adapt02_fixtures.py",
        "tools/build_adapt03_fixtures.py",
        "tools/build_adapt04_fixtures.py",
        "tools/build_adapt04_authoritative_binding.py",
        "tools/build_adapt05_fixtures.py",
        "tools/build_adapt05_authoritative_binding.py",
        "tools/build_adapt06_fixtures.py",
        "tools/build_adapt06_authoritative_binding.py",
        "tools/run_adapt06_release_proof.py",
        "tools/run_adapt06_independent_proof.py",
        "tools/pack_adapt06_release_proof_zip.py",
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
            "schema": "NURION_ADAPT06_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R1",
            "stage": "ADAPT-06",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "AD6-G20": "HUMAN_FINAL_ONLY",
            "canonicalSeal": {
                "candidateSha256": seal["candidateSha256"],
                "qualificationReportDigest": seal["qualificationReportDigest"],
                "runtimeCompatibilityDigest": seal["runtimeCompatibilityDigest"],
                "adapt05HandoffDigest": seal["adapt05HandoffDigest"],
                "releaseReportDigest": seal["releaseReportDigest"],
                "finalReleaseDigest": seal["finalReleaseDigest"],
            },
            "adapt05CanonicalSealPinned": True,
            "immutableUpstreamEvidence": list(IMMUTABLE_EVIDENCE),
            "upstreamEvidenceSha256": upstream_pins,
            "entries": sorted(a for a, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {
                "cmd": "python repo/tools/run_adapt06_independent_proof.py",
                "also": "python repo/tools/run_adapt06_release_proof.py",
            },
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    digest = sha256_file(OUT)
    meta = {
        "schema": "NURION_ADAPT06_R1_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R1",
        "zip": str(OUT),
        "finalAuditZipSha256": digest,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "AD6-G20": "HUMAN_FINAL_ONLY",
        "candidateSha256": seal["candidateSha256"],
        "qualificationReportDigest": seal["qualificationReportDigest"],
        "runtimeCompatibilityDigest": seal["runtimeCompatibilityDigest"],
        "adapt05HandoffDigest": seal["adapt05HandoffDigest"],
        "releaseReportDigest": seal["releaseReportDigest"],
        "finalReleaseDigest": seal["finalReleaseDigest"],
    }
    (EV / "NURION-ADAPT-06_R1_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-ADAPT-06_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R1",
                "finalAuditZipSha256": digest,
                "payloadCanonicalDigest": payload_digest,
                "byteLength": OUT.stat().st_size,
                "releaseReportDigest": seal["releaseReportDigest"],
                "finalReleaseDigest": seal["finalReleaseDigest"],
                "candidateSha256": seal["candidateSha256"],
                "qualificationReportDigest": seal["qualificationReportDigest"],
                "adapt05HandoffDigest": seal["adapt05HandoffDigest"],
                "runtimeCompatibilityDigest": seal["runtimeCompatibilityDigest"],
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
