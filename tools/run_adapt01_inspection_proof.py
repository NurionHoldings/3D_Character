#!/usr/bin/env python3
"""ADAPT-01 proof — AD1-G01…G15 automated. AD1-G16 HUMAN ONLY. Ceiling: READY_FOR_HUMAN_AUDIT.

Self-contained for extracted audit ZIP: no fast_track.runtime / PRODUCT imports.
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

_ROOTS = None


def _roots():
    global _ROOTS
    if _ROOTS is None:
        # bootstrap path helper without requiring package yet
        here = Path(__file__).resolve()
        parent = here.parents[1]
        if parent.name == "repo":
            sys.path.insert(0, str(parent))
        else:
            sys.path.insert(0, str(Path(os.environ.get("NURION_REPO_ROOT", str(parent)))))
        from fast_track.adaptation.audit_paths import resolve_adapt01_roots

        _ROOTS = resolve_adapt01_roots(__file__)
    return _ROOTS


def _bind():
    r = _roots()
    from fast_track.adaptation.inspector import (
        canonical_sha256,
        inspect_character,
        sha256_file,
    )

    # Local alias — same canonical JSON SHA semantics; no PRODUCT runtime dependency
    canonical_json_sha256 = canonical_sha256
    return r, inspect_character, sha256_file, canonical_json_sha256


# Protected NURION V1 digests — must remain unchanged (mutation NONE)
V1_RELEASE_DIGEST = "30d9f70790b6c834a3cc3283489b8ba60d2bf4b2d1ad956b74eb0e93c542fd4a"
V1_P06_BASELINE = "1a714e78f9c1eb3a09f498f29c94116d8afad79fb519a589d9f52a73167786ed"
V1_P06_ZIP = "9aacac94e9e48024c3f5195ee445eee49fb83c655bd1864aa66ebf6e08d52192"


def _ok(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _write(ev: Path, name: str, obj: object) -> Path:
    ev.mkdir(parents=True, exist_ok=True)
    p = ev / name
    p.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def run_all() -> dict:
    r, inspect_character, sha256_file, canonical_json_sha256 = _bind()
    EV: Path = r["evidence"]  # type: ignore[assignment]
    REP: Path = r["reports"]  # type: ignore[assignment]
    FIX: Path = r["fixtures"]  # type: ignore[assignment]
    SEM: Path = r["semantic"]  # type: ignore[assignment]
    REPO: Path = r["repoRoot"]  # type: ignore[assignment]
    EXTRACTED: bool = bool(r["extracted"])
    REP.mkdir(parents=True, exist_ok=True)
    EV.mkdir(parents=True, exist_ok=True)
    FIX.mkdir(parents=True, exist_ok=True)

    CONTRACT = SEM / "NURION_ADAPT01_CHARACTER_INTAKE_INSPECTION_CONTRACT_V1.json"
    TRACK = SEM / "NURION_ADAPTATION_ENGINE_TRACK_V1.json"

    # Build/refresh fixtures into FIX (works in extracted + monorepo)
    os.environ["NURION_ADAPT01_FIXTURE_DIR"] = str(FIX)
    os.environ["NURION_ADAPT01_REPO_ROOT"] = str(REPO)
    from tools.build_adapt01_fixtures import main as build_fix

    build_fix()

    pos = FIX / "positive_rigged_with_face.glb"
    miss = FIX / "body_compatible_missing_face.glb"
    renamed = FIX / "renamed_nonstandard_bones.glb"
    malformed = FIX / "malformed_not_glb.bin"
    fbx = FIX / "unsupported_fake.fbx"
    nomesh = FIX / "no_mesh.glb"

    r_pos = inspect_character(pos, character_id="fixture_positive_rigged")
    r_miss = inspect_character(miss, character_id="fixture_missing_face")
    r_ren = inspect_character(renamed, character_id="fixture_renamed_bones")
    r_mal = inspect_character(malformed, character_id="fixture_malformed")
    r_fbx = inspect_character(fbx, character_id="fixture_fbx_reserved")
    r_empty = inspect_character(nomesh, character_id="fixture_no_mesh")

    for name, rep in [
        ("ADAPT01_report_positive.json", r_pos),
        ("ADAPT01_report_missing_face.json", r_miss),
        ("ADAPT01_report_renamed.json", r_ren),
        ("ADAPT01_report_malformed.json", r_mal),
        ("ADAPT01_report_fbx.json", r_fbx),
        ("ADAPT01_report_no_mesh.json", r_empty),
    ]:
        (REP / name).write_text(json.dumps(rep, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    gates: dict[str, dict] = {}

    _ok(r_pos["sourceAsset"]["sha256"] == sha256_file(pos), "pos sha")
    _ok(len(r_pos["sourceAsset"]["sha256"]) == 64, "sha len")
    gates["AD1-G01"] = {
        "status": "PASS",
        "fixtureSha256": r_pos["sourceAsset"]["sha256"],
        "byteLength": r_pos["sourceAsset"]["byteLength"],
    }

    _ok(r_pos["parseStatus"] == "OK", "pos parse")
    _ok(r_mal["parseStatus"] == "FAILED", "mal parse fail")
    gates["AD1-G02"] = {"status": "PASS", "positive": "OK", "malformed": "FAILED"}

    _ok(r_pos["scene"]["nodeCount"] >= 10, "nodes")
    _ok(isinstance(r_pos["scene"]["nodes"], list), "node list")
    gates["AD1-G03"] = {"status": "PASS", "nodeCount": r_pos["scene"]["nodeCount"]}

    _ok(r_pos["meshes"]["count"] >= 1, "mesh")
    _ok(r_pos["skeleton"]["skinsDetected"] is True, "skin")
    gates["AD1-G04"] = {
        "status": "PASS",
        "meshes": r_pos["meshes"]["count"],
        "skins": r_pos["skeleton"]["skinCount"],
    }

    _ok(r_pos["skeleton"]["jointCount"] >= 8, "joints")
    _ok(r_pos["skeleton"]["hierarchyEdgeCount"] >= 1, "edges")
    gates["AD1-G05"] = {
        "status": "PASS",
        "jointCount": r_pos["skeleton"]["jointCount"],
        "edges": r_pos["skeleton"]["hierarchyEdgeCount"],
    }

    c_ren = r_ren["semanticBoneCandidates"]["candidates"]
    _ok(c_ren["pelvis"]["status"] in ("DETECTED", "AMBIGUOUS"), "ren pelvis")
    _ok(c_ren["head"]["status"] in ("DETECTED", "AMBIGUOUS"), "ren head")
    _ok(c_ren["pelvis"]["selected"]["observedSourceNodeName"] == "HipBone", "preserve name")
    _ok(c_ren["head"]["selected"]["observedSourceNodeName"] == "Cranium", "preserve cranium")
    c_pos = r_pos["semanticBoneCandidates"]["candidates"]
    _ok(c_pos["pelvis"]["status"] == "DETECTED", "pos hips")
    _ok(c_pos["head"]["status"] == "DETECTED", "pos head")
    gates["AD1-G06"] = {
        "status": "PASS",
        "renamedPelvis": c_ren["pelvis"]["selected"]["observedSourceNodeName"],
        "renamedHead": c_ren["head"]["selected"]["observedSourceNodeName"],
        "policy": r_ren["semanticBoneCandidates"]["detectionPolicy"],
    }

    _ok(r_pos["faceCapabilities"]["blendshapesDetected"] is True, "blend pos")
    _ok(r_miss["expressionCapabilities"]["blendshapeCount"] == 0, "miss blend 0")
    gates["AD1-G07"] = {
        "status": "PASS",
        "positiveBlendshapes": r_pos["expressionCapabilities"]["blendshapeCount"],
        "missingFaceBlendshapes": r_miss["expressionCapabilities"]["blendshapeCount"],
    }

    _ok(r_pos["eyeCapabilities"]["leftEyeBone"]["status"] == "DETECTED", "eyeL")
    _ok(r_pos["jawCapabilities"]["bone"]["status"] == "DETECTED", "jaw")
    _ok(r_miss["eyeCapabilities"]["leftEyeBone"]["status"] == "NOT_DETECTED", "miss eye")
    gates["AD1-G08"] = {"status": "PASS", "positiveEyesJaw": True, "missingFaceNoEyes": True}

    _ok(r_pos["expressionCapabilities"]["blendshapeCount"] >= 10, "morphs")
    gates["AD1-G09"] = {
        "status": "PASS",
        "blendshapeCount": r_pos["expressionCapabilities"]["blendshapeCount"],
    }

    _ok(r_pos["animationCapabilities"]["clipCount"] >= 1, "anim")
    gates["AD1-G10"] = {
        "status": "PASS",
        "clipCount": r_pos["animationCapabilities"]["clipCount"],
    }

    _ok(r_pos["axisAndScale"]["status"] == "OBSERVED", "axis")
    _ok(r_pos["axisAndScale"]["upAxis"] in ("Y", "NOT_DECLARED"), "up")
    gates["AD1-G11"] = {"status": "PASS", "upAxis": r_pos["axisAndScale"]["upAxis"]}

    for p in (pos, miss, renamed, malformed, fbx, nomesh):
        before = p.read_bytes()
        inspect_character(p, character_id="preserve_check")
        after = p.read_bytes()
        _ok(before == after, f"bytes changed: {p.name}")
    gates["AD1-G12"] = {"status": "PASS", "sourceBytesUnchanged": True, "autoRepair": "DENY"}

    cls_pos = r_pos["adaptationClassification"]["adaptationClass"]
    cls_miss = r_miss["adaptationClassification"]["adaptationClass"]
    cls_mal = r_mal["adaptationClassification"]["adaptationClass"]
    cls_empty = r_empty["adaptationClassification"]["adaptationClass"]
    _ok(cls_pos in ("CLASS_A", "CLASS_B"), f"pos class {cls_pos}")
    _ok(cls_miss in ("CLASS_B", "CLASS_C"), f"miss class {cls_miss}")
    _ok(cls_mal == "BLOCKED", "mal blocked")
    _ok(cls_empty == "BLOCKED", "empty blocked")
    _ok(r_fbx["adaptationClassification"]["adaptationClass"] == "BLOCKED", "fbx blocked")
    cls_ren = r_ren["adaptationClassification"]["adaptationClass"]
    _ok(cls_ren in ("CLASS_A", "CLASS_B", "CLASS_C"), f"ren class {cls_ren}")
    gates["AD1-G13"] = {
        "status": "PASS",
        "positive": cls_pos,
        "missingFace": cls_miss,
        "renamed": cls_ren,
        "malformed": cls_mal,
        "noMesh": cls_empty,
        "fbx": "BLOCKED",
    }

    _ok(any(i.get("code") == "PARSE_FAILURE" for i in r_mal["issues"]), "parse issue")
    _ok(any(i.get("code") == "FORMAT_RESERVED_NOT_IMPLEMENTED" for i in r_fbx["issues"]), "fbx issue")
    _ok(any(i.get("code") == "NO_USABLE_MESH" for i in r_empty["issues"]), "nomesh issue")
    gates["AD1-G14"] = {"status": "PASS", "failClosed": True, "autoRepair": "DENY"}

    r1 = inspect_character(pos, character_id="fixture_positive_rigged")
    r2 = inspect_character(pos, character_id="fixture_positive_rigged")
    _ok(r1["reportCanonicalSha256"] == r2["reportCanonicalSha256"], "digest repeat")
    _ok(r1["adaptationClassification"] == r2["adaptationClassification"], "class repeat")
    gates["AD1-G15"] = {
        "status": "PASS",
        "reportCanonicalSha256": r1["reportCanonicalSha256"],
        "identical": True,
    }

    gates["AD1-G16"] = {
        "status": "HUMAN_FINAL_ONLY",
        "agentMayNotPass": True,
        "note": "Human auditor only may declare ADAPT-01 CLOSED / PASS",
    }

    # V1 mutation check — live verify only when monorepo artifacts present.
    # Extracted audit ZIP must not require PRODUCT runtime modules or V1 payload files.
    p06_baseline = REPO / "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_V1.json"
    # In extracted mode REPO is .../repo without working tree — also check monorepo via env
    if EXTRACTED:
        mono = Path(os.environ.get("NURION_REPO_ROOT", ""))
        if mono.is_dir():
            p06_baseline = mono / "fast_track/working/meshy_silver_starlight/semantic/NURION_PRODUCT06_PRODUCT_INTEGRATION_RELEASE_BASELINE_V1.json"
            p06_zip = mono / "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-06_release_baseline_proof.zip"
        else:
            p06_zip = Path("__absent__")
    else:
        p06_zip = REPO / "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-06_release_baseline_proof.zip"

    baseline_obs = None
    zip_obs = None
    verify_mode = "DECLARED_ANCHORS_ONLY"
    if p06_baseline.is_file():
        baseline_obs = canonical_json_sha256(json.loads(p06_baseline.read_text(encoding="utf-8")))
        _ok(baseline_obs == V1_P06_BASELINE, "V1 baseline mutated")
        verify_mode = "LIVE_CANONICAL_VERIFY"
    if p06_zip.is_file():
        zip_obs = sha256_file(p06_zip)
        _ok(zip_obs == V1_P06_ZIP, "V1 zip mutated")
        verify_mode = "LIVE_CANONICAL_VERIFY"

    v1_mutation = {
        "NURION_CHARACTER_PRODUCT_PIPELINE_V1": "CLOSED / PASS / CONSUME ONLY — untouched",
        "canonicalReleaseDigest_declared": V1_RELEASE_DIGEST,
        "product06BaselineCanonicalSha_declared": V1_P06_BASELINE,
        "product06ZipSha_declared": V1_P06_ZIP,
        "product06BaselineCanonicalSha_observed": baseline_obs,
        "product06ZipSha_observed": zip_obs,
        "verifyMode": verify_mode,
        "mutation": "NONE",
        "adapt02Started": False,
        "product07": "DOES NOT EXIST",
        "noProductRuntimeImport": True,
    }

    impl_files = [
        "fast_track/adaptation/__init__.py",
        "fast_track/adaptation/audit_paths.py",
        "fast_track/adaptation/glb_io.py",
        "fast_track/adaptation/semantic_candidates.py",
        "fast_track/adaptation/classifier.py",
        "fast_track/adaptation/inspector.py",
        "tools/build_adapt01_fixtures.py",
        "tools/run_adapt01_inspection_proof.py",
        "tools/pack_adapt01_inspection_proof_zip.py",
        "tools/run_adapt01_independent_proof.py",
    ]
    impl_hashes = {}
    for rel in impl_files:
        p = REPO / rel
        if p.exists():
            impl_hashes[rel] = sha256_file(p)
    # semantic contracts may live under package SEM
    if CONTRACT.exists():
        impl_hashes["semantic/NURION_ADAPT01_CHARACTER_INTAKE_INSPECTION_CONTRACT_V1.json"] = sha256_file(CONTRACT)
    if TRACK.exists():
        impl_hashes["semantic/NURION_ADAPTATION_ENGINE_TRACK_V1.json"] = sha256_file(TRACK)

    fixture_hashes = json.loads((FIX / "FIXTURE_MANIFEST.json").read_text(encoding="utf-8"))

    summary = {
        "schema": "NURION_ADAPT01_PROOF_RECEIPT_V1",
        "revision": "R1",
        "track": "NURION_CHARACTER_ADAPTATION_ENGINE_V1",
        "stage": "ADAPT-01",
        "executionMode": r["mode"],
        "agentStatus": "READY_FOR_HUMAN_AUDIT",
        "pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "ADAPT-01_CLOSED_PASS": "DENY_AGENT",
        "ADAPT-02": "NOT_STARTED",
        "gates": gates,
        "criticalGates": {
            "AD1-G02": gates["AD1-G02"]["status"],
            "AD1-G05": gates["AD1-G05"]["status"],
            "AD1-G06": gates["AD1-G06"]["status"],
            "AD1-G12": gates["AD1-G12"]["status"],
            "AD1-G14": gates["AD1-G14"]["status"],
            "AD1-G15": gates["AD1-G15"]["status"],
        },
        "automatedGatePassCount": sum(
            1 for k, g in gates.items() if k != "AD1-G16" and g.get("status") == "PASS"
        ),
        "automatedGateTotal": 15,
        "fixtureHashes": fixture_hashes,
        "implementationHashes": impl_hashes,
        "nurionV1Mutation": v1_mutation,
        "contractSha256": sha256_file(CONTRACT) if CONTRACT.exists() else None,
        "trackSha256": sha256_file(TRACK) if TRACK.exists() else None,
        "classificationSamples": {
            "positive": r_pos["adaptationClassification"],
            "missingFace": r_miss["adaptationClassification"],
            "renamed": r_ren["adaptationClassification"],
            "malformed": r_mal["adaptationClassification"],
        },
        "digestSemantics": {
            "payloadCanonicalDigest": "hash of sealed payload bytes BEFORE zip (see packaging)",
            "finalAuditZipSha256": "EXTERNAL_ONLY — written beside ZIP after seal; never embedded as self-hash inside ZIP",
            "r0MismatchExplanation": (
                "R0 READY receipt embedded a prior ZIP SHA (e3a7…) while the submitted ZIP was "
                "161676… because READY was updated after an earlier pack then re-packed, "
                "creating impossible self-referential provenance. R1 forbids embedding final ZIP SHA inside the ZIP."
            ),
        },
    }
    _ok(summary["automatedGatePassCount"] == 15, "not all automated gates pass")
    _write(EV, "NURION-ADAPT-01_inspection_proof_receipt.json", summary)
    _write(EV, "NURION-ADAPT-01_gate_matrix.json", {"gates": gates, "critical": summary["criticalGates"]})
    _write(EV, "NURION-ADAPT-01_nurion_v1_mutation_none.json", v1_mutation)
    return summary


def main() -> int:
    try:
        summary = run_all()
        print(
            json.dumps(
                {
                    "ok": True,
                    "revision": "R1",
                    "executionMode": summary["executionMode"],
                    "agentStatus": summary["agentStatus"],
                    "automatedGates": f"{summary['automatedGatePassCount']}/15 PASS",
                    "AD1-G16": "HUMAN_FINAL_ONLY",
                    "nurionV1Mutation": "NONE",
                    "ADAPT-02": "NOT_STARTED",
                    "pass": "NOT_DECLARED",
                },
                indent=2,
            )
        )
        return 0
    except Exception as e:
        print(json.dumps({"ok": False, "error": str(e), "trace": traceback.format_exc()}, indent=2))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
