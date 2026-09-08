#!/usr/bin/env python3
"""Pack V2-CR-04 R3 Human Audit ZIP — GAP-01 Sporty resolved facial generalization."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

EV = ROOT / "fast_track/working/adaptation_engine_v2/evidence"
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr04"
SEM = ROOT / "fast_track/working/adaptation_engine_v2/semantic"
DER = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr04"
ASSETS = ROOT / "fast_track/working/adaptation_engine_v2/assets_cr04"
OUT = EV / "NURION-V2-CR04_R3_gap01_sporty_resolved_facial_proof.zip"

PIN_SECOND = "f3f9e343c8ba3c9a503a8423293dec90bb6be50f809f1321f4f6658b1bea133e"
PIN_GAP01_SPEC = "4a8467ad945d3c56d9222075c44ae4cc12e8df5edcd833d4091b046901b903f3"
PIN_CR04_SPEC = "203466befd67d01a4acf42a60048d6b2ac01c42b4dd2ffea49da73f0c8edface"

REPO_FILES = [
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/adaptation/inspector.py",
    "fast_track/adaptation/classifier.py",
    "fast_track/adaptation/semantic_candidates.py",
    "fast_track/change_control/__init__.py",
    "fast_track/change_control/nurion_change_control_gate_v1.py",
    "fast_track/v2_cr01/__init__.py",
    "fast_track/v2_cr01/flexible_adapter.py",
    "fast_track/v2_cr01/torso_chain.py",
    "fast_track/v2_cr01/semantic_assignment.py",
    "fast_track/v2_cr01/skeleton_inspection.py",
    "fast_track/v2_cr01/retarget_safety.py",
    "fast_track/v2_cr01/audit_paths.py",
    "fast_track/v2_cr02/__init__.py",
    "fast_track/v2_cr02/facial_deformation.py",
    "fast_track/v2_cr03/glb_measure.py",
    "fast_track/v2_cr03/pins.py",
    "fast_track/v2_cr04/__init__.py",
    "fast_track/v2_cr04/audit_paths.py",
    "fast_track/v2_cr04/pins.py",
    "fast_track/v2_cr04/fasttrack.py",
    "fast_track/v2_cr04/facial_region_resolve.py",
    "fast_track/v2_cr04/gap01_pipeline.py",
    "tools/run_v2_cr04_gap01_r3.py",
    "tools/run_v2_cr04_gap01_independent_proof.py",
    "tools/pack_v2_cr04_r3_proof_zip.py",
]

HUMAN_README = """# V2-CR-04 R3 Human Audit — GAP-01 Asset-Independent Facial Region Resolution

## Authority

- V2-CR-04 = READY_FOR_HUMAN_AUDIT (corrective V2-CR-04-GAP-01)
- CR04-P07 / G20 = HUMAN_FINAL_ONLY (agent cannot declare PASS)
- CR01 / CR02 / CR03 = CONSUME ONLY / REOPEN DENY / HUMAN PASS PRESERVED
- Engine V2 = NOT OPEN

## What R3 proves

Same Sporty second asset as R2, with CR04 consume-path facial selection that:

1. Resolves Head via CR01 `NURION_head` → `skin.joints` local index (no `HEAD_SKIN_LOCAL = 21` SoT)
2. Uses head-weight + head-local relative geometry (no absolute `FACE_Y_MIN = 1.28`)
3. Does **not** call `v2_cr02.select_facial_vertices`
4. Expands hardcoding scan to CR04 facial consume modules (AST) and documents CR02 literals as historical

## Second asset pin (PRESERVED — DO NOT RESELECT)

- Meshy_AI_Sporty_Studio_Portrai_biped / Idle_15_withSkin
- SHA256 = f3f9e343c8ba3c9a503a8423293dec90bb6be50f809f1321f4f6658b1bea133e
- File: assets/SECOND_ASSET_BASELINE.glb

## R2 status (preserved)

- R2 = FUNCTIONAL PIPELINE PASS + HUMAN AUDIT BLOCKED (CR04-GENERALIZATION-HC-01)
- R2 ZIP SHA = cf89065ef81cc1acc933f057bad929898e4b9f573d550437abf0d4b5b1a7912c

## Coincidence note

On Sporty, resolved `headJointLocalIndex` may equal 21. That is **not** acceptance of Idle_15 hardcoding.
Acceptance requires resolver provenance `CR01_NURION_head→skin.joints.index` and `hardcodedIdle15Index21 = NOT_USED`.

## Independent proof

```bash
python repo/tools/run_v2_cr04_gap01_independent_proof.py
```

