"""Gate 9 reinstall smoke: install RC ZIP, rebuild Formal Bow + face sync, reinstall, compare."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .parameters import (
    ADDON_MODULE,
    GATE9_PARAMETERS,
    INHERITED_LIMITATIONS,
    V04_RC1_SHA256,
    parameter_hash,
)
from .packaging import sha256_file, verify_frozen_hashes


def _sha_json(doc) -> str:
    return hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


@dataclass
class Gate9Result:
    report: Dict
    validation: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    package_sha256: str = ""


def _addon_dir() -> Optional[Path]:
    import addon_utils

    for mod in addon_utils.modules():
        if getattr(mod, "__name__", "") == ADDON_MODULE:
            return Path(mod.__file__).resolve().parent
    return None


def _install_enable(zip_path: Path) -> Dict:
    import bpy

    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        try:
            bpy.ops.preferences.addon_disable(module=ADDON_MODULE)
        except Exception:
            pass
    # Remove prior install folder if present
    scripts = Path(bpy.utils.user_resource("SCRIPTS", path="addons"))
    prior = scripts / ADDON_MODULE
    if prior.exists():
        shutil.rmtree(prior, ignore_errors=True)

    bpy.ops.preferences.addon_install(filepath=str(zip_path), overwrite=True)
    bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
    enabled = ADDON_MODULE in bpy.context.preferences.addons
    adir = _addon_dir()
    return {"enabled": enabled, "addonDir": str(adir) if adir else "", "scriptsAddons": str(scripts)}


def _disable_remove() -> None:
    import addon_utils
    import bpy

    try:
        addon_utils.disable(ADDON_MODULE, default_set=True)
    except Exception:
        pass
    prefs = bpy.context.preferences
    if ADDON_MODULE in prefs.addons:
        try:
            del prefs.addons[ADDON_MODULE]
        except Exception:
            pass
    # Background mode: avoid addon_remove (needs UI area); delete install dir directly
    scripts = Path(bpy.utils.user_resource("SCRIPTS", path="addons"))
    prior = scripts / ADDON_MODULE
    if prior.exists():
        shutil.rmtree(prior, ignore_errors=True)


def _clean_import(fbx: Path) -> None:
    import bpy

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=str(fbx), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()


def _run_smoke_session(
    *,
    zip_path: Path,
    workspace_root: Path,
    fbx_path: Path,
    mesh_name: str,
    runs: int,
) -> Dict:
    """Factory reset → install → enable → import FBX → N pipeline runs → fingerprint."""
    import bpy
    import importlib
    import sys

    bpy.ops.wm.read_factory_settings(use_empty=True)
    inst = _install_enable(zip_path)
    if not inst["enabled"]:
        raise RuntimeError("addon failed to enable")

    bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
    bpy.context.view_layer.update()

    adir = _addon_dir()
    if adir is None:
        raise RuntimeError("addon dir missing")
    sp = str(adir)
    if sp in sys.path:
        sys.path.remove(sp)
    sys.path.insert(0, sp)
    for key in list(sys.modules):
        if key.startswith(("nurion_v05_body_motion", "nurion_v04_face_rig", "nurion_universal_eye")):
            del sys.modules[key]

    from nurion_v05_body_motion.gate1.parameters import parameter_hash as g1
    from nurion_v05_body_motion.gate2.parameters import parameter_hash as g2
    from nurion_v05_body_motion.gate3.parameters import parameter_hash as g3
    from nurion_v05_body_motion.gate4.parameters import parameter_hash as g4
    from nurion_v05_body_motion.gate5.parameters import parameter_hash as g5
    from nurion_v05_body_motion.gate6.parameters import parameter_hash as g6
    from nurion_v05_body_motion.gate7.parameters import parameter_hash as g7
    from nurion_v05_body_motion.gate8.parameters import parameter_hash as g8
    from nurion_v05_body_motion.gate8.pipeline import run_clean_pipeline_once
    from nurion_v05_body_motion.gate9.parameters import (
        GATE1_FROZEN,
        GATE2_FROZEN,
        GATE3_FROZEN,
        GATE4_FROZEN,
        GATE5_FROZEN,
        GATE6_FROZEN,
        GATE7_FROZEN,
        GATE8_FROZEN,
    )

    hash_ok = (
        g1() == GATE1_FROZEN
        and g2() == GATE2_FROZEN
        and g3() == GATE3_FROZEN
        and g4() == GATE4_FROZEN
        and g5() == GATE5_FROZEN
        and g6() == GATE6_FROZEN
        and g7() == GATE7_FROZEN
        and g8() == GATE8_FROZEN
    )
    if not hash_ok:
        raise RuntimeError("installed addon Gate1–8 hashes drifted")

    results = []
    # First run uses already-imported scene; subsequent runs clean-import without removing addon
    for i in range(int(runs)):
        if i > 0:
            # Keep addon; only reload empty scene + FBX
            bpy.ops.wm.read_factory_settings(use_empty=True)
            # factory reset drops addon enable — re-enable without reinstall
            bpy.ops.preferences.addon_enable(module=ADDON_MODULE)
            for key in list(sys.modules):
                if key.startswith(("nurion_v05_body_motion", "nurion_v04_face_rig", "nurion_universal_eye")):
                    del sys.modules[key]
            sys.path.insert(0, sp)
            bpy.ops.import_scene.fbx(filepath=str(fbx_path), automatic_bone_orientation=True, use_anim=True)
            bpy.context.view_layer.update()
            # re-import modules
            from nurion_v05_body_motion.gate8.pipeline import run_clean_pipeline_once as _run

            results.append(
                _run(fbx_path=fbx_path, mesh_name=mesh_name, root=workspace_root, seed_mode=True)
            )
        else:
            results.append(
                run_clean_pipeline_once(
                    fbx_path=fbx_path, mesh_name=mesh_name, root=workspace_root, seed_mode=True
                )
            )

    hashes = [r["determinismHash"] for r in results]
    det = "PASS" if hashes and all(h == hashes[0] for h in hashes) else "FAIL"
    last = results[-1]
    fp = last["fingerprint"]
    objects_ok = all(
        bpy.data.objects.get(n) is not None
        for n in (
            "NURION_BodyRigClone",
            "NURION_BodyMotionCandidate",
            "NURION_SyncFacialPerformance",
            "NURION_EyeDome.L",
        )
    )
    return {
        "install": inst,
        "hashOk": hash_ok,
        "determinism": det,
        "determinismHashes": hashes,
        "fingerprint": fp,
        "determinismHash": hashes[0] if hashes else "",
        "objectsOk": objects_ok,
        "slidesFinal": fp.get("slidesFinal"),
        "maxDepthM": fp.get("maxDepthM"),
        "faceBindOk": fp.get("faceBindOk"),
        "speechWindow": fp.get("speechWindow"),
    }


def build_validation(
    *,
    frozen_ok: bool,
    v04_ok: bool,
    seed_ok: bool,
    install_ok: bool,
    reinstall_ok: bool,
    det_ok: bool,
    same_result: bool,
    param_change: int,
) -> Dict:
    gates = {
        "FROZEN_HASHES_G1_G8": "PASS" if frozen_ok else "FAIL",
        "INSTALL_ACTIVATE": "PASS" if install_ok else "FAIL",
        "REINSTALL": "PASS" if reinstall_ok else "FAIL",
        "FORMAL_BOW_REBUILD_SMOKE": "PASS" if install_ok and det_ok else "FAIL",
        "WORD_CONFIRM_FACE_SYNC_SMOKE": "PASS" if install_ok and det_ok else "FAIL",
        "REINSTALL_SAME_RESULT": "PASS" if same_result else "FAIL",
        "DETERMINISM": "PASS" if det_ok else "FAIL",
        "GATE1_8_PARAMETER_CHANGE": param_change,
        "SOURCE_V04_SEAL_MUTATION": 0 if (v04_ok and seed_ok) else 1,
        "MANUAL_CORRECTION": 0,
        "PARAMETER_TUNING": 0,
        "SUPPORTED_DOMAIN": "LIMITED",
        "SEALED": False,
        "PRODUCTION": "NO-GO",
        "REPACK": "DENY",
    }

    def ok(k, v):
        if k in (
            "FROZEN_HASHES_G1_G8",
            "INSTALL_ACTIVATE",
            "REINSTALL",
            "FORMAL_BOW_REBUILD_SMOKE",
            "WORD_CONFIRM_FACE_SYNC_SMOKE",
            "REINSTALL_SAME_RESULT",
            "DETERMINISM",
        ):
            return v == "PASS"
        if k == "SUPPORTED_DOMAIN":
            return v == "LIMITED"
        if k == "SEALED":
            return v is False
        if k == "PRODUCTION":
            return v == "NO-GO"
        if k == "REPACK":
            return v == "DENY"
        return v == 0

    fails = [k for k, v in gates.items() if not ok(k, v)]
    limitations = list(INHERITED_LIMITATIONS) + ["LIMITED_DOMAIN", "RC_NOT_SEALED", "HOLDOUT_WAITING"]
    verdict = "FAIL" if fails else "PASS_WITH_LIMITATIONS"
    return {
        "schema": "NURION_V05_GATE9_VALIDATION",
        "gates": gates,
        "fails": fails,
        "limitations": sorted(set(limitations)),
        "verdict": verdict,
        "parameterHash": parameter_hash(),
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
    }


def run_gate9_reinstall_smoke(
    *,
    zip_path: Path,
    fbx_path: Path,
    workspace_root: Path,
    mesh_name: str = "char1",
    runs: int = 3,
) -> Gate9Result:
    notes: List[str] = []
    workspace_root = Path(workspace_root)
    zip_path = Path(zip_path)
    fbx_path = Path(fbx_path)

    frozen = verify_frozen_hashes(workspace_root)
    if not frozen["ok"]:
        notes.append(f"frozen hash fail: {frozen['checks']}")

    rc1 = workspace_root / "dist/v0.4/gate8b/package/NURION_Native_Face_Rig_LipSync_v0.4.0-rc.1.zip"
    v04_ok = rc1.exists() and sha256_file(rc1) == V04_RC1_SHA256
    seed_ok = fbx_path.exists() and sha256_file(fbx_path) == GATE9_PARAMETERS["seedFbxSha256"]
    pkg_sha = sha256_file(zip_path) if zip_path.exists() else ""

    # Ensure zip does not contain excluded artifacts
    import zipfile

    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
    if any(n.lower().endswith(".fbx") for n in names):
        notes.append("FBX leaked in RC zip")
        seed_ok = False
    if any("NURION_Native_Face_Rig_LipSync" in n for n in names):
        notes.append("v0.4 package leaked in RC zip")
        v04_ok = False

    session1 = _run_smoke_session(
        zip_path=zip_path,
        workspace_root=workspace_root,
        fbx_path=fbx_path,
        mesh_name=mesh_name,
        runs=runs,
    )
    _disable_remove()
    session2 = _run_smoke_session(
        zip_path=zip_path,
        workspace_root=workspace_root,
        fbx_path=fbx_path,
        mesh_name=mesh_name,
        runs=runs,
    )

    # Post mutation checks
    v04_ok = v04_ok and sha256_file(rc1) == V04_RC1_SHA256
    seed_ok = seed_ok and sha256_file(fbx_path) == GATE9_PARAMETERS["seedFbxSha256"]
    pkg_sha_after = sha256_file(zip_path)
    if pkg_sha_after != pkg_sha:
        notes.append("RC ZIP mutated during smoke")

    same = session1["determinismHash"] == session2["determinismHash"] and session1["determinism"] == "PASS"
    det_ok = session1["determinism"] == "PASS" and session2["determinism"] == "PASS"
    install_ok = bool(session1.get("install", {}).get("enabled")) and session1.get("objectsOk") and session1.get(
        "faceBindOk"
    )
    reinstall_ok = bool(session2.get("install", {}).get("enabled")) and session2.get("objectsOk") and session2.get(
        "faceBindOk"
    )

    validation = build_validation(
        frozen_ok=frozen["ok"],
        v04_ok=v04_ok,
        seed_ok=seed_ok,
        install_ok=install_ok,
        reinstall_ok=reinstall_ok,
        det_ok=det_ok,
        same_result=same,
        param_change=0 if frozen["ok"] else 1,
    )

    report = {
        "schema": "NURION_V05_GATE9_REINSTALL_SMOKE_REPORT",
        "version": GATE9_PARAMETERS["version"],
        "parameterHash": parameter_hash(),
        "package": zip_path.name,
        "packageSha256": pkg_sha,
        "packageSha256After": pkg_sha_after,
        "repack": "DENY",
        "frozenHashes": frozen,
        "session1": {
            "determinism": session1["determinism"],
            "determinismHash": session1["determinismHash"],
            "slidesFinal": session1["slidesFinal"],
            "maxDepthM": session1["maxDepthM"],
            "speechWindow": session1["speechWindow"],
            "faceBindOk": session1["faceBindOk"],
        },
        "session2": {
            "determinism": session2["determinism"],
            "determinismHash": session2["determinismHash"],
            "slidesFinal": session2["slidesFinal"],
            "maxDepthM": session2["maxDepthM"],
            "speechWindow": session2["speechWindow"],
            "faceBindOk": session2["faceBindOk"],
        },
        "reinstallSameResult": same,
        "inheritedLimitations": INHERITED_LIMITATIONS,
        "supportedDomain": "LIMITED",
        "production": "NO-GO",
        "sealed": False,
        "holdout": "WAITING",
        "finalSeal": "HOLD",
        "notes": notes,
        "next": "FRESH_HOLDOUT",
    }
    return Gate9Result(
        report=report,
        validation=validation,
        verdict=validation["verdict"],
        notes=notes,
        parameter_hash=parameter_hash(),
        package_sha256=pkg_sha,
    )
