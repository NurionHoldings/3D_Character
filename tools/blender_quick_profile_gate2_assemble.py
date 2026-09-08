"""
Blender assembler for Quick Profile Gate 2 dry-run.
Clones Gate5 sealed blend ONLY into quick_profile/gate2 output.
Applies recipe shape-key values. Does not mutate sealed baselines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _find_mesh():
    for obj in bpy.data.objects:
        if obj.type == "MESH" and obj.data is not None:
            return obj
    return None


def _set_keys(obj, values: dict) -> dict:
    applied = {}
    if obj.data.shape_keys is None:
        return applied
    sk = obj.data.shape_keys.key_blocks
    for name, val in values.items():
        kb = sk.get(name)
        if kb is not None:
            kb.value = float(val)
            applied[name] = float(f"{kb.value:.6f}")
    return applied


def main() -> int:
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate5-blend", required=True)
    ap.add_argument("--expected-gate5-sha256", required=True)
    ap.add_argument("--recipe-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--case-id", required=True)
    args = ap.parse_args(argv)

    src = Path(args.gate5_blend)
    exp = args.expected_gate5_sha256.lower()
    got = _sha(src).lower()
    if got != exp:
        raise SystemExit(f"Gate5 blend mutated: {got} != {exp}")

    out_dir = Path(args.out_dir) / f"run{args.run_id}" / args.case_id
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "NURION_QuickProfile_DryRun_work.blend"
    final = out_dir / "NURION_QuickProfile_DryRun_V1.blend"
    shutil.copy2(src, work)

    bpy.ops.wm.open_mainfile(filepath=str(work))
    recipe = json.loads(Path(args.recipe_json).read_text(encoding="utf-8"))
    mesh = _find_mesh()
    if mesh is None:
        raise SystemExit("No mesh in Gate5 blend")

    applied_id = _set_keys(mesh, recipe.get("identityValues", {}))
    applied_beau = _set_keys(mesh, recipe.get("beautificationValues", {}))
    applied_body = _set_keys(mesh, recipe.get("bodyMorphValues", {}))

    mesh["qp_hair"] = recipe.get("hair", "")
    mesh["qp_outfit"] = recipe.get("outfit", "")
    mesh["qp_body_preset"] = recipe.get("bodyPreset", "")
    mesh["qp_beautification_mode"] = recipe.get("beautificationMode", "POLISHED")
    mesh["qp_result_grade"] = "QUICK_PROFILE_PREVIEW"
    mesh["qp_gate8_evidence"] = "DENY"
    mesh["qp_arkaon_generation"] = "DENY"

    bpy.ops.wm.save_as_mainfile(filepath=str(final))
    blend_sha = _sha(final)

    # sealed source must still match
    if _sha(src).lower() != exp:
        raise SystemExit("Gate5 sealed source mutated during assemble")

    fingerprint_payload = {
        "caseId": args.case_id,
        "appliedIdentity": applied_id,
        "appliedBeautification": applied_beau,
        "appliedBody": applied_body,
        "hair": recipe.get("hair"),
        "outfit": recipe.get("outfit"),
        "bodyPreset": recipe.get("bodyPreset"),
        "beautificationMode": recipe.get("beautificationMode"),
        "silentHomepagePresets": recipe.get("silentHomepagePresets"),
        "arkaonPresetBinding": recipe.get("arkaonPresetBinding"),
    }
    raw = json.dumps(fingerprint_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    fp = hashlib.sha256(raw).hexdigest()

    report = {
        "schema": "NURION_V07_QP_GATE2_ASSEMBLE_REPORT",
        "caseId": args.case_id,
        "runId": int(args.run_id),
        "sourceGate5Sha256": got,
        "sourceGate5Unchanged": True,
        "outputBlend": str(final),
        "outputBlendSha256": blend_sha,
        "assembleFingerprintSha256": fp,
        "fingerprintExcludesBlendBytes": True,
        "fingerprintNote": "Blend file byte hash may vary by Blender save metadata; assemble fingerprint uses applied recipe values only.",
        "appliedIdentityCount": len(applied_id),
        "appliedBeautificationCount": len(applied_beau),
        "appliedBodyCount": len(applied_body),
        "countsAsGate8ParticipantEvidence": "DENY",
        "arkaonGenerationIntervention": "DENY",
        "production": "NO-GO",
        "completedAt": datetime.now(timezone.utc).isoformat(),
        "fingerprintPayload": fingerprint_payload,
    }
    _write(out_dir / "V07_QP_GATE2_ASSEMBLE_REPORT.json", report)
    print(json.dumps({"assembleFingerprintSha256": fp, "blendSha256": blend_sha}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
