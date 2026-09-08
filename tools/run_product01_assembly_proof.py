#!/usr/bin/env python3
"""
NURION-PRODUCT-01 — Character Assembly & Runtime Baseline proof (P1a–P1d).

Human PASS NOT DECLARED here.
Packaged baseline is audited BEFORE any overwrite (P1b/P1c).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_character_assembly import (
    ASSET_GLB_REL,
    EXPECTED_ASSET_SHA256,
    FACE_RIG_ROOT,
    SOLE_ATTACHMENT,
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    build_mjn_assembly_baseline,
    canonical_json_bytes,
    canonical_json_sha256,
    reload_assembly_deterministic,
)
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS
from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"
ASM_PATH = SEM / "NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json"
GLB_PATH = ROOT / ASSET_GLB_REL


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_packaged() -> dict:
    _ok(ASM_PATH.exists(), f"packaged baseline missing: {ASM_PATH}")
    return json.loads(ASM_PATH.read_text(encoding="utf-8"))


def test_protected():
    h = assert_protected_sot_unchanged()
    return {"protectedHashMatch": True, "hashes": h, "frozen": PROTECTED_SOT_SHA256}


def test_packaged_baseline_matches_asset():
    """P1b — packaged assembly.asset.sha256 must match on-disk GLB BEFORE rebuild overwrite."""
    packaged = _load_packaged()
    assert_assembly_has_no_absolute_paths(packaged)
    glb_rel = assert_logical_repo_path(packaged["asset"]["glb"], field="packaged.asset.glb")
    _ok(glb_rel == ASSET_GLB_REL, f"logical glb path: {glb_rel}")
    _ok(GLB_PATH.exists(), f"GLB missing at {GLB_PATH}")
    actual = _sha256_file(GLB_PATH)
    packaged_sha = packaged["asset"]["sha256"]
    _ok(actual == packaged_sha, f"asset drift actual={actual} packaged={packaged_sha}")
    _ok(actual == EXPECTED_ASSET_SHA256, f"not frozen candidate SHA: {actual}")
    _ok(packaged_sha == EXPECTED_ASSET_SHA256, f"packaged not frozen candidate: {packaged_sha}")
    return {
        "glb": glb_rel,
        "actualSha256": actual,
        "packagedSha256": packaged_sha,
        "expectedSha256": EXPECTED_ASSET_SHA256,
    }


def test_assembly_completeness():
    """Preserve packaged JSON, validate structure, then require fresh rebuild exact match (P1c)."""
    packaged_text = ASM_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    packaged_hash = canonical_json_sha256(packaged)

    required = [
        "assemblyId",
        "productDonorProfileId",
        "asset",
        "scale",
        "coreBones",
        "idle",
        "faceBodyInterface",
        "bindings",
        "runtimeScene",
        "foundation",
    ]
    for k in required:
        _ok(k in packaged, f"packaged missing {k}")
    _ok(packaged["productDonorProfileId"] == "mjn_legacy_v1", "MJN profile")
    _ok((ROOT / packaged["asset"]["glb"]).exists(), "GLB missing via logical path")
    _ok(len(packaged["asset"]["sha256"]) == 64, "asset sha")
    _ok(packaged["runtimeScene"]["idleDrive"]["enabled"] is True, "idle drive")
    assert_assembly_has_no_absolute_paths(packaged)

    fresh = build_mjn_assembly_baseline().to_json_dict()
    fresh_hash = canonical_json_sha256(fresh)
    _ok(
        fresh_hash == packaged_hash,
        f"P1c fresh!=packaged fresh={fresh_hash} packaged={packaged_hash}",
    )

    # Restore exact packaged bytes (never leave a silent overwrite)
    ASM_PATH.write_text(packaged_text, encoding="utf-8")
    after = canonical_json_sha256(json.loads(ASM_PATH.read_text(encoding="utf-8")))
    _ok(after == packaged_hash, "packaged baseline mutated after completeness")

    return {
        "assemblyId": packaged["assemblyId"],
        "packagedCanonicalSha256": packaged_hash,
        "freshCanonicalSha256": fresh_hash,
        "exactMatch": True,
    }


def test_core23_runtime_resolution():
    d = _load_packaged()
    _ok(d["coreBoneCount"] == 23, f"count={d['coreBoneCount']}")
    _ok(len(d["coreBones"]) == 23, "list len")
    pose = d["idle"]["canonicalPose"]
    _ok(set(pose.keys()) == set(d["coreBones"]), "pose keys != core")
    return {"coreBones": 23, "poseKeys": len(pose)}


def test_root_pelvis_ownership():
    d = _load_packaged()
    pose = d["idle"]["canonicalPose"]
    owners = set(d["translationOwners"])
    _ok(owners == set(TRANSLATION_OWNERS), "owner set")
    non_owner_tr = []
    for b, bl in pose.items():
        tr = bl["translation"]
        mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
        if b not in owners and mag > 1e-9:
            non_owner_tr.append(b)
    _ok(not non_owner_tr, f"non-owner translation: {non_owner_tr}")
    return {"translationOwners": sorted(owners), "violations": non_owner_tr}


def test_face_body_interface():
    d = _load_packaged()
    iface = d["faceBodyInterface"]
    _ok(iface["soleAttachment"] == SOLE_ATTACHMENT, "soleAttachment")
    _ok(iface["bodyAttachmentBone"] == "NURION_head", "head")
    _ok(iface["faceRigRoot"] == FACE_RIG_ROOT, "face root")
    _ok(iface["crossBoundaryOwnershipCollision"] == "DENY", "collision DENY")
    _ok(iface["BODY_owns"] == ["root", "pelvis", "torso", "limbs", "neck", "head_transform"], "BODY")
    face = set(iface["FACE_owns"])
    _ok({"eyes", "eyelids", "jaw", "tongue", "facial_deformation"}.issubset(face), "FACE owns")
    edges = d["runtimeScene"]["edges"]
    _ok(any(e.get("relation") == "SOLE_ATTACHMENT" for e in edges), "attachment edge")
    return {"soleAttachment": iface["soleAttachment"], "faceRigRoot": iface["faceRigRoot"]}


def test_idle_baseline():
    d = _load_packaged()
    idle = d["idle"]
    _ok("canonicalPose" in idle and idle["canonicalPose"], "pose")
    _ok(idle["frameIndex"] == 2, "frame")
    drive = d["runtimeScene"]["idleDrive"]
    _ok(drive["clip"] == "mjn_idle_15", "clip")
    _ok(drive["enabled"] is True, "enabled")
    _ok("NURION_head" in idle["canonicalPose"], "head in pose")
    assert_logical_repo_path(idle["fixture"], field="idle.fixture")
    return {"frameIndex": idle["frameIndex"], "clip": drive["clip"]}


def test_scale_normalization():
    d = _load_packaged()
    sc = d["scale"]
    _ok(sc["unitScale"] == 0.01, f"unit={sc['unitScale']}")
    aws = sc["armatureWorldScale"]
    _ok(aws == [0.01, 0.01, 0.01], f"armature={aws}")
    return sc


def test_no_missing_duplicate_binding():
    d = _load_packaged()
    core = set(d["coreBones"])
    mapped = {
        b["canonical"]
        for b in d["bindings"]
        if b.get("canonical") and b.get("role") != "FACE_SOLE_ATTACHMENT"
    }
    _ok(core.issubset(mapped), f"unmapped core: {core - mapped}")
    non_collapse = [
        b["canonical"]
        for b in d["bindings"]
        if b.get("canonical")
        and b.get("role")
        not in ("HELPER_DROP", "ADAPTER_INTERMEDIARY", "COLLAPSE_COMPOUND", "FACE_SOLE_ATTACHMENT")
    ]
    dup = [c for c, n in Counter(non_collapse).items() if n > 1]
    _ok(not dup, f"duplicates: {dup}")
    return {"mappedCore": len(core & mapped), "duplicates": dup}


def test_deterministic_load_reload():
    a1 = build_mjn_assembly_baseline()
    a2 = build_mjn_assembly_baseline()
    h1 = hashlib.sha256(a1.deterministic_bytes()).hexdigest()
    h2 = hashlib.sha256(a2.deterministic_bytes()).hexdigest()
    _ok(h1 == h2, "same-root rebuild drift")
    _, ha, hb = reload_assembly_deterministic(ASM_PATH)
    _ok(ha == hb, "reload drift")
    packaged_hash = canonical_json_sha256(_load_packaged())
    _ok(h1 == packaged_hash, f"rebuild vs packaged drift {h1}!={packaged_hash}")
    return {"rebuildHash": h1, "reloadHash": ha, "packagedHash": packaged_hash}


def test_relocation_determinism():
    """P1d — same repo under Root-A and Root-B must yield identical canonical assembly hash."""
    rel_paths = [
        "fast_track/__init__.py",
        "fast_track/runtime/__init__.py",
        "fast_track/runtime/body_retarget_engine.py",
        "fast_track/runtime/donor_skeleton_profile.py",
        "fast_track/runtime/retarget_contract_validator.py",
        "fast_track/runtime/product_character_assembly.py",
        "fast_track/runtime/retarget/__init__.py",
        "fast_track/runtime/retarget/engine.py",
        "fast_track/runtime/retarget/quat.py",
        "fast_track/runtime/retarget/canonical.py",
        "fast_track/runtime/retarget/protected.py",
        "fast_track/runtime/retarget/registry.py",
        "fast_track/runtime/retarget/profile.py",
        "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/NURION_RIG02_PRODUCT_BOUNDARY_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json",
        ASSET_GLB_REL,
        "fast_track/working/meshy_silver_starlight/evidence/rig02b_fixtures/mjn_idle_15_pose_extract.json",
    ]

    def materialize(dst: Path) -> None:
        for rel in rel_paths:
            src = ROOT / rel
            _ok(src.exists(), f"missing source for relocation copy: {rel}")
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            # ensure empty package markers exist
        for pkg in ("fast_track/__init__.py", "fast_track/runtime/__init__.py", "fast_track/runtime/retarget/__init__.py"):
            p = dst / pkg
            if not p.exists():
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text("", encoding="utf-8")

    snippet = (
        "import hashlib, json, os, sys\n"
        "from pathlib import Path\n"
        "root = Path(os.environ['NURION_REPO_ROOT'])\n"
        "sys.path.insert(0, str(root))\n"
        "from fast_track.runtime.product_character_assembly import build_mjn_assembly_baseline\n"
        "b = build_mjn_assembly_baseline().deterministic_bytes()\n"
        "print(hashlib.sha256(b).hexdigest())\n"
    )

    with tempfile.TemporaryDirectory(prefix="p01_rootA_") as ta, tempfile.TemporaryDirectory(
        prefix="p01_rootB_"
    ) as tb:
        root_a = Path(ta) / "repo"
        root_b = Path(tb) / "repo"
        materialize(root_a)
        materialize(root_b)
        hashes = []
        for root in (root_a, root_b):
            env = {**os.environ, "NURION_REPO_ROOT": str(root)}
            proc = subprocess.run(
                [sys.executable, "-c", snippet],
                capture_output=True,
                text=True,
                cwd=str(root),
                env=env,
            )
            _ok(proc.returncode == 0, f"relocation build fail: {proc.stderr[-500:]}")
            h = (proc.stdout or "").strip().splitlines()[-1].strip()
            _ok(len(h) == 64, f"bad hash output: {h!r}")
            hashes.append(h)
        h1, h2 = hashes
        _ok(h1 == h2, f"relocation drift H1={h1} H2={h2}")
        packaged_hash = canonical_json_sha256(_load_packaged())
        _ok(h1 == packaged_hash, f"relocated build != packaged {h1}!={packaged_hash}")
    return {"H1": h1, "H2": h2, "packagedHash": packaged_hash, "match": True}


def test_jake_product_path_blocked():
    detail = assert_jake_product_path_blocked()
    d = _load_packaged()
    _ok(d["productDonorProfileId"] != "jake_cc_v1", "assembly must not be Jake")
    _ok(d["scope"]["jakeProductUse"] == "DENY", "scope")
    pb = json.loads((SEM / "NURION_RIG02_PRODUCT_BOUNDARY_V1.json").read_text(encoding="utf-8"))
    _ok(pb["donors"]["jake_cc_v1"]["product_use"] is False, "boundary Jake")
    _ok(pb["donors"]["mjn_legacy_v1"]["product_use"] is True, "boundary MJN")
    return detail


def main() -> int:
    before = assert_protected_sot_unchanged()
    tests = [
        ("test_protected", test_protected),
        ("test_packaged_baseline_matches_asset", test_packaged_baseline_matches_asset),
        ("test_assembly_completeness", test_assembly_completeness),
        ("test_core23_runtime_resolution", test_core23_runtime_resolution),
        ("test_root_pelvis_ownership", test_root_pelvis_ownership),
        ("test_face_body_interface", test_face_body_interface),
        ("test_idle_baseline", test_idle_baseline),
        ("test_scale_normalization", test_scale_normalization),
        ("test_no_missing_duplicate_binding", test_no_missing_duplicate_binding),
        ("test_deterministic_load_reload", test_deterministic_load_reload),
        ("test_relocation_determinism", test_relocation_determinism),
        ("test_jake_product_path_blocked", test_jake_product_path_blocked),
    ]
    results = []
    for name, fn in tests:
        try:
            detail = fn()
            results.append({"test": name, "status": "PASS", "detail": detail})
        except Exception as e:
            results.append({"test": name, "status": "FAIL", "error": str(e)})
    after = assert_protected_sot_unchanged()
    try:
        _ok(before == after == PROTECTED_SOT_SHA256, "protected drift during proof")
    except AssertionError as e:
        results.append({"test": "test_protected_after", "status": "FAIL", "error": str(e)})

    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {
        "stage": "NURION-PRODUCT-01_CHARACTER_ASSEMBLY_RUNTIME_BASELINE",
        "patch": "P1a-P1d",
        "product01Pass": "NOT_DECLARED",
        "product01Status": "PATCHED_AWAITING_REAUDIT",
        "productPipelineOverall": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "protectedBefore": before,
        "protectedAfter": after,
        "results": results,
    }
    out = EV / "NURION-PRODUCT-01_assembly_proof_stdout.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out)}, ensure_ascii=True))
    print(
        {
            "passed": summary["passed"],
            "failed": summary["failed"],
            "results": [{"test": r["test"], "status": r["status"]} for r in results],
        }
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
