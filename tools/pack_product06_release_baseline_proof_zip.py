#!/usr/bin/env python3
"""Pack NURION-PRODUCT-06_release_baseline_proof.zip — READY_FOR_HUMAN_AUDIT only."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
REL = ROOT / "fast_track/working/meshy_silver_starlight/release/NURION_CHARACTER_PRODUCT_RELEASE_V1"
ZIP_PATH = EV / "NURION-PRODUCT-06_release_baseline_proof.zip"
MANIFEST = EV / "NURION-PRODUCT-06_release_baseline_proof_manifest.json"
SIDECAR = EV / "NURION-PRODUCT-06_release_baseline_proof.zip.sha256"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sys.path.insert(0, str(ROOT))
    from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

    for p in (ROOT / "fast_track/__init__.py", ROOT / "fast_track/runtime/__init__.py"):
        if not p.exists():
            p.write_text("", encoding="utf-8")

    env = {**os.environ, "NURION_REPO_ROOT": str(ROOT)}
    subprocess.run(
        [sys.executable, str(ROOT / "tools/build_product06_release_baseline.py")],
        check=True,
        cwd=str(ROOT),
        env=env,
    )
    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    ups_before = {
        "p01": sha256(SEM / "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"),
        "p02": sha256(SEM / "NURION_PRODUCT02_MOTION_LIBRARY_V1.json"),
        "p03": sha256(SEM / "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json"),
        "p04": sha256(SEM / "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json"),
        "p05": sha256(SEM / "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1.json"),
    }

    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_product06_release_baseline_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    sot_after = assert_protected_sot_unchanged()
    ups_after = {
        "p01": sha256(SEM / "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"),
        "p02": sha256(SEM / "NURION_PRODUCT02_MOTION_LIBRARY_V1.json"),
        "p03": sha256(SEM / "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json"),
        "p04": sha256(SEM / "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json"),
        "p05": sha256(SEM / "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1.json"),
    }
    if ups_before != ups_after:
        raise SystemExit("BLOCKER: PRODUCT-01…05 mutated during PRODUCT-06 proof")

    proof = json.loads(
        (EV / "NURION-PRODUCT-06_release_baseline_proof_stdout.json").read_text(encoding="utf-8")
    )
    bl_path = SEM / "NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_V1.json"
    baseline = json.loads(bl_path.read_text(encoding="utf-8"))
    bl_canon = hashlib.sha256(
        json.dumps(baseline, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()

    digest = {
        "gates": [
            {
                "gate": r["gate"],
                "status": r["status"],
                **({"detail": r["detail"]} if "detail" in r else {}),
                **({"error": r["error"]} if "error" in r else {}),
            }
            for r in proof["results"]
        ]
    }
    digest_path = EV / "NURION-PRODUCT-06_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    critical_ids = (
        "P6-G04",
        "P6-G05",
        "P6-G08",
        "P6-G10",
        "P6-G12",
        "P6-G14",
        "P6-G16",
        "P6-G19",
    )
    critical = {g: next((r for r in proof["results"] if r["gate"] == g), None) for g in critical_ids}
    receipt = {
        "receiptId": f"NURION-PRODUCT-06_{ts}",
        "stage": "NURION-PRODUCT-06_PRODUCT_INTEGRATION_RELEASE_BASELINE",
        "status": "READY_FOR_HUMAN_AUDIT",
        "product06Pass": "NOT_DECLARED",
        "pipelineOverallPass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "P6-G20": "HUMAN_FINAL_REAUDIT_ONLY",
        "NURION_CHARACTER_PRODUCT_RELEASE_V1": "NOT_YET_AUTHORITATIVE_FINAL",
        "releaseId": baseline.get("releaseId"),
        "canonicalReleaseDigest": baseline.get("canonicalReleaseDigest"),
        "criticalGates": {k: (v or {}).get("status") for k, v in critical.items()},
        "agentSelfCheck": {
            "passed": proof["passed"],
            "failed": proof["failed"],
            "tests": [{"gate": r["gate"], "status": r["status"]} for r in proof["results"]],
        },
        "baselineCanonicalSha256": bl_canon,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "upstreamUnmutated": ups_before == ups_after,
        "packagedAtUtc": ts,
        "humanAuditRequest": "Independent ZIP reaudit G01–G20 + pipeline closure; only then CLOSED/PASS",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-PRODUCT-06_release_baseline_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files: list[tuple[Path, str]] = [
        (ROOT / "fast_track/__init__.py", "repo/fast_track/__init__.py"),
        (ROOT / "fast_track/runtime/__init__.py", "repo/fast_track/runtime/__init__.py"),
    ]
    for name in [
        "product_release_baseline.py",
        "product_behavior_runtime.py",
        "product_entrance_state.py",
        "product_face_body_runtime.py",
        "product_character_assembly.py",
        "product_motion_library.py",
        "body_retarget_engine.py",
        "donor_skeleton_profile.py",
        "retarget_contract_validator.py",
        "face_composition.py",
        "expression_mixer.py",
        "korean_lip_sync_v2.py",
        "canonical_facial_actuator.py",
        "legacy_face_adapter.py",
    ]:
        p = ROOT / "fast_track/runtime" / name
        files.append((p, f"repo/fast_track/runtime/{name}"))
    for name in ["__init__.py", "engine.py", "quat.py", "canonical.py", "protected.py", "registry.py", "profile.py"]:
        p = ROOT / "fast_track/runtime/retarget" / name
        files.append((p, f"repo/fast_track/runtime/retarget/{name}"))

    for name in [
        "NURION_BODY_CANONICAL_BONE_SPEC_V1.json",
        "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json",
        "NURION_FACE_PRODUCT_LOCK_V1.json",
        "NURION_BODY_PRODUCT_LOCK_V1.json",
        "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json",
        "NURION_PRODUCT02_MOTION_LIBRARY_V1.json",
        "NURION_PRODUCT03_FACE_BODY_RUNTIME_V1.json",
        "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json",
        "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1.json",
        "NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_CONTRACT_V1.json",
        "NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_V1.json",
        "NURION_PRODUCT_CHARACTER_PIPELINE_TRACK_V1.json",
        "retarget_profiles/mjn_legacy_profile_v1.json",
        "retarget_profiles/jake_cc_profile_v1.json",
    ]:
        files.append((SEM / name, f"repo/fast_track/working/meshy_silver_starlight/semantic/{name}"))

    for name in [
        "NURION-PRODUCT-01_PASS_receipt.json",
        "NURION-PRODUCT-02_PASS_receipt.json",
        "NURION-PRODUCT-03_PASS_receipt.json",
        "NURION-PRODUCT-04_PASS_receipt.json",
        "NURION-PRODUCT-05_PASS_receipt.json",
        "NURION-PRODUCT-06_CONTRACT_FREEZE_receipt.json",
        "NURION-PRODUCT-06_PURPOSE_ADOPTION_receipt.json",
        "NURION-PRODUCT-06_release_baseline_proof_stdout.json",
    ]:
        files.append((EV / name, f"repo/fast_track/working/meshy_silver_starlight/evidence/{name}"))

    # Include staged release tree
    for p in REL.rglob("*"):
        if p.is_file():
            rel = p.relative_to(ROOT).as_posix()
            files.append((p, f"repo/{rel}"))

    files.extend(
        [
            (
                digest_path,
                "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-06_expected_observed_digest.json",
            ),
            (
                receipt_path,
                "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-06_release_baseline_proof_receipt.json",
            ),
            (ROOT / "tools/build_product06_release_baseline.py", "repo/tools/build_product06_release_baseline.py"),
            (
                ROOT / "tools/run_product06_release_baseline_proof.py",
                "repo/tools/run_product06_release_baseline_proof.py",
            ),
            (ROOT / "tools/run_product06_independent_proof.py", "run_product06_independent_proof.py"),
        ]
    )

    missing = [str(s) for s, _ in files if not s.exists()]
    if missing:
        raise SystemExit(f"missing: {missing[:20]}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)
        zf.writestr(
            "evidence/PRODUCT06_proof_runner_console.txt",
            (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""),
        )
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "PRODUCT-06 Product Integration & Release Baseline audit",
                    "product06Pass": "NOT_DECLARED",
                    "pipelineOverallPass": "NOT_DECLARED",
                    "status": "READY_FOR_HUMAN_AUDIT",
                    "releaseId": baseline.get("releaseId"),
                    "canonicalReleaseDigest": baseline.get("canonicalReleaseDigest"),
                    "howToIndependentRerun": ["Extract ZIP", "py -3 run_product06_independent_proof.py"],
                    "gates": "P6-G01…G19 automated; P6-G20 human only (also seals PIPELINE OVERALL)",
                    "criticalGates": list(critical_ids),
                    "auditFocus": [
                        "Upstream hash-chain MATCH (P05=R2 only)",
                        "Copy-without-mutation byte equality",
                        "E2E lifecycle consume P03/P04/P05",
                        "Tamper fail-closed / no auto-repair",
                        "Canonical release digest reproducibility",
                        "Independent packaged runner",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )

    manifest = {
        "package": "NURION-PRODUCT-06_release_baseline_proof.zip",
        "status": "READY_FOR_HUMAN_AUDIT",
        "product06Pass": "NOT_DECLARED",
        "pipelineOverallPass": "NOT_DECLARED",
        "packagedAtUtc": ts,
        "agentProofSummary": {"passed": proof["passed"], "failed": proof["failed"]},
        "baselineCanonicalSha256": bl_canon,
        "canonicalReleaseDigest": baseline.get("canonicalReleaseDigest"),
        "contents": [arc for _, arc in files]
        + ["evidence/PRODUCT06_proof_runner_console.txt", "README_AUDIT.json"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST, arcname="evidence/NURION-PRODUCT-06_release_baseline_proof_manifest.json")
    zsha = sha256(ZIP_PATH)
    manifest["sha256"] = zsha
    manifest["bytes"] = ZIP_PATH.stat().st_size
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    SIDECAR.write_text(zsha + "\n", encoding="utf-8")
    receipt["sourceReviewPackage"] = str(ZIP_PATH)
    receipt["sourceReviewPackageSha256"] = zsha
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        with zipfile.ZipFile(ZIP_PATH, "r") as zf:
            zf.extractall(td_path)
        ind = subprocess.run(
            [sys.executable, str(td_path / "run_product06_independent_proof.py")],
            capture_output=True,
            text=True,
            cwd=str(td_path),
            env={**os.environ, "NURION_REPO_ROOT": str(td_path / "repo")},
        )

    print(
        json.dumps(
            {
                "zip": str(ZIP_PATH),
                "sha256": zsha,
                "bytes": ZIP_PATH.stat().st_size,
                "baselineCanonicalSha256": bl_canon,
                "releaseId": baseline.get("releaseId"),
                "canonicalReleaseDigest": baseline.get("canonicalReleaseDigest"),
                "product06Pass": "NOT_DECLARED",
                "pipelineOverallPass": "NOT_DECLARED",
                "status": "READY_FOR_HUMAN_AUDIT",
                "passed": proof["passed"],
                "failed": proof["failed"],
                "testsExit": proc.returncode,
                "critical": {k: (v or {}).get("status") for k, v in critical.items()},
                "independentRerun": {
                    "exit": ind.returncode,
                    "stdoutTail": (ind.stdout or "")[-800:],
                    "stderrTail": (ind.stderr or "")[-400:],
                },
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    ok = (
        ZIP_PATH.exists()
        and sot_before == sot_after == PROTECTED_SOT_SHA256
        and proof["failed"] == 0
        and proc.returncode == 0
        and ind.returncode == 0
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
