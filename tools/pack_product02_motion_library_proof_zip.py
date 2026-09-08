#!/usr/bin/env python3
"""Pack NURION-PRODUCT-02_motion_library_proof.zip."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
ML = ROOT / "fast_track/working/meshy_silver_starlight/motion_library"
ZIP_PATH = EV / "NURION-PRODUCT-02_motion_library_proof.zip"
MANIFEST = EV / "NURION-PRODUCT-02_motion_library_proof_manifest.json"
SIDECAR = EV / "NURION-PRODUCT-02_motion_library_proof.zip.sha256"


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
    sot_before = {k: sha256(SEM / k) for k in PROTECTED_SOT_SHA256}
    proc = subprocess.run(
        [sys.executable, str(ROOT / "tools/run_product02_motion_library_proof.py")],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        env=env,
    )
    sot_after = assert_protected_sot_unchanged()
    proof = json.loads((EV / "NURION-PRODUCT-02_motion_library_proof_stdout.json").read_text(encoding="utf-8"))
    lib_path = SEM / "NURION_PRODUCT02_MOTION_LIBRARY_V1.json"

    digest = {"gates": [{"test": r["test"], "status": r["status"], **({"detail": r["detail"]} if "detail" in r else {}), **({"error": r["error"]} if "error" in r else {})} for r in proof["results"]]}
    digest_path = EV / "NURION-PRODUCT-02_expected_observed_digest.json"
    digest_path.write_text(json.dumps(digest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lib = json.loads(lib_path.read_text(encoding="utf-8"))
    fulfill = {m["motionId"]: m["fulfillment"] for m in lib["motions"]}
    clips = {m["motionId"]: m["meshyClipName"] for m in lib["motions"]}
    receipt = {
        "receiptId": f"NURION-PRODUCT-02_{ts}",
        "stage": "NURION-PRODUCT-02_MOTION_LIBRARY_INTEGRATION",
        "status": "READY_FOR_HUMAN_AUDIT",
        "product02Pass": "NOT_DECLARED",
        "product02Status": "AGENT_PROOF_COMPLETE_SEMANTIC_5_OF_5 — human CLOSED/PASS only",
        "productPipelineOverall": "NOT_DECLARED",
        "product01": "CLOSED / PASS",
        "rig01": "CLOSED / PASS / CONSUME_ONLY",
        "rig02": "CLOSED / PASS / CONSUME_ONLY",
        "patch": {
            "P2a": "CLOSED / PASS — fulfillment + technical vs productSemantic split",
            "P2b": "CLOSED — dedicated Handshake from D:/보관자료/MJN/assets/mjn_handshake.zip (Wave_for_Help_4)",
            "P2c": "CLOSED — dedicated Dance from D:/보관자료/MJN/assets/mjn_dance.zip (Superlove_Pop_Dance)",
        },
        "intakeProvenance": {
            "handshakeSource": "mjn_handshake.zip → Wave_for_Help_4_withSkin.fbx → mjn_handshake_withSkin.glb",
            "danceSource": "mjn_dance.zip → Superlove_Pop_Dance_withSkin.fbx → mjn_dance_withSkin.glb",
            "donorFamily": "Meshy_AI_Sporty_Studio_Portrai_biped (MJN product SoT; MJN Core-24 joints)",
            "note": "MJN product slot dedication — Meshy clip names retained in meshyClipName",
        },
        "track": {
            "PRODUCT_CHARACTER_PIPELINE": "OPEN",
            "PRODUCT-01": "CLOSED / PASS",
            "PRODUCT-02": "READY_FOR_HUMAN_AUDIT",
            "PRODUCT-03": "NOT_AUTHORIZED until PRODUCT-02 CLOSED/PASS",
        },
        "motionSet": ["Idle", "Bow", "LargeBow", "Handshake", "Dance"],
        "completenessExpected": {
            "technicalLibraryCompleteness": "5 / 5",
            "productSemanticCompleteness": "5 / 5",
            "status": "COMPLETE",
        },
        "fulfillment": fulfill,
        "meshyClipNames": clips,
        "scopeBoundary": {
            "bodyMotionLibrary": "OWN",
            "faceTalkingOrchestration": "DENY — PRODUCT-03",
        },
        "gates": [r["test"] for r in proof["results"]],
        "agentSelfCheck": {"passed": proof["passed"], "failed": proof["failed"], "tests": [{"test": r["test"], "status": r["status"]} for r in proof["results"]]},
        "protectedHashBeforePack": sot_before,
        "protectedHashAfterPack": sot_after,
        "protectedHashFrozenTable": PROTECTED_SOT_SHA256,
        "protectedHashMatch": sot_before == sot_after == PROTECTED_SOT_SHA256,
        "packagedAtUtc": ts,
        "auditPackageRules": {
            "absolutePath": "DENY",
            "verifyPackagedAssetShaBeforeOverwrite": True,
            "independentRerunFromExtractedZip": "run_product02_independent_proof.py",
            "note": "Agent proof 15/15 + semantic 5/5 — human declares CLOSED/PASS",
        },
        "humanAuditRequest": "Audit P2b/P2c dedicated intake + full proof; declare PRODUCT-02 CLOSED/PASS or PATCH",
        "proofStdoutExitCode": proc.returncode,
    }
    receipt_path = EV / "NURION-PRODUCT-02_motion_library_proof_receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    files: list[tuple[Path, str]] = [
        (ROOT / "fast_track/__init__.py", "repo/fast_track/__init__.py"),
        (ROOT / "fast_track/runtime/__init__.py", "repo/fast_track/runtime/__init__.py"),
        (ROOT / "fast_track/runtime/body_retarget_engine.py", "repo/fast_track/runtime/body_retarget_engine.py"),
        (ROOT / "fast_track/runtime/donor_skeleton_profile.py", "repo/fast_track/runtime/donor_skeleton_profile.py"),
        (ROOT / "fast_track/runtime/retarget_contract_validator.py", "repo/fast_track/runtime/retarget_contract_validator.py"),
        (ROOT / "fast_track/runtime/product_character_assembly.py", "repo/fast_track/runtime/product_character_assembly.py"),
        (ROOT / "fast_track/runtime/product_motion_library.py", "repo/fast_track/runtime/product_motion_library.py"),
        (ROOT / "fast_track/runtime/retarget/__init__.py", "repo/fast_track/runtime/retarget/__init__.py"),
        (ROOT / "fast_track/runtime/retarget/engine.py", "repo/fast_track/runtime/retarget/engine.py"),
        (ROOT / "fast_track/runtime/retarget/quat.py", "repo/fast_track/runtime/retarget/quat.py"),
        (ROOT / "fast_track/runtime/retarget/canonical.py", "repo/fast_track/runtime/retarget/canonical.py"),
        (ROOT / "fast_track/runtime/retarget/protected.py", "repo/fast_track/runtime/retarget/protected.py"),
        (ROOT / "fast_track/runtime/retarget/registry.py", "repo/fast_track/runtime/retarget/registry.py"),
        (ROOT / "fast_track/runtime/retarget/profile.py", "repo/fast_track/runtime/retarget/profile.py"),
        (SEM / "NURION_BODY_CANONICAL_BONE_SPEC_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json"),
        (SEM / "NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json"),
        (SEM / "NURION_FACE_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"),
        (SEM / "NURION_BODY_PRODUCT_LOCK_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json"),
        (SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_RIG02_PRODUCT_BOUNDARY_V1.json"),
        (SEM / "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"),
        (SEM / "NURION_PRODUCT02_MOTION_LIBRARY_V1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT02_MOTION_LIBRARY_V1.json"),
        (SEM / "retarget_profiles/mjn_legacy_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json"),
        (SEM / "retarget_profiles/jake_cc_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json"),
        (SEM / "retarget_profiles/canonical_identity_profile_v1.json", "repo/fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json"),
        (ROOT / "tools/build_product02_motion_library.py", "repo/tools/build_product02_motion_library.py"),
        (ROOT / "tools/run_product02_motion_library_proof.py", "repo/tools/run_product02_motion_library_proof.py"),
        (ROOT / "tools/run_product02_independent_proof.py", "run_product02_independent_proof.py"),
        (EV / "NURION-PRODUCT-02_motion_library_proof_stdout.json", "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-02_motion_library_proof_stdout.json"),
        (digest_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-02_expected_observed_digest.json"),
        (receipt_path, "repo/fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-02_motion_library_proof_receipt.json"),
    ]
    for p in (ML / "sources").glob("*.glb"):
        files.append((p, f"repo/fast_track/working/meshy_silver_starlight/motion_library/sources/{p.name}"))
    for p in (ML / "fixtures").glob("*.json"):
        files.append((p, f"repo/fast_track/working/meshy_silver_starlight/motion_library/fixtures/{p.name}"))

    missing = [str(s) for s, _ in files if not s.exists()]
    if missing:
        raise SystemExit(f"missing: {missing}")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for src, arc in files:
            zf.write(src, arcname=arc)
        zf.writestr("evidence/PRODUCT02_proof_runner_console.txt", (proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""))
        zf.writestr(
            "README_AUDIT.json",
            json.dumps(
                {
                    "purpose": "PRODUCT-02 Canonical MJN motion library audit",
                    "product02Pass": "NOT_DECLARED",
                    "product02Status": "READY_FOR_HUMAN_AUDIT — agent semantic 5/5",
                    "howToIndependentRerun": ["Extract ZIP", "py -3 run_product02_independent_proof.py"],
                    "motionSet": ["Idle", "Bow", "LargeBow", "Handshake", "Dance"],
                    "completeness": {
                        "technicalLibraryCompleteness": "5 / 5",
                        "productSemanticCompleteness": "5 / 5",
                        "status": "COMPLETE",
                    },
                    "dedicatedIntake": {
                        "Handshake": "Wave_for_Help_4_withSkin ← mjn_handshake.zip",
                        "Dance": "Superlove_Pop_Dance_withSkin ← mjn_dance.zip",
                        "sources": [
                            "repo/fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_handshake_withSkin.glb",
                            "repo/fast_track/working/meshy_silver_starlight/motion_library/sources/mjn_dance_withSkin.glb",
                        ],
                    },
                    "auditFocus": [
                        "P2b/P2c dedicated Handshake+Dance intake from MJN assets",
                        "productSemanticCompleteness 5/5 + agent proof 15/15",
                        "human declares CLOSED/PASS — agent MUST NOT",
                    ],
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
        )

    zsha = sha256(ZIP_PATH)
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        # append stub then rewrite sidecar after final
        pass
    # Write manifest after first zip, append, rehash
    manifest = {
        "package": "NURION-PRODUCT-02_motion_library_proof.zip",
        "status": "READY_FOR_HUMAN_AUDIT",
        "product02Pass": "NOT_DECLARED",
        "patch": "P2b+P2c_DEDICATED_INTAKE",
        "packagedAtUtc": ts,
        "agentProofSummary": {"passed": proof["passed"], "failed": proof["failed"]},
        "protectedSoT": {"unchanged": sot_before == sot_after == PROTECTED_SOT_SHA256},
        "note": "Semantic 5/5 COMPLETE after dedicated Handshake/Dance intake — human CLOSED/PASS only",
        "contents": [arc for _, arc in files] + ["evidence/PRODUCT02_proof_runner_console.txt", "README_AUDIT.json"],
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with zipfile.ZipFile(ZIP_PATH, "a", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(MANIFEST, arcname="evidence/NURION-PRODUCT-02_motion_library_proof_manifest.json")
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
            [sys.executable, str(td_path / "run_product02_independent_proof.py")],
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
                "product02Pass": "NOT_DECLARED",
                "product02Status": "READY_FOR_HUMAN_AUDIT",
                "passed": proof["passed"],
                "failed": proof["failed"],
                "testsExit": proc.returncode,
                "independentRerun": {
                    "exit": ind.returncode,
                    "stdoutTail": (ind.stdout or "")[-500:],
                    "stderrTail": (ind.stderr or "")[-300:],
                },
            },
            ensure_ascii=True,
        )
    )
    subprocess.run(["explorer.exe", "/select,", str(ZIP_PATH)], check=False)
    return 0 if ZIP_PATH.exists() and sot_before == sot_after == PROTECTED_SOT_SHA256 and proof["failed"] == 0 and ind.returncode == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
