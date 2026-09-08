#!/usr/bin/env python3
"""NURION-PRODUCT-06 proof — P6-G01…G19 automated. G20 human only."""

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
    canonical_json_sha256,
)
from fast_track.runtime.product_face_body_runtime import RUNTIME_REL as P03_RUNTIME_REL
from fast_track.runtime.product_motion_library import LIBRARY_REL
from fast_track.runtime.product_release_baseline import (
    AUTH_PACKAGE,
    BASELINE_PATH,
    FACE_LOCK_REL,
    ONE_LINE,
    P04_STATE_REL,
    P05_RUNTIME_REL,
    RELEASE_DIR,
    RELEASE_ID,
    build_and_hash,
    build_release_baseline,
    verify_upstream_authority,
)
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
    _ok(BASELINE_PATH.exists(), f"missing {BASELINE_PATH}")
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def test_g01():
    u = verify_upstream_authority()
    for pid, meta in AUTH_PACKAGE.items():
        _ok(meta["pass"] == "PASS", pid)
        _ok("CLOSED" in meta["status"], pid)
    return {"upstreamClosed": True, "p05": "R2"}


def test_g02():
    st = _load()
    _ok(st["releaseId"] == RELEASE_ID, st["releaseId"])
    _ok(st["manifest"]["identityRules"]["releaseId_neq_local_path"] is True, "path")
    _ok(st["manifest"]["identityRules"]["releaseId_neq_build_timestamp"] is True, "ts")
    return {"releaseId": RELEASE_ID}


def test_g03():
    st = _load()
    m = st["manifest"]
    for k in (
        "releaseId",
        "releaseVersion",
        "releaseSchemaVersion",
        "product01",
        "product02",
        "product03",
        "product04",
        "product05",
        "releaseEntrypoint",
        "dependencyLock",
        "upstreamHashChain",
        "packageManifest",
        "buildIdentity",
        "buildInputs",
        "buildResult",
        "canonicalReleaseDigest",
        "pipelineStatus",
        "humanPassAuthority",
    ):
        _ok(k in m, k)
    return {"manifestComplete": True}


def test_g04():
    st = _load()
    chain = st["upstreamHashChain"]
    _ok(chain["status"] == "MATCH", chain)
    p05 = next(l for l in chain["links"] if l["product"] == "PRODUCT-05")
    _ok(p05["authoritativePackage"] == "R2", p05)
    _ok(p05["sourceReviewSha256"] == AUTH_PACKAGE["PRODUCT-05"]["sourceReviewSha256"], p05)
    _ok(p05["canonicalMatch"] is True, p05)
    _ok(p05["r1Status"].startswith("SUPERSEDED"), p05)
    return {"hashChain": "MATCH", "p05": "R2"}


def test_g05():
    st = _load()
    for c in st["copyWithoutMutation"]:
        _ok(c["copyWithoutMutation"] is True, c)
        _ok(c["sourceSha256"] == c["payloadSha256"], c)
        payload = RELEASE_DIR / c["payloadRel"]
        _ok(payload.exists(), c["payloadRel"])
        _ok(_sha256_file(payload) == c["payloadSha256"], "live payload")
    return {"copies": len(st["copyWithoutMutation"]), "bytesMatch": True}


def test_g06():
    st = _load()
    dep = RELEASE_DIR / "dependency_lock.json"
    _ok(dep.exists(), "dep")
    lock = json.loads(dep.read_text(encoding="utf-8"))
    _ok(lock["releaseId"] == RELEASE_ID, lock)
    _ok("pins" in lock, lock)
    return {"dependencyLock": True}


def test_g07():
    st = _load()
    entry = RELEASE_DIR / "entry/release_entrypoint.json"
    _ok(entry.exists(), "entry")
    e = json.loads(entry.read_text(encoding="utf-8"))
    _ok(e["authorities"]["finalLiveIdle"] == "PRODUCT-03", e)
    _ok(e["authorities"]["entrance"] == "PRODUCT-04", e)
    _ok(e["authorities"]["behavior"] == "PRODUCT-05", e)
    _ok(e["absolutePath"] is False, e)
    return {"entrypoint": True}


def test_g08():
    st = _load()
    idn = st["e2eLifecycle"]["identity"]
    _ok(idn["proxyCharacter"] is False, idn)
    _ok(idn["jakeProductUse"] is False, idn)
    _ok(idn["continuous"] is True, idn)
    return {"identityContinuous": True}


