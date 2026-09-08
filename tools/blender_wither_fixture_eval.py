"""
Run WITHER_ASSET_GT_MISMATCH fixture — bad-asset detection regression.

Does NOT rewrite Alpha3 frozen artifacts. Writes under fixtures/WITHER_ASSET_GT_MISMATCH/out/.
"""

from __future__ import annotations

import hashlib
import json
import traceback
from datetime import datetime, timezone
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / "fixtures" / "WITHER_ASSET_GT_MISMATCH"
FIXTURE = FIXTURE_DIR / "FIXTURE.json"
EXPECTED = FIXTURE_DIR / "EXPECTED.json"
OUT = FIXTURE_DIR / "out"
EVIDENCE = ROOT / "dist" / "v0.2" / "alpha3" / "reports" / "mesh-gt-mismatch.json"
ALPHA3_LOCK = ROOT / "dist" / "v0.2" / "alpha3" / "ALPHA3_LOCK.json"


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    import sys

    sys.path.insert(0, str(ROOT))

    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    expected = json.loads(EXPECTED.read_text(encoding="utf-8"))
    if not ALPHA3_LOCK.exists():
        raise RuntimeError("ALPHA3_LOCK.json missing — freeze Alpha3 before fixture eval")
    lock = json.loads(ALPHA3_LOCK.read_text(encoding="utf-8"))
    if not lock.get("frozen"):
        raise RuntimeError("Alpha3 must be frozen before running Wither fixture")

    evidence_sha = _sha256(EVIDENCE) if EVIDENCE.exists() else None
    evidence_ok = evidence_sha == expected.get("evidenceSha256")

    fbx = ROOT / fixture["asset"]["fbxRelative"]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=False)
    meshes = sorted([o for o in bpy.data.objects if o.type == "MESH"], key=lambda o: len(o.data.vertices), reverse=True)
    arms = sorted([o for o in bpy.data.objects if o.type == "ARMATURE"], key=lambda o: len(o.data.bones), reverse=True)
    mesh, arm = meshes[0], arms[0]

    from nurion_character_landmarker.core.transform_normalize import build_world_mesh_view
    from nurion_character_landmarker.evaluation.asset_eligibility import evaluate_asset_eligibility

    view = build_world_mesh_view(mesh)
    result = evaluate_asset_eligibility(mesh, arm, view=view)
    payload = result.to_dict()

    # Fixture assertions
    failures = []
    if result.assetEligible != expected["assetEligible"]:
        failures.append(f"assetEligible expected {expected['assetEligible']} got {result.assetEligible}")
    if result.reasonCode != expected["reasonCode"]:
        failures.append(f"reasonCode expected {expected['reasonCode']} got {result.reasonCode}")
    if result.evaluationAllowed != expected["evaluationAllowed"]:
        failures.append("evaluationAllowed mismatch")
    if result.autoRigAllowed != expected["autoRigAllowed"]:
        failures.append("autoRigAllowed mismatch")
    for joint in expected.get("blockedJoints", []):
        if joint not in result.blockedJoints:
            failures.append(f"missing blockedJoint {joint}")
    for joint in expected.get("evaluationExcluded", []):
        if joint not in result.evaluationExcluded:
            failures.append(f"missing evaluationExcluded {joint}")
    for check in expected.get("checksMustFail", []):
        if result.checks.get(check, True):
            failures.append(f"check {check} should fail")
    for joint, spec in expected.get("ankleBestInsideError_cm", {}).items():
        err = (result.details.get("jointReachability") or {}).get(joint, {}).get("bestInsideError_cm")
        if err is None or err < float(spec["min"]):
            failures.append(f"{joint} bestInsideError_cm {err} < min {spec['min']}")
    if not evidence_ok:
        failures.append(f"evidence sha mismatch got {evidence_sha}")

    report = {
        "schema": "NURION_WITHER_FIXTURE_REPORT",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fixtureId": "WITHER_ASSET_GT_MISMATCH",
        "pass": len(failures) == 0,
        "failures": failures,
        "evidenceSha256": evidence_sha,
        "evidenceShaMatch": evidence_ok,
        "eligibility": payload,
        "blocker": True,
        "autoRigConfirm": "DENY",
        "alpha3FrozenSha256": lock.get("sha256"),
        "failClass": "ASSET_GT_MISMATCH",
    }
    _write(OUT / "fixture-report.json", report)
    _write(OUT / "asset-eligibility.json", payload)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["pass"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
