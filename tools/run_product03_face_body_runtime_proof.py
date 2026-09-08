#!/usr/bin/env python3
"""
NURION-PRODUCT-03 — FACE/BODY Runtime Integration proof (P3-G01…G17 automated).

P3-G18 Human Final Reaudit is NOT declared here.
Agent MUST NOT declare CLOSED/PASS.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))
sys.path.insert(0, str(ROOT))

from fast_track.runtime.product_character_assembly import (
    ASSEMBLY_BASELINE_REL,
    EXPECTED_ASSET_SHA256 as PRODUCT01_IDLE_SHA,
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    canonical_json_sha256,
)
from fast_track.runtime.product_face_body_runtime import (
    CONTRACT_REL,
    FACE_LOCK_REL,
    ONE_LINE,
    RUNTIME_PATH,
    RUNTIME_REL,
    Product03Blocker,
    Product03Error,
    build_and_hash,
    build_face_body_runtime,
    consume_locked_inputs,
)
from fast_track.runtime.product_motion_library import LIBRARY_REL, REQUIRED_MOTION_IDS
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
    _ok(RUNTIME_PATH.exists(), f"packaged runtime missing: {RUNTIME_PATH}")
    return json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))


def test_g01_protected_sot():
    before = assert_protected_sot_unchanged()
    consumed = consume_locked_inputs()
    after = assert_protected_sot_unchanged()
    _ok(before == after == PROTECTED_SOT_SHA256, "protected SoT drift")
    fp = consumed["fingerprints"]
    _ok(fp["faceLockSha256"] == PROTECTED_SOT_SHA256["NURION_FACE_PRODUCT_LOCK_V1.json"], "face lock")
    # PRODUCT-01/02 fingerprints match on-disk (no mutation during proof so far)
    _ok(fp["product01AssemblySha256"] == _sha256_file(ROOT / ASSEMBLY_BASELINE_REL), "p01")
    _ok(fp["product02LibrarySha256"] == _sha256_file(ROOT / LIBRARY_REL), "p02")
    return {"protected": before, "product01": fp["product01AssemblySha256"][:16], "product02": fp["product02LibrarySha256"][:16]}


def test_g02_face_body_interface():
    rt = _load_packaged()
    att = rt["attachmentAuthority"]
    _ok(att["parent"] == "NURION_head" and att["child"] == "FACE_Rig_Root", att)
    _ok(att["relation"] == "SOLE_ATTACHMENT", att)
    iface = rt["faceBodyInterface"]
    _ok(iface["binding"]["parent"] == "NURION_head", iface)
    _ok(iface["binding"]["child"] == "FACE_Rig_Root", iface)
    return {"attachment": att}


def test_g03_root_pelvis_ownership():
    rt = _load_packaged()
    own = rt["ownership"]
    _ok(own["rootEqualsPelvis"] is False, "root==pelvis")
    _ok("NURION_root" in own["translationOwners"], own)
    _ok("NURION_pelvis" in own["translationOwners"], own)
    _ok(own["NURION_root"] != own.get("merged"), "merge")
    return own


def test_g04_runtime_assembly():
    rt = _load_packaged()
    nodes = {n["id"] for n in rt["runtimeScene"]["nodes"]}
    _ok("FACE_Rig_Root" in nodes, nodes)
    _ok("CanonicalBodyPose" in nodes, nodes)
    _ok(rt["runtimeScene"]["faceDriver"]["talking"] == "GO", "talking")
    _ok(rt["oneLineContract"] == ONE_LINE, "contract line")
    return {"nodes": sorted(nodes)}


def test_g05_motion_binding():
    rt = _load_packaged()
    ids = [m["motionId"] for m in rt["motionBindings"]]
    _ok(sorted(ids) == sorted(REQUIRED_MOTION_IDS), ids)
    for m in rt["motionBindings"]:
        _ok(m["bound"] is True, m)
        _ok(m["fulfillment"] == "DEDICATED", m)
        _ok(m["coreBones"] == 23, m)
        _ok(m["retargetStatus"] == "OK", m)
    return {"bound": ids}


def test_g06_face_preservation():
    rt = _load_packaged()
    for row in rt["facePreservationDuringMotion"]:
        _ok(row["status"] == "PASS", row)
        _ok(row["samplesChecked"] >= 2, row)
    return {"motions": [r["motionId"] for r in rt["facePreservationDuringMotion"]]}


def test_g07_eye_preservation():
    rt = _load_packaged()
    eye = rt["eyePreservation"]
    _ok(eye["stableAcrossAllMotions"] is True, eye)
    _ok(len(eye["channels"]) == 6, eye)
    _ok(bool(eye["calibrationFingerprintSha256"]), "fp")
    # All face-pres rows share eye fingerprint identity across motions (neutral baseline)
    fps = [canonical_json_sha256(r["eyeFingerprint"]) for r in rt["facePreservationDuringMotion"]]
    _ok(len(set(fps)) == 1, fps)
    return eye


def test_g08_talking_compatibility():
    rt = _load_packaged()
    tc = rt["talkingCompatibility"]
    _ok(tc["talking_status"] == "GO", tc)
    _ok(tc["faceLockUnmutated"] is True, tc)
    for row in tc["coplay"]:
        _ok(row["status"] == "PASS" and row["speechActive"] and row["eyeStable"], row)
    face_lock = json.loads((ROOT / FACE_LOCK_REL).read_text(encoding="utf-8"))
    _ok(face_lock["talking_status"] == "GO", "lock still GO")
    return {"coplay": len(tc["coplay"])}


def test_g09_transitions():
    rt = _load_packaged()
    _ok(len(rt["transitions"]) == 4, rt["transitions"])
    for t in rt["transitions"]:
        _ok(t["from"] == "Idle" and t["back"] == "Idle" and t["status"] == "OK", t)
        _ok(t["idleEndHasHead"] is True, t)
    return {"n": len(rt["transitions"])}


def test_g10_transform_scale():
    rt = _load_packaged()
    for row in rt["transformScaleStability"]:
        _ok(row["contamination"] == 0, row)
    return {"n": len(rt["transformScaleStability"])}


def test_g11_donor_isolation():
    rt = _load_packaged()
    d = rt["donorIsolation"]
    _ok(d["jakeProductUse"] is False, d)
    _ok(d["Jake"]["productPathBlocked"] is True, d)
    assert_jake_product_path_blocked()
    return d


def test_g12_runtime_determinism():
    packaged_text = RUNTIME_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    packaged_hash = canonical_json_sha256(packaged)
    fresh = build_face_body_runtime()
    fresh_hash = canonical_json_sha256(fresh)
    _ok(fresh_hash == packaged_hash, f"fresh!=packaged {fresh_hash}!={packaged_hash}")
    # restore packaged bytes exactly (no overwrite drift)
    RUNTIME_PATH.write_text(packaged_text, encoding="utf-8")
    return {"hash": packaged_hash}


def test_g13_relocation_determinism():
    packaged = _load_packaged()
    h0 = canonical_json_sha256(packaged)
    with tempfile.TemporaryDirectory() as td:
        root_b = Path(td) / "rootB"
        # Mirror minimal repo tree via copy of consume artifacts + runtime code
        for rel in [
            ASSEMBLY_BASELINE_REL,
            LIBRARY_REL,
            FACE_LOCK_REL,
            "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_COMPOSITION_POLICY_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json",
            "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json",
            "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json",
            RUNTIME_REL,
            CONTRACT_REL,
        ]:
            src = ROOT / rel
            dst = root_b / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        # copy runtime package
        for pattern in ["fast_track/runtime", "fast_track/__init__.py"]:
            src = ROOT / pattern
            dst = root_b / pattern
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
        env_root = os.environ.get("NURION_REPO_ROOT")
        os.environ["NURION_REPO_ROOT"] = str(root_b)
        try:
            # re-import under new root by calling build with env
            import importlib
            import fast_track.runtime.product_face_body_runtime as p3

            importlib.reload(p3)
            rebuilt = p3.build_face_body_runtime()
            h1 = p3.canonical_json_sha256(rebuilt)
        finally:
            if env_root is None:
                os.environ.pop("NURION_REPO_ROOT", None)
            else:
                os.environ["NURION_REPO_ROOT"] = env_root
            import importlib
            import fast_track.runtime.product_face_body_runtime as p3

            importlib.reload(p3)
    _ok(h0 == h1, f"relocation mismatch {h0}!={h1}")
    return {"hash": h0}


def test_g14_negative_fail_closed():
    # Missing FACE lock path must BLOCKER — without mutating real SoT
    from fast_track.runtime import product_face_body_runtime as p3

    real = p3.FACE_LOCK_REL
    try:
        p3.FACE_LOCK_REL = (
            "fast_track/working/meshy_silver_starlight/semantic/DOES_NOT_EXIST_FACE_LOCK.json"
        )
        raised = False
        try:
            p3.consume_locked_inputs()
        except Exception as e:
            raised = True
            _ok(
                "BLOCKER" in str(e) or type(e).__name__ == "Product03Blocker",
                f"expected BLOCKER, got {type(e)}: {e}",
            )
        _ok(raised, "expected BLOCKER for missing FACE lock")
    finally:
        p3.FACE_LOCK_REL = real
    return {"missingFaceLock": "BLOCKER_OK"}


def test_g15_packaged_matches_assets():
    """Verify packaged consume SHAs vs on-disk BEFORE any rebuild overwrite."""
    rt = _load_packaged()
    assert_assembly_has_no_absolute_paths(rt)
    c = rt["consumes"]
    _ok(c["PRODUCT-01"]["sha256"] == _sha256_file(ROOT / ASSEMBLY_BASELINE_REL), "p01 sha")
    _ok(c["PRODUCT-02"]["sha256"] == _sha256_file(ROOT / LIBRARY_REL), "p02 sha")
    _ok(c["FACE_PRODUCT_LOCK"]["sha256"] == _sha256_file(ROOT / FACE_LOCK_REL), "face sha")
    _ok(c["idleAssetSha256"] == PRODUCT01_IDLE_SHA, "idle")
    return {"consumesOk": True}


def test_g16_product_semantic_runtime():
    rt = _load_packaged()
    sem = rt["productSemanticRuntime"]
    _ok(sem["motionsDedicated"] == 5, sem)
    _ok(sem["facePreserved"] and sem["eyePreserved"] and sem["talkingGo"], sem)
    _ok(rt["pass"] == "NOT_DECLARED", "agent must not declare PASS")
    _ok(rt["humanPassAuthority"] == "RESERVED", "authority")
    _ok(rt["scope"]["PRODUCT-04"] == "DENY", "p04")
    return sem


def test_g17_packaging_integrity_preflight():
    """Fresh build matches packaged; packaged text restored; consume SHAs unchanged."""
    p01_before = _sha256_file(ROOT / ASSEMBLY_BASELINE_REL)
    p02_before = _sha256_file(ROOT / LIBRARY_REL)
    face_before = _sha256_file(ROOT / FACE_LOCK_REL)
    packaged_text = RUNTIME_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    fresh = build_and_hash()
    _ok(fresh.sha256 == canonical_json_sha256(packaged), "fresh!=packaged")
    RUNTIME_PATH.write_text(packaged_text, encoding="utf-8")
    _ok(_sha256_file(ROOT / ASSEMBLY_BASELINE_REL) == p01_before, "p01 mutated")
    _ok(_sha256_file(ROOT / LIBRARY_REL) == p02_before, "p02 mutated")
    _ok(_sha256_file(ROOT / FACE_LOCK_REL) == face_before, "face mutated")
    return {"canonicalSha256": fresh.sha256}


def main() -> int:
    tests = [
        ("P3-G01", test_g01_protected_sot),
        ("P3-G15", test_g15_packaged_matches_assets),  # before overwrite-sensitive rebuilds
        ("P3-G02", test_g02_face_body_interface),
        ("P3-G03", test_g03_root_pelvis_ownership),
        ("P3-G04", test_g04_runtime_assembly),
        ("P3-G05", test_g05_motion_binding),
        ("P3-G06", test_g06_face_preservation),
        ("P3-G07", test_g07_eye_preservation),
        ("P3-G08", test_g08_talking_compatibility),
        ("P3-G09", test_g09_transitions),
        ("P3-G10", test_g10_transform_scale),
        ("P3-G11", test_g11_donor_isolation),
        ("P3-G12", test_g12_runtime_determinism),
        ("P3-G13", test_g13_relocation_determinism),
        ("P3-G14", test_g14_negative_fail_closed),
        ("P3-G16", test_g16_product_semantic_runtime),
        ("P3-G17", test_g17_packaging_integrity_preflight),
    ]
    results = []
    passed = failed = 0
    for name, fn in tests:
        try:
            detail = fn()
            results.append({"gate": name, "status": "PASS", "detail": detail})
            passed += 1
        except Product03Blocker as e:
            results.append({"gate": name, "status": "BLOCKER", "error": str(e)})
            failed += 1
        except Exception as e:
            results.append({"gate": name, "status": "FAIL", "error": str(e)})
            failed += 1

    out = {
        "stage": "NURION-PRODUCT-03_FACE_BODY_RUNTIME_PROOF",
        "passed": passed,
        "failed": failed,
        "product03Pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "P3-G18": "HUMAN_FINAL_REAUDIT_ONLY",
        "results": results,
    }
    EV.mkdir(parents=True, exist_ok=True)
    stdout_path = EV / "NURION-PRODUCT-03_face_body_runtime_proof_stdout.json"
    stdout_path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "failed": failed, "out": str(stdout_path)}, ensure_ascii=True))
    print(out)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