def test_g09():
    st = _load()
    ent = st["e2eLifecycle"]["entrance"]
    _ok(ent["currentState"] == "LIVE_IDLE", ent)
    states = [t["state"] for t in st["e2eLifecycle"]["trace"]]
    for s in ("ENTRANCE_PLAYING", "RUNTIME_HANDOFF", "LIVE_IDLE"):
        _ok(s in states, s)
    return {"entranceE2E": True}


def test_g10():
    st = _load()
    auth = st["authorityMap"]
    _ok(auth["entranceOrchestration"] == "PRODUCT-04", auth)
    _ok(auth["canonicalRuntime"] == "PRODUCT-03", auth)
    _ok(auth["dualRuntimeAuthorityObserved"] is False, auth)
    handoff = st["e2eLifecycle"]["entrance"].get("handoff") or {}
    _ok(handoff.get("dualAuthorityObserved") is False or "dualAuthorityObserved" in handoff or handoff, handoff)
    if "dualAuthorityObserved" in handoff:
        _ok(handoff["dualAuthorityObserved"] is False, handoff)
    return {"handoffAuthority": "PRODUCT-04→PRODUCT-03"}


def test_g11():
    st = _load()
    beh = st["e2eLifecycle"]["behavior"]
    _ok(beh["currentState"] == "LIVE_IDLE", beh)
    _ok(beh["dualBehaviorAuthorityObserved"] is False, beh)
    states = [t["state"] for t in st["e2eLifecycle"]["trace"]]
    for s in ("INTERACTION_RECEIVED", "BEHAVIOR_EXECUTING", "RECOVERY"):
        _ok(s in states, s)
    return {"behaviorE2E": True}


def test_g12():
    st = _load()
    ps = st["protectedPreservation"]
    for k in ("FACE", "Eye", "TALKING", "BODY", "PRODUCT-01", "PRODUCT-02", "PRODUCT-03", "PRODUCT-04", "PRODUCT-05"):
        _ok(ps[k].get("mutated") is False, k)
    before = assert_protected_sot_unchanged()
    after = assert_protected_sot_unchanged()
    _ok(before == after == PROTECTED_SOT_SHA256, "protected")
    return {"protectedUnmutated": True}


def test_g13():
    st = _load()
    _ok(st["e2eLifecycle"]["finalLiveIdleAuthority"] == "PRODUCT-03", st)
    _ok(st["authorityMap"]["finalLiveIdle"] == "PRODUCT-03", st)
    _ok(st["authorityMap"]["product06CharacterAuthority"] is False, st)
    return {"finalLiveIdle": "PRODUCT-03"}


def test_g14():
    st = _load()
    t = st["tamperProof"]
    for k in (
        "P01_artifact_mutation",
        "P02_artifact_mutation",
        "P03_runtime_mutation",
        "P04_entrance_mutation",
        "P05_behavior_mutation",
        "release_manifest_inconsistency",
        "dependency_lock_mutation",
        "payload_missing",
        "undeclared_payload_insertion",
        "hash_chain_mismatch",
    ):
        _ok(t.get(k) == "BLOCKED", f"{k}={t.get(k)}")
    _ok(t["autoRepair"] == "DENY", t)
    _ok(t["successBypass"] == "DENY", t)
    return {"tamperFailClosed": True, "cases": 10}


def test_g15():
    st = _load()
    _ok(st["packageIntegrity"]["parity"] is True, st["packageIntegrity"])
    _ok(st["packageIntegrity"]["unsafePath"] is False, st["packageIntegrity"])
    return st["packageIntegrity"]


def test_g16():
    st = _load()
    _ok(st["reproducibility"]["stable"] is True, st["reproducibility"])
    _ok(st["reproducibility"]["digestA"] == st["reproducibility"]["digestB"], st)
    _ok(st["canonicalReleaseDigest"] == st["reproducibility"]["digestA"], st)
    a = build_release_baseline()
    b = build_release_baseline()
    _ok(a["canonicalReleaseDigest"] == b["canonicalReleaseDigest"], "rebuild digest")
    return {"canonicalReleaseDigest": st["canonicalReleaseDigest"]}


