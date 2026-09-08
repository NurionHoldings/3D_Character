#!/usr/bin/env python3
"""NURION-PRODUCT-04 proof — P4-G01…G17 automated. G18 human only."""

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
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    canonical_json_sha256,
)
from fast_track.runtime.product_entrance_state import (
    FACE_LOCK_REL,
    ONE_LINE,
    STATE_PATH,
    STATE_REL,
    Product04Blocker,
    build_and_hash,
    build_entrance_state,
    consume_upstream,
)
from fast_track.runtime.product_face_body_runtime import RUNTIME_REL as PRODUCT03_RUNTIME_REL
from fast_track.runtime.product_motion_library import LIBRARY_REL
from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

EV = ROOT / "fast_track/working/meshy_silver_starlight/evidence"


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load() -> dict:
    _ok(STATE_PATH.exists(), f"missing {STATE_PATH}")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def test_g01():
    before = assert_protected_sot_unchanged()
    u = consume_upstream()
    after = assert_protected_sot_unchanged()
    _ok(before == after == PROTECTED_SOT_SHA256, "protected drift")
    st = _load()
    ps = st["protectedState"]
    _ok(ps["PRODUCT-01"]["sha256"] == _sha256_file(ROOT / ASSEMBLY_BASELINE_REL), "p01")
    _ok(ps["PRODUCT-02"]["sha256"] == _sha256_file(ROOT / LIBRARY_REL), "p02")
    _ok(ps["PRODUCT-03"]["fileSha256"] == _sha256_file(ROOT / PRODUCT03_RUNTIME_REL), "p03")
    _ok(ps["FACE"]["sha256"] == PROTECTED_SOT_SHA256["NURION_FACE_PRODUCT_LOCK_V1.json"], "face")
    return {"protectedOk": True, "upstream": u["fingerprints"]["product03RuntimeCanonicalSha256"][:16]}


def test_g02():
    st = _load()
    _ok(st["currentState"] == "LIVE_IDLE", st["currentState"])
    for row in st["deniedTransitionProof"]:
        _ok(row["denied"] is True, row)
    blocked = next(r for r in st["deniedTransitionProof"] if r["from"] == "BLOCKED" and r["to"] == "LIVE_IDLE")
    _ok(blocked["denied"] is True, "BLOCKED->LIVE_IDLE")
    _ok(st["recoveryProof"]["blockedToLiveIdle"] == "DENY", st["recoveryProof"])
    return {"denied": len(st["deniedTransitionProof"])}


def test_g03():
    st = _load()
    plan = st["run"]["preloadPlan"]
    _ok(plan["idleAssetSha256"].startswith("a113cca6"), plan)
    _ok(st["stateTrace"][0]["from"] == "BOOTSTRAP", st["stateTrace"][0])
    return {"bootstrap": "PASS"}


def test_g04():
    st = _load()
    # LIVE_IDLE only after PRODUCT-03 ready (encoded in trace)
    ready = next(t for t in st["stateTrace"] if t["to"] == "ENTRANCE_READY")
    _ok(ready["detail"].get("p03Ready") is True, ready)
    live = next(t for t in st["stateTrace"] if t["to"] == "LIVE_IDLE")
    _ok(live["from"] == "RUNTIME_HANDOFF", live)
    return {"p03ReadyBeforeLive": True}


def test_g05():
    st = _load()
    plan = st["run"]["preloadPlan"]
    for key in ("product01", "product02", "product03", "faceLock"):
        _ok((ROOT / plan[key]).exists(), plan[key])
    return {"deps": True}


def test_g06():
    st = _load()
    playing = next(t for t in st["stateTrace"] if t["to"] == "ENTRANCE_PLAYING")
    _ok(playing["from"] == "ENTRANCE_READY", playing)
    return {"startFromReady": True}


def test_g07():
    st = _load()
    _ok(st["run"]["entrance"]["singleSequence"] is True, st["run"]["entrance"])
    return {"singleSequence": True}


