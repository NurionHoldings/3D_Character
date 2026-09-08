"""NURION Quick Profile Gate 3 consented-human draft review runner.

This runner executes the frozen Gate 2 recipe pipeline without modifying it.
It is deliberately all-or-none: every participant must pass consent, pinned
byte, operator filter, and quality checks before Blender draft assembly starts.
It never writes to Gate 8 evidence and never performs human scoring.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


RUNNER_SCHEMA = "NURION_V07_QP_GATE3_CONSENTED_HUMAN_REVIEW_RUNNER_V1"
PARTICIPANTS = ("P001", "P002", "P003")
EXPECTED = {
    "gate1_blend": "71194ac233b894dbf2f02d3d74b33fa00029c89b639ce500a7c9df05c8b3caa2",
    "gate4_blend": "72b8b2a6ff9708f6d3890de88d95fe670403e238f4514f55cd4c14a621ed502f",
    "gate5_blend": "c47177d77008ae18df3a44d5e5b99dee3bc909c14e0bea05a4076ce8b65c7c86",
    "gate1_parameter": "fdc57d1a276cd51fe58d8f65f0f8246cdf5ba88fdc233e0dbfc9b96c15e798d1",
    "gate2_parameter": "f58def1d79f66b0a04189b9694af3ddb7283e5236b4288f511434c6577b545b3",
    "gate3_parameter": "cde535402d8a92b50371bed8fefb82efabbb15c9ce2da64081855dd6a98f81bd",
    "gate3_intake_parameter": "961d3829602fa4ef644dddfd9e025ae1415738cef2ce6cd21306725bd56bf495",
    "gate8_parameter": "d846ca45e00f5d1cfc97777c90b7c9f064b4baaecb6976272c5a91cb55f25697",
}


class SafeAbort(RuntimeError):
    """Expected policy stop; no partial generation is allowed."""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_obj(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        value = json.load(f)
    if not isinstance(value, dict):
        raise SafeAbort(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise SafeAbort(f"MISSING_{label}:{path}")
    return path


def require_hash(path: Path, expected: str, label: str) -> str:
    got = sha256_file(require_file(path, label))
    if got.lower() != expected.lower():
        raise SafeAbort(f"{label}_HASH_MISMATCH:{got}")
    return got


def require_field(doc: dict, key: str, expected: Any, label: str) -> None:
    if doc.get(key) != expected:
        raise SafeAbort(f"{label}_{key}_MISMATCH")


def default_paths(root: Path) -> dict[str, Path]:
    return {
        "gate1_blend": root / "dist/v0.7/canonical/gate1/asset/NURION_CanonicalHuman_V1.blend",
        "gate4_blend": root / "dist/v0.7/canonical/gate4/run3/NURION_CanonicalIdentityBeautification_V1.blend",
        "gate5_blend": root / "dist/v0.7/canonical/gate5/run3/NURION_CanonicalBodyPresets_V1.blend",
        "gate1_params": root / "dist/v0.7/product/quick_profile/gate1/V07_QP_GATE1_PARAMETERS.json",
        "gate2_freeze": root / "dist/v0.7/product/quick_profile/gate2/V07_QP_GATE2_OFFICIAL_FREEZE.json",
        "gate3_params": root / "dist/v0.7/product/quick_profile/gate3/V07_QP_GATE3_PARAMETERS.json",
        "intake_params": root / "dist/v0.7/product/quick_profile/gate3/intake/V07_QP_GATE3_INTAKE_PARAMETERS.json",
        "precheck": root / "dist/v0.7/product/quick_profile/gate3/intake/V07_QP_GATE3_PACKAGE_PRECHECK.json",
        "pinned": root / "dist/v0.7/product/quick_profile/gate3/intake/V07_QP_GATE3_PINNED_SHA256_RECORD.json",
        "packages": root / "dist/v0.7/product/quick_profile/gate3/intake/packages",
        "core": root / "tools/nurion_quick_profile_core.py",
        "assembler": root / "tools/blender_quick_profile_gate3_assemble.py",
    }


def validate_runtime(root: Path, blender: Path) -> tuple[dict[str, Path], dict[str, str]]:
    paths = default_paths(root)
    hashes = {
        "gate1Blend": require_hash(paths["gate1_blend"], EXPECTED["gate1_blend"], "GATE1_BLEND"),
        "gate4Blend": require_hash(paths["gate4_blend"], EXPECTED["gate4_blend"], "GATE4_BLEND"),
        "gate5Blend": require_hash(paths["gate5_blend"], EXPECTED["gate5_blend"], "GATE5_BLEND"),
    }
    require_file(paths["core"], "FROZEN_GATE2_CORE")
    require_file(paths["assembler"], "GATE3_ASSEMBLER")
    require_file(blender, "BLENDER_5_0_1")

    g1 = read_json(require_file(paths["gate1_params"], "GATE1_PARAMETERS"))
    require_field(g1, "parameterHash", EXPECTED["gate1_parameter"], "GATE1")
    g2 = read_json(require_file(paths["gate2_freeze"], "GATE2_FREEZE"))
    require_field(g2, "parameterHash", EXPECTED["gate2_parameter"], "GATE2")
    require_field(g2, "LOCKED", True, "GATE2")
    g3 = read_json(require_file(paths["gate3_params"], "GATE3_PARAMETERS"))
    require_field(g3, "parameterHash", EXPECTED["gate3_parameter"], "GATE3")
    intake = read_json(require_file(paths["intake_params"], "GATE3_INTAKE_PARAMETERS"))
    require_field(intake, "parameterHash", EXPECTED["gate3_intake_parameter"], "GATE3_INTAKE")
    require_field(intake, "countsAsGate8ParticipantEvidence", "DENY", "GATE3_INTAKE_USAGE") if "countsAsGate8ParticipantEvidence" in intake else None
    return paths, hashes


def consent_ok(consent: dict, pid: str) -> list[str]:
    required_true = (
        "adultConfirmed",
        "photoUseConsentInternalDraftReviewOnly",
        "heightWeightUseConsent",
        "characterLikenessConsentInternalOnly",
        "characterGenerationAndInternalReviewConsent",
        "understandsNotGate8Evidence",
        "understandsNotProductQualityApproval",
        "deletionAfterReviewIfChosen",
        "retentionUnderstood",
        "deletionUnderstood",
        "accessControlAcknowledged",
        "signatureOrEquivalent",
        "nameContactSeparatedFromPipeline",
    )
    reasons = []
    if consent.get("anonymousParticipantId") != pid:
        reasons.append("CONSENT_PARTICIPANT_ID_MISMATCH")
    if consent.get("status") != "COLLECTED":
        reasons.append("CONSENT_NOT_COLLECTED")
    reasons.extend(f"CONSENT_FALSE_{key}" for key in required_true if consent.get(key) is not True)
    if consent.get("countsAsGate8ParticipantEvidence") != "DENY":
        reasons.append("GATE8_EVIDENCE_DENY_MISSING")
    if consent.get("retentionOrDeletionChoice") not in ("DELETE_AFTER_REVIEW", "KEEP_FOR_DAYS"):
        reasons.append("RETENTION_CHOICE_INVALID")
    return reasons


def operator_filter_reasons(precheck_entry: dict) -> list[str]:
    text = " ".join(str(x) for x in precheck_entry.get("eligibilityFlags", []))
    correction = str(precheck_entry.get("filterBeautyCorrection", ""))
    bad_tokens = ("SUSPECTED", "PRESENT", "CAT_OVERLAY", "SPARKLE_OVERLAY", "BEAUTY_CORRECTED")
    if any(token in text.upper() for token in bad_tokens) or correction not in ("NONE", "NONE_OBSERVED", "FILTER_FREE"):
        return ["OPERATOR_FILTER_OR_BEAUTY_FLAG"]
    return []


def validate_packages(paths: dict[str, Path]) -> tuple[list[dict], dict[str, str]]:
    pinned = read_json(require_file(paths["pinned"], "PINNED_SHA256_RECORD"))
    pins = pinned.get("pinnedSha256", {})
    precheck = read_json(require_file(paths["precheck"], "PACKAGE_PRECHECK"))
    entries = precheck.get("packages", {})
    validated = []
    hashes_before = {}

    for pid in PARTICIPANTS:
        folder = paths["packages"] / pid
        face = require_file(folder / "face.png", f"{pid}_FACE")
        inp = read_json(require_file(folder / "participant_input.json", f"{pid}_INPUT"))
        consent = read_json(require_file(folder / "consent.json", f"{pid}_CONSENT"))
        got = sha256_file(face)
        hashes_before[pid] = got
        reasons = []
        if pins.get(pid) != got or inp.get("originalImageSha256") != got:
            reasons.append("PINNED_IMAGE_HASH_MISMATCH")
        if inp.get("anonymousParticipantId") != pid:
            reasons.append("PARTICIPANT_ID_MISMATCH")
        if inp.get("mutationAfterFix") != "DENY":
            reasons.append("INPUT_MUTATION_POLICY_MISSING")
        if not isinstance(inp.get("heightCm"), (int, float)) or not isinstance(inp.get("weightKg"), (int, float)):
            reasons.append("HEIGHT_WEIGHT_INVALID")
        reasons.extend(consent_ok(consent, pid))
        reasons.extend(operator_filter_reasons(entries.get(pid, {})))
        validated.append({"participantId": pid, "face": face, "input": inp, "consent": consent, "reasons": sorted(set(reasons))})
    return validated, hashes_before


def blind_assignment(pid: str) -> dict[str, str]:
    bit = int(hashlib.sha256(f"{RUNNER_SCHEMA}:{pid}".encode()).hexdigest(), 16) & 1
    return {"A": "NATURAL", "B": "POLISHED"} if bit == 0 else {"A": "POLISHED", "B": "NATURAL"}


def human_review_template(pid: str, blind: dict[str, str]) -> dict:
    return {
        "schema": "NURION_V07_QP_GATE3_HUMAN_REVIEW_TEMPLATE_V1",
        "anonymousParticipantId": pid,
        "blindDrafts": ["A", "B"],
        "blindMappingStoredSeparately": True,
        "selfEvaluation": {
            "completed": False,
            "preferredDraft": None,
            "faceShapeAndMajorProportions": None,
            "eyeBrowNoseMouthJawSignature": None,
            "naturalAsymmetryPreserved": None,
            "identityPreservedAfterPolish": None,
            "silentExpressionImpression": None,
            "comment": None,
        },
        "internalVisualReview": {
            "completed": False,
            "excessiveBeautification": None,
            "identityLoss": None,
            "offFrontalVirtualViewCollapse": None,
            "standardBodyBlocksRecognition": None,
            "unobservablePartsDisclosureComplete": None,
            "comment": None,
        },
        "automaticPass": "DENY",
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
        "_blindMappingForReceiptOnly": blind,
    }


def run_blender(blender: Path, assembler: Path, source: Path, recipe: Path, out: Path, pid: str, mode: str) -> dict:
    cmd = [
        str(blender), "--background", "--python", str(assembler), "--",
        "--source-blend", str(source),
        "--expected-source-sha256", EXPECTED["gate5_blend"],
        "--recipe-json", str(recipe),
        "--out-dir", str(out),
        "--participant-id", pid,
        "--mode", mode,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    log_dir = out / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / f"{pid}_{mode}_stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (log_dir / f"{pid}_{mode}_stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    if proc.returncode != 0:
        raise SafeAbort(f"BLENDER_ASSEMBLY_FAILED:{pid}:{mode}")
    return read_json(out / "drafts" / pid / mode / "V07_QP_GATE3_ASSEMBLE_REPORT.json")


def execute(root: Path, blender: Path, output: Path, preflight_only: bool = False) -> dict:
    paths, baseline_hashes = validate_runtime(root, blender)
    participants, input_hashes_before = validate_packages(paths)
    package_failures = {p["participantId"]: p["reasons"] for p in participants if p["reasons"]}
    if package_failures:
        raise SafeAbort("PACKAGE_PRECHECK_ABSTAIN:" + json.dumps(package_failures, sort_keys=True))

    if preflight_only:
        return {
            "schema": RUNNER_SCHEMA,
            "verdict": "PREFLIGHT_PASS_NOT_EXECUTED",
            "participantCount": 3,
            "baselineHashes": baseline_hashes,
            "gate8EvidenceCounting": "DENY",
            "production": "NO-GO",
        }

    sys.path.insert(0, str(root / "tools"))
    from nurion_quick_profile_core import InputBundle, run_pipeline  # type: ignore

    gate1 = read_json(paths["gate1_params"])
    pipeline_params = {
        "inputContract": gate1["inputContract"],
        "photoQualityCriteria": gate1["photoQualityCriteria"],
        "exaggerationBan": gate1["exaggerationBan"],
    }

    prepared = []
    for p in participants:
        inp = p["input"]
        result = run_pipeline(
            InputBundle(p["participantId"], str(p["face"]), float(inp["heightCm"]), float(inp["weightKg"]), inp.get("declaredPose", "FRONTAL")),
            pipeline_params,
        )
        if result.get("verdict") != "QUICK_PROFILE_DRAFT_READY":
            raise SafeAbort(f"QUALITY_ABSTAIN:{p['participantId']}:{result.get('abstainReasons', [])}")
        polished = copy.deepcopy(result["recipe"])
        natural = copy.deepcopy(polished)
        natural["beautificationMode"] = "NATURAL"
        natural["beautificationValues"] = {k: 0.0 for k in polished.get("beautificationValues", {})}
        prepared.append({"participantId": p["participantId"], "pipeline": result, "recipes": {"NATURAL": natural, "POLISHED": polished}})

    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for item in prepared:
        pid = item["participantId"]
        mode_reports = {}
        for mode in ("NATURAL", "POLISHED"):
            recipe_path = output / "recipes" / pid / f"{mode}.json"
            write_json(recipe_path, item["recipes"][mode])
            mode_reports[mode] = run_blender(blender, paths["assembler"], paths["gate5_blend"], recipe_path, output, pid, mode)
        blind = blind_assignment(pid)
        template = human_review_template(pid, blind)
        mapping = template.pop("_blindMappingForReceiptOnly")
        write_json(output / "reviews" / f"{pid}_HUMAN_REVIEW.json", template)
        write_json(output / "blind" / f"{pid}_BLIND_MAPPING.json", {"participantId": pid, "mapping": mapping, "access": "OPERATOR_ONLY"})
        reports.append({
            "participantId": pid,
            "pipelineFingerprintSha256": item["pipeline"].get("pipelineFingerprintSha256"),
            "bodyPreset": item["pipeline"]["bodyRecommendation"]["recommendedPreset"],
            "drafts": {m: {"outputBlendSha256": mode_reports[m]["outputBlendSha256"], "assembleFingerprintSha256": mode_reports[m]["assembleFingerprintSha256"]} for m in mode_reports},
            "reviewState": "AWAITING_HUMAN_REVIEW",
        })

    input_hashes_after = {p["participantId"]: sha256_file(p["face"]) for p in participants}
    if input_hashes_after != input_hashes_before:
        raise SafeAbort("PARTICIPANT_INPUT_MUTATION_DETECTED")
    for key, expected in (("gate1_blend", EXPECTED["gate1_blend"]), ("gate4_blend", EXPECTED["gate4_blend"]), ("gate5_blend", EXPECTED["gate5_blend"])):
        if sha256_file(paths[key]) != expected:
            raise SafeAbort(f"BASELINE_MUTATION_DETECTED:{key}")

    receipt = {
        "schema": "NURION_V07_QP_GATE3_EXECUTION_RECEIPT_V1",
        "verdict": "DRAFTS_READY_AWAITING_HUMAN_REVIEW",
        "runnerSchema": RUNNER_SCHEMA,
        "participantResults": reports,
        "humanReviewCompleted": False,
        "automaticGatePromotion": "DENY",
        "participantInputMutation": 0,
        "baselineMutation": 0,
        "gate8EvidenceCounting": "DENY",
        "retentionDeletionState": "DELETE_AFTER_REVIEW_PENDING_HUMAN_REVIEW",
        "production": "NO-GO",
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    receipt["executionFingerprintSha256"] = sha256_obj({k: v for k, v in receipt.items() if k not in ("completedAt", "executionFingerprintSha256")})
    write_json(output / "V07_QP_GATE3_EXECUTION_RECEIPT.json", receipt)
    return receipt


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--blender", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--preflight-only", action="store_true")
    args = ap.parse_args()
    try:
        result = execute(args.root.resolve(), args.blender.resolve(), args.output.resolve(), args.preflight_only)
    except SafeAbort as exc:
        result = {
            "schema": RUNNER_SCHEMA,
            "verdict": "SAFE_ABORT",
            "reason": str(exc),
            "partialGeneration": "DENY",
            "gate8EvidenceCounting": "DENY",
            "production": "NO-GO",
        }
        args.output.mkdir(parents=True, exist_ok=True)
        write_json(args.output / "V07_QP_GATE3_SAFE_ABORT_RECEIPT.json", result)
        print(json.dumps(result, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
