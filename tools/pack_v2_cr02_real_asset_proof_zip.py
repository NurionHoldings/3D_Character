#!/usr/bin/env python3
"""Pack V2-CR-02 R1 Human Audit ZIP — Idle_15 end-to-end real-asset proof."""

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
CR01_EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
OUT = EV / "NURION-V2-CR02_idle15_real_asset_proof_R1.zip"

EXCLUDE = {
    "NURION-V2-CR02_R1_audit_zip_receipt.json",
    "NURION-V2-CR02_final_zip_sha_EXTERNAL.json",
}

IDLE15_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"

REPO_FILES = [
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/classifier.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/adaptation/inspector.py",
    "fast_track/adaptation/semantic_candidates.py",
    "fast_track/v2_cr01/__init__.py",
    "fast_track/v2_cr01/flexible_adapter.py",
    "fast_track/v2_cr01/retarget_safety.py",
    "fast_track/v2_cr01/semantic_assignment.py",
    "fast_track/v2_cr01/skeleton_inspection.py",
    "fast_track/v2_cr01/torso_chain.py",
    "fast_track/v2_cr02/__init__.py",
    "fast_track/v2_cr02/audit_paths.py",
    "fast_track/v2_cr02/capability_gap.py",
    "fast_track/v2_cr02/augmentation_plan.py",
    "fast_track/v2_cr02/eye_blink_augmentation.py",
    "fast_track/v2_cr02/jaw_expression_talking.py",
    "fast_track/v2_cr02/runtime_coexistence.py",
    "fast_track/v2_cr02/real_asset_proof.py",
    "tools/run_v2_cr02_p06_real_asset_proof.py",
    "tools/run_v2_cr02_independent_proof.py",
    "tools/pack_v2_cr02_real_asset_proof_zip.py",
]