def test_g08():
    st = _load()
    idn = st["entranceIdentity"]
    _ok(idn["proxyCharacter"] is False and idn["jakeProductUse"] is False, idn)
    _ok(idn["idleAssetSha256"] == st["consumes"]["idleAssetSha256"], "sha")
    _ok(st["criticalGates"]["P4-G08"]["status"] == "PASS", "g08")
    return idn


def test_g09():
    st = _load()
    ps = st["protectedState"]
    _ok(ps["FACE"]["mutated"] is False and ps["TALKING"]["status"] == "GO", ps)
    _ok(ps["Eye"]["preserved"] is True, ps)
    return {"preserved": True}


def test_g10():
    st = _load()
    br = st["run"]["bodyRoot"]
    _ok(br["rootEqualsPelvis"] is False and br["preserved"] is True, br)
    return br


def test_g11():
    st = _load()
    h = st["handoff"]
    _ok(h["from"] == "ENTRANCE" and h["through"] == "RUNTIME_HANDOFF" and h["to"] == "LIVE_IDLE", h)
    _ok(h["dualAuthorityObserved"] is False, h)
    _ok(h["zeroAuthorityObservedDuringCommittedHandoff"] is False, h)
    _ok(h["authorityTransferCount"] == 1, h)
    g = st["criticalGates"]["P4-G11"]
    _ok(g["dualAuthorityObserved"] is False and g["zeroAuthorityObservedDuringCommittedHandoff"] is False, g)
    return {"dual": False, "zero": False, "transfers": 1}


def test_g12():
    st = _load()
    vc = st["visualContinuity"]
    _ok(vc["unexpectedTeleport"] is False and vc["unexpectedSnap"] is False, vc)
    _ok(vc["scaleDelta"] == 0.0, vc)
    _ok("rootTranslationDelta" in vc and "headRotationDelta" in vc, vc)
    _ok("PRODUCT-01" in vc.get("referenceSource", ""), vc)
    _ok(st["criticalGates"]["P4-G12"]["status"] == "PASS", "g12")
    return vc


def test_g13():
    st = _load()
    _ok(st["liveIdleAuthority"] == "PRODUCT-03", st)
    _ok(st["run"]["liveIdle"]["product04OwnsCharacter"] is False, st["run"]["liveIdle"])
    _ok(st["characterAuthority"] == "PRODUCT03_RUNTIME", st["characterAuthority"])
    return {"authority": "PRODUCT-03"}


def test_g14():
    st = _load()
    _ok(st["buildDeterminism"]["stable"] is True, st["buildDeterminism"])
    return st["buildDeterminism"]


def test_g15():
    st = _load()
    _ok(st["failClosed"]["status"] == "BLOCKER_OK", st["failClosed"])
    return st["failClosed"]


def test_g16():
    packaged_text = STATE_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    h0 = canonical_json_sha256(packaged)
    fresh = build_entrance_state()
    _ok(canonical_json_sha256(fresh) == h0, "determinism")
    with tempfile.TemporaryDirectory() as td:
        root_b = Path(td) / "rootB"
        for rel in [
            ASSEMBLY_BASELINE_REL,
            LIBRARY_REL,
            PRODUCT03_RUNTIME_REL,
            FACE_LOCK_REL,
            "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_COMPOSITION_POLICY_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_CANONICAL_BONE_SPEC_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_PRODUCT_LOCK_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_BODY_AXIS_RETARGET_CONVENTION_V1.json",
            "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_CANONICAL_V1_NAMING_TABLE.json",
            "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/mjn_legacy_profile_v1.json",
            "fast_track/working/meshy_silver_starlight/semantic/retarget_profiles/jake_cc_profile_v1.json",
            "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_PASS_receipt.json",
            "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-02_PASS_receipt.json",
            "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-03_PASS_receipt.json",
            STATE_REL,
            "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_CONTRACT_V1.json",
        ]:
            src = ROOT / rel
            dst = root_b / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
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
            import importlib
            import fast_track.runtime.product_entrance_state as p4

            importlib.reload(p4)
            rebuilt = p4.build_entrance_state()
            h1 = p4.canonical_json_sha256(rebuilt) if hasattr(p4, "canonical_json_sha256") else canonical_json_sha256(rebuilt)
        finally:
            if env_root is None:
                os.environ.pop("NURION_REPO_ROOT", None)
            else:
                os.environ["NURION_REPO_ROOT"] = env_root
            import importlib
            import fast_track.runtime.product_entrance_state as p4

            importlib.reload(p4)
    _ok(h0 == h1, f"relocation {h0}!={h1}")
    STATE_PATH.write_text(packaged_text, encoding="utf-8")
    return {"hash": h0}


