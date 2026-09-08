#!/usr/bin/env python3
"""Pack V2-CR-02 R2 Human Audit ZIP — actual facial deformation (GLB-measured)."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr02"
SEM = ROOT / "fast_track/working/adaptation_engine_v2/semantic"
DER = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02"
IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
OUT = EV / "NURION-V2-CR02_R2_actual_facial_deformation_proof.zip"

EXCLUDE = {
    "NURION-V2-CR02_R2_audit_zip_receipt.json",
    "NURION-V2-CR02_R2_final_zip_sha_EXTERNAL.json",
}

IDLE15_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"
DERIVED_SHA = "1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd"

REPO_FILES = [
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/classifier.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/adaptation/inspector.py",
    "fast_track/adaptation/semantic_candidates.py",
    "fast_track/v2_cr02/__init__.py",
    "fast_track/v2_cr02/facial_deformation.py",
    "fast_track/v2_cr02/r2_independent_gates.py",
    "tools/run_v2_cr02_r2_independent_proof.py",
    "tools/run_v2_cr02_r2_facial_deformation_proof.py",
    "tools/pack_v2_cr02_r2_deformation_proof_zip.py",
]

HUMAN_README = """# V2-CR-02 R2 Human Audit — Actual Facial Deformation

## Authority

- V2-CR-02 R1 = HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED
- V2-CR-02 R2 = OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT
- Agent digests = REPORTED ONLY until Human PASS
- CR02-R2-G20 = HUMAN_FINAL_ONLY
- NURION ADAPTATION ENGINE V2 = NOT OPEN

## Independent proof (REQUIRED)

```bash
python repo/tools/run_v2_cr02_r2_independent_proof.py
```

This runner **must not** trust report JSON PASS fields.
It reads GLB BIN → accessors → morph target POSITION → computes:

activated = V0 + morphDelta * 1.0
restored  = V0 + morphDelta * 0.0
maxNorm(activated - V0) > 1e-4
maxNorm(restored - V0) <= 1e-6

## Gates G05–G15

Blink_L/R, Jaw, SMILE/BROW_UP/FROWN, AA/OH/EE — actual POSITION Δ
G14: AA≠OH≠EE geometrically (delta vectors)
G16: Blink L/R laterality (cross-contamination check)
G17: BODY base POSITION / JOINTS / WEIGHTS unchanged

## R1 blocker under test

