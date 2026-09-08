"""Gate 8C holdout asset eligibility."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import BANNED_MODEL_SHA256, BANNED_NAME_SUBSTRINGS


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_holdout_zip(zip_path: Path, dest: Path) -> Dict:
    zip_path = Path(zip_path)
    dest = Path(dest)
    if dest.exists():
        import shutil

        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(dest)
    models = sorted(
        list(dest.rglob("*.fbx")) + list(dest.rglob("*.FBX")) + list(dest.rglob("*.glb")) + list(dest.rglob("*.GLB"))
    )
    textures = sorted(
        list(dest.rglob("*.png"))
        + list(dest.rglob("*.jpg"))
        + list(dest.rglob("*.jpeg"))
        + list(dest.rglob("*.tga"))
        + list(dest.rglob("*.webp"))
    )
    return {
        "extractDir": str(dest).replace("\\", "/"),
        "modelPaths": [str(p).replace("\\", "/") for p in models],
        "textureCount": len(textures),
        "zipSha256": sha256_file(zip_path),
    }


def pick_primary_model(extract_info: Dict) -> Optional[Path]:
    paths = [Path(p) for p in extract_info.get("modelPaths") or []]
    if not paths:
        return None

    def score(p: Path) -> Tuple[int, str]:
        n = p.name.lower()
        s = 0
        if p.suffix.lower() == ".fbx":
            s += 100
        if "withskin" in n or "with_skin" in n:
            s += 50
        if "walking" in n:
            s += 10
        if any(k in n for k in ("apose", "a-pose", "tpose", "t-pose", "rest")):
            s += 30
        return (-s, str(p).lower())

    return sorted(paths, key=score)[0]


def pre_import_eligibility(zip_path: Path, extract_info: Dict, model_path: Optional[Path]) -> Dict:
    notes: List[str] = []
    gates: Dict[str, str] = {}

    gates["ZIP_PRESENT"] = "PASS" if Path(zip_path).exists() else "FAIL"
    gates["MODEL_PRESENT"] = "PASS" if model_path is not None else "FAIL"
    if model_path is None:
        notes.append("No FBX/GLB found in ZIP")

    model_sha = sha256_file(model_path) if model_path else ""
    banned = BANNED_MODEL_SHA256.get(model_sha)
    name_hit = None
    if model_path is not None:
        low = model_path.name.lower()
        for sub in BANNED_NAME_SUBSTRINGS:
            if sub in low:
                name_hit = sub
                break
    gates["UNUSED_ASSET"] = "FAIL" if banned or name_hit else "PASS"
    if banned:
        notes.append(f"Banned prior asset: {banned}")
    if name_hit:
        notes.append(f"Banned name substring: {name_hit}")

    gates["TEXTURES_PRESENT"] = "PASS" if int(extract_info.get("textureCount") or 0) > 0 else "FAIL"
    if gates["TEXTURES_PRESENT"] == "FAIL":
        notes.append("No textures found in ZIP — original Meshy texture package required")

    fails = [k for k in ("ZIP_PRESENT", "MODEL_PRESENT", "UNUSED_ASSET", "TEXTURES_PRESENT") if gates.get(k) == "FAIL"]
    return {
        "gates": gates,
        "notes": notes,
        "modelSha256": model_sha,
        "modelPath": str(model_path).replace("\\", "/") if model_path else None,
        "verdict": "PASS" if not fails else "ASSET_INELIGIBLE",
        "fails": fails,
    }


def scene_structural_eligibility() -> Dict:
    import bpy

    notes: List[str] = []
    gates: Dict[str, str] = {}
    arms = [o for o in bpy.data.objects if o.type == "ARMATURE"]
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    skinned = []
    for m in meshes:
        for mod in m.modifiers:
            if mod.type == "ARMATURE" and getattr(mod, "object", None) is not None:
                skinned.append(m.name)
                break
        if m.vertex_groups and m.parent and m.parent.type == "ARMATURE":
            if m.name not in skinned:
                skinned.append(m.name)

    gates["ARMATURE_PRESENT"] = "PASS" if arms else "FAIL"
    gates["MESH_PRESENT"] = "PASS" if meshes else "FAIL"
    gates["WITH_SKIN"] = "PASS" if skinned else "FAIL"
    if not arms:
        notes.append("No armature")
    if not skinned:
        notes.append("No skinned mesh detected")

    rest_ok = all(getattr(a.data, "pose_position", "REST") == "REST" for a in arms) if arms else False
    gates["REST_POSE_FORCED"] = "PASS" if rest_ok else "FAIL"

    fails = [k for k, v in gates.items() if v == "FAIL"]
    return {
        "gates": gates,
        "notes": notes,
        "armatureCount": len(arms),
        "meshCount": len(meshes),
        "skinnedMeshes": skinned,
        "verdict": "PASS" if not fails else "ASSET_INELIGIBLE",
        "fails": fails,
    }


def face_mouth_eligibility(mesh_name: str = "") -> Dict:
    """Face + mouth identifiable (v0.4 Gate1 capability). Eyes via sealed v0.3 basis."""
    from nurion_universal_eye.gate1.face_basis_validator import validate_face_basis
    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis
    from nurion_v04_face_rig.gate1.capability_diagnosis import diagnose_once

    notes: List[str] = []
    try:
        basis = build_universal_face_basis(mesh_name=mesh_name or "")
        face_rep = validate_face_basis(basis, determinism_profiles=None)
        cap = diagnose_once(mesh_name=mesh_name or "")
    except Exception as exc:  # noqa: BLE001
        return {
            "gates": {"FACE_BASIS_BUILD": "FAIL"},
            "notes": [f"Face/mouth eligibility failed: {exc}"],
            "verdict": "ASSET_INELIGIBLE",
            "fails": ["FACE_BASIS_BUILD"],
        }

    critical_eye = ["HEAD_LOCAL_AXES_STABLE", "FACE_FORWARD_RESOLVED", "EYE_REGIONS_RESOLVED"]
    gates = {k: face_rep.get("gates", {}).get(k, "FAIL") for k in critical_eye}
    mouth = (cap.get("capability") or {}).get("mouth") or {}
    dens_raw = mouth.get("openMouthDeformDensity")
    # Gate1 emits class strings: HIGH | MEDIUM | LOW | NONE (not numeric)
    dens_ok = False
    if isinstance(dens_raw, (int, float)):
        dens_ok = float(dens_raw) > 0.0
    else:
        dens_ok = str(dens_raw or "").upper() in ("HIGH", "MEDIUM", "LOW")
    gates["MOUTH_BOUNDARY"] = "PASS" if mouth.get("mouthBoundary") else "FAIL"
    gates["PERIORAL_DENSITY"] = "PASS" if dens_ok else "FAIL"
    if gates["MOUTH_BOUNDARY"] == "FAIL":
        notes.append("Mouth boundary not resolved")
    if gates["PERIORAL_DENSITY"] == "FAIL":
        notes.append(f"Insufficient peri-oral deform density signal: {dens_raw!r}")

    fails = [k for k, v in gates.items() if v != "PASS"]
    return {
        "gates": gates,
        "notes": notes,
        "meshName": basis.mesh_name,
        "visemePath": (cap.get("viseme") or {}).get("visemePath"),
        "mouth": mouth,
        "verdict": "PASS" if not fails else "ASSET_INELIGIBLE",
        "fails": fails,
    }