HUMAN_README = """# V2-CR-02 Human Audit ZIP (R1) — Idle_15 End-to-End Real-Asset Proof

## Authority (do not exceed)

- V2-CR-02 R1 SPEC = HUMAN REVIEW PASS / APPROVED
- V2-CR-02 = OPEN / PROTOTYPE / **READY_FOR_HUMAN_AUDIT**
- CR02-P01…P06 = AUTOMATED PROOF VERIFIED (re-verify independently)
- CR02-P07 / CR02-G20 = **HUMAN_FINAL_ONLY**
- V2-CR-01 = CONSUME ONLY
- NURION ADAPTATION ENGINE V2 = **NOT OPEN**
- Engine V1 = CLOSED / PASS / CONSUME ONLY

Human PASS ceiling: **PROTOTYPE HUMAN PASS / TECHNICAL BASIS CONFIRMED** — not V2 engine open.

## Independent proof

```bash
python repo/tools/run_v2_cr02_independent_proof.py
```

Expected: exit 0, CR02-G01…G19 PASS, CR02-G20 = HUMAN_FINAL_ONLY.

## Provenance chain (verify)

Idle_15 ORIGINAL → CR01 → P01 Gap → P02 Plan → P03 Eye/Blink → P04 Jaw/Expr/TALKING → P05 Qualification → P06 Seal

## Critical: QUALIFIED_WITH_LIMITATIONS carry-forward

runtimeQualification = QUALIFIED_WITH_LIMITATIONS (MUST NOT be promoted to QUALIFIED)

- embeddedMotionClips = [Idle]
- Bow/LargeBow/Handshake/Dance = PROFILE_SIMULATION
- FACE/BODY_FAILURE = NONE

## Human focus

1. Actual GLB structure: FACE_Rig_Root under Head + AUX_* nodes in derived artifacts
2. N→A→N functional evidence linked to derived structure (not JSON-only claims)
3. Mutation ledger NONE
4. Limitations not rewritten
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    from tools.run_v2_cr02_p06_real_asset_proof import run_all

    seal = run_all(ROOT / "tools/run_v2_cr02_p06_real_asset_proof.py")
    if seal.get("status") != "READY_FOR_HUMAN_AUDIT":
        raise SystemExit("P06 not READY_FOR_HUMAN_AUDIT")
    if seal.get("runtimeQualification") != "QUALIFIED_WITH_LIMITATIONS":
        raise SystemExit("illegal qualification rewrite at pack time")

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
        "NURION_ADAPTATION_ENGINE_V2_CR02_MESHY_FACE_EYE_JAW_TALKING_AUGMENTATION_V1.json",
        "NURION_ADAPTATION_ENGINE_V2_TRACK_V1.json",
        "NURION_ADAPTATION_ENGINE_V2_CR01_FLEXIBLE_MESHY_SKELETON_SEMANTIC_ADAPTER_V1.json",
    ):
        add(f"semantic/{name}", SEM / name)

    for p in sorted(EV.glob("NURION-V2-CR02*.json")):
        if p.name in EXCLUDE:
            continue
        add(f"evidence/{p.name}", p)
    # CR01 consume references
    for name in (
        "NURION-V2-CR01_R2_HUMAN_PASS_receipt.json",
        "NURION-V2-CR01_CONSUME_ONLY_SEAL.json",
    ):
        add(f"evidence/{name}", CR01_EV / name)

    for p in sorted(REP.glob("*.json")):
        add(f"reports/{p.name}", p)

    add("assets/Idle_15_withSkin_WORKING_BASELINE.glb", IDLE15)
    add("derived/Idle_15_P03_eye_blink.glb", DER / "Idle_15_P03_eye_blink.glb")
    add("derived/Idle_15_P04_jaw_expression_talking.glb", DER / "Idle_15_P04_jaw_expression_talking.glb")

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
            "schema": "NURION_V2_CR02_AUDIT_ZIP_MANIFEST_V1",
            "revision": "R1",
            "changeRequestId": "V2-CR-02",
            "agentStatus": "READY_FOR_HUMAN_AUDIT",
            "pass": "NOT_DECLARED",
            "CR02-G20": "HUMAN_FINAL_ONLY",
            "CR02-P07": "HUMAN_FINAL_ONLY",
            "v2Engine": "NOT OPEN",
            "runtimeQualification": "QUALIFIED_WITH_LIMITATIONS",
            "limitations": seal["limitations"],
            "realAssetProofDigest": seal["realAssetProofDigest"],
            "finalCandidateSha256": seal["finalCandidate"]["sha256"],
            "idle15Sha256": IDLE15_SHA,
            "entries": sorted(a for a, _, _ in files),
            "payloadCanonicalDigest": payload_digest,
            "finalAuditZipSha256": "EXTERNAL_ONLY",
            "independentRun": {
                "cmd": "python repo/tools/run_v2_cr02_independent_proof.py",
            },
        }
        zf.writestr("MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    zip_sha = sha256_file(OUT)
    meta = {
        "schema": "NURION_V2_CR02_R1_AUDIT_ZIP_RECEIPT_V1",
        "revision": "R1",
        "changeRequestId": "V2-CR-02",
        "zip": str(OUT),
        "finalAuditZipSha256": zip_sha,
        "payloadCanonicalDigest": payload_digest,
        "byteLength": OUT.stat().st_size,
        "entryCount": len(files) + 1,
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "CR02-G20": "HUMAN_FINAL_ONLY",
        "realAssetProofDigest": seal["realAssetProofDigest"],
        "finalCandidateSha256": seal["finalCandidate"]["sha256"],
        "runtimeQualification": "QUALIFIED_WITH_LIMITATIONS",
        "v2Engine": "NOT OPEN",
        "humanPassCeiling": "PROTOTYPE HUMAN PASS / TECHNICAL BASIS CONFIRMED",
    }
    (EV / "NURION-V2-CR02_R1_audit_zip_receipt.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR02_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "revision": "R1",
                "finalAuditZipSha256": zip_sha,
                "payloadCanonicalDigest": payload_digest,
                "byteLength": OUT.stat().st_size,
                "realAssetProofDigest": seal["realAssetProofDigest"],
                "finalCandidateSha256": seal["finalCandidate"]["sha256"],
                "runtimeQualification": "QUALIFIED_WITH_LIMITATIONS",
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    with tempfile.TemporaryDirectory(prefix="v2cr02_audit_") as tmp:
        extract = Path(tmp) / "extract"
        extract.mkdir()
        with zipfile.ZipFile(OUT, "r") as zf:
            zf.extractall(extract)
        proof = extract / "repo/tools/run_v2_cr02_independent_proof.py"
        result = subprocess.run(
            [sys.executable, str(proof)], cwd=str(extract), check=False, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(result.stdout)
            print(result.stderr, file=sys.stderr)
            raise SystemExit(f"extracted independent proof failed: exit {result.returncode}")

    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