AUXILIARY_CONTROL_METADATA_WITHOUT_ACTUAL_FACIAL_DEFORMATION
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    # Refresh independent proof before pack
    from tools.run_v2_cr02_r2_independent_proof import main as indep_main

    rc = indep_main()
    if rc != 0:
        raise SystemExit("independent proof failed before pack")

    seal = json.loads((EV / "NURION-V2-CR02_R2_READY_FOR_HUMAN_AUDIT_receipt.json").read_text(encoding="utf-8"))
    if seal.get("status") != "READY_FOR_HUMAN_AUDIT":
        raise SystemExit("not READY_FOR_HUMAN_AUDIT")

    if sha256_file(IDLE15) != IDLE15_SHA:
        raise SystemExit("Idle_15 SHA mismatch")
    if sha256_file(DER / "Idle_15_R2_facial_deformation.glb") != DERIVED_SHA:
        raise SystemExit("R2 derived SHA mismatch")

    files: list[tuple[str, Path | None, str | None]] = []
    seen: set[str] = set()

    def add(arc: str, path: Path) -> None:
        if arc in seen or not path.is_file():
            return
        seen.add(arc)
        files.append((arc, path, None))

    def add_text(arc: str, text: str) -> None:
        if arc in seen:
            return
        seen.add(arc)
        files.append((arc, None, text))

    for name in (
        "NURION_ADAPTATION_ENGINE_V2_CR02_R2_ACTUAL_FACIAL_DEFORMATION_HARDENING_V1.json",
        "NURION_ADAPTATION_ENGINE_V2_TRACK_V1.json",
    ):
        add(f"semantic/{name}", SEM / name)

    for p in sorted(EV.glob("NURION-V2-CR02_R*.json")):
        if p.name in EXCLUDE:
            continue
        add(f"evidence/{p.name}", p)
    add("evidence/NURION-V2-CR02_R1_HUMAN_AUDIT_BLOCKED_receipt.json", EV / "NURION-V2-CR02_R1_HUMAN_AUDIT_BLOCKED_receipt.json")
    add("evidence/NURION-V2-CR02_R2_OPEN_PROTOTYPE_receipt.json", EV / "NURION-V2-CR02_R2_OPEN_PROTOTYPE_receipt.json")
    add("evidence/NURION-V2-CR02_R2_DEFORMATION_PROOF_PASS_receipt.json", EV / "NURION-V2-CR02_R2_DEFORMATION_PROOF_PASS_receipt.json")
    add("evidence/NURION-V2-CR02_R2_READY_FOR_HUMAN_AUDIT_receipt.json", EV / "NURION-V2-CR02_R2_READY_FOR_HUMAN_AUDIT_receipt.json")

    for name in (
        "V2_CR02_R2_facial_deformation_idle15.json",
        "V2_CR02_R2_independent_gate_matrix.json",
    ):
        add(f"reports/{name}", REP / name)

    add("assets/Idle_15_withSkin_WORKING_BASELINE.glb", IDLE15)
    add("derived/Idle_15_R2_facial_deformation.glb", DER / "Idle_15_R2_facial_deformation.glb")

    for rel in REPO_FILES:
        p = ROOT / rel
        if p.exists():
            add(f"repo/{rel.replace(chr(92), '/')}", p)

    add_text("HUMAN_AUDIT_README.md", HUMAN_README)

    payload_h = hashlib.sha256()
    for arc, path, text in sorted(files, key=lambda x: x[0]):
        payload_h.update(arc.encode("utf-8"))
        payload_h.update(b"\0")
        payload_h.update(path.read_bytes() if path else text.encode("utf-8"))
        payload_h.update(b"\0")
    payload_digest = payload_h.hexdigest()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for arc, path, text in files:
            assert ".." not in Path(arc).parts
            if path:
                zf.write(path, arcname=arc)
            else:
                zf.writestr(arc, text)
        manifest = {
            "schema": "NURION_V2_CR02_R2_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R2",
            "changeRequestId": "V2-CR-02",
            "title": "ACTUAL FACIAL DEFORMATION PROOF",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "CR02-R2-G20": "HUMAN_FINAL_ONLY",
            "r1Status": "HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED",
            "r1Blocker": "AUXILIARY_CONTROL_METADATA_WITHOUT_ACTUAL_FACIAL_DEFORMATION",
            "v2Engine": "NOT OPEN",
            "idle15Sha256": IDLE15_SHA,
            "derivedSha256": DERIVED_SHA,
            "independentProofDigest": seal.get("independentProofDigest"),
            "agentReportedProofDigest": seal.get("agentReportedProofDigest"),
            "agentReportedOnly": True,
            "thresholds": seal.get("thresholds"),
            "measurementPolicy": "GLB morph POSITION only — report JSON PASS not trusted",
            "entries": sorted(a for a, _, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {"cmd": "python repo/tools/run_v2_cr02_r2_independent_proof.py"},
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    zip_sha = sha256_file(OUT)
    meta = {
        "schema": "NURION_V2_CR02_R2_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R2",
        "changeRequestId": "V2-CR-02",
        "zip": str(OUT),
        "finalAuditZipSha256": zip_sha,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "CR02-R2-G20": "HUMAN_FINAL_ONLY",
        "independentProofDigest": seal.get("independentProofDigest"),
        "agentReportedProofDigest": seal.get("agentReportedProofDigest"),
        "agentReportedOnly": True,
        "derivedSha256": DERIVED_SHA,
        "v2Engine": "NOT OPEN",
        "humanPassCeiling": "PROTOTYPE HUMAN PASS / TECHNICAL BASIS CONFIRMED — NOT V2 ENGINE OPEN",
    }
    (EV / "NURION-V2-CR02_R2_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR02_R2_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R2",
                "finalAuditZipSha256": zip_sha,
                "payloadCanonicalDigest": payload_digest,
                "byteLength": OUT.stat().st_size,
                "independentProofDigest": seal.get("independentProofDigest"),
                "agentReportedProofDigest": seal.get("agentReportedProofDigest"),
                "derivedSha256": DERIVED_SHA,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory(prefix="v2cr02_r2_") as tmp:
        extract = Path(tmp) / "extract"
        extract.mkdir()
        with zipfile.ZipFile(OUT, "r") as zf:
            zf.extractall(extract)
        proof = extract / "repo/tools/run_v2_cr02_r2_independent_proof.py"
        result = subprocess.run(
            [sys.executable, str(proof)], cwd=str(extract), check=False, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"extracted independent proof failed: {result.returncode}")

    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
