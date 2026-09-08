#!/usr/bin/env python3
"""Pack V2-CR-01 R2 Human Audit ZIP — self-contained prototype proof (CR01-G01…G19)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr01"
FIX = ROOT / "fast_track/v2_cr01/fixtures"
SEM = ROOT / "fast_track/working/adaptation_engine_v2/semantic"
RAAT = ROOT / "fast_track/working/raat01/evidence"
IDLE15 = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
OUT = EV / "NURION-V2-CR01_prototype_proof_R2.zip"

EXCLUDE = {
    "NURION-V2-CR01_R1_audit_zip_receipt.json",
    "NURION-V2-CR01_R2_audit_zip_receipt.json",
    "NURION-V2-CR01_final_zip_sha_EXTERNAL.json",
}

IDLE15_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"

REPO_FILES = [
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/classifier.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/adaptation/inspector.py",
    "fast_track/adaptation/semantic_candidates.py",
    "fast_track/v2_cr01/__init__.py",
    "fast_track/v2_cr01/audit_paths.py",
    "fast_track/v2_cr01/flexible_adapter.py",
    "fast_track/v2_cr01/retarget_safety.py",
    "fast_track/v2_cr01/semantic_assignment.py",
    "fast_track/v2_cr01/skeleton_inspection.py",
    "fast_track/v2_cr01/torso_chain.py",
    "tools/build_v2_cr01_fixtures.py",
    "tools/run_v2_cr01_prototype_proof.py",
    "tools/run_v2_cr01_independent_proof.py",
    "tools/pack_v2_cr01_prototype_proof_zip.py",
]

HUMAN_README = """# V2-CR-01 Human Audit ZIP (R2)

## R2 scope (ambiguity hardening only)

R1 Human Audit BLOCKED on: `SHOULDER_SIDE_AMBIGUOUS` did not fail-closed.

R2 fixes:
- `SHOULDER_SIDE_AMBIGUOUS` → blocker (no `shoulder_cands[0/1]` fallback)
- G13 negative fixtures: ambiguous shoulder, multiple pelvis, multiple head

V1 mutation: **NONE**

## Authority (do not exceed on PASS)

- V2-CR-01 R1 SPEC = HUMAN REVIEW PASS / APPROVED
- V2-CR-01 = OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT
- CR01-P01…P05 = AUTOMATED PROOF VERIFIED (re-verify in Human Audit)
- CR01-P06 / CR01-G20 = HUMAN_FINAL_ONLY
- NURION ADAPTATION ENGINE V2 = NOT OPEN
- Engine V1 = CLOSED / PASS / CONSUME ONLY

Human PASS ceiling: **PROTOTYPE HUMAN PASS / TECHNICAL BASIS CONFIRMED** — not V2 engine open.

## Independent proof

```bash
python repo/tools/run_v2_cr01_independent_proof.py
```

Expected: exit 0, CR01-G01…G19 PASS, CR01-G20 = HUMAN_FINAL_ONLY.

## G13 — Ambiguity Fail-Closed (priority for R2 re-audit)

Verify all four cases in gate matrix:
1. `counter_spine_name_no_shoulders.glb` — named Spine rejected
2. `counter_ambiguous_shoulder_side.glb` — **SHOULDER_SIDE_AMBIGUOUS → BLOCKED**
3. `counter_multiple_pelvis.glb` — **MULTIPLE_PELVIS_CANDIDATES → BLOCKED**
4. `counter_multiple_head.glb` — **MULTIPLE_HEAD_CANDIDATES → BLOCKED**

## Human blockers (instant BLOCK)

