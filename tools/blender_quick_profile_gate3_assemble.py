"""Blender 5.0.1 assembler for Gate 3 NATURAL/POLISHED review drafts."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def set_shape_keys(mesh, values: dict) -> dict:
    applied = {}
    if mesh.data.shape_keys is None:
        return applied
    blocks = mesh.data.shape_keys.key_blocks
    for name, value in values.items():
        key = blocks.get(name)
        if key is not None:
            key.value = float(value)
            applied[name] = float(f"{key.value:.6f}")
    return applied


def main() -> int:
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--source-blend", required=True)
    ap.add_argument("--expected-source-sha256", required=True)
    ap.add_argument("--recipe-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--participant-id", choices=("P001", "P002", "P003"), required=True)
    ap.add_argument("--mode", choices=("NATURAL", "POLISHED"), required=True)
    args = ap.parse_args(argv)

    source = Path(args.source_blend)
    source_hash = sha256_file(source)
    if source_hash != args.expected_source_sha256.lower():
        raise SystemExit("SOURCE_GATE5_HASH_MISMATCH")

    recipe = json.loads(Path(args.recipe_json).read_text(encoding="utf-8"))
    if recipe.get("beautificationMode") != args.mode:
        raise SystemExit("RECIPE_MODE_MISMATCH")
    if args.mode == "NATURAL" and any(float(v) != 0.0 for v in recipe.get("beautificationValues", {}).values()):
        raise SystemExit("NATURAL_BEAUTIFICATION_NOT_ZERO")

    out = Path(args.out_dir) / "drafts" / args.participant_id / args.mode
    out.mkdir(parents=True, exist_ok=True)
    work = out / "NURION_QP_Gate3_work.blend"
    final = out / f"NURION_QP_Gate3_{args.participant_id}_{args.mode}.blend"
    shutil.copy2(source, work)
    bpy.ops.wm.open_mainfile(filepath=str(work))
    mesh = next((o for o in bpy.data.objects if o.type == "MESH" and o.data is not None), None)
    if mesh is None:
        raise SystemExit("NO_MESH")

    applied_id = set_shape_keys(mesh, recipe.get("identityValues", {}))
    applied_beauty = set_shape_keys(mesh, recipe.get("beautificationValues", {}))
    applied_body = set_shape_keys(mesh, recipe.get("bodyMorphValues", {}))
    mesh["qp_gate3_participant_id"] = args.participant_id
    mesh["qp_gate3_mode"] = args.mode
    mesh["qp_gate8_evidence"] = "DENY"
    mesh["qp_face_authentication"] = "OUT_OF_SCOPE"
    mesh["qp_production"] = "NO-GO"
    mesh["qp_arkaon_generation"] = "DENY"
    bpy.ops.wm.save_as_mainfile(filepath=str(final))

    if sha256_file(source) != args.expected_source_sha256.lower():
        raise SystemExit("SOURCE_GATE5_MUTATED")

    payload = {
        "participantId": args.participant_id,
        "mode": args.mode,
        "appliedIdentity": applied_id,
        "appliedBeautification": applied_beauty,
        "appliedBody": applied_body,
        "bodyPreset": recipe.get("bodyPreset"),
        "hair": recipe.get("hair"),
        "outfit": recipe.get("outfit"),
        "silentHomepagePresets": recipe.get("silentHomepagePresets"),
        "arkaonPresetBinding": recipe.get("arkaonPresetBinding"),
    }
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    report = {
        "schema": "NURION_V07_QP_GATE3_ASSEMBLE_REPORT_V1",
        "participantId": args.participant_id,
        "mode": args.mode,
        "sourceGate5Sha256": source_hash,
        "sourceGate5Unchanged": True,
        "outputBlend": str(final),
        "outputBlendSha256": sha256_file(final),
        "assembleFingerprintSha256": fp,
        "fingerprintPayload": payload,
        "countsAsGate8ParticipantEvidence": "DENY",
        "production": "NO-GO",
        "completedAt": datetime.now(timezone.utc).isoformat(),
    }
    write_json(out / "V07_QP_GATE3_ASSEMBLE_REPORT.json", report)
    print(json.dumps({"assembleFingerprintSha256": fp, "outputBlendSha256": report["outputBlendSha256"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