def test_g17():
    p01 = _sha256_file(ROOT / ASSEMBLY_BASELINE_REL)
    p02 = _sha256_file(ROOT / LIBRARY_REL)
    p03 = _sha256_file(ROOT / PRODUCT03_RUNTIME_REL)
    face = _sha256_file(ROOT / FACE_LOCK_REL)
    packaged_text = STATE_PATH.read_text(encoding="utf-8")
    packaged = json.loads(packaged_text)
    assert_assembly_has_no_absolute_paths(packaged)
    fresh = build_and_hash()
    _ok(fresh.sha256 == canonical_json_sha256(packaged), "fresh!=packaged")
    STATE_PATH.write_text(packaged_text, encoding="utf-8")
    _ok(_sha256_file(ROOT / ASSEMBLY_BASELINE_REL) == p01, "p01 mutated")
    _ok(_sha256_file(ROOT / LIBRARY_REL) == p02, "p02 mutated")
    _ok(_sha256_file(ROOT / PRODUCT03_RUNTIME_REL) == p03, "p03 mutated")
    _ok(_sha256_file(ROOT / FACE_LOCK_REL) == face, "face mutated")
    st = _load()
    _ok(st["product04Pass"] == "NOT_DECLARED", "self pass")
    _ok(st["humanPassAuthority"] == "RESERVED", "authority")
    _ok(st["oneLineContract"] == ONE_LINE, "contract")
    _ok(st["scope"]["PRODUCT-05"] == "DENY", "p05")
    assert_jake_product_path_blocked()
    return {"canonicalSha256": fresh.sha256}


def main() -> int:
    tests = [
        ("P4-G01", test_g01),
        ("P4-G02", test_g02),
        ("P4-G03", test_g03),
        ("P4-G04", test_g04),
        ("P4-G05", test_g05),
        ("P4-G06", test_g06),
        ("P4-G07", test_g07),
        ("P4-G08", test_g08),
        ("P4-G09", test_g09),
        ("P4-G10", test_g10),
        ("P4-G11", test_g11),
        ("P4-G12", test_g12),
        ("P4-G13", test_g13),
        ("P4-G14", test_g14),
        ("P4-G15", test_g15),
        ("P4-G16", test_g16),
        ("P4-G17", test_g17),
    ]
    results = []
    passed = failed = 0
    for name, fn in tests:
        try:
            detail = fn()
            results.append({"gate": name, "status": "PASS", "detail": detail})
            passed += 1
        except Product04Blocker as e:
            results.append({"gate": name, "status": "BLOCKER", "error": str(e)})
            failed += 1
        except Exception as e:
            results.append({"gate": name, "status": "FAIL", "error": str(e)})
            failed += 1
    out = {
        "stage": "NURION-PRODUCT-04_ENTRANCE_STATE_PROOF",
        "passed": passed,
        "failed": failed,
        "product04Pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "P4-G18": "HUMAN_FINAL_REAUDIT_ONLY",
        "results": results,
    }
    EV.mkdir(parents=True, exist_ok=True)
    path = EV / "NURION-PRODUCT-04_entrance_state_proof_stdout.json"
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "failed": failed, "out": str(path)}, ensure_ascii=True))
    print(json.dumps(out, ensure_ascii=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
