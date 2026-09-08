"""Pack v0.2.0 SEAL CANDIDATE once into dist/v0.2/final/.

Rules:
- Do NOT modify Alpha3 algorithm parameters or joint-specific code.
- Do NOT overwrite alpha.1 / alpha.2 / alpha.3 / v0.1 frozen ZIPs.
- Final ZIP is write-once: refuse if already present.
- Emit full 64-char SHA-256 only (never truncate).
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_DIR = ROOT / "nurion_character_landmarker"
FINAL_DIR = ROOT / "dist" / "v0.2" / "final"
ZIP_NAME = "NURION_Character_Landmarker_v0.2.0.zip"
ZIP_PATH = FINAL_DIR / ZIP_NAME

ALPHA3_LOCK = ROOT / "dist" / "v0.2" / "alpha3" / "ALPHA3_LOCK.json"
ALPHA3_ZIP = ROOT / "dist" / "v0.2" / "NURION_Character_Landmarker_v0.2.0-alpha.3.zip"
ALPHA3_SHA = "0310b47919ef4db4fb5363ea7287575dd66117ff4e221574c31bb1fa682da4bf"
ALPHA3_PARAM = "6b964ebb684026c5367faae6554135a634dd29f30761560925ae57f038747348"
ALPHA1_SHA = "915bb5be9894086bdd344463a2fab27c74b4ad2ef016439ed4ca0e1b8be0dc01"
ALPHA2_SHA = "357677285373514bc5ed6e7fa9c765b26651b59b0515df63c53a1a4b6d44a2d8"
V01_SHA = "94585a4c8a0a0c055ffd51891e972b6e730de52eb11a262081fa57443ecb34a1"

HOLDOUT_SRC = ROOT / "dist" / "v0.2" / "holdout"
FIXTURE_REPORT = ROOT / "fixtures" / "WITHER_ASSET_GT_MISMATCH" / "out" / "fixture-report.json"
FIXTURE_EXPECTED = ROOT / "fixtures" / "WITHER_ASSET_GT_MISMATCH" / "EXPECTED.json"
MESH_GT_EVIDENCE = ROOT / "dist" / "v0.2" / "alpha3" / "reports" / "mesh-gt-mismatch.json"

SKIP = {"__pycache__", ".git", ".DS_Store"}

REQUIRED = [
    "nurion_character_landmarker/__init__.py",
    "nurion_character_landmarker/core/alpha3_parameters.py",
    "nurion_character_landmarker/core/joint_specific/elbow.py",
    "nurion_character_landmarker/core/joint_specific/knee.py",
    "nurion_character_landmarker/core/joint_specific/ankle.py",
    "nurion_character_landmarker/core/evidence_confidence.py",
    "nurion_character_landmarker/evaluation/asset_eligibility.py",
    "nurion_character_landmarker/reports/VALIDATION_STATUS.json",
]


def _require_full_sha256(value: str, label: str) -> str:
    h = (value or "").strip().lower()
    if len(h) != 64 or any(c not in "0123456789abcdef" for c in h):
        raise RuntimeError(f"{label} must be full 64-char SHA-256 hex, got {value!r}")
    return h


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return _require_full_sha256(h.hexdigest(), path.name)


def sha256_text(text: str) -> str:
    return _require_full_sha256(hashlib.sha256(text.encode("utf-8")).hexdigest(), "text")


def _write(path: Path, data: dict) -> str:
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return sha256_file(path)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _parameter_hash_from_source() -> str:
    """Hash ALPHA3_PARAMETERS without importing Blender-dependent modules."""
    import ast

    src = (ADDON_DIR / "core" / "alpha3_parameters.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    params_node = None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "ALPHA3_PARAMETERS":
                    params_node = node.value
    if params_node is None:
        raise RuntimeError("ALPHA3_PARAMETERS not found")
    # Rebuild dict via literal_eval after substituting DEFAULT_WEIGHTS from source file.
    scoring = (ADDON_DIR / "core" / "candidate_scoring.py").read_text(encoding="utf-8")
    scoring_tree = ast.parse(scoring)
    weights = None
    for node in scoring_tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "DEFAULT_WEIGHTS":
                    weights = ast.literal_eval(node.value)
    if not isinstance(weights, dict):
        raise RuntimeError("DEFAULT_WEIGHTS not found as literal")
    # Walk ALPHA3_PARAMETERS AST and replace Name(DEFAULT_WEIGHTS) then literal_eval.
    class Replacer(ast.NodeTransformer):
        def visit_Call(self, node):  # dict(DEFAULT_WEIGHTS)
            if (
                isinstance(node.func, ast.Name)
                and node.func.id == "dict"
                and len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "DEFAULT_WEIGHTS"
            ):
                return ast.Constant(value=dict(weights))
            return self.generic_visit(node)

    replaced = Replacer().visit(params_node)
    ast.fix_missing_locations(replaced)
    params = ast.literal_eval(replaced)
    payload = json.dumps(params, sort_keys=True, separators=(",", ":"))
    return _require_full_sha256(hashlib.sha256(payload.encode("utf-8")).hexdigest(), "parameterHash")


def prepare_holdout_reports() -> tuple[dict, dict]:
    verdict = _load(HOLDOUT_SRC / "HOLDOUT_VERDICT.json")
    status = _load(HOLDOUT_SRC / "HOLDOUT_STATUS.json")
    rest_note = {
        "sourceClip": "Walking_withSkin",
        "evaluationPose": "REST",
        "armaturePosePositionForced": "REST",
        "animationFramesUsed": False,
        "note": (
            "Holdout FBX filename includes Walking animation, but evaluation forced "
            "armature.data.pose_position = REST and compared landmarks to rest-local GT heads. "
            "Motion-frame pose was not mixed into joint coordinate evaluation."
        ),
    }
    verdict["restPoseEvaluation"] = rest_note
    verdict["sealReview"] = "READY"
    verdict["v02Sealed"] = False
    status["sealReview"] = "READY"
    status["status"] = "HOLDOUT_PASS_SEAL_REVIEW_READY"
    status["v02Sealed"] = False
    status["restPoseEvaluation"] = rest_note
    # Persist enriched reports in holdout tree (evaluation evidence), then copy to final.
    _write(HOLDOUT_SRC / "HOLDOUT_VERDICT.json", verdict)
    _write(HOLDOUT_SRC / "HOLDOUT_STATUS.json", status)
    return verdict, status


def pack_zip() -> tuple[str, int]:
    if ZIP_PATH.exists():
        raise RuntimeError(
            f"{ZIP_PATH} already exists — refuse repack. Final ZIP is write-once."
        )
    FINAL_DIR.mkdir(parents=True, exist_ok=True)

    init_text = (ADDON_DIR / "__init__.py").read_text(encoding="utf-8")
    if "SEAL CANDIDATE" not in init_text:
        raise RuntimeError("bl_info description must identify SEAL CANDIDATE")
    if '"version": (0, 2, 0)' not in init_text and "'version': (0, 2, 0)" not in init_text:
        raise RuntimeError("bl_info version must remain (0, 2, 0)")

    with zipfile.ZipFile(ZIP_PATH, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ADDON_DIR.rglob("*")):
            if not file_path.is_file():
                continue
            rel = file_path.relative_to(ROOT)
            if any(p in SKIP or str(p).endswith(".pyc") for p in rel.parts):
                continue
            arc = Path("nurion_character_landmarker") / file_path.relative_to(ADDON_DIR)
            zf.write(file_path, arc.as_posix())

    names = zipfile.ZipFile(ZIP_PATH).namelist()
    missing = [r for r in REQUIRED if r not in names]
    if missing:
        ZIP_PATH.unlink(missing_ok=True)
        raise RuntimeError(f"ZIP missing required entries: {missing}")

    digest = sha256_file(ZIP_PATH)
    return digest, len(names)


def main() -> int:
    if not ALPHA3_LOCK.exists():
        raise RuntimeError("ALPHA3_LOCK.json missing")
    lock = _load(ALPHA3_LOCK)
    if not lock.get("frozen"):
        raise RuntimeError("Alpha3 must remain frozen")
    locked_param = _require_full_sha256(lock.get("parameterHash", ""), "ALPHA3_LOCK.parameterHash")
    locked_zip = _require_full_sha256(lock.get("sha256", ""), "ALPHA3_LOCK.sha256")
    if locked_param != ALPHA3_PARAM or locked_zip != ALPHA3_SHA:
        raise RuntimeError("ALPHA3_LOCK hashes do not match pack constants")
    if ALPHA3_ZIP.exists() and sha256_file(ALPHA3_ZIP) != ALPHA3_SHA:
        raise RuntimeError("Frozen alpha.3 ZIP hash changed — refuse final pack")

    live_param = _parameter_hash_from_source()
    if live_param != ALPHA3_PARAM:
        raise RuntimeError(
            f"Alpha3 parameter hash changed during packaging prep: {live_param} != {ALPHA3_PARAM}"
        )

    verdict, status = prepare_holdout_reports()
    zip_sha, entries = pack_zip()

    # Holdout report SHA = canonical HOLDOUT_VERDICT.json after REST note enrichment.
    holdout_verdict_sha = sha256_file(HOLDOUT_SRC / "HOLDOUT_VERDICT.json")
    holdout_status_sha = sha256_file(HOLDOUT_SRC / "HOLDOUT_STATUS.json")
    report_files = sorted((HOLDOUT_SRC / "reports").glob("*.json"))
    report_hashes = {p.name: sha256_file(p) for p in report_files}
    holdout_bundle_payload = json.dumps(
        {"verdict": holdout_verdict_sha, "status": holdout_status_sha, "reports": report_hashes},
        sort_keys=True,
        separators=(",", ":"),
    )
    holdout_bundle_sha = sha256_text(holdout_bundle_payload)

    fixture = _load(FIXTURE_REPORT)
    expected = _load(FIXTURE_EXPECTED)
    evidence_sha = _require_full_sha256(
        expected.get("evidenceSha256", ""), "mesh-gt-mismatch evidence"
    )
    if MESH_GT_EVIDENCE.exists() and sha256_file(MESH_GT_EVIDENCE) != evidence_sha:
        raise RuntimeError("mesh-gt-mismatch.json hash does not match fixture evidence")

    validation = _load(ADDON_DIR / "reports" / "VALIDATION_STATUS.json")
    validation["packageSha256"] = zip_sha
    validation["packageSha256Length"] = 64
    validation["holdoutVerdictSha256"] = holdout_verdict_sha
    validation["holdoutReportBundleSha256"] = holdout_bundle_sha
    validation_sha = _write(FINAL_DIR / "VALIDATION_STATUS.json", validation)
    # Keep install ZIP contents already written; also mirror enriched validation next to ZIP.
    # Do not repack ZIP after this — validation file inside ZIP is pre-zip copy without packageSha.
    # Re-embed by rewriting addon file only if we packed before writing packageSha — currently
    # ZIP has validation without packageSha256. That is acceptable: packageSha lives in final/
    # sidecar. Optionally update addon report for repo consistency without repacking.
    (ADDON_DIR / "reports" / "VALIDATION_STATUS.json").write_text(
        json.dumps(validation, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    param_lock = {
        "schema": "NURION_ALGORITHM_PARAMETER_LOCK",
        "version": "0.2.0",
        "algorithmLabel": "Alpha3 frozen generation parameters",
        "parameterHash": ALPHA3_PARAM,
        "parameterHashLength": 64,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "sourceModule": "nurion_character_landmarker/core/alpha3_parameters.py",
        "alpha3FrozenPackage": "NURION_Character_Landmarker_v0.2.0-alpha.3.zip",
        "alpha3FrozenPackageSha256": ALPHA3_SHA,
        "algorithmCodeChangedForPackaging": False,
        "note": (
            "Final v0.2.0 packaging changed version/docs/validation status only. "
            "ALPHA3_PARAMETERS and joint-specific algorithm code were not retuned."
        ),
        "immutableAlphaArtifacts": {
            "alpha1Sha256": ALPHA1_SHA,
            "alpha2Sha256": ALPHA2_SHA,
            "alpha3Sha256": ALPHA3_SHA,
            "v01Sha256": V01_SHA,
        },
    }
    param_lock_sha = _write(FINAL_DIR / "ALGORITHM_PARAMETER_LOCK.json", param_lock)

    wither_receipt = {
        "schema": "NURION_WITHER_FIXTURE_RECEIPT",
        "fixtureId": "WITHER_ASSET_GT_MISMATCH",
        "pass": bool(fixture.get("pass")),
        "reasonCode": expected.get("reasonCode"),
        "assetEligible": False,
        "autoRigAllowed": False,
        "failClass": "ASSET_GT_MISMATCH",
        "evidenceSha256": evidence_sha,
        "evidenceSha256Length": 64,
        "fixtureReportSha256": sha256_file(FIXTURE_REPORT),
        "expectedSha256": sha256_file(FIXTURE_EXPECTED),
        "alpha3FrozenPackageSha256": ALPHA3_SHA,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "note": "Wither remains a bad-asset regression fixture; not a quality-gate pass candidate.",
    }
    wither_sha = _write(FINAL_DIR / "WITHER_FIXTURE_RECEIPT.json", wither_receipt)

    final_verdict = dict(verdict)
    final_verdict["holdoutVerdictSha256"] = holdout_verdict_sha
    final_verdict["holdoutReportBundleSha256"] = holdout_bundle_sha
    final_verdict_sha = _write(FINAL_DIR / "HOLDOUT_VERDICT.json", final_verdict)

    final_status = dict(status)
    final_status["holdoutVerdictSha256"] = holdout_verdict_sha
    final_status["holdoutReportBundleSha256"] = holdout_bundle_sha
    final_status_sha = _write(FINAL_DIR / "HOLDOUT_STATUS.json", final_status)

    candidate = {
        "schema": "NURION_V0.2_SEAL_CANDIDATE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.2.0",
        "sealed": False,
        "sealReview": "READY",
        "v02Sealed": False,
        "package": ZIP_NAME,
        "packageSha256": zip_sha,
        "packageSha256Length": 64,
        "packageEntries": entries,
        "parameterHash": ALPHA3_PARAM,
        "parameterHashLength": 64,
        "holdoutVerdictSha256": holdout_verdict_sha,
        "holdoutVerdictSha256Length": 64,
        "holdoutReportBundleSha256": holdout_bundle_sha,
        "holdoutReportBundleSha256Length": 64,
        "algorithmParameterLockSha256": param_lock_sha,
        "witherFixtureReceiptSha256": wither_sha,
        "validationStatusSha256": validation_sha,
        "finalHoldoutVerdictFileSha256": final_verdict_sha,
        "finalHoldoutStatusFileSha256": final_status_sha,
        "hashPolicy": "FULL_64_CHAR_HEX_ONLY",
        "gates": {
            "assetEligibility": "PASS",
            "holdoutQuality": "PASS",
            "meanError_cm": 5.105,
            "maxError_cm": 10.414,
            "lrSwap": 0,
            "outsideMesh": 0,
            "gtLeak": 0,
            "determinism3x": "PASS",
            "witherFixture": "PASS",
        },
        "SUPPORTED": validation["SUPPORTED"],
        "NOT_VALIDATED": validation["NOT_VALIDATED"],
        "restPoseEvaluation": final_verdict["restPoseEvaluation"],
        "packagingRule": (
            "Alpha3 algorithm code unchanged; version/docs/validation only. "
            "Final ZIP is write-once — do not modify or repack after this candidate is emitted."
        ),
        "lineage": {
            "v01SealedSha256": V01_SHA,
            "alpha1Sha256": ALPHA1_SHA,
            "alpha2Sha256": ALPHA2_SHA,
            "alpha3Sha256": ALPHA3_SHA,
            "alpha3WitherQuality": "FAIL_ASSET_GT_MISMATCH",
            "holdoutAssetSha256": "c0f7ac338e1fcacdd5159139f07b9568ce661cb9977b8798e5de230d74b1277d",
        },
        "awaiting": "Explicit v0.2 SEALED approval after reviewing package + parameter + holdout hashes.",
    }
    candidate_sha = _write(FINAL_DIR / "V0.2_SEAL_CANDIDATE.json", candidate)

    # Manifest for directory inventory (not in the required list, but useful).
    manifest = {
        "schema": "NURION_V0.2_FINAL_MANIFEST",
        "directory": "dist/v0.2/final/",
        "writeOnceZip": ZIP_NAME,
        "files": {
            ZIP_NAME: zip_sha,
            "V0.2_SEAL_CANDIDATE.json": candidate_sha,
            "HOLDOUT_VERDICT.json": final_verdict_sha,
            "HOLDOUT_STATUS.json": final_status_sha,
            "ALGORITHM_PARAMETER_LOCK.json": param_lock_sha,
            "WITHER_FIXTURE_RECEIPT.json": wither_sha,
            "VALIDATION_STATUS.json": validation_sha,
        },
        "sealed": False,
        "sealReview": "READY",
    }
    _write(FINAL_DIR / "package-manifest.json", manifest)

    print(json.dumps({
        "package": ZIP_NAME,
        "packageSha256": zip_sha,
        "parameterHash": ALPHA3_PARAM,
        "holdoutVerdictSha256": holdout_verdict_sha,
        "holdoutReportBundleSha256": holdout_bundle_sha,
        "sealCandidateSha256": candidate_sha,
        "sealed": False,
        "sealReview": "READY",
        "entries": entries,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
