#!/usr/bin/env python3
"""Pack V2-CR-04 Human Audit ZIP — second Meshy asset generalization."""

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
OUT = EV / "NURION-V2-CR04_R2_second_meshy_generalization_proof.zip"

PIN_SECOND = "f3f9e343c8ba3c9a503a8423293dec90bb6be50f809f1321f4f6658b1bea133e"
PIN_SPEC = "203466befd67d01a4acf42a60048d6b2ac01c42b4dd2ffea49da73f0c8edface"

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
    "tools/run_v2_cr04_independent_proof.py",
    "tools/run_v2_cr04_fasttrack.py",
    "tools/pack_v2_cr04_proof_zip.py",
]

HUMAN_README = """# V2-CR-04 Human Audit — Second Real Meshy Asset Generalization

## Authority

- V2-CR-04 = OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT
- CR04-P07 / G20 = HUMAN_FINAL_ONLY
- CR01/CR02/CR03 = CONSUME ONLY / REOPEN DENY
- Engine V2 = NOT OPEN

## Second asset pin (R2)

- Meshy_AI_Sporty_Studio_Portrai_biped / Idle_15_withSkin
- Source zip: D:/보관자료/MJN/assets/mjn_15.zip
- SHA256 = f3f9e343c8ba3c9a503a8423293dec90bb6be50f809f1321f4f6658b1bea133e
- File in package: assets/SECOND_ASSET_BASELINE.glb
- Prior Bolt Voyager pin = SUPERSEDED / HISTORICAL / PRESERVED

## Independent proof

```bash
python repo/tools/run_v2_cr04_independent_proof.py
```

Recompute from GLBs: source SHA, CR01 mapping, morph deformation, weights animation V(t), BODY preservation, hardcoding absence.
Do not trust report PASS fields.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    baseline = ASSETS / "SECOND_ASSET_BASELINE.glb"
    derived = DER / "SECOND_ASSET_CR03_talking_weights.glb"
    if sha256_file(baseline) != PIN_SECOND:
        raise SystemExit("second asset pin drift")
    ready = json.loads((EV / "NURION-V2-CR04_READY_FOR_HUMAN_AUDIT_receipt.json").read_text(encoding="utf-8"))
    der_sha = sha256_file(derived)
    if der_sha != ready.get("derivedSha256"):
        raise SystemExit(f"derived drift {der_sha}")

    # Independent proof before pack
    from tools.run_v2_cr04_independent_proof import main as indep_main

    if indep_main() != 0:
        raise SystemExit("independent proof failed")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "HUMAN_README.md").write_text(HUMAN_README, encoding="utf-8")
        for sub in ("evidence", "reports", "semantic", "derived", "assets", "repo"):
            (root / sub).mkdir(parents=True, exist_ok=True)
        shutil.copy2(baseline, root / "assets" / "SECOND_ASSET_BASELINE.glb")
        shutil.copy2(derived, root / "derived" / "SECOND_ASSET_CR03_talking_weights.glb")
        if (DER / "SECOND_ASSET_CR02_facial_deformation.glb").is_file():
            shutil.copy2(
                DER / "SECOND_ASSET_CR02_facial_deformation.glb",
                root / "derived" / "SECOND_ASSET_CR02_facial_deformation.glb",
            )
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
        # upstream consume seals (pins only)
        for name in (
            "NURION-V2-CR01_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR02_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR03_R2_HUMAN_PASS_receipt.json",
            "NURION-V2-CR01_CONSUME_ONLY_SEAL.json",
            "NURION-V2-CR02_R2_CONSUME_ONLY_SEAL.json",
            "NURION-V2-CR03_R2_CONSUME_ONLY_SEAL.json",
        ):
            src = EV / name
            if src.is_file():
                shutil.copy2(src, root / "evidence" / name)
        for rel in REPO_FILES:
            src = ROOT / rel
            if not src.is_file():
                continue
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
        "receiptId": "NURION-V2-CR04_R2_audit_zip_receipt",
        "changeRequestId": "V2-CR-04",
        "packagingRevision": "R2",
        "zipPath": str(OUT).replace("\\", "/"),
        "zipSha256": zip_sha,
        "secondAssetSha256": PIN_SECOND,
        "derivedSha256": der_sha,
        "approvedSpecDigest": PIN_SPEC,
        "finalCandidateSemanticDigest": ready.get("finalCandidateSemanticDigest"),
        "priorBoltVoyagerPin": "SUPERSEDED / HISTORICAL / PRESERVED",
        "CR04-G20": "HUMAN_FINAL_ONLY",
        "status": "READY_FOR_HUMAN_AUDIT",
    }
    (EV / "NURION-V2-CR04_R2_audit_zip_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-CR04_R2_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "packagingRevision": "R2",
                "zipSha256": zip_sha,
                "derivedSha256": der_sha,
                "secondAssetSha256": PIN_SECOND,
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
