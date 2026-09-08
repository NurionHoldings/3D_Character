"""NURION Parametric Head Candidate A Restore v1 And Non-Destructive Oral Eye Topology Reconstruction GO."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))

from nurion_qp_geometry_face_v2.gate5_contract import gate5_parameter_hash
from nurion_qp_geometry_face_v2.nurion_derived_head_from_hm08 import EXP_G5, sha256_file
from nurion_qp_geometry_face_v2.nurion_derived_head_v1_nd_reconstruct import (
    REJECTED_V2_SKIN_SHA,
    V1_BASELINE_SKIN_SHA,
    reconstruct_from_v1_basis,
    write_nd_bundle,
)

COMMAND = (
    "NURION Parametric Head Candidate A Restore v1 And "
    "Non-Destructive Oral Eye Topology Reconstruction GO"
)
ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
V1_DIR = CAND / "derived_v1"
V1_SKIN = V1_DIR / "NURION_DerivedHead_v1_skin.obj"
V2_DIR = CAND / "derived_v2"
V2_SKIN = V2_DIR / "NURION_DerivedHead_v2_skin.obj"
ND_DIR = CAND / "derived_v1_basis_nd"
BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
RENDER_PY = ROOT / "tools/blender_qp_derived_head_neutral_gray_qa_render.py"

GRAY_VIEWS = ("front", "left", "right", "top", "bottom")
WIRE_QUAD_VIEWS = ("front", "left", "right")
MOUTH_VIEWS = ("mouth_open_front", "mouth_open_left", "mouth_open_interior")


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _v2_rejection_block() -> dict[str, Any]:
    v2_sha = sha256_file(V2_SKIN) if V2_SKIN.is_file() else REJECTED_V2_SKIN_SHA
    return {
        "verdict": "REJECTED_FRAGMENTED_DERIVATION",
        "officialFailVerdict": "ALGORITHM_FAIL_BOUNDARY_REPAIR_FRAGMENTED_MESH",
        "rejectedSkinSha256": v2_sha,
        "knownRejectedSha256": REJECTED_V2_SKIN_SHA,
        "mergeIntoV1": "DENY",
        "preserveAsEvidenceOnly": True,
        "evidencePath": str(V2_DIR.relative_to(ROOT)).replace("\\", "/") if V2_DIR.is_dir() else None,
        "doNotRepairFurther": True,
    }


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"v1_restore_nd_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    if gate5_parameter_hash() != EXP_G5:
        write_json(out / "RECEIPT.json", {"verdict": "SEALED_BASELINE_MUTATION_DENY"})
        return 2

    if not V1_SKIN.is_file():
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "V1_SKIN_MISSING"})
        return 2

    v1_sha = sha256_file(V1_SKIN)
    if v1_sha != V1_BASELINE_SKIN_SHA:
        write_json(
            out / "RECEIPT.json",
            {
                "verdict": "ALGORITHM_FAIL",
                "reason": "V1_BASELINE_SHA_MISMATCH",
                "expected": V1_BASELINE_SKIN_SHA,
                "actual": v1_sha,
            },
        )
        return 2

    v2_rejection = _v2_rejection_block()
    write_json(CAND / "V07_QP_DERIVED_HEAD_V2_REJECTION_RECEIPT.json", v2_rejection)
    write_json(out / "V07_QP_DERIVED_HEAD_V2_REJECTION_RECEIPT.json", v2_rejection)

    result = reconstruct_from_v1_basis(V1_DIR)
    assets = write_nd_bundle(
        ND_DIR,
        V1_DIR,
        result,
        header=[
            "# NURION Derived Head v1 basis — non-destructive reconstruction",
            f"# BasisSkinSha256: {V1_BASELINE_SKIN_SHA}",
            f"# RunId: {run_id}",
        ],
    )

    qa_render_created = 0
    review_desk = None
    render_verdict = "DENY_NUMERIC_VALIDATION_NOT_PASS"

    if result.verdict == "NUMERIC_VALIDATION_PASS":
        cap = out / "captures"
        cap.mkdir(parents=True, exist_ok=True)
        meta_path = out / "render_meta.json"
        log = out / "logs/render.txt"
        log.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(
            [
                str(BLENDER),
                "--background",
                "--python",
                str(RENDER_PY),
                "--",
                f"--skin-obj={ND_DIR / 'NURION_DerivedHead_v1_basis_skin.obj'}",
                f"--rig-obj={ND_DIR / 'NURION_DerivedHead_v1_basis_rig_helpers.obj'}",
                f"--out-dir={cap}",
                "--label=DERIVED_V1_BASIS_ND",
                f"--meta-json={meta_path}",
                "--resolution=1280",
            ],
            capture_output=True,
            text=True,
        )
        log.write_text((proc.stdout or "") + "\n---STDERR---\n" + (proc.stderr or ""), encoding="utf-8")

        required = []
        for v in GRAY_VIEWS:
            required.append(cap / f"DERIVED_V1_BASIS_ND_gray_{v}.png")
        for v in WIRE_QUAD_VIEWS:
            required.append(cap / f"DERIVED_V1_BASIS_ND_wire_quad_{v}.png")
        required.append(cap / f"DERIVED_V1_BASIS_ND_wire_tri_note_front.png")
        for v in MOUTH_VIEWS:
            required.append(cap / f"DERIVED_V1_BASIS_ND_{v}.png")
        missing = [str(p.relative_to(ROOT)).replace("\\", "/") for p in required if not p.is_file()]

        if proc.returncode == 0 and not missing:
            pres = out / "presentation"
            pres.mkdir(parents=True, exist_ok=True)
            for p in required:
                (pres / p.name).write_bytes(p.read_bytes())
            qa_render_created = len(required)
            render_verdict = "QA_RENDER_MORPH_ONLY_AWAITING_HUMAN"
            desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>v1 Basis ND QA</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem}}
img{{width:100%;background:#111;border-radius:.35rem}}
code{{color:#9cdcfe;font-size:.85rem}}
</style></head><body>
<h1>v1 Basis — Non-Destructive Morph QA</h1>
<span class="badge">{render_verdict}</span>
<span class="badge">v2 REJECTED evidence only</span>
<span class="badge">skin face deletion DENY</span>
<span class="badge">Production NO-GO</span>
<p>Basis SHA: <code>{V1_BASELINE_SKIN_SHA}</code></p>
<p>Mouth-open via jaw rig morph only. Skin topology unchanged.</p>
<div class="grid">
<img src="DERIVED_V1_BASIS_ND_gray_front.png"/><img src="DERIVED_V1_BASIS_ND_gray_left.png"/><img src="DERIVED_V1_BASIS_ND_gray_right.png"/>
<img src="DERIVED_V1_BASIS_ND_mouth_open_front.png"/><img src="DERIVED_V1_BASIS_ND_mouth_open_left.png"/><img src="DERIVED_V1_BASIS_ND_mouth_open_interior.png"/>
</div>
</body></html>
"""
            review_desk = pres / "V1_BASIS_ND_QA_DESK.html"
            review_desk.write_text(desk, encoding="utf-8")
            try:
                subprocess.Popen(["cmd", "/c", "start", "", str(review_desk)], shell=False)
            except Exception:
                pass
        else:
            render_verdict = "ALGORITHM_FAIL_QA_RENDER"
            write_json(out / "QA_RENDER_FAIL.json", {"missing": missing, "log": str(log)})

    receipt = {
        "schema": "NURION_V07_V1_RESTORE_ND_RECONSTRUCTION_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": result.verdict if qa_render_created == 0 else render_verdict,
        "numericValidation": result.validation,
        "activeBaseline": {
            "asset": "NURION_DerivedHead_v1_skin",
            "sha256": V1_BASELINE_SKIN_SHA,
            "restoredFromV1Bytes": True,
        },
        "v2Rejection": v2_rejection,
        "nonDestructiveRules": {
            "skinFaceDeletion": "DENY",
            "lipSealBasis": "PRESERVED",
            "oralOpening": "MORPH_JAW_ONLY",
            "oralCavity": "SEPARATE_INTERNAL_MESH",
            "eyeOpening": "MORPH_BLINK_OPEN_ONLY",
            "neckCut": "EXPLICIT_CUT_ALLOWED_ONLY",
            "correspondenceNewLossAllowance": 0,
        },
        "boundaryLoopMap": str((ND_DIR / "BOUNDARY_LOOP_MAP.json").relative_to(ROOT)).replace("\\", "/"),
        "morphSpec": str((ND_DIR / "MORPH_SPEC.json").relative_to(ROOT)).replace("\\", "/"),
        "ndBundleDir": str(ND_DIR.relative_to(ROOT)).replace("\\", "/"),
        "qaRender": {
            "allowedOnlyAfterNumericPass": True,
            "created": qa_render_created,
            "verdict": render_verdict,
            "reviewDesk": str(review_desk.relative_to(ROOT)).replace("\\", "/") if review_desk else None,
        },
        "identityFitting": "DENY",
        "p001Reapply": "DENY",
        "humanSimilarityEval": "DENY",
        "production": "NO-GO",
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_V1_RESTORE_ND_RECONSTRUCTION_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_V1_RESTORE_ND_RECONSTRUCTION_RECEIPT.json", receipt)
    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": receipt["verdict"],
            "activeBaseline": "NURION_DerivedHead_v1_skin",
            "activeBaselineSha256": V1_BASELINE_SKIN_SHA,
            "v2Status": "REJECTED_FRAGMENTED_DERIVATION",
            "v2MergeIntoV1": "DENY",
            "ndBundle": receipt["ndBundleDir"],
            "identityFitting": "DENY",
            "p001Reapply": "DENY",
            "humanSimilarityEval": "DENY",
            "production": "NO-GO",
            "updatedAt": now,
            "lastRunId": run_id,
        },
    )

    print(
        json.dumps(
            {
                "verdict": receipt["verdict"],
                "activeBaselineSha256": V1_BASELINE_SKIN_SHA,
                "v2Rejected": v2_rejection["verdict"],
                "numericValidationPass": result.validation["pass"],
                "qaRenderCreated": qa_render_created,
                "identityFitting": "DENY",
                "production": "NO-GO",
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0 if result.validation["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
