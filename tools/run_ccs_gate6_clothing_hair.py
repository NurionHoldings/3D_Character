"""Run CCS Gate 6 — Clothing & Hair Library (3× determinism)."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
SCRIPT = ROOT / "tools" / "blender_ccs_gate6_clothing_hair.py"
OUT = ROOT / "dist" / "v0.7" / "canonical" / "gate6"
GATE5_BLEND = ROOT / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend"
GATE5_BLEND_SHA = "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86"
GATE1_BLEND = ROOT / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend"
GATE1_BLEND_SHA = "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2"
GATE2_BLEND = ROOT / "dist/v0.7/canonical/gate2/NURION_CanonicalRig_V1.blend"
GATE2_BLEND_SHA = "c1e503ef37acf1ade4e7c1e15a8bbae5d8ef6d27b1f7900680bc32c42bf81dc3"
GATE3_BLEND = ROOT / "dist/v0.7/canonical/gate3/run3/NURION_CanonicalWeights_V1.blend"
GATE3_BLEND_SHA = "7d4f04f3da7c95bb0f1bf711d9ac4aff56e830e94e9ab99643e9855698bc01df"
GATE4_BLEND = ROOT / "dist/v0.7/canonical/gate4/run3/NURION_CanonicalIdentityBeautification_V1.blend"
GATE4_BLEND_SHA = "72b8b2a6ff9708f6d3890de88d95fe670403e238f4514f55cd4c14a621ed502f"
GATE1_HASH = "4455eebf5382e7b05e99dd2748b2db67b3a2c41621540a98c3d06c41180da121"
GATE2_HASH = "d70740ac1dd91f0ea6c1b1f47426711be4e884422aaebe93639c4e4a228b30e0"
GATE3_HASH = "142230368d75491fba392938c9ccfdf9250784cec21514dabff99d09cd5a8a76"
GATE4_HASH = "e2a227d2cf22c1f1d73c84efad4aa3e0498565364291da07c7e4e0d507a13728"
GATE5_HASH = "2414b81dab660dccdd7f4f3ec6597c8afdbc824bf97cd8cb2f428ae4b3a7290b"
GATE5_BODY_FP = "4db69cb2657bc3e2cba3cf533d1d0e1d3e86c58e9989b4b999cc736ae4999c14"
PRODUCT = "c483f1a189f762cd8af08b780f55f55412aafcf6e5e5a7b8cdae263bf9095c2f"
CLOTHING = [
    "BUSINESS_SUIT_01",
    "BUSINESS_SUIT_02",
    "OFFICE_CASUAL_01",
    "BLOUSE_SLACKS_01",
    "FORMAL_DRESS_01",
    "BRAND_UNIFORM_01",
]
HAIR = [
    "SHORT_NEAT_01",
    "SHORT_LAYERED_01",
    "BOB_01",
    "MEDIUM_STRAIGHT_01",
    "LONG_TIED_01",
    "LONG_WAVE_01",
]


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
        (GATE5_BLEND, GATE5_BLEND_SHA, "Gate5"),
    ):
        if _sha(p) != exp:
            raise SystemExit(f"{label} blend mutated")

    params_path = OUT / "V07_CCS_GATE6_PARAMETERS.json"
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
            "--gate5-blend",
            str(GATE5_BLEND),
            "--expected-gate5-sha256",
            GATE5_BLEND_SHA,
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
            print(proc.stderr[-7000:] if proc.stderr else proc.stdout)
            return proc.returncode
        reports.append(json.loads((OUT / f"run{run_id}/V07_CCS_GATE6_RUN_REPORT.json").read_text(encoding="utf-8")))

    fps = [r["libraryFingerprintSha256"] for r in reports]
    determinism = len(set(fps)) == 1
    r1 = reports[0]
    fails = []

    if sorted(r1["clothingLibrary"]) != sorted(CLOTHING):
        fails.append("CLOTHING_LIBRARY_INCOMPLETE")
    if sorted(r1["hairLibrary"]) != sorted(HAIR):
        fails.append("HAIR_LIBRARY_INCOMPLETE")
    if r1["matrixSize"] != 6 * 6 * 6:
        fails.append("MATRIX_SIZE_NOT_216")
    if not r1["canonicalTopologyUnchanged"]:
        fails.append("TOPOLOGY_MUTATED")
    if not r1["canonicalRigUnchanged"]:
        fails.append("RIG_MUTATED")
    if not r1["identityMorphUnchanged"]:
        fails.append("IDENTITY_MORPH_MUTATED")
    if r1["weightTransferFails"] > 0:
        fails.append("WEIGHT_TRANSFER_FAIL")
    if r1["homepagePoseResults"]["penetration"] > 0:
        fails.append("HOMEPAGE_POSE_PENETRATION")
    if r1["homepagePoseResults"]["jitter"] > 0:
        fails.append("HOMEPAGE_POSE_JITTER")
    if r1["homepagePoseResults"]["explode"] > 0:
        fails.append("HOMEPAGE_POSE_EXPLODE")
    if r1["regionPenetrationSevereTotal"] > 0:
        fails.append("REGION_PENETRATION")
    if not r1["interiorMask"].get("sourceBodyDeleted") is False:
        fails.append("SOURCE_BODY_DELETED")
    if r1.get("artistQualityCertification") != "NOT_CLAIMED":
        fails.append("ARTIST_QUALITY_OVERCLAIM")
    if r1["abstainCount"] < 1:
        fails.append("ABSTAIN_POLICY_MISSING")
    if r1["eligibleCount"] < 1:
        fails.append("NO_ELIGIBLE_COMBOS")
    # ownership evidence present for all assets
    own_c = {o["assetId"] for o in r1["ownership"]["clothing"]}
    own_h = {o["assetId"] for o in r1["ownership"]["hair"]}
    if own_c != set(CLOTHING) or own_h != set(HAIR):
        fails.append("OWNERSHIP_EVIDENCE_INCOMPLETE")
    if not r1.get("variantSeparation", {}).get("baseAssetsDoNotBakeBrandColors"):
        fails.append("VARIANT_SEPARATION_FAIL")
    if not determinism:
        fails.append("DETERMINISM_FAIL")
    if (
        _sha(GATE1_BLEND) != GATE1_BLEND_SHA
        or _sha(GATE2_BLEND) != GATE2_BLEND_SHA
        or _sha(GATE3_BLEND) != GATE3_BLEND_SHA
        or _sha(GATE4_BLEND) != GATE4_BLEND_SHA
        or _sha(GATE5_BLEND) != GATE5_BLEND_SHA
    ):
        fails.append("BASELINE_MUTATION_G12345")

    verdict = "PASS" if not fails else "FAIL"
    status = {
        "schema": "NURION_V07_CCS_GATE6_STATUS",
        "track": "NURION Canonical Character System",
        "gate": 6,
        "name": "CLOTHING_AND_HAIR_LIBRARY",
        "V07_CCS_GATE6": verdict,
        "parameterHash": ph,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "gate5BodyFingerprintSha256": GATE5_BODY_FP,
        "gate1BlendMutation": 0,
        "gate2BlendMutation": 0,
        "gate3BlendMutation": 0,
        "gate4BlendMutation": 0,
        "gate5BlendMutation": 0,
        "determinismRuns": 3,
        "determinismMatch": determinism,
        "libraryFingerprintSha256": fps[0],
        "clothingCount": 6,
        "hairCount": 6,
        "matrixSize": r1["matrixSize"],
        "eligibleCount": r1["eligibleCount"],
        "abstainCount": r1["abstainCount"],
        "canonicalTopologyRigIdentityUnchanged": bool(
            r1["canonicalTopologyUnchanged"] and r1["canonicalRigUnchanged"] and r1["identityMorphUnchanged"]
        ),
        "weightTransferRenormalize": "PASS" if r1["weightTransferFails"] == 0 else "FAIL",
        "homepagePosePenetrationJitterExplode": r1["homepagePoseResults"],
        "interiorMaskWithoutDeletingSource": True,
        "variantSeparation": ["MATERIAL", "COLOR", "BRAND"],
        "proceduralQualityRole": "FUNCTIONAL_VERIFICATION_ONLY_NOT_ARTIST_CERTIFIED",
        "artistQualityCertification": "NOT_CLAIMED",
        "fails": fails,
        "limitations": [],
        "infoNotes": [
            "PROCEDURAL_CLOTHING_HAIR_FUNCTIONAL_ONLY_NOT_ARTIST_CERTIFIED",
            "BRAND_UNIFORM_ABSTAINS_PENDING_LICENSE_PACK",
            "V06_PACKAGE_ABSENT_NO_BYTE_VERIFY",
        ],
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "manualGt": "INDEPENDENT_PARALLEL_OFFICIAL_MANUAL_ANNOTATION_WAIT",
        "productBaselineParameterHash": PRODUCT,
        "production": "NO-GO",
        "LOCKED": verdict == "PASS",
        "artifacts": {
            "blend": "run3/NURION_CanonicalClothingHair_V1.blend",
            "runReports": [f"run{i}/V07_CCS_GATE6_RUN_REPORT.json" for i in (1, 2, 3)],
            "ownership": "run3/V07_CCS_GATE6_OWNERSHIP.json",
            "eligibilityMatrix": "run3/V07_CCS_GATE6_ELIGIBILITY_MATRIX.json",
        },
        "next": "V07_CCS_GATE7_OR_HOLD" if verdict == "PASS" else "REPAIR_GATE6",
        "updatedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE6_STATUS.json", status)
    freeze = {
        "schema": "NURION_V07_CCS_GATE6_OFFICIAL_FREEZE",
        "V07_CCS_GATE6": verdict,
        "LOCKED": verdict == "PASS",
        "parameterHash": ph,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "libraryFingerprintSha256": fps[0],
        "determinismMatch": determinism,
        "gate1ParameterHash": GATE1_HASH,
        "gate2ParameterHash": GATE2_HASH,
        "gate3ParameterHash": GATE3_HASH,
        "gate4ParameterHash": GATE4_HASH,
        "gate5ParameterHash": GATE5_HASH,
        "gate1BlendSha256": GATE1_BLEND_SHA,
        "gate2BlendSha256": GATE2_BLEND_SHA,
        "gate3BlendSha256": GATE3_BLEND_SHA,
        "gate4BlendSha256": GATE4_BLEND_SHA,
        "gate5BlendSha256": GATE5_BLEND_SHA,
        "proceduralQualityRole": "FUNCTIONAL_VERIFICATION_ONLY_NOT_ARTIST_CERTIFIED",
        "inheritedLimitations": params.get("inheritedLimitations", []),
        "production": "NO-GO",
        "lockedAt": datetime.now(timezone.utc).isoformat(),
    }
    _write(OUT / "V07_CCS_GATE6_OFFICIAL_FREEZE.json", freeze)
    print(json.dumps({"verdict": verdict, "parameterHash": ph, "determinism": determinism, "fails": fails}, indent=2))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