def test_g17():
    st = _load()
    digest0 = st["canonicalReleaseDigest"]
    release_id0 = st["releaseId"]
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        # relocate release tree
        dest = td_path / "relocated_release"
        shutil.copytree(RELEASE_DIR, dest)
        man = json.loads((dest / "MANIFEST.json").read_text(encoding="utf-8"))
        _ok(man["releaseId"] == release_id0, man)
        digest_file = (dest / "CANONICAL_RELEASE_DIGEST.txt").read_text(encoding="utf-8").strip()
        _ok(digest_file == digest0, digest_file)
        # rebuild under same ROOT still same digest (path independence of identity)
        fresh = build_and_hash()
        _ok(fresh.baseline["canonicalReleaseDigest"] == digest0, "identity")
        _ok(fresh.baseline["releaseId"] == RELEASE_ID, "id")
    return {"relocated": True, "digestUnchanged": True}


def test_g18():
    st = _load()
    d = st["downstream"]
    _ok(d["applications"] == "CONSUMERS ONLY", d)
    _ok(d["applicationSpecificDeploymentPass"] == "OUT OF SCOPE", d)
    _ok(d["canonicalMutation"] == "DENY", d)
    return {"downstream": "CONSUMERS ONLY"}


def test_g19():
    packaged = _load()
    packaged_text = BASELINE_PATH.read_text(encoding="utf-8")
    packaged_canon = canonical_json_sha256(packaged)
    p01 = _sha256_file(ROOT / ASSEMBLY_BASELINE_REL)
    p02 = _sha256_file(ROOT / LIBRARY_REL)
    p03 = _sha256_file(ROOT / P03_RUNTIME_REL)
    p04 = _sha256_file(ROOT / P04_STATE_REL)
    p05 = _sha256_file(ROOT / P05_RUNTIME_REL)
    face = _sha256_file(ROOT / FACE_LOCK_REL)
    fresh = build_and_hash()
    _ok(fresh.sha256 == packaged_canon, "fresh!=packaged")
    _ok(fresh.baseline["canonicalReleaseDigest"] == packaged["canonicalReleaseDigest"], "digest")
    BASELINE_PATH.write_text(packaged_text, encoding="utf-8")
    _ok(_sha256_file(ROOT / ASSEMBLY_BASELINE_REL) == p01, "p01")
    _ok(_sha256_file(ROOT / LIBRARY_REL) == p02, "p02")
    _ok(_sha256_file(ROOT / P03_RUNTIME_REL) == p03, "p03")
    _ok(_sha256_file(ROOT / P04_STATE_REL) == p04, "p04")
    _ok(_sha256_file(ROOT / P05_RUNTIME_REL) == p05, "p05")
    _ok(_sha256_file(ROOT / FACE_LOCK_REL) == face, "face")
    _ok(packaged["oneLineContract"] == ONE_LINE, "contract")
    return {
        "baselineCanonicalSha256": packaged_canon,
        "canonicalReleaseDigest": packaged["canonicalReleaseDigest"],
        "packagingRestore": True,
    }


TESTS = [
    ("P6-G01", test_g01),
    ("P6-G02", test_g02),
    ("P6-G03", test_g03),
    ("P6-G04", test_g04),
    ("P6-G05", test_g05),
    ("P6-G06", test_g06),
    ("P6-G07", test_g07),
    ("P6-G08", test_g08),
    ("P6-G09", test_g09),
    ("P6-G10", test_g10),
    ("P6-G11", test_g11),
    ("P6-G12", test_g12),
    ("P6-G13", test_g13),
    ("P6-G14", test_g14),
    ("P6-G15", test_g15),
    ("P6-G16", test_g16),
    ("P6-G17", test_g17),
    ("P6-G18", test_g18),
    ("P6-G19", test_g19),
]


def main() -> int:
    results = []
    passed = failed = 0
    for gate, fn in TESTS:
        try:
            detail = fn()
            results.append({"gate": gate, "status": "PASS", "detail": detail})
            passed += 1
        except Exception as e:
            results.append({"gate": gate, "status": "FAIL", "error": f"{type(e).__name__}: {e}"})
            failed += 1
    out = {
        "stage": "NURION-PRODUCT-06_RELEASE_BASELINE_PROOF",
        "passed": passed,
        "failed": failed,
        "product06Pass": "NOT_DECLARED",
        "pipelineOverallPass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "P6-G20": "HUMAN_FINAL_REAUDIT_ONLY",
        "NURION_CHARACTER_PRODUCT_RELEASE_V1": "NOT_YET_AUTHORITATIVE_FINAL",
        "results": results,
    }
    path = EV / "NURION-PRODUCT-06_release_baseline_proof_stdout.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"passed": passed, "failed": failed, "out": str(path)}, ensure_ascii=True))
    print(json.dumps(out, ensure_ascii=True))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
