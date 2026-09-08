#!/usr/bin/env python3
"""Pack V2-IRG R2 Human Audit ZIP — self-contained P06 (closes IRG-P06-SELF-CONTAINED-01)."""

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
REP = ROOT / "fast_track/working/adaptation_engine_v2/reports_irg"
SEM = ROOT / "fast_track/working/adaptation_engine_v2/semantic"
PKG = ROOT / "fast_track/working/adaptation_engine_v2"
OUT = EV / "NURION-V2-IRG_R2_integration_release_proof.zip"
PIN_SPEC = "a78769ecbcfc2c0094ad059dd312e565c27c975f3d68bef218c5d03c1539511a"

# Minimal closure for clean-extraction independent runner (+ HC-01 historical CR02 source)
REPO_FILES = [
    "fast_track/__init__.py",
    "fast_track/change_control/__init__.py",
    "fast_track/change_control/nurion_change_control_gate_v1.py",
    "fast_track/adaptation/__init__.py",
    "fast_track/adaptation/glb_io.py",
    "fast_track/v2_cr02/__init__.py",
    "fast_track/v2_cr02/facial_deformation.py",
    "fast_track/v2_cr03/__init__.py",
    "fast_track/v2_cr03/pins.py",
    "fast_track/v2_cr03/glb_measure.py",
    "fast_track/v2_cr04/__init__.py",
    "fast_track/v2_cr04/pins.py",
    "fast_track/v2_cr04/facial_region_resolve.py",
    "fast_track/v2_cr04/gap01_pipeline.py",
    "fast_track/v2_cr04/fasttrack.py",
    "fast_track/v2_irg/__init__.py",
    "fast_track/v2_irg/pins.py",
    "fast_track/v2_irg/audit_paths.py",
    "fast_track/v2_irg/hc01_regression_scan.py",
    "fast_track/v2_irg/fasttrack.py",
    "tools/run_v2_irg_fasttrack.py",
    "tools/run_v2_irg_independent_proof.py",
    "tools/pack_v2_irg_proof_zip.py",
]

HUMAN_README = """# V2-IRG-01 R2 Human Audit — Integration / Release Gate

## Authority

- V2-IRG-01 = READY_FOR_HUMAN_AUDIT (R2 packaging)
- R1 = HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED (IRG-P06-SELF-CONTAINED-01)
- V2-RG-P07 / G20 = HUMAN_FINAL_ONLY
- CR01–CR04 = HUMAN PASS / CONSUME ONLY / REOPEN DENY
- Engine V2 = NOT OPEN until Human Final PASS

## R1 blocker closed by R2

Missing `fast_track/v2_cr03/pins.py` (and related self-contained deps) included.
Independent runner must exit 0 from a clean empty-directory extraction.

## Approved SPEC digest

a78769ecbcfc2c0094ad059dd312e565c27c975f3d68bef218c5d03c1539511a

## Independent proof

```bash
python repo/tools/run_v2_irg_independent_proof.py
```

Do not trust report PASS fields.
"""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _ensure_fast_track_inits() -> None:
    init = ROOT / "fast_track" / "__init__.py"
    if not init.is_file():
        init.write_text("# fast_track package\n", encoding="utf-8")


