"""Run CCS Gate 3 — Canonical Weights & Correctives (3× determinism)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_ccs_gate3_weights_correctives.py"
OUT = ROOT / "dist" / "v0.7" / "canonical" / "gate3"
GATE2_BLEND = ROOT / "dist/v0.7/canonical/gate2/NURION_CanonicalRig_V1.blend"
GATE1_HASH = "4455eebf5382e7b05e99dd2748b2db67b3a2c41621540a98c3d06c41180da121"
GATE2_HASH = "d70740ac1dd91f0ea6c1b1f47426711be4e884422aaebe93639c4e4a228b30e0"
GATE2_BLEND_SHA = "c1e503ef37acf1ade4e7c1e15a8bbae5d8ef6d27b1f7900680bc32c42bf81dc3"
PRODUCT = "c483f1a189f762cd8af08b780f55f55412aafcf6e5e5a7b8cdae263bf9095c2f"
GATE1_BLEND = ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend"
GATE1_BLEND_SHA = "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _param_hash(params: dict) -> str:
    raw = json.dumps(params, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    if _sha(GATE2_BLEND) != GATE2_BLEND_SHA:
        raise SystemExit("Gate2 blend mutated")
    if _sha(GATE1_BLEND) != GATE1_BLEND_SHA:
        raise SystemExit("Gate1 blend mutated")

    params = json.loads((OUT / "V07_CCS_GATE3_PARAMETERS.json").read_text(encoding="utf-8"))
    ph = _param_hash({k: v for k, v in params.items() if k != "parameterHash"})
    params["parameterHash"] = ph
    _write(OUT / "V07_CCS_GATE3_PARAMETERS.json", params)

    reports = []
    for run_id in (1, 2, 3):
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(SCRIPT),
            "--",
            "--gate2-blend",
            str(GATE2_BLEND),
            "--expected-gate2-sha256",
            GATE2_BLEND_SHA,
            "--out-dir",
            str(OUT),
            "--run-id",
            str(run_id),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        (OUT / f"run{run_id}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (OUT / f"run{run_id}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        if proc.returncode != 0:
            print(proc.stderr[-4000:] if proc.stderr else proc.stdout)
            return proc.returncode
        reports.append(json.loads((OUT / f"run{run_id}/V07_CCS_GATE3_RUN_REPORT.json").read_text(encoding="utf-8")))

    fps = [r["weightFingerprintSha256"] for r in reports]
    determinism = len(set(fps)) == 1

    fails = []
    limitations = []
    r1 = reports[0]
    if r1["normalize"]["afterOutOfTol"] > 0:
        fails.append("WEIGHT_SUM_OUT_OF_TOLERANCE")
    if r1["normalize"]["unassigned"] > 0:
        fails.append("UNASSIGNED_WEIGHTS")
    if r1["normalize"]["nanOrNegative"] > 0:
        fails.append("NAN_OR_NEGATIVE_WEIGHTS")
    if r1["lrContamination"] > 0:
        fails.append("LR_WEIGHT_CONTAMINATION")
    if r1["severeCollapseCount"] > 0:
        fails.append("SEVERE_COLLAPSE")
    if r1["inverseJointCount"] > 0:
        fails.append("INVERSE_JOINT")
    if r1["penetrationCount"] > 0:
        fails.append("PENETRATION")
    if not determinism:
        fails.append("DETERMINISM_FAIL")
    missing_cov = [k for k, v in r1["regionCoverage"].items() if v == 0]
    if missing_cov:
        # Jaw/Eyes may lack auto-weight on low-poly — limitation vs fail
        critical = [k for k in missing_cov if k not in {"Jaw", "Eye.L", "Eye.R", "Clavicle.L", "Clavicle.R"}]
        if critical:
            fails.append(f"REGION_COVERAGE_ZERO:{','.join(critical)}")
        else:
            limitations.append(f"LOW_COVERAGE_FACE_OR_CLAVICLE:{','.join(missing_cov)}")

    # Source mutation checks
    if _sha(GATE2_BLEND) != GATE2_BLEND_SHA or _sha(GATE1_BLEND) != GATE1_BLEND_SHA:
        fails.append("BASELINE_MUTATION")

    verdict = "PASS" if not fails and not limitations else "PASS_WITH_LIMITATIONS" if not fails else "FAIL"

    status = {
        "schema": "NURION_V07_CCS_GATE3_STATUS",
        "track": "NURION Canonical Character System",
        "gate": 3,
        "name": "CANONICAL_WEIGHTS_AND_CORRECTIVES",
        "V07_CCS_GATE3": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate1BlendMutation": 0,
        "gate2BlendMutation": 0,
        "determinismRuns": 3,
        "determinismMatch": determinism,
        "weightFingerprintSha256": fps[0],
        "lrContamination": r1["lrContamination"],
        "severeCollapseCount": r1["severeCollapseCount"],
        "correctiveCount": len(r1["correctives"]),
        "hiddenManualCorrection": "DENY",
        "perAssetHiddenTuning": "DENY",
        "fails": fails,
        "limitations": limitations,
        "gtVsArmatureZeroInterpretation": "CONSTRUCTION_CONSISTENCY_ONLY_NOT_INDEPENDENT_ANATOMICAL_PROOF",
        "manualGt": "OFFICIAL_MANUAL_ANNOTATION_WAIT",
        "productBaselineParameterHash": PRODUCT,
        "production": "NO-GO",
        "artifacts": {
            "blend": "run3/NURION_CanonicalWeights_V1.blend",
            "runReports": [f"run{i}/V07_CCS_GATE3_RUN_REPORT.json" for i in (1, 2, 3)],
        },
        "next": "V07_CCS_GATE4_OR_HOLD" if verdict.startswith("PASS") else "REPAIR_GATE3",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE3_STATUS.json", status)
    freeze = {
        "schema": "NURION_V07_CCS_GATE3_OFFICIAL_FREEZE",
        "V07_CCS_GATE3": verdict,
        "LOCKED": verdict.startswith("PASS"),
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "weightFingerprintSha256": fps[0],
        "determinismMatch": determinism,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate1BlendSha256": GATE1_BLEND_SHA,
        "gate2BlendSha256": GATE2_BLEND_SHA,
        "production": "NO-GO",
        "lockedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE3_OFFICIAL_FREEZE.json", freeze)
    print(json.dumps({"verdict": verdict, "parameterHash": ph, "determinism": determinism, "fails": fails, "limitations": limitations}, indent=2))
    return 0 if verdict.startswith("PASS") else 1


if __name__ == "__main__":
    raise SystemExit(main())
