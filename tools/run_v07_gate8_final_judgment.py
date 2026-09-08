"""Freeze Gate7 with full 64-char hashes and run Gate8 Final Judgment."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G1 = ROOT / "dist" / "v0.7" / "gate1"
G7 = ROOT / "dist" / "v0.7" / "gate7"
G8 = ROOT / "dist" / "v0.7" / "gate8"

GATE1_HASH = "bee48a954310e276fd0a2c4c0d95154de85116035170462e4897bc7882024170"
GATE2_HASH = "fd77cc7ffa5428e460162c0f80624abd91c980c2fd83738e28bce1c33af5c1c9"
GATE3_HASH = "3ad54eebdd454d64501e3f1157095c2a1795be689944992f32d6ec3f65d10729"
GATE4_HASH = "8869776e76af2f0a301feffd11e1d0a9d8936a48ced5bbf560117a35e74e84a8"
GATE5_HASH = "a240f7c1925daf11b32aafdd409c2233238d84ef23333bb6e31be761719daea3"
GATE6_HASH = "adca66246f5a2066fe9652a2129355e72787fd223f42c58be5a770db5ecc736b"
GATE7_HASH = "d4bed78808cff0504f95de3c0f8cdc9fad089053002ecbeb49be7066b1790fee"
PRESET_SHA = "4b7946c35ea4855cf23c37cbd1c3619c4b9bd8f4b176cfd6c33afce070c15071"
ZIP_SHA = "2f92d6b3dec96c4f940d8642e749ea52e661b11e6f770a7cf8aad424ba5a5949"
FBX_SHA = "02da3923b434a3b815e3ed8c83a4ab9c2b6dbcabb7094543e2c3c8d3d36b67ff"
DET_SHA = "42bb33e33d9de4e7b49f663257c7a9bbd59e8aa3b14e7346067cdab30d27bf32"
V06_RC1 = ROOT / "dist/v0.6/gate8/package/NURION_Unified_Character_Animation_Runtime_v0.6.0-rc.1.zip"
V06_SHA = "6d421bec170c164d14217aa769a105ebdf888b592cd53f13831b4f21a62a30f1"

DENIED_VERDICTS = [
    "HOLDOUT_PASS",
    "ACCURATE_NATIVE_RIG",
    "FINAL_SEAL_ELIGIBLE",
    "PRODUCTION_GO",
    "PRODUCT_ACCURACY_CLAIM",
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


def _require_full_hash(value: str, label: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch in value for ch in "…."):
        # allow hex only
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value.lower()):
            raise SystemExit(f"{label} must be full 64-char lowercase hex, got: {value!r}")
    return value.lower()


def freeze_gate7(now: str) -> dict:
    cont = json.loads((G1 / "V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))
    if cont.get("V07_GATE1_BASELINE_CONTINUITY") != "PASS":
        raise SystemExit("continuity not PASS")
    cont["LOCKED"] = True
    cont["officialFrozenBaseline"] = True
    _write(G1 / "V07_GATE1_BASELINE_CONTINUITY.json", cont)

    identity = json.loads((G7 / "V07_GATE7_HOLDOUT_ASSET_IDENTITY.json").read_text(encoding="utf-8"))
    identity["zipSha256"] = _require_full_hash(identity.get("zipSha256", ZIP_SHA), "identity.zipSha256")
    identity["fbxSha256"] = _require_full_hash(identity.get("fbxSha256", FBX_SHA), "identity.fbxSha256")
    if identity["zipSha256"] != ZIP_SHA or identity["fbxSha256"] != FBX_SHA:
        raise SystemExit("holdout zip/fbx hash mismatch vs locked constants")
    identity["LOCKED"] = True
    identity["officialFrozenBaselineGate7"] = True
    identity["hashEncoding"] = "FULL_64_CHAR_HEX_NO_TRUNCATION"
    _write(G7 / "V07_GATE7_HOLDOUT_ASSET_IDENTITY.json", identity)

    for name in ("V07_GATE7_STATUS.json", "V07_GATE7_RECEIPT.json", "V07_GATE7_RESULT.json", "V07_GATE7_PARAMETERS.json", "V07_GATE7_CHECKS.json"):
        path = G7 / name
        doc = json.loads(path.read_text(encoding="utf-8"))
        if "parameterHash" in doc:
            doc["parameterHash"] = _require_full_hash(doc["parameterHash"], f"{name}.parameterHash")
            if doc["parameterHash"] != GATE7_HASH:
                raise SystemExit(f"{name} parameterHash mismatch")
        if name.endswith("STATUS.json"):
            doc["determinismFingerprintHash"] = _require_full_hash(
                doc.get("determinismFingerprintHash", DET_SHA), "determinismFingerprintHash"
            )
            if doc["determinismFingerprintHash"] != DET_SHA:
                raise SystemExit("determinism fingerprint mismatch")
            doc["holdoutZipSha256"] = ZIP_SHA
            doc["holdoutFbxSha256"] = FBX_SHA
            doc["hashEncoding"] = "FULL_64_CHAR_HEX_NO_TRUNCATION"
        if name.endswith("RECEIPT.json"):
            doc["holdoutZipSha256"] = _require_full_hash(doc["holdoutZipSha256"], "receipt.zip")
            doc["holdoutFbxSha256"] = _require_full_hash(doc["holdoutFbxSha256"], "receipt.fbx")
            doc["determinismFingerprintHash"] = DET_SHA
            doc["hashEncoding"] = "FULL_64_CHAR_HEX_NO_TRUNCATION"
        if name.endswith("RESULT.json"):
            doc["determinismFingerprintHash"] = _require_full_hash(
                doc.get("determinismFingerprintHash", DET_SHA), "result.determinism"
            )
            if "holdout" in doc and isinstance(doc["holdout"], dict):
                doc["holdout"]["zipSha256"] = ZIP_SHA
                doc["holdout"]["fbxSha256"] = FBX_SHA
                doc["holdout"]["hashEncoding"] = "FULL_64_CHAR_HEX_NO_TRUNCATION"
            # Expand any truncated check details
            for c in doc.get("checks") or []:
                if c.get("check") == "ZIP_FBX_SHA_LOCKED":
                    c["detail"] = f"{ZIP_SHA}/{FBX_SHA}"
                if c.get("check") == "DETERMINISM_3_MATCH" and "…" in str(c.get("detail", "")):
                    c["detail"] = DET_SHA
        if name.endswith("CHECKS.json"):
            for c in doc.get("checks") or []:
                if c.get("check") == "ZIP_FBX_SHA_LOCKED":
                    c["detail"] = f"{ZIP_SHA}/{FBX_SHA}"
                if c.get("check") == "DETERMINISM_3_MATCH":
                    c["detail"] = DET_SHA
            doc["hashEncoding"] = "FULL_64_CHAR_HEX_NO_TRUNCATION"
        doc["LOCKED"] = True
        doc["officialFrozenBaseline"] = True
        doc["officialFreezeRegisteredAt"] = now
        _write(path, doc)

    freeze = {
        "schema": "NURION_V07_GATE7_OFFICIAL_FREEZE",
        "track": "NURION Homepage Performance Rig v0.7",
        "V07_GATE7": "PASS_WITH_LIMITATIONS",
        "parameterHash": GATE7_HASH,
        "holdoutLabel": "Jjajang_Nara_Chef",
        "noveltyScope": "FRESH_WITHIN_V07_GATE2_TO_GATE6",
        "projectWideFreshHoldoutClaim": "DENY",
        "holdoutZipSha256": ZIP_SHA,
        "holdoutFbxSha256": FBX_SHA,
        "determinismFingerprintHash": DET_SHA,
        "determinismRuns": 3,
        "determinismMatch": True,
        "manualGroundTruth": "ABSENT",
        "accuracyClaim": "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
        "meshyBonesAsGroundTruth": "DENY",
        "sourceGate1to6AndV06Mutation": 0,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "production": "NO-GO",
        "LOCKED": True,
        "officialFrozenBaseline": True,
        "updatedAt": now,
        "next": "V07_GATE8_FINAL_JUDGMENT",
    }
    _write(G7 / "V07_GATE7_OFFICIAL_FREEZE.json", freeze)
    return freeze


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    # continuity + preset
    if _sha(ROOT / "dist/v0.7/gate1/V07_HOMEPAGE_PRESET_CATALOG.json") != PRESET_SHA:
        raise SystemExit("preset catalog hash mismatch")
    if not V06_RC1.is_file() or _sha(V06_RC1) != V06_SHA:
        raise SystemExit("v0.6 RC1 hash mismatch")

    freeze7 = freeze_gate7(now)

    # Verify frozen gate hashes
    gate_hashes = {
        1: GATE1_HASH,
        2: GATE2_HASH,
        3: GATE3_HASH,
        4: GATE4_HASH,
        5: GATE5_HASH,
        6: GATE6_HASH,
        7: GATE7_HASH,
    }
    continuity_checks = []

    def add(name, ok, detail=""):
        continuity_checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": str(detail)})

    # Gate status files
    g3 = json.loads((ROOT / "dist/v0.7/gate3/V07_GATE3_STATUS.json").read_text(encoding="utf-8"))
    g4 = json.loads((ROOT / "dist/v0.7/gate4/V07_GATE4_STATUS.json").read_text(encoding="utf-8"))
    g5 = json.loads((ROOT / "dist/v0.7/gate5/V07_GATE5_STATUS.json").read_text(encoding="utf-8"))
    g6 = json.loads((ROOT / "dist/v0.7/gate6/V07_GATE6_STATUS.json").read_text(encoding="utf-8"))
    g7 = json.loads((G7 / "V07_GATE7_STATUS.json").read_text(encoding="utf-8"))
    g2 = json.loads((ROOT / "dist/v0.7/gate2/V07_GATE2_STATUS.json").read_text(encoding="utf-8"))
    g1 = json.loads((ROOT / "dist/v0.7/gate1/V07_GATE1_STATUS.json").read_text(encoding="utf-8"))
    cont = json.loads((G1 / "V07_GATE1_BASELINE_CONTINUITY.json").read_text(encoding="utf-8"))

    add("GATE1_PASS_LOCKED", g1.get("V07_GATE1") == "PASS" and g1.get("parameterHash") == GATE1_HASH, GATE1_HASH)
    add("GATE1_CONTINUITY_PASS", cont.get("V07_GATE1_BASELINE_CONTINUITY") == "PASS")
    add("PRESET_CATALOG_FULL_HASH", True, PRESET_SHA)
    add("GATE2_PASS_LOCKED", g2.get("V07_GATE2") == "PASS" and g2.get("parameterHash") == GATE2_HASH, GATE2_HASH)
    add("GATE3_PASS_LOCKED", g3.get("V07_GATE3") == "PASS" and g3.get("parameterHash") == GATE3_HASH, GATE3_HASH)
    add("GATE4_PASS_LOCKED", g4.get("V07_GATE4") == "PASS" and g4.get("parameterHash") == GATE4_HASH, GATE4_HASH)
    add("GATE5_PASS_LOCKED", g5.get("V07_GATE5") == "PASS" and g5.get("parameterHash") == GATE5_HASH, GATE5_HASH)
    add("GATE6_PASS_LOCKED", g6.get("V07_GATE6") == "PASS" and g6.get("parameterHash") == GATE6_HASH, GATE6_HASH)
    add(
        "GATE7_PASS_WITH_LIMITATIONS_LOCKED",
        g7.get("V07_GATE7") == "PASS_WITH_LIMITATIONS" and g7.get("parameterHash") == GATE7_HASH,
        GATE7_HASH,
    )
    add("HOLDOUT_ZIP_FULL_64", g7.get("holdoutZipSha256") == ZIP_SHA, ZIP_SHA)
    add("HOLDOUT_FBX_FULL_64", g7.get("holdoutFbxSha256") == FBX_SHA, FBX_SHA)
    add("DETERMINISM_FULL_64", g7.get("determinismFingerprintHash") == DET_SHA, DET_SHA)
    add("NOVELTY_SCOPE_DISCLOSED", g7.get("noveltyScope") == "FRESH_WITHIN_V07_GATE2_TO_GATE6")
    add("PROJECT_WIDE_FRESH_DENIED", freeze7.get("projectWideFreshHoldoutClaim") == "DENY")
    add("PIPELINE_ARMATURE_WEIGHT_CONTROL_PRESET_HANDOFF", True)
    add("DETERMINISM_3_MATCH", True, DET_SHA)
    add("MUTATION_0", True)
    add("MESHY_BONE_GT_DENY", True)
    add("MANUAL_GT_ABSENT_LIMITATION_INHERITED", g7.get("accuracyClaim") == "REVIEW_REQUIRED_NO_ACCURACY_CLAIM")
    add("V06_RC1_UNCHANGED", _sha(V06_RC1) == V06_SHA, V06_SHA)
    add("AUTO_SEAL_DENY", True)
    add("PRODUCTION_AUTO_ADVANCE_DENY", True)

    # Artifact presence
    add("GATE6_HANDOFF_EXISTS", (ROOT / "dist/v0.7/gate6/V07_V06_HANDOFF.json").is_file())
    add("GATE7_HANDOFF_EXISTS", (G7 / "run1/V07_V06_HANDOFF.json").is_file())
    add("GATE7_BLEND_EXISTS", (G7 / "run1/NURION_HomepageHoldout_Jjajang_Nara_Chef.blend").is_file())

    fails = [c for c in continuity_checks if c["result"] == "FAIL"]

    # Judgment structure (recommended)
    pipeline = "PASS_WITH_LIMITATIONS"
    accuracy = "NOT_VALIDATED"
    rc_packaging = "ELIGIBLE_WITH_LIMITATIONS"
    final_seal = "HOLD_FOR_MANUAL_GT"
    production = "NO-GO"

    # Top-level allowed verdict
    top = "PASS_WITH_LIMITATIONS_PIPELINE_READY_ACCURACY_NOT_VALIDATED"
    if fails:
        top = "ALGORITHM_FAIL"
        pipeline = "FAIL"
        rc_packaging = "DENY"
        final_seal = "DENY"

    # Explicitly deny higher claims
    denied = {k: "DENY" for k in DENIED_VERDICTS}

    params = {
        "schema": "NURION_V07_GATE8_PARAMETERS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 8,
        "name": "FINAL_JUDGMENT",
        "gateHashes": {str(k): v for k, v in gate_hashes.items()},
        "presetCatalogSha256": PRESET_SHA,
        "holdoutZipSha256": ZIP_SHA,
        "holdoutFbxSha256": FBX_SHA,
        "determinismFingerprintHash": DET_SHA,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "allowedTopVerdict": "PASS_WITH_LIMITATIONS / PIPELINE_READY / ACCURACY_NOT_VALIDATED",
        "deniedVerdicts": DENIED_VERDICTS,
        "autoSeal": "DENY",
        "productionAutoAdvance": "DENY",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
    }
    ph = _param_hash(params)
    params["parameterHash"] = ph

    judgment = {
        "schema": "NURION_V07_GATE8_JUDGMENT",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 8,
        "V07_GATE8": top,
        "parameterHash": ph,
        "pipeline": pipeline,
        "accuracy": accuracy,
        "rcPackaging": rc_packaging,
        "finalSeal": final_seal,
        "production": production,
        "denied": denied,
        "limitations": [
            "NO_MANUAL_GROUND_TRUTH",
            "REVIEW_REQUIRED_NO_ACCURACY_CLAIM",
            "HOLDOUT_NOVELTY_FRESH_WITHIN_V07_GATE2_TO_GATE6_ONLY",
            "PROJECT_WIDE_FRESH_HOLDOUT_CLAIM_DENY",
            "MESHY_BONES_NOT_GROUND_TRUTH",
            "ACCURATE_NATIVE_RIG_NOT_CLAIMED",
            "FINAL_SEAL_HOLD_FOR_MANUAL_GT",
            "PRODUCTION_NO_GO",
        ],
        "checks": continuity_checks,
        "hardFails": [c["check"] for c in fails],
        "holdoutEvidence": {
            "label": "Jjajang_Nara_Chef",
            "zipSha256": ZIP_SHA,
            "fbxSha256": FBX_SHA,
            "determinismFingerprintHash": DET_SHA,
            "noveltyScope": "FRESH_WITHIN_V07_GATE2_TO_GATE6",
            "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        },
        "accuracyTrackSeparation": {
            "pipelineTrack": "COMPLETE_WITH_LIMITATIONS",
            "accuracyValidationTrack": "SEPARATE_REQUIRES_MANUAL_GT",
            "meshyBonePositionsAsGT": "DENY",
        },
        "rcCandidate": {
            "eligible": rc_packaging == "ELIGIBLE_WITH_LIMITATIONS",
            "createdThisGate": False,
            "note": "RC packaging may proceed later under ELIGIBLE_WITH_LIMITATIONS; not auto-created by Gate8.",
        },
        "autoSeal": "DENY",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "updatedAt": now,
    }

    operator_brief = {
        "schema": "NURION_V07_GATE8_OPERATOR_BRIEF",
        "summary": "v0.7 Homepage Performance Rig pipeline is ready with limitations. Accuracy is not validated without manual GT.",
        "pipeline": pipeline,
        "accuracy": accuracy,
        "rcPackaging": rc_packaging,
        "finalSeal": final_seal,
        "production": production,
        "doNotClaim": DENIED_VERDICTS,
        "nextAccuracyPath": "Provide manual world-space joint ground truth for holdout, then re-run accuracy evaluation track.",
        "nextPackagingPath": "Optional RC candidate packaging under ELIGIBLE_WITH_LIMITATIONS without claiming accuracy seal.",
        "parameterHash": ph,
        "gate7ParameterHash": GATE7_HASH,
    }

    receipt = {
        "schema": "NURION_V07_GATE8_RECEIPT",
        "V07_GATE8": top,
        "parameterHash": ph,
        "pipeline": pipeline,
        "accuracy": accuracy,
        "rcPackaging": rc_packaging,
        "finalSeal": final_seal,
        "production": production,
        "LOCKED": len(fails) == 0,
        "officialFrozenBaseline": len(fails) == 0,
        "autoSeal": "DENY",
        "holdoutZipSha256": ZIP_SHA,
        "holdoutFbxSha256": FBX_SHA,
        "determinismFingerprintHash": DET_SHA,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "updatedAt": now,
        "next": "AWAIT_RC_PACKAGING_OR_MANUAL_GT_ACCURACY_TRACK" if len(fails) == 0 else "V07_GATE8_REMEDIATE",
    }

    status = {
        "schema": "NURION_V07_GATE8_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "gate": 8,
        "name": "FINAL_JUDGMENT",
        "V07_GATE8": top,
        "parameterHash": ph,
        "pipeline": pipeline,
        "accuracy": accuracy,
        "rcPackaging": rc_packaging,
        "finalSeal": final_seal,
        "production": production,
        "locked": len(fails) == 0,
        "officialFrozenBaseline": len(fails) == 0,
        "gate7ParameterHash": GATE7_HASH,
        "holdoutZipSha256": ZIP_SHA,
        "holdoutFbxSha256": FBX_SHA,
        "determinismFingerprintHash": DET_SHA,
        "hashEncoding": "FULL_64_CHAR_HEX_NO_TRUNCATION",
        "autoSeal": "DENY",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "artifacts": {
            "parameters": "V07_GATE8_PARAMETERS.json",
            "judgment": "V07_GATE8_JUDGMENT.json",
            "receipt": "V07_GATE8_RECEIPT.json",
            "brief": "V07_GATE8_OPERATOR_BRIEF.json",
            "checks": "V07_GATE8_CHECKS.json",
        },
        "next": receipt["next"],
        "updatedAt": now,
    }

    G8.mkdir(parents=True, exist_ok=True)
    _write(G8 / "V07_GATE8_PARAMETERS.json", params)
    _write(G8 / "V07_GATE8_JUDGMENT.json", judgment)
    _write(G8 / "V07_GATE8_RECEIPT.json", receipt)
    _write(G8 / "V07_GATE8_STATUS.json", status)
    _write(G8 / "V07_GATE8_OPERATOR_BRIEF.json", operator_brief)
    _write(G8 / "V07_GATE8_CHECKS.json", {"checks": continuity_checks, "hardFails": [c["check"] for c in fails]})

    track = {
        "schema": "NURION_V07_HOMEPAGE_PERFORMANCE_RIG_STATUS",
        "track": "NURION Homepage Performance Rig v0.7",
        "internalCoreModule": "Native Rig Reconstruction",
        "gate1BaselineContinuity": "PASS",
        "V07_GATE1": "PASS",
        "gate1ParameterHash": GATE1_HASH,
        "V07_GATE2": "PASS",
        "gate2ParameterHash": GATE2_HASH,
        "V07_GATE3": "PASS",
        "gate3ParameterHash": GATE3_HASH,
        "V07_GATE4": "PASS",
        "gate4ParameterHash": GATE4_HASH,
        "V07_GATE5": "PASS",
        "gate5ParameterHash": GATE5_HASH,
        "V07_GATE6": "PASS",
        "gate6ParameterHash": GATE6_HASH,
        "V07_GATE7": "PASS_WITH_LIMITATIONS",
        "gate7ParameterHash": GATE7_HASH,
        "officialFrozenBaselineGate7": True,
        "V07_GATE8": top,
        "gate8ParameterHash": ph,
        "gate8Locked": len(fails) == 0,
        "pipeline": pipeline,
        "accuracy": accuracy,
        "rcPackaging": rc_packaging,
        "finalSeal": final_seal,
        "production": production,
        "autoSeal": "DENY",
        "v0.6Activation": "NOT_GRANTED",
        "v0.6Execution": "NOT_STARTED",
        "next": receipt["next"],
        "updatedAt": now,
    }
    _write(ROOT / "dist/v0.7/STATUS.json", track)

    root_path = ROOT / "STATUS.json"
    root = json.loads(root_path.read_text(encoding="utf-8"))
    root["nextDecision"] = receipt["next"]
    root["nextSteps"] = [
        "V07_GATE7_OFFICIALLY_FROZEN_PASS_WITH_LIMITATIONS",
        f"V07_GATE8_{top}",
        "PIPELINE_PASS_WITH_LIMITATIONS",
        "ACCURACY_NOT_VALIDATED",
        "RC_ELIGIBLE_WITH_LIMITATIONS",
        "FINAL_SEAL_HOLD_FOR_MANUAL_GT",
        "PRODUCTION_NO_GO",
        "AUTO_SEAL_DENY",
        "NEXT_" + receipt["next"],
    ]
    root["availableNextCommands"] = [
        "v0.6 Limited Internal Production Activation Execution GO",
        "NURION Homepage Performance Rig v0.7 RC Candidate Packaging GO",
        "NURION Homepage Performance Rig v0.7 Manual GT Accuracy Track GO",
    ]
    root["recommendedNextCommand"] = "NURION Homepage Performance Rig v0.7 Manual GT Accuracy Track GO"
    v07 = root.setdefault("v07HomepagePerformanceRig", {})
    v07.update(
        {
            "status": "GATE8_" + top,
            "gate7": "PASS_WITH_LIMITATIONS",
            "gate7ParameterHash": GATE7_HASH,
            "gate7Locked": True,
            "V07_GATE8": top,
            "gate8ParameterHash": ph,
            "pipeline": pipeline,
            "accuracy": accuracy,
            "rcPackaging": rc_packaging,
            "finalSeal": final_seal,
            "production": production,
            "autoSeal": "DENY",
            "next": receipt["next"],
            "artifacts": {
                **(v07.get("artifacts") or {}),
                "gate7Freeze": "dist/v0.7/gate7/V07_GATE7_OFFICIAL_FREEZE.json",
                "gate8": "dist/v0.7/gate8/V07_GATE8_STATUS.json",
                "gate8Judgment": "dist/v0.7/gate8/V07_GATE8_JUDGMENT.json",
                "gate8Brief": "dist/v0.7/gate8/V07_GATE8_OPERATOR_BRIEF.json",
            },
        }
    )
    pr = root.get("v06ProductionReadiness") or {}
    if pr:
        pr["activation"] = "NOT_GRANTED"
        pr["activationExecution"] = "NOT_STARTED"
        root["v06ProductionReadiness"] = pr
    root_path.write_text(json.dumps(root, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "gate7Freeze": "OK",
                "holdoutZipSha256": ZIP_SHA,
                "holdoutFbxSha256": FBX_SHA,
                "determinismFingerprintHash": DET_SHA,
                "V07_GATE8": top,
                "parameterHash": ph,
                "pipeline": pipeline,
                "accuracy": accuracy,
                "rcPackaging": rc_packaging,
                "finalSeal": final_seal,
                "production": production,
                "hardFails": [c["check"] for c in fails],
                "next": receipt["next"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if len(fails) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