- Idle_15 SHA special-case in adapter code
- Idle_15 bone lookup table
- Spine02/Spine01/Spine fixed order mapping
- Alias-first topology bypass
- Ambiguous topology guessing (including shoulder side fallback)
- Source skeleton rewrite
- V1 modification
- Nondeterministic mapping
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    from tools.build_v2_cr01_fixtures import main as build_fix
    from tools.run_v2_cr01_prototype_proof import run_all

    build_fix()
    summary = run_all(ROOT / "tools/run_v2_cr01_prototype_proof.py")

    if summary.get("status") != "READY_FOR_HUMAN_AUDIT":
        raise SystemExit("proof not READY_FOR_HUMAN_AUDIT before pack")
    digest = summary["idle15"]["semanticAdapterDigest"]

    if not IDLE15.is_file():
        raise FileNotFoundError(IDLE15)
    if sha256_file(IDLE15) != IDLE15_SHA:
        raise SystemExit("Idle_15 SHA mismatch before pack")

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
        "NURION_ADAPTATION_ENGINE_V2_CR01_FLEXIBLE_MESHY_SKELETON_SEMANTIC_ADAPTER_V1.json",
        "NURION_ADAPTATION_ENGINE_V2_TRACK_V1.json",
    ):
        add(f"semantic/{name}", SEM / name)

    for p in sorted(EV.glob("NURION-V2-CR01*.json")):
        if p.name in EXCLUDE:
            continue
        add(f"evidence/{p.name}", p)

    for name in (
        "NURION-MESHY-COMPATIBILITY-GAP-01.json",
        "NURION-MESHY-IDLE15_SEMANTIC_ADAPTER_ANALYSIS.json",
    ):
        add(f"reference/{name}", RAAT / name)

    for p in sorted(REP.glob("*.json")):
        add(f"reports/{p.name}", p)

    for p in sorted(FIX.iterdir()):
        if p.is_file():
            add(f"fixtures/{p.name}", p)

    add("assets/Idle_15_withSkin_WORKING_BASELINE.glb", IDLE15)

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
            "schema": "NURION_V2_CR01_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R2",
            "changeRequestId": "V2-CR-01",
            "r1HumanAuditBlocked": "SHOULDER_SIDE_AMBIGUOUS DOES NOT FAIL CLOSED",
            "r2Scope": "AMBIGUITY_HARDENING_ONLY",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "CR01-G20": "HUMAN_FINAL_ONLY",
            "CR01-P06": "HUMAN_FINAL_ONLY",
            "v2Engine": "NOT OPEN",
            "engineV1": "CLOSED / PASS / CONSUME ONLY",
            "idle15Sha256": IDLE15_SHA,
            "semanticAdapterDigest": digest,
            "entries": sorted(a for a, _, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {
                "cmd": "python repo/tools/run_v2_cr01_independent_proof.py",
                "also": "python repo/tools/run_v2_cr01_prototype_proof.py",
            },
            "humanBlockers": [
                "Idle_15 SHA special-case",
                "Idle_15 bone lookup table",
                "Spine02/Spine01/Spine fixed order",
                "alias-first topology bypass",
                "ambiguous topology guessing",
                "source skeleton rewrite",
                "V1 modification",
                "nondeterministic mapping",
            ],
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    zip_sha = sha256_file(OUT)
    meta = {
        "schema": "NURION_V2_CR01_R2_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R2",
        "changeRequestId": "V2-CR-01",
        "zip": str(OUT),
        "finalAuditZipSha256": zip_sha,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "CR01-G20": "HUMAN_FINAL_ONLY",
        "CR01-P06": "HUMAN_FINAL_ONLY",
        "v2Engine": "NOT OPEN",
        "idle15Sha256": IDLE15_SHA,
        "semanticAdapterDigest": digest,
        "humanPassCeiling": "PROTOTYPE HUMAN PASS / TECHNICAL BASIS CONFIRMED",
    }
    (EV / "NURION-V2-CR01_R2_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR01_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R2",
                "finalAuditZipSha256": zip_sha,
                "payloadCanonicalDigest": payload_digest,
                "byteLength": OUT.stat().st_size,
                "semanticAdapterDigest": digest,
                "idle15Sha256": IDLE15_SHA,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory(prefix="v2cr01_audit_") as tmp:
        extract = Path(tmp) / "extract"
        extract.mkdir()
        with zipfile.ZipFile(OUT, "r") as zf:
            zf.extractall(extract)
        proof = extract / "repo/tools/run_v2_cr01_independent_proof.py"
        if not proof.is_file():
            raise SystemExit("extracted independent proof runner missing")
        result = subprocess.run([sys.executable, str(proof)], cwd=str(extract), check=False, capture_output=True, text=True)
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"extracted independent proof failed: exit {result.returncode}")

    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
