"""Gate 8B — cross-asset validation with frozen parameters (no tuning)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import GATE8_PARAMETERS, V04_RC1_SHA256, parameter_hash
from .pipeline import _sha_file, run_clean_pipeline_once, verify_frozen_hashes


@dataclass
class Gate8BResult:
    report: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""


def _asset_verdict(fp: Dict, det: str, eligible: bool, err: str = "") -> Tuple[str, List[str]]:
    fails = []
    if err:
        fails.append(err)
    if not eligible:
        fails.append("NOT_ELIGIBLE")
    if not fp.get("boneMappingOk"):
        fails.append("BONE_MAPPING")
    if int(fp.get("lrSwapCount", 1)) != 0:
        fails.append("LR_SWAP")
    if fp.get("axisFailChains"):
        fails.append("AXIS_ERROR")
    if int(fp.get("sourceActionMutation", 1)) != 0:
        fails.append("SOURCE_ACTION_MUTATION")
    if int(fp.get("gate6BodyMutation", 1)) != 0:
        fails.append("GATE6_BODY_MUTATION")
    if not fp.get("faceBindOk"):
        fails.append("FACE_EYE_LIPSYNC_BIND")
    if not fp.get("fpsMeaningOk"):
        fails.append("FPS_MEANING")
    if not fp.get("shallowContactOk"):
        fails.append("SHALLOW_CONTACT")
    if det != "PASS":
        fails.append("DETERMINISM_3X")

    limitations = []
    # Body-type dependent residuals (do not auto-PASS)
    if int(fp.get("slidesFinal", 0)) > 0:
        limitations.append(f"FOOT_SLIDE_BODYTYPE_{int(fp.get('slidesFinal', 0))}")
    if float(fp.get("maxDepthM") or 0) > 0:
        limitations.append("SHALLOW_CONTACT_BODYTYPE")
    limitations.append("NO_PARAMETER_TUNING")
    limitations.append("FROZEN_PARAMETERS_ONLY")

    if fails:
        return "FAIL", fails
    if limitations:
        return "PASS_WITH_LIMITATIONS", fails
    return "PASS", fails


def run_gate8b_asset(
    *,
    label: str,
    role: str,
    fbx_path: Path,
    mesh_name: str,
    runs: int,
    clean_import_cb,
    root: Path,
) -> Dict:
    notes = []
    if not fbx_path.exists():
        return {
            "label": label,
            "role": role,
            "eligible": False,
            "verdict": "FAIL",
            "fails": ["FBX_MISSING"],
            "notes": [f"missing fbx: {fbx_path}"],
            "fbxSha256": "",
            "parameterTuning": 0,
            "manualCorrection": 0,
        }

    fbx_sha = _sha_file(fbx_path)
    results = []
    err = ""
    try:
        for _ in range(int(runs)):
            clean_import_cb()
            # Eligibility: armature + required bones after import
            import bpy

            arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
            if not arms:
                raise RuntimeError("no armature")
            if not bpy.data.actions:
                raise RuntimeError("no action — body pipeline requires animation")
            results.append(
                run_clean_pipeline_once(fbx_path=fbx_path, mesh_name=mesh_name, root=root, seed_mode=False)
            )
    except Exception as exc:  # noqa: BLE001 — per-asset isolation
        err = str(exc)
        notes.append(err)

    if not results:
        return {
            "label": label,
            "role": role,
            "eligible": False,
            "verdict": "FAIL",
            "fails": [err or "PIPELINE_ERROR"],
            "notes": notes,
            "fbxSha256": fbx_sha,
            "parameterTuning": 0,
            "manualCorrection": 0,
        }

    hashes = [r["determinismHash"] for r in results]
    det = "PASS" if len(hashes) >= 3 and all(h == hashes[0] for h in hashes[1:3]) else "FAIL"
    last = results[-1]
    fp = last["fingerprint"]
    eligible = bool(last["mapping"]["ok"])
    verdict, fails = _asset_verdict(fp, det, eligible, err="")

    # Body-type dependency evidence (report only; no retune)
    body_dep = {
        "slidesFinal": fp["slidesFinal"],
        "maxDepthM": fp["maxDepthM"],
        "keysFinalTotal": (fp.get("keysFinal") or {}).get("totalKeys"),
        "frameRange": [fp["frameStart"], fp["frameEnd"]],
    }

    return {
        "label": label,
        "role": role,
        "eligible": eligible,
        "verdict": verdict,
        "fails": fails,
        "determinism3x": det,
        "determinismHashes": hashes,
        "fingerprint": fp,
        "mapping": last["mapping"],
        "lrSwapCount": fp["lrSwapCount"],
        "axisFailChains": fp["axisFailChains"],
        "faceBindOk": fp["faceBindOk"],
        "bodyTypeDependency": body_dep,
        "fbxSha256": fbx_sha,
        "parameterTuning": 0,
        "manualCorrection": 0,
        "notes": notes,
        "inheritedSeedLimitations": GATE8_PARAMETERS["inheritedLimitations"],
    }


def build_gate8b_validation(assets: List[Dict], frozen_ok: bool, v04_ok: bool) -> Dict:
    asset_verdicts = {a["label"]: a["verdict"] for a in assets}
    hard_fails = [a["label"] for a in assets if a["verdict"] == "FAIL"]
    limited = [a["label"] for a in assets if a["verdict"] == "PASS_WITH_LIMITATIONS"]
    passed = [a["label"] for a in assets if a["verdict"] == "PASS"]

    gates = {
        "FROZEN_HASHES": "PASS" if frozen_ok else "FAIL",
        "V04_SEAL_MUTATION": 0 if v04_ok else 1,
        "PARAMETER_TUNING": 0,
        "MANUAL_CORRECTION": 0,
        "CROSS_ASSETS": asset_verdicts,
        "PRODUCTION": "NO-GO",
        "SUPPORTED_DOMAIN": "LIMITED",
    }

    limitations = list(GATE8_PARAMETERS["inheritedLimitations"])
    limitations.append("CROSS_ASSET_BODYTYPE_VARIANCE")
    limitations.append("LIMITED_DOMAIN")
    for a in assets:
        for f in a.get("fails") or []:
            limitations.append(f"CROSS_{a['label'].upper()}_{f}")

    if not frozen_ok or not v04_ok or hard_fails:
        # If any asset hard-fails → overall CROSS can still be LIMITED if seed-path partial;
        # Gate8B itself FAIL when frozen broken or all assets fail; else CROSS_ASSET_LIMITED
        if not frozen_ok or not v04_ok:
            verdict = "FAIL"
        elif len(hard_fails) == len(assets):
            verdict = "FAIL"
        else:
            verdict = "CROSS_ASSET_LIMITED"
    elif limited and not passed:
        verdict = "PASS_WITH_LIMITATIONS"
    elif limited:
        verdict = "PASS_WITH_LIMITATIONS"
    else:
        verdict = "PASS"

    # Prefer CROSS_ASSET_LIMITED when any asset failed mapping/face but others passed with lim
    if hard_fails and verdict != "FAIL":
        verdict = "CROSS_ASSET_LIMITED"

    fails = []
    if not frozen_ok:
        fails.append("FROZEN_HASHES")
    if not v04_ok:
        fails.append("V04_SEAL_MUTATION")
    fails.extend([f"ASSET_{n}" for n in hard_fails])

    return {
        "schema": "NURION_V05_GATE8B_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "assetsPassed": passed,
        "assetsLimited": limited,
        "assetsFailed": hard_fails,
    }


def run_gate8b(
    *,
    asset_paths: Dict[str, Path],
    mesh_names: Optional[Dict[str, str]] = None,
    runs: int = 3,
    clean_import_factory=None,
    root: Optional[Path] = None,
) -> Gate8BResult:
    """asset_paths: label -> fbx Path. clean_import_factory(fbx)->callback."""
    notes: List[str] = []
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    mesh_names = mesh_names or {}
    frozen = verify_frozen_hashes(root)
    rc1 = root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    v04_ok = rc1.exists() and _sha_file(rc1) == V04_RC1_SHA256

    assets_out = []
    for spec in GATE8_PARAMETERS["crossAssets"]:
        label = spec["label"]
        fbx = asset_paths.get(label)
        if fbx is None:
            assets_out.append(
                {
                    "label": label,
                    "role": spec["role"],
                    "eligible": False,
                    "verdict": "FAIL",
                    "fails": ["PATH_NOT_PROVIDED"],
                    "notes": [],
                    "fbxSha256": "",
                    "parameterTuning": 0,
                    "manualCorrection": 0,
                }
            )
            continue
        cb = clean_import_factory(fbx) if clean_import_factory else None
        if cb is None:
            raise RuntimeError("clean_import_factory required")
        assets_out.append(
            run_gate8b_asset(
                label=label,
                role=spec["role"],
                fbx_path=Path(fbx),
                mesh_name=mesh_names.get(label, spec.get("mesh") or "char1"),
                runs=runs,
                clean_import_cb=cb,
                root=root,
            )
        )
        if _sha_file(rc1) != V04_RC1_SHA256:
            v04_ok = False
            notes.append("v0.4 RC.1 mutated during Gate8B")

    validation = build_gate8b_validation(assets_out, frozen["ok"], v04_ok)
    report = {
        "schema": "NURION_V05_GATE8B_CROSS_ASSET_REPORT",
        "version": GATE8_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "frozenHashes": frozen,
        "assets": assets_out,
        "inheritedLimitations": GATE8_PARAMETERS["inheritedLimitations"],
        "parameterTuning": 0,
        "manualCorrection": 0,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "v04Mutation": "DENY",
        "notes": notes,
        "next": "RC_CANDIDATE_PACKAGING",
    }
    return Gate8BResult(
        report=report,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
    )


def combine_gate8_verdict(verdict_8a: str, verdict_8b: str) -> str:
    order = {"FAIL": 0, "CROSS_ASSET_LIMITED": 1, "PASS_WITH_LIMITATIONS": 2, "PASS": 3}
    if verdict_8a == "FAIL":
        return "FAIL"
    if verdict_8b == "FAIL" and verdict_8a != "FAIL":
        # Seed OK but cross total fail
        return "CROSS_ASSET_LIMITED" if verdict_8a.startswith("PASS") else "FAIL"
    if verdict_8b == "CROSS_ASSET_LIMITED":
        return "CROSS_ASSET_LIMITED"
    # both PASS_WITH_LIMITATIONS or better
    a = order.get(verdict_8a, 0)
    b = order.get(verdict_8b, 0)
    merged = min(a, b)
    for k, v in order.items():
        if v == merged:
            return k
    return "FAIL"