def _build_staging(root: Path) -> None:
    (root / "HUMAN_README.md").write_text(HUMAN_README, encoding="utf-8")
    for sub in ("evidence", "reports", "semantic", "derived", "assets", "repo"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    copies = [
        (PKG / "derived_cr02/Idle_15_R2_facial_deformation.glb", "derived/Idle_15_R2_facial_deformation.glb"),
        (PKG / "derived_cr03/Idle_15_CR03_talking_weights.glb", "derived/Idle_15_CR03_talking_weights.glb"),
        (PKG / "assets_cr04/SECOND_ASSET_BASELINE.glb", "assets/SECOND_ASSET_BASELINE.glb"),
        (
            PKG / "derived_cr04/SECOND_ASSET_GAP01_facial_deformation.glb",
            "derived/SECOND_ASSET_GAP01_facial_deformation.glb",
        ),
        (
            PKG / "derived_cr04/SECOND_ASSET_GAP01_talking_weights.glb",
            "derived/SECOND_ASSET_GAP01_talking_weights.glb",
        ),
    ]
    idle_base = ROOT / "fast_track/working/meshy_silver_starlight/baseline/Idle_15_withSkin_WORKING_BASELINE.glb"
    if idle_base.is_file():
        copies.append((idle_base, "assets/Idle_15_BASELINE.glb"))
    for src, rel in copies:
        if not src.is_file():
            raise SystemExit(f"missing pin asset: {src}")
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for p in SEM.glob("NURION*"):
        if p.suffix != ".json" and p.suffix != ".md":
            continue
        if any(
            k in p.name
            for k in (
                "ADAPTATION_ENGINE_V2",
                "CHANGE_CONTROL",
                "IRG",
                "INTEGRATION_RELEASE",
                "RELEASE_",
                "CR01",
                "CR02",
                "CR03",
                "CR04",
            )
        ):
            shutil.copy2(p, root / "semantic" / p.name)

    for p in REP.glob("V2_IRG*"):
        shutil.copy2(p, root / "reports" / p.name)

    for p in EV.glob("NURION-V2-*"):
        if p.suffix == ".zip":
            continue
        if any(
            x in p.name
            for x in (
                "CR01",
                "CR02",
                "CR03",
                "CR04",
                "IRG",
                "AUTHORITY_LINE_POST_CR04",
                "HOLD_POST_CR04",
            )
        ):
            shutil.copy2(p, root / "evidence" / p.name)

    for rel in REPO_FILES:
        src = ROOT / rel
        if not src.is_file():
            raise SystemExit(f"missing repo file for pack: {rel}")
        dst = root / "repo" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def _clean_extract_independent_proof(zip_path: Path) -> None:
    """Fail closed: empty dir + unzip + runner must exit 0."""
    with tempfile.TemporaryDirectory(prefix="irg_r2_clean_") as td:
        td_path = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(td_path)
        # unsafe path check
        for name in zf.namelist() if False else []:
            pass
        with zipfile.ZipFile(zip_path, "r") as zf:
            for name in zf.namelist():
                if name.startswith("/") or ".." in Path(name).parts:
                    raise SystemExit(f"unsafe path in zip: {name}")
        runner = td_path / "repo" / "tools" / "run_v2_irg_independent_proof.py"
        if not runner.is_file():
            raise SystemExit("clean extract missing independent runner")
        # required dep that R1 missed
        pins = td_path / "repo" / "fast_track" / "v2_cr03" / "pins.py"
        if not pins.is_file():
            raise SystemExit("clean extract still missing v2_cr03/pins.py")
        proc = subprocess.run(
            [sys.executable, str(runner)],
            cwd=str(td_path),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise SystemExit(
                "clean-extraction independent runner FAILED\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            )


def main() -> int:
    _ensure_fast_track_inits()
    if sha256_file(SEM / "NURION_ADAPTATION_ENGINE_V2_INTEGRATION_RELEASE_GATE_SPEC_R1.json") != PIN_SPEC:
        raise SystemExit("SPEC digest drift")
    ready = json.loads((EV / "NURION-V2-IRG_READY_FOR_HUMAN_AUDIT_receipt.json").read_text(encoding="utf-8"))

    # Monorepo independent proof first
    from tools.run_v2_irg_independent_proof import main as indep_main

    if indep_main() != 0:
        raise SystemExit("monorepo independent proof failed")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        _build_staging(root)
        if OUT.exists():
            OUT.unlink()
        with zipfile.ZipFile(OUT, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for f in root.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(root).as_posix())

    _clean_extract_independent_proof(OUT)

    zip_sha = sha256_file(OUT)
    receipt = {
        "receiptId": "NURION-V2-IRG_R2_audit_zip_receipt",
        "changeRequestId": "V2-IRG-01",
        "packagingRevision": "R2",
        "closes": "IRG-P06-SELF-CONTAINED-01",
        "r1": {
            "status": "HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED",
            "zipSha256": "49f015f90f5be2cbcbc3520b4e0ba5f5d0ca0909f31b0ebcdec7a048a4352fb9",
            "blocker": "IRG-P06-SELF-CONTAINED-01",
        },
        "zipPath": str(OUT).replace("\\", "/"),
        "zipSha256": zip_sha,
        "approvedSpecDigest": PIN_SPEC,
        "releaseManifestDigest": ready.get("releaseManifestDigest"),
        "releaseCandidateDigest": ready.get("releaseCandidateDigest"),
        "integrationProofDigest": ready.get("integrationProofDigest"),
        "finalReleaseDigest": ready.get("finalReleaseDigest"),
        "cleanExtractionIndependentRunner": "PASS / EXIT 0",
        "status": "READY_FOR_HUMAN_AUDIT",
        "engineV2": "NOT_OPEN",
        "V2-RG-G20": "HUMAN_FINAL_ONLY",
        "upstreamReopen": "DENY",
    }
    (EV / "NURION-V2-IRG_R2_audit_zip_receipt.json").write_text(
        json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (EV / "NURION-V2-IRG_R2_final_zip_sha_EXTERNAL.json").write_text(
        json.dumps(
            {
                "packagingRevision": "R2",
                "zipSha256": zip_sha,
                "approvedSpecDigest": PIN_SPEC,
                "closes": "IRG-P06-SELF-CONTAINED-01",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    # convenience copy for Human attach
    shutil.copy2(OUT, ROOT / "NURION-V2-IRG_R2_integration_release_proof.zip")
    print(json.dumps({"zip": str(OUT), "zipSha256": zip_sha, "closes": "IRG-P06-SELF-CONTAINED-01"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