Recompute from GLBs. Do not trust report PASS fields.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    baseline = ASSETS / "SECOND_ASSET_BASELINE.glb"
    face = DER / "SECOND_ASSET_GAP01_facial_deformation.glb"
    talk = DER / "SECOND_ASSET_GAP01_talking_weights.glb"
    if sha256_file(baseline) != PIN_SECOND:
        raise SystemExit("Sporty second asset pin drift")
    ready = json.loads((EV / "NURION-V2-CR04_R3_READY_FOR_HUMAN_AUDIT_receipt.json").read_text(encoding="utf-8"))
    face_sha = sha256_file(face)
    talk_sha = sha256_file(talk)
    if talk_sha != ready.get("derivedSha256"):
        raise SystemExit(f"talking derived drift {talk_sha}")
    if face_sha != ready.get("facialDerivedSha256"):
        raise SystemExit(f"facial derived drift {face_sha}")

    from tools.run_v2_cr04_gap01_independent_proof import main as indep_main

    if indep_main() != 0:
        raise SystemExit("GAP-01 independent proof failed")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "HUMAN_README.md").write_text(HUMAN_README, encoding="utf-8")
        for sub in ("evidence", "reports", "semantic", "derived", "assets", "repo"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline, root / "assets" / "SECOND_ASSET_BASELINE.glb")
        shutil.copy2(face, root / "derived" / "SECOND_ASSET_GAP01_facial_deformation.glb")
        shutil.copy2(talk, root / "derived" / "SECOND_ASSET_GAP01_talking_weights.glb")
        for p in SEM.glob("NURION*CR04*"):
            shutil.copy2(p, root / "semantic" / p.name)
        for name in ("NURION_CHANGE_CONTROL_GATE_V1.json", "NURION_ADAPTATION_ENGINE_V2_TRACK_V1.json"):
            src = SEM / name
            if src.is_file():
                shutil.copy2(src, root / "semantic" / name)
        for p in REP.glob("V2_CR04*"):
            shutil.copy2(p, root / "reports" / p.name)
        for p in EV.glob("NURION-V2-CR04*"):
            if p.suffix == ".zip" or "final_zip" in p.name or "audit_zip_receipt" in p.name:
                continue
            shutil.copy2(p, root / "evidence" / p.name)
        for p in EV.glob("NURION-V2-CR04-GAP01*"):
            shutil.copy2(p, root / "evidence" / p.name)
        for name in (
            "NURION-V2-CR01_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR02_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR03_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR01_CONSUME_ONLY_SEAL.json",
            "NURION-V2-CR02_R2_CONSUME_ONLY_SEAL.json",
            "NURION-V2-CR03_R2_CONSUME_ONLY_SEAL.json",
            "NURION-V2-CR04_R2_HUMAN_AUDIT_BLOCKED_receipt.json",
        ):
            src = EV / name
            if src.is_file():
                shutil.copy2(src, root / "evidence" / name)
        for rel in REPO_FILES:
            src = ROOT / rel
            if not src.is_file():
                raise SystemExit(f"missing repo file for pack: {rel}")
            dst = root / "repo" / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

        if OUT.exists():
            OUT.unlink()
        with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(root).as_posix())

    zip_sha = sha256_file(OUT)
    receipt = {
        "receiptId": "NURION-V2-CR04_R3_audit_zip_receipt",
        "changeRequestId": "V2-CR-04",
        "corrective": "V2-CR-04-GAP-01",
        "packagingRevision": "R3",
        "zipPath": str(OUT).replace("\\", "/"),
        "zipSha256": zip_sha,
        "secondAssetSha256": PIN_SECOND,
        "facialDerivedSha256": face_sha,
        "derivedSha256": talk_sha,
        "approvedGap01SpecDigest": PIN_GAP01_SPEC,
        "approvedCr04SpecDigest": PIN_CR04_SPEC,
        "finalCandidateSemanticDigest": ready.get("finalCandidateSemanticDigest"),
        "headJointLocalIndexResolved": ready.get("headJointLocalIndexResolved"),
        "headResolveProvenance": ready.get("headResolveProvenance"),
        "r2Status": "HUMAN_AUDIT_BLOCKED / FUNCTIONAL_PRESERVED",
        "r2ZipSha256": "cf89065ef81cc1acc933f057bad929898e4b9f573d550437abf0d4b5b1a7912c",
        "CR04-G20": "HUMAN_FINAL_ONLY",
        "status": "READY_FOR_HUMAN_AUDIT",
    }
    (EV / "NURION-V2-CR04_R3_audit_zip_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR04_R3_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "packagingRevision": "R3",
                "zipSha256": zip_sha,
                "derivedSha256": talk_sha,
                "facialDerivedSha256": face_sha,
                "secondAssetSha256": PIN_SECOND,
                "corrective": "V2-CR-04-GAP-01",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"zip": str(OUT), "zipSha256": zip_sha, "derivedSha256": talk_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
