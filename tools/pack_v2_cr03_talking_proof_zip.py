#!/usr/bin/env python3
"""Pack V2-CR-03 R2 Human Audit ZIP — minimal deps (no inspector/classifier).

Does NOT regenerate P02–P05 derived artifacts. Re-packages existing derived +
dependency-minimized independent runner only.
"""

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
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_cr03"
SEM = ROOT / "fast_track/working/adaptation_engine_v2/semantic"
DER = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr03"
CR02_DER = ROOT / "fast_track/working/adaptation_engine_v2/derived_cr02/Idle_15_R2_facial_deformation.glb"
OUT = EV / "NURION-V2-CR03_R2_morph_weight_runtime_talking_proof.zip"

PIN_DERIVED_SHA = "fe493789135aaa80f96a6c2377daafd0a3ed016f402ba8d8611c9e3d07c7c8ca"
PIN_CR02_SHA = "1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd"
PIN_SPEC = "3e3885335bcfd8489209a302852230ae6cdd55da89fb8328048f82d8fe4a206c"

# Minimal self-contained audit surface — no inspector/classifier/facial_deformation
REPO_FILES = [
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/change_control/__init__.py",
    "fast_track/change_control/nurion_change_control_gate_v1.py",
    "fast_track/v2_cr03/__init__.py",
    "fast_track/v2_cr03/audit_paths.py",
    "fast_track/v2_cr03/pins.py",
    "fast_track/v2_cr03/glb_measure.py",
    "fast_track/v2_cr03/p03_temporal_proof.py",
    "fast_track/v2_cr03/p04_regression.py",
    "fast_track/v2_cr03/independent_gates.py",
    "tools/run_v2_cr03_independent_proof.py",
    "tools/pack_v2_cr03_talking_proof_zip.py",
]

HUMAN_README = """# V2-CR-03 R2 Human Audit — Morph-Weight Runtime Talking

## Packaging revision

R1 ZIP blocked: `ModuleNotFoundError: fast_track.adaptation.classifier`
Cause: independent runner imported `inspector` transitively.
R2 fix: measurement helpers in `v2_cr03/glb_measure.py` — **no inspector/classifier**.

## Authority

- CR03-P01…P05 = Agent PASS / PRESERVED (not re-run)
- CR03 = READY_FOR_HUMAN_AUDIT
- CR03-P06 / G20 = HUMAN_FINAL_ONLY
- Engine V2 = NOT OPEN

## Pins (must match)

- approvedSpecDigest = 3e3885335bcfd8489209a302852230ae6cdd55da89fb8328048f82d8fe4a206c
- CR02 R2 input = 1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd
- derived = fe493789135aaa80f96a6c2377daafd0a3ed016f402ba8d8611c9e3d07c7c8ca

## Independent proof

```bash
python repo/tools/run_v2_cr03_independent_proof.py
```

Requires: Python 3 + numpy. Does not trust report PASS fields.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    derived = DER / "Idle_15_CR03_talking_weights.glb"
    der_sha = sha256_file(derived)
    if der_sha != PIN_DERIVED_SHA:
        raise SystemExit(f"derived SHA drift — refuse pack: {der_sha}")
    if sha256_file(CR02_DER) != PIN_CR02_SHA:
        raise SystemExit("CR02 input SHA drift — refuse pack")

    # Smoke independent proof in monorepo before pack
    from tools.run_v2_cr03_independent_proof import main as indep_main

    rc = indep_main()
    if rc != 0:
        raise SystemExit("independent proof failed before R2 pack")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "HUMAN_README.md").write_text(HUMAN_README, encoding="utf-8")
        for sub in ("evidence", "reports", "semantic", "derived", "assets", "repo"):
            (root / sub).mkdir(parents=True, exist_ok=True)

        shutil.copy2(CR02_DER, root / "assets" / "Idle_15_R2_facial_deformation.glb")
        shutil.copy2(derived, root / "derived" / "Idle_15_CR03_talking_weights.glb")

        for p in SEM.glob("NURION*CR03*"):
            shutil.copy2(p, root / "semantic" / p.name)
        for name in (
            "NURION_CHANGE_CONTROL_GATE_V1.json",
            "NURION_ADAPTATION_ENGINE_V2_TRACK_V1.json",
        ):
            src = SEM / name
            if src.is_file():
                shutil.copy2(src, root / "semantic" / name)

        for p in REP.glob("V2_CR03*"):
            shutil.copy2(p, root / "reports" / p.name)

        for p in EV.glob("NURION-V2-CR03*"):
            if p.suffix == ".zip":
                continue
            if "final_zip_sha" in p.name or "audit_zip_receipt" in p.name:
                continue
            shutil.copy2(p, root / "evidence" / p.name)

        for rel in REPO_FILES:
            src = ROOT / rel
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
        "receiptId": "NURION-V2-CR03_R2_audit_zip_receipt",
        "changeRequestId": "V2-CR-03",
        "packagingRevision": "R2",
        "r1Blocker": "SELF-CONTAINED AUDIT ZIP INCOMPLETE — missing fast_track.adaptation.classifier",
        "r1BlockerDisposition": "CLOSED BY R2 — independent runner deps minimized (no inspector)",
        "zipPath": str(OUT).replace("\\", "/"),
        "zipSha256": zip_sha,
        "derivedSha256": der_sha,
        "approvedSpecDigest": PIN_SPEC,
        "cr02R2InputSha256": PIN_CR02_SHA,
        "p02_to_p05": "PRESERVED — not re-run",
        "CR03-G20": "HUMAN_FINAL_ONLY",
        "status": "READY_FOR_HUMAN_AUDIT",
    }
    (EV / "NURION-V2-CR03_R2_audit_zip_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR03_R2_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "packagingRevision": "R2",
                "zipSha256": zip_sha,
                "derivedSha256": der_sha,
                "approvedSpecDigest": PIN_SPEC,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"zip": str(OUT), "zipSha256": zip_sha, "derivedSha256": der_sha}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
