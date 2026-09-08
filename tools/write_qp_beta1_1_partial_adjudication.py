"""Official Beta 1.1 partial-improvement adjudication — blockers remain."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
OUT = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_beta1"
ALPHA = ROOT / "dist/v0.7/product/quick_profile/complete_vertical_slice_alpha"


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    gray_bar = {
        "suspectedObject": "Beta1Hair_SHORT_NEAT_01",
        "objectType": "CUBE_SHELL_PROXY",
        "sourceScript": "tools/blender_qp_beta1_visual_assembly.py::_shell",
        "mechanism": "Hair proxy cube scaled (body_head_w*1.15, 0.18, 0.14) at ~eye/head Z intersects face bounding box",
        "alsoSuspect": ["Beta1Outfit_BUSINESS_SUIT_01", "Canonical block head remnants"],
        "hideOnlyInsufficient": True,
        "requiredAction": "TRACE_AND_EXCLUDE_FROM_HEAD_ONLY_SCENE",
    }
    receipt = {
        "schema": "NURION_V07_QP_BETA1_1_PARTIAL_IMPROVEMENT_ADJUDICATION_V1",
        "verdict": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
        "adjudicatedAt": now,
        "improvements": [
            "WHITE_EYEBALL_PROTRUSION_REMOVED",
            "FACEMESH_FRAGMENT_RENDER_REMOVED",
            "FRONTAL_TEXTURE_CONTINUOUS",
            "P001_BASIC_IMPRESSION_PARTIAL",
        ],
        "blockersRemaining": [
            "GRAY_CUBOID_THROUGH_EYE_LINE",
            "ELLIPSOID_PHOTO_WRAP_NOT_TRUE_PARAMETRIC_DEPTH",
            "FLAT_PANEL_DISTORTION_AT_45DEG",
            "INSUFFICIENT_NOSE_LIP_CHIN_SIDE_DEPTH",
            "HAIR_AS_SURFACE_CAP_NOT_SEPARATE_STRUCTURE",
            "HEAD_NECK_JOIN_INCOMPLETE",
            "FULL_BODY_STILL_BLOCK_PROXY",
            "NATURAL_POLISHED_NOT_EVALUABLE",
        ],
        "grayBarTrace": gray_bar,
        "policy": {
            "screenshotBeforeAutoAudit": "DENY",
            "fullBodyAssemblyUntilHeadAuditPass": "DENY",
            "forcedPass": "DENY",
            "production": "NO-GO",
        },
        "nextCommand": "NURION Quick Profile Beta 1.1 Head-Only Scene Isolation Object Audit And True Parametric Depth GO",
        "requiredOutputsOnly": [
            "HEAD_ONLY_WIREFRAME",
            "HEAD_ONLY_FRONT",
            "HEAD_ONLY_LEFT45",
            "HEAD_ONLY_RIGHT45",
        ],
    }
    raw = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(OUT / "V07_QP_BETA1_1_PARTIAL_IMPROVEMENT_ADJUDICATION.json", receipt)
    write_json(
        OUT / "V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS.json",
        {
            "schema": "NURION_V07_QP_COMPLETE_VERTICAL_SLICE_BETA1_STATUS_V1",
            "status": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
            "qualityGate": "REVIEW_REQUIRED",
            "updatedAt": now,
            "forcedPass": "DENY",
            "production": "NO-GO",
            "fullBodyAssembly": "DENY_UNTIL_HEAD_ONLY_AUDIT_PASS",
            "grayBarSuspect": gray_bar["suspectedObject"],
            "next": receipt["nextCommand"],
        },
    )
    alpha_path = ALPHA / "V07_QP_COMPLETE_VERTICAL_SLICE_ALPHA_STATUS.json"
    if alpha_path.is_file():
        alpha = json.loads(alpha_path.read_text(encoding="utf-8"))
        alpha.update(
            {
                "beta1Status": "BETA1_1_PARTIAL_IMPROVEMENT_BLOCKERS_REMAIN",
                "faceOutput": "IDENTITY_RENDER_INVALID",
                "preserveAs": "PIPELINE_PLUMBING_EVIDENCE_ONLY",
                "updatedAt": now,
            }
        )
        write_json(alpha_path, alpha)
    print(json.dumps({"verdict": receipt["verdict"], "grayBarSuspect": gray_bar["suspectedObject"]}, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
