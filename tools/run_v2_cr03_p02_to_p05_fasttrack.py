#!/usr/bin/env python3
"""CR03 fast-track: P02 → P03 → P04 → P05 → READY_FOR_HUMAN_AUDIT (fail-closed)."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.v2_cr03.audit_paths import resolve_v2_cr03_roots
from fast_track.v2_cr03.independent_gates import run_cr03_independent_gates
from fast_track.v2_cr03.p02_weights_injection import inject_talking_weights_animation
from fast_track.v2_cr03.p03_temporal_proof import prove_temporal_vertex_deformation
from fast_track.v2_cr03.p04_regression import run_idle_talking_regression
from fast_track.v2_cr03.pins import APPROVED_SPEC_DIGEST


def _write_json(path: Path, obj: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return sha256_file(path)


def _receipt(ev: Path, stage: str, status: str, **extra) -> Path:
    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    name = f"NURION-V2-CR03_{stage}_{'PASS' if status == 'PASS' else 'BLOCKED'}_receipt.json"
    body = {
        "receiptId": name.replace(".json", ""),
        "changeRequestId": "V2-CR-03",
        "stage": stage,
        "status": status,
        "declaredAtUtc": utc,
        "approvedSpecDigest": APPROVED_SPEC_DIGEST,
        **extra,
    }
    path = ev / name
    _write_json(path, body)
    return path


def main() -> int:
    roots = resolve_v2_cr03_roots(__file__)
    pkg = Path(roots["packageRoot"])
    sem = Path(roots["semantic"])
    ev = Path(roots["evidence"])
    rep = Path(roots["reports"])
    der = Path(roots["derived"])
    der.mkdir(parents=True, exist_ok=True)
    rep.mkdir(parents=True, exist_ok=True)

    track_path = sem / "NURION_ADAPTATION_ENGINE_V2_CR03_TRACK_V1.json"
    spec_path = (
        sem / "NURION_ADAPTATION_ENGINE_V2_CR03_MORPH_WEIGHT_RUNTIME_TALKING_SEQUENCE_SPEC_R1.json"
    )
    track = json.loads(track_path.read_text(encoding="utf-8"))
    input_glb = Path(roots["cr02Derived"])
    derived_glb = der / "Idle_15_CR03_talking_weights.glb"

    # --- P02 ---
    p02 = inject_talking_weights_animation(
        input_glb=input_glb,
        output_glb=derived_glb,
        track=track,
        spec_path=spec_path,
    )
    p02_path = rep / "V2_CR03_P02_weights_injection_idle15.json"
    _write_json(p02_path, p02)
    _receipt(
        ev,
        "P02",
        p02["status"],
        derivedSha256=(p02.get("derived") or {}).get("sha256"),
        reportPath=str(p02_path.relative_to(pkg)).replace("\\", "/"),
        role="STRUCTURAL_INJECTION_ONLY",
    )
    if p02["status"] != "PASS":
        print(json.dumps({"stoppedAt": "P02", "blockers": p02.get("blockers")}, indent=2))
        return 1

    track["stages"]["CR03-P02"] = "PASS"
    track["stages"]["CR03-P03"] = "AUTHORIZED"

    # --- P03 ---
    p03 = prove_temporal_vertex_deformation(
        derived_glb=derived_glb, track=track, spec_path=spec_path
    )
    p03_path = rep / "V2_CR03_P03_temporal_vertex_idle15.json"
    _write_json(p03_path, p03)
    _receipt(
        ev,
        "P03",
        p03["status"],
        runtimeVertexProofDigest=p03.get("runtimeVertexProofDigest"),
        reportPath=str(p03_path.relative_to(pkg)).replace("\\", "/"),
    )
    if p03["status"] != "PASS":
        print(json.dumps({"stoppedAt": "P03", "blockers": p03.get("blockers")}, indent=2))
        return 1

    track["stages"]["CR03-P03"] = "PASS"
    track["stages"]["CR03-P04"] = "AUTHORIZED"

    # --- P04 ---
    p04 = run_idle_talking_regression(
        input_glb=input_glb, derived_glb=derived_glb, track=track, spec_path=spec_path
    )
    p04_path = rep / "V2_CR03_P04_idle_talking_regression_idle15.json"
    _write_json(p04_path, p04)
    _receipt(
        ev,
        "P04",
        p04["status"],
        regressionDigest=p04.get("regressionDigest"),
        reportPath=str(p04_path.relative_to(pkg)).replace("\\", "/"),
    )
    if p04["status"] != "PASS":
        print(json.dumps({"stoppedAt": "P04", "blockers": p04.get("blockers")}, indent=2))
        return 1

    track["stages"]["CR03-P04"] = "PASS"
    track["stages"]["CR03-P05"] = "AUTHORIZED"

    # --- Independent matrix ---
    matrix = run_cr03_independent_gates(
        input_glb=input_glb, derived_glb=derived_glb, track=track, spec_path=spec_path
    )
    matrix_path = rep / "V2_CR03_independent_gate_matrix.json"
    _write_json(matrix_path, matrix)
    if matrix["status"] != "PASS":
        print(json.dumps({"stoppedAt": "INDEPENDENT_GATES", "blockers": matrix.get("blockers")}, indent=2))
        return 1

    # --- P05 seal (packaging metadata; ZIP via separate packer) ---
    derived_sha = sha256_file(derived_glb)
    semantic = canonical_sha256(
        {
            "approvedSpecDigest": APPROVED_SPEC_DIGEST,
            "cr02R2DerivedSha256": sha256_file(input_glb),
            "timelineDigest": p02["provenance"]["timelineDigest"],
            "animationSamplerDigest": p02["provenance"]["animationSamplerDigest"],
            "animationChannelDigest": p02["provenance"]["animationChannelDigest"],
            "runtimeVertexProofDigest": p03["runtimeVertexProofDigest"],
            "regressionDigest": p04["regressionDigest"],
            "derivedAssetSha256": derived_sha,
            "morphIndexMap": p02["morphIndexMap"],
        }
    )
    p05 = {
        "schema": "NURION_V2_CR03_P05_REAL_ASSET_PROOF_SEAL_V1",
        "changeRequestId": "V2-CR-03",
        "stage": "CR03-P05",
        "status": "PASS",
        "authority": {
            "V2-CR-01": "CONSUME ONLY / REOPEN DENY",
            "V2-CR-02": "CONSUME ONLY / REOPEN DENY",
            "V2-CR-03": "OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT",
            "V2-CR-04": "CANDIDATE / NOT OPEN",
            "NURION_ADAPTATION_ENGINE_V2": "NOT OPEN",
        },
        "derived": {
            "path": str(derived_glb.relative_to(pkg)).replace("\\", "/"),
            "sha256": derived_sha,
        },
        "provenance": {
            **p02["provenance"],
            "runtimeVertexProofDigest": p03["runtimeVertexProofDigest"],
            "regressionDigest": p04["regressionDigest"],
            "cr03DerivedSemanticDigest": semantic,
            "targetMeshIdentity": p02["targetMeshIdentity"],
            "talkingAnimationName": p02["talkingAnimationName"],
            "talkingAnimationIndex": p02["talkingAnimationIndex"],
            "morphIndexMap": p02["morphIndexMap"],
        },
        "stages": {
            "CR03-P01": "PASS / CONSUME ONLY",
            "CR03-P02": "PASS (structural injection)",
            "CR03-P03": "PASS (temporal vertex)",
            "CR03-P04": "PASS (Idle+TALKING regression)",
            "CR03-P05": "PASS (packaging seal)",
            "CR03-P06": "HUMAN_FINAL_ONLY",
        },
        "CR03-G20": "HUMAN_FINAL_ONLY",
        "agentCeiling": "READY_FOR_HUMAN_AUDIT",
        "completionEstimateNote": "Large progress at P03 temporal deformation; Human Final still required",
    }
    p05_path = rep / "V2_CR03_P05_real_asset_proof_seal.json"
    _write_json(p05_path, p05)
    _receipt(ev, "P05", "PASS", cr03DerivedSemanticDigest=semantic, derivedSha256=derived_sha)

    utc = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ready = {
        "receiptId": "NURION-V2-CR03_READY_FOR_HUMAN_AUDIT",
        "changeRequestId": "V2-CR-03",
        "status": "READY_FOR_HUMAN_AUDIT",
        "declaredAtUtc": utc,
        "approvedSpecDigest": APPROVED_SPEC_DIGEST,
        "derivedSha256": derived_sha,
        "cr03DerivedSemanticDigest": semantic,
        "runtimeVertexProofDigest": p03["runtimeVertexProofDigest"],
        "independentGateMatrix": str(matrix_path.relative_to(pkg)).replace("\\", "/"),
        "agentCeiling": "READY_FOR_HUMAN_AUDIT",
        "CR03-P06": "HUMAN_FINAL_ONLY",
        "CR03-G20": "HUMAN_FINAL_ONLY",
        "engineV2": "NOT_OPEN",
        "next": "Human Final Gate — recompute from GLB; Agent must not declare Human PASS",
    }
    _write_json(ev / "NURION-V2-CR03_READY_FOR_HUMAN_AUDIT_receipt.json", ready)

    track["stages"]["CR03-P05"] = "PASS"
    track["stages"]["CR03-P06"] = "HUMAN_FINAL_ONLY"
    track["status"] = "OPEN_PROTOTYPE"
    track["phase"] = "READY_FOR_HUMAN_AUDIT"
    track["updatedAtUtc"] = utc
    track["pins"] = {
        "derivedSha256": derived_sha,
        "cr03DerivedSemanticDigest": semantic,
        "runtimeVertexProofDigest": p03["runtimeVertexProofDigest"],
        "approvedSpecDigest": APPROVED_SPEC_DIGEST,
    }
    track["next"] = "CR03-P06 / G20 Human Final Audit — Agent PASS deny"
    _write_json(track_path, track)

    print(
        json.dumps(
            {
                "status": "READY_FOR_HUMAN_AUDIT",
                "derivedSha256": derived_sha,
                "cr03DerivedSemanticDigest": semantic,
                "runtimeVertexProofDigest": p03["runtimeVertexProofDigest"],
                "p02": "PASS",
                "p03": "PASS",
                "p04": "PASS",
                "p05": "PASS",
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
