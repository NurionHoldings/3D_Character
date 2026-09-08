"""Run CCS Gate 5 — Body Presets & Rig Adaptation (3× determinism)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_ccs_gate5_body_presets_rig_adapt.py"
OUT = ROOT / "dist" / "v0.7" / "canonical" / "gate5"
GATE4_BLEND = ROOT / "dist/v0.7/canonical/gate4/run3/NURION_CanonicalIdentityBeautification_V1.blend"
GATE4_BLEND_SHA = "72b8b2a6ff9708f6d3890de88d95fe670403e238f4514f55cd4c14a621ed502f"
GATE1_BLEND = ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend"
GATE1_BLEND_SHA = "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"
GATE2_BLEND = ROOT / "dist/v0.7/canonical/gate2/NURION_CanonicalRig_V1.blend"
GATE2_BLEND_SHA = "c1e503ef37acf1ade4e7c1e15a8bbae5d8ef6d27b1f7900680bc32c42bf81dc3"
GATE3_BLEND = ROOT / "dist/v0.7/canonical/gate3/run3/NURION_CanonicalWeights_V1.blend"
GATE3_BLEND_SHA = "7d4f04f3da7c95bb0f1bf711d9ac4aff56e830e94e9ab99643e9855698bc01df"
GATE1_HASH = "4455eebf5382e7b05e99dd2748b2db67b3a2c41621540a98c3d06c41180da121"
GATE2_HASH = "d70740ac1dd91f0ea6c1b1f47426711be4e884422aaebe93639c4e4a228b30e0"
GATE3_HASH = "142230368d75491fba392938c9ccfdf9250784cec21514dabff99d09cd5a8a76"
GATE4_HASH = "e2a227d2cf22c1f1d73c84efad4aa3e0498565364291da07c7e4e0d507a13728"
GATE4_MORPH_FP = "ea37894bc3b5fa42e6df6a04699c550231dbd114695a4d8c30963973894dc501"
PRODUCT = "c483f1a189f762cd8af08b780f55f55412aafcf6e5e5a7b8cdae263bf9095c2f"
REQUIRED_PRESETS = ["BALANCED", "SLIM", "SOFT", "ATHLETIC", "TALL_BALANCED", "MINI_SD"]


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
    for p, exp, label in (
        (GATE1_BLEND, GATE1_BLEND_SHA, "Gate1"),
        (GATE2_BLEND, GATE2_BLEND_SHA, "Gate2"),
        (GATE3_BLEND, GATE3_BLEND_SHA, "Gate3"),
        (GATE4_BLEND, GATE4_BLEND_SHA, "Gate4"),
    ):
        if _sha(p) != exp:
            raise SystemExit(f"{label} blend mutated")

    params_path = OUT / "V07_CCS_GATE5_PARAMETERS.json"
    params = json.loads(params_path.read_text(encoding="utf-8"))
    ph = _param_hash({k: v for k, v in params.items() if k != "parameterHash"})
    params["parameterHash"] = ph
    _write(params_path, params)

    reports = []
    for run_id in (1, 2, 3):
        cmd = [
            str(BLENDER),
            "--background",
            "--python",
            str(SCRIPT),
            "--",
            "--gate4-blend",
            str(GATE4_BLEND),
            "--expected-gate4-sha256",
            GATE4_BLEND_SHA,
            "--params-json",
            str(params_path),
            "--out-dir",
            str(OUT),
            "--run-id",
            str(run_id),
        ]
        proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
        (OUT / f"run{run_id}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (OUT / f"run{run_id}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        if proc.returncode != 0:
            print(proc.stderr[-6000:] if proc.stderr else proc.stdout)
            return proc.returncode
        reports.append(json.loads((OUT / f"run{run_id}/V07_CCS_GATE5_RUN_REPORT.json").read_text(encoding="utf-8")))

    fps = [r["bodyFingerprintSha256"] for r in reports]
    determinism = len(set(fps)) == 1
    r1 = reports[0]
    fails = []

    missing = [p for p in REQUIRED_PRESETS if p not in r1["presets"]]
    if missing:
        fails.append(f"PRESETS_MISSING:{','.join(missing)}")
    if len(r1.get("bodyAxes", [])) < 9:
        fails.append("BODY_AXES_INCOMPLETE")
    if not r1["topologyImmutable"]:
        fails.append("TOPOLOGY_MUTATED")
    if r1["identityBodyContamination"]["contaminationCount"] > 0:
        fails.append("IDENTITY_BODY_CONTAMINATION")
    if r1["severeCollapseCount"] > 0:
        fails.append("SEVERE_COLLAPSE")
    if r1["inverseJointCount"] > 0:
        fails.append("INVERSE_JOINT")
    if r1["penetrationCount"] > 0:
        fails.append("PENETRATION")
    if r1.get("correctiveContractInheritance") != "PASS":
        fails.append("CORRECTIVE_CONTRACT_NOT_INHERITED")
    if r1["extremeBodyCombo"].get("verdict") != "ABSTAIN":
        fails.append("EXTREME_COMBO_NOT_ABSTAINED")
    for pname, pres in r1["presets"].items():
        if not pres.get("boneNamesPreserved") or not pres.get("hierarchyPreserved") or not pres.get("rollPreserved"):
            fails.append(f"BONE_CONTRACT_FAIL:{pname}")
        if pres.get("weightNormalize", {}).get("afterOutOfTol", 1) > 0:
            fails.append(f"WEIGHT_SUM_FAIL:{pname}")
        if pres.get("weightNormalize", {}).get("unassigned", 1) > 0:
            fails.append(f"WEIGHT_UNASSIGNED:{pname}")
    if not determinism:
        fails.append("DETERMINISM_FAIL")
    if (
        _sha(GATE1_BLEND) != GATE1_BLEND_SHA
        or _sha(GATE2_BLEND) != GATE2_BLEND_SHA
        or _sha(GATE3_BLEND) != GATE3_BLEND_SHA
        or _sha(GATE4_BLEND) != GATE4_BLEND_SHA
    ):
        fails.append("BASELINE_MUTATION_G1234")

    verdict = "PASS" if not fails else "FAIL"
    status = {
        "schema": "NURION_V07_CCS_GATE5_STATUS",
        "track": "NURION Canonical Character System",
        "gate": 5,
        "name": "BODY_PRESETS_AND_RIG_ADAPTATION",
        "V07_CCS_GATE5": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate4MorphFingerprintSha256": GATE4_MORPH_FP,
        "gate1BlendMutation": 0,
        "gate2BlendMutation": 0,
        "gate3BlendMutation": 0,
        "gate4BlendMutation": 0,
        "determinismRuns": 3,
        "determinismMatch": determinism,
        "bodyFingerprintSha256": fps[0],
        "presetCount": len(r1["presets"]),
        "presets": REQUIRED_PRESETS,
        "bodyAxisCount": len(r1.get("bodyAxes", [])),
        "topologyImmutable": r1["topologyImmutable"],
        "identityBodyContamination": r1["identityBodyContamination"]["contaminationCount"],
        "jointAdaptation": "J_prime = J + sum_i(w_i * DeltaJ_i)",
        "boneNameHierarchyRollPreserved": all(
            p.get("boneNamesPreserved") and p.get("hierarchyPreserved") and p.get("rollPreserved")
            for p in r1["presets"].values()
        ),
        "weightRenormalizeRelax": True,
        "correctiveContractInheritance": r1.get("correctiveContractInheritance"),
        "severeCollapseCount": r1["severeCollapseCount"],
        "inverseJointCount": r1["inverseJointCount"],
        "penetrationCount": r1["penetrationCount"],
        "extremeBodyCombo": "ABSTAIN",
        "fails": fails,
        "limitations": [],
        "infoNotes": [
            "PROCEDURAL_BODY_MORPHS_NOT_ARTIST_CERTIFIED",
            "EXTREME_BODY_COMBO_ABSTAIN_NO_FORCED_PASS",
        ],
        "inheritedLimitationsFromGate4": params.get("inheritedLimitationsFromGate4", []),
        "manualGt": "INDEPENDENT_PARALLEL_OFFICIAL_MANUAL_ANNOTATION_WAIT",
        "productBaselineParameterHash": PRODUCT,
        "production": "NO-GO",
        "LOCKED": verdict == "PASS",
        "artifacts": {
            "blend": "run3/NURION_CanonicalBodyPresets_V1.blend",
            "runReports": [f"run{i}/V07_CCS_GATE5_RUN_REPORT.json" for i in (1, 2, 3)],
        },
        "next": "V07_CCS_GATE6_OR_HOLD" if verdict == "PASS" else "REPAIR_GATE5",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE5_STATUS.json", status)
    freeze = {
        "schema": "NURION_V07_CCS_GATE5_OFFICIAL_FREEZE",
        "V07_CCS_GATE5": verdict,
        "LOCKED": verdict == "PASS",
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "bodyFingerprintSha256": fps[0],
        "determinismMatch": determinism,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate1BlendSha256": GATE1_BLEND_SHA,
        "gate2BlendSha256": GATE2_BLEND_SHA,
        "gate3BlendSha256": GATE3_BLEND_SHA,
        "gate4BlendSha256": GATE4_BLEND_SHA,
        "extremeBodyCombo": "ABSTAIN",
        "inheritedLimitationsFromGate4": params.get("inheritedLimitationsFromGate4", []),
        "production": "NO-GO",
        "lockedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE5_OFFICIAL_FREEZE.json", freeze)
    print(json.dumps({"verdict": verdict, "parameterHash": ph, "determinism": determinism, "fails": fails}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
