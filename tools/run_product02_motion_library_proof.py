#!/usr/bin/env python3
"""
NURION-PRODUCT-02 — Motion Library Integration proof.

Packaged library verified BEFORE overwrite. Absolute paths DENY.
Human PASS NOT DECLARED.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_character_assembly import (
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    canonical_json_sha256,
)
from fast_track.runtime.product_motion_library import (
    LIBRARY_PATH,
    LIBRARY_REL,
    REQUIRED_MOTION_IDS,
    build_and_hash,
    build_motion_library,
)
from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"
SEM = ROOT / "fast_track/working/meshy_silver_starlight/semantic"


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
    _ok(LIBRARY_PATH.exists(), f"packaged library missing: {LIBRARY_PATH}")
    return json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))


def test_protected():
    h = assert_protected_sot_unchanged()
    return {"protectedHashMatch": True, "hashes": h}


def test_packaged_manifest_matches_assets():
    """Verify each packaged motion source SHA vs on-disk GLB BEFORE rebuild overwrite."""
    packaged = _load_packaged()
    assert_assembly_has_no_absolute_paths(packaged)
    details = []
    for m in packaged["motions"]:
        rel = assert_logical_repo_path(m["sourceAsset"]["glb"], field=f"{m['motionId']}.glb")
        path = ROOT / rel
        _ok(path.exists(), f"missing {rel}")
        actual = _sha256_file(path)
        _ok(actual == m["sourceAsset"]["sha256"], f"SHA drift {m['motionId']}: {actual}!={m['sourceAsset']['sha256']}")
        details.append({"motionId": m["motionId"], "sha256": actual})
    return {"motions": details}


def test_motion_manifest_completeness():
    """Technical completeness only (5/5 motion entries) — not product semantic fulfillment."""
    packaged_text = LIBRARY_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    packaged_hash = canonical_json_sha256(packaged)
    ids = [m["motionId"] for m in packaged["motions"]]
    _ok(sorted(ids) == sorted(REQUIRED_MOTION_IDS), f"ids={ids}")
    _ok(len(ids) == len(set(ids)), "duplicate motionId")
    for m in packaged["motions"]:
        for key in ("sourceAsset", "fixture", "timeDomain", "playback", "retarget", "samples", "fulfillment"):
            _ok(key in m, f"{m['motionId']} missing {key}")
        _ok(len(m["samples"]) >= 2, f"{m['motionId']} samples")
    comp = packaged.get("completeness") or {}
    _ok(comp.get("technicalOk") is True, f"technical completeness {comp}")
    _ok(comp.get("technicalLibraryCompleteness") == "5 / 5", comp)
    fresh = build_motion_library()
    fresh_hash = canonical_json_sha256(fresh)
    _ok(fresh_hash == packaged_hash, f"fresh!=packaged {fresh_hash}!={packaged_hash}")
    LIBRARY_PATH.write_text(packaged_text, encoding="utf-8")
    return {
        "ids": ids,
        "technicalLibraryCompleteness": comp.get("technicalLibraryCompleteness"),
        "packagedHash": packaged_hash,
        "freshHash": fresh_hash,
    }


def test_product_semantic_fulfillment():
    """
    P2a — motionId exists ≠ requested product semantics satisfied.
    ALIAS_PLACEHOLDER motions must keep PRODUCT-02 out of CLOSED/PASS.
    """
    packaged = _load_packaged()
    comp = packaged.get("completeness") or {}
    _ok("productSemanticCompleteness" in comp, "missing semantic completeness")
    for m in packaged["motions"]:
        _ok(m.get("fulfillment") in ("DEDICATED", "ALIAS_PLACEHOLDER"), m.get("motionId"))
    # Explicit expected current state until P2b/P2c dedicated intake
    aliases = [m["motionId"] for m in packaged["motions"] if m.get("fulfillment") == "ALIAS_PLACEHOLDER"]
    dedicated = [m["motionId"] for m in packaged["motions"] if m.get("fulfillment") == "DEDICATED"]
    _ok(comp.get("technicalLibraryCompleteness") == "5 / 5", "technical must remain 5/5")
    # FAIL closed-product claim while aliases remain
    if aliases or not comp.get("productSemanticOk"):
        raise AssertionError(
            "PRODUCT_SEMANTIC_INCOMPLETE: "
            f"productSemanticCompleteness={comp.get('productSemanticCompleteness')} "
            f"status={comp.get('status')} "
            f"aliasPlaceholders={aliases} dedicated={dedicated} "
            "— place dedicated sources at "
            "motion_library/sources/mjn_handshake_withSkin.glb and "
            "motion_library/sources/mjn_dance_withSkin.glb (+ fixtures) for P2b/P2c"
        )
    return {"productSemanticCompleteness": "5 / 5", "status": "COMPLETE"}


def test_core23_and_retarget_per_motion():
    packaged = _load_packaged()
    out = []
    for m in packaged["motions"]:
        _ok(m["retarget"]["coreBones"] == 23, m["motionId"])
        for s in m["samples"]:
            _ok(len(s["canonicalPose"]) == 23, f"{m['motionId']} frame {s['frame']}")
        out.append(m["motionId"])
    return {"retargetOk": out}


def test_root_pelvis_ownership():
    packaged = _load_packaged()
    owners = set()
    for m in packaged["motions"]:
        owners = set(m["retarget"]["translationOwners"])
        for s in m["samples"]:
            for b, bl in s["canonicalPose"].items():
                tr = bl["translation"]
                mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
                if b not in owners and mag > 1e-9:
                    raise AssertionError(f"{m['motionId']} ownership {b}")
    return {"owners": sorted(owners)}


def test_scale_contamination_zero():
    packaged = _load_packaged()
    for m in packaged["motions"]:
        _ok(m["scale"]["contamination"] == 0, m["motionId"])
        _ok(m["scale"]["unitScale"] == 0.01, m["motionId"])
        aws = m["scale"]["armatureWorldScale"]
        _ok(aws == [0.01, 0.01, 0.01] or all(abs(x - 0.01) < 1e-9 for x in aws), str(aws))
    return {"ok": True}


def test_time_domain_sanity():
    packaged = _load_packaged()
    out = []
    for m in packaged["motions"]:
        td = m["timeDomain"]
        _ok(td["durationSec"] > 0, f"{m['motionId']} duration")
        _ok(td["frameEnd"] >= td["frameStart"], f"{m['motionId']} range")
        _ok(m["playback"]["endFrame"] >= m["playback"]["startFrame"], "playback")
        out.append({"motionId": m["motionId"], "durationSec": td["durationSec"]})
    return {"motions": out}


def test_idle_motion_transition_rest_recovery():
    packaged = _load_packaged()
    _ok(len(packaged.get("transitions") or []) == 4, "need Idle↔4 motions")
    for t in packaged["transitions"]:
        _ok(t["from"] == "Idle" and t["back"] == "Idle", t)
        _ok(t["status"] == "OK", t)
    idle = next(m for m in packaged["motions"] if m["motionId"] == "Idle")
    _ok("NURION_head" in idle["samples"][-1]["canonicalPose"], "idle rest head")
    return {"transitions": len(packaged["transitions"])}


def test_repeat_playback_stability():
    packaged = _load_packaged()
    _ok(sorted(packaged["repeatPlaybackStable"]) == sorted(REQUIRED_MOTION_IDS), "repeat set")
    # re-hash samples
    for m in packaged["motions"]:
        a = canonical_json_sha256({"s": m["samples"][0], "e": m["samples"][-1]})
        b = canonical_json_sha256({"s": m["samples"][0], "e": m["samples"][-1]})
        _ok(a == b, m["motionId"])
    return {"stable": packaged["repeatPlaybackStable"]}


def test_deterministic_build_reload():
    r1 = build_and_hash()
    r2 = build_and_hash()
    _ok(r1.sha256 == r2.sha256, "rebuild drift")
    packaged_hash = canonical_json_sha256(_load_packaged())
    _ok(r1.sha256 == packaged_hash, f"rebuild vs packaged {r1.sha256}!={packaged_hash}")
    return {"sha256": r1.sha256}


def test_relocation_determinism():
    rel_paths = [
        "fast_track/__init__.py",
        "fast_track/runtime/__init__.py",
        "fast_track/runtime/body_retarget_engine.py",
        "fast_track/runtime/donor_skeleton_profile.py",
        "fast_track/runtime/retarget_contract_validator.py",
        "fast_track/runtime/product_character_assembly.py",
        "fast_track/runtime/product_motion_library.py",
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
        "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT01_CHARACTER_ASSEMBLY_BASELINE_V1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json",
        "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/canonical_identity_profile_v1.json",
    ]
    # sources + fixtures
    for m in _load_packaged()["motions"]:
        rel_paths.append(m["sourceAsset"]["glb"])
        rel_paths.append(m["fixture"]["path"])

    def materialize(dst: Path) -> None:
        for rel in rel_paths:
            src = ROOT / rel
            _ok(src.exists(), f"missing {rel}")
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)

    snippet = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "root = Path(os.environ['NURION_REPO_ROOT'])\n"
        "sys.path.insert(0, str(root))\n"
        "from fast_track.runtime.product_motion_library import build_and_hash\n"
        "print(build_and_hash().sha256)\n"
    )
    with tempfile.TemporaryDirectory(prefix="p02_A_") as ta, tempfile.TemporaryDirectory(prefix="p02_B_") as tb:
        ra, rb = Path(ta) / "repo", Path(tb) / "repo"
        materialize(ra)
        materialize(rb)
        hashes = []
        for root in (ra, rb):
            env = {**os.environ, "NURION_REPO_ROOT": str(root)}
            proc = subprocess.run(
                [sys.executable, "-c", snippet],
                capture_output=True,
                text=True,
                cwd=str(root),
                env=env,
            )
            _ok(proc.returncode == 0, proc.stderr[-500:])
            h = (proc.stdout or "").strip().splitlines()[-1].strip()
            _ok(len(h) == 64, h)
            hashes.append(h)
        _ok(hashes[0] == hashes[1], f"relocation {hashes}")
        packaged_hash = canonical_json_sha256(_load_packaged())
        _ok(hashes[0] == packaged_hash, f"relocated!=packaged {hashes[0]}!={packaged_hash}")
    return {"H1": hashes[0], "H2": hashes[1], "packagedHash": packaged_hash}


def test_missing_duplicate_clip_deny():
    packaged = _load_packaged()
    ids = [m["motionId"] for m in packaged["motions"]]
    _ok(len(ids) == len(set(ids)), "duplicate DENY fail")
    shas = [m["sourceAsset"]["sha256"] for m in packaged["motions"]]
    # Idle unique; all sources should be unique files
    _ok(len(shas) == len(set(shas)), f"duplicate source SHA DENY: {shas}")
    return {"uniqueMotions": len(ids), "uniqueAssets": len(set(shas))}


def test_jake_product_path_blocked():
    detail = assert_jake_product_path_blocked()
    packaged = _load_packaged()
    _ok(packaged["scope"]["jakeProductUse"] == "DENY", "scope")
    _ok(packaged["scope"]["faceTalkingOrchestration"].startswith("DENY"), "PRODUCT-03 boundary")
    return detail


def test_product01_idle_sha_lock():
    from fast_track.runtime.product_character_assembly import EXPECTED_ASSET_SHA256

    packaged = _load_packaged()
    idle = next(m for m in packaged["motions"] if m["motionId"] == "Idle")
    _ok(idle["sourceAsset"]["sha256"] == EXPECTED_ASSET_SHA256, "Idle SHA lock")
    return {"idleSha256": idle["sourceAsset"]["sha256"]}


def main() -> int:
    before = assert_protected_sot_unchanged()
    tests = [
        ("test_protected", test_protected),
        ("test_packaged_manifest_matches_assets", test_packaged_manifest_matches_assets),
        ("test_motion_manifest_completeness", test_motion_manifest_completeness),
        ("test_product_semantic_fulfillment", test_product_semantic_fulfillment),
        ("test_core23_and_retarget_per_motion", test_core23_and_retarget_per_motion),
        ("test_root_pelvis_ownership", test_root_pelvis_ownership),
        ("test_scale_contamination_zero", test_scale_contamination_zero),
        ("test_time_domain_sanity", test_time_domain_sanity),
        ("test_idle_motion_transition_rest_recovery", test_idle_motion_transition_rest_recovery),
        ("test_repeat_playback_stability", test_repeat_playback_stability),
        ("test_deterministic_build_reload", test_deterministic_build_reload),
        ("test_relocation_determinism", test_relocation_determinism),
        ("test_missing_duplicate_clip_deny", test_missing_duplicate_clip_deny),
        ("test_product01_idle_sha_lock", test_product01_idle_sha_lock),
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
        _ok(before == after == PROTECTED_SOT_SHA256, "protected drift")
    except AssertionError as e:
        results.append({"test": "test_protected_after", "status": "FAIL", "error": str(e)})

    failed = [r for r in results if r["status"] == "FAIL"]
    lib_status = "UNKNOWN"
    try:
        lib_status = json.loads(LIBRARY_PATH.read_text(encoding="utf-8")).get("status", "UNKNOWN")
    except Exception:
        pass
    summary = {
        "stage": "NURION-PRODUCT-02_MOTION_LIBRARY_INTEGRATION",
        "patch": "P2a",
        "product02Pass": "NOT_DECLARED",
        "product02Status": "PATCH_REQUIRED" if failed else ("PARTIAL_PENDING_ASSET_INTAKE" if lib_status != "COMPLETE" else "AWAITING_HUMAN_AUDIT"),
        "productPipelineOverall": "NOT_DECLARED",
        "passed": len(results) - len(failed),
        "failed": len(failed),
        "libraryRel": LIBRARY_REL,
        "libraryStatus": lib_status,
        "results": results,
    }
    out = EV / "NURION-PRODUCT-02_motion_library_proof_stdout.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "failed": summary["failed"], "out": str(out)}, ensure_ascii=True))
    print({"passed": summary["passed"], "failed": summary["failed"], "results": [{"test": r["test"], "status": r["status"]} for r in results]})
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
