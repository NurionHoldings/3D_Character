"""Holdout asset eligibility — unused Meshy humanoid ZIP, face/eyes evaluable."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import BANNED_MODEL_SHA256


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_holdout_zip(zip_path: Path, dest: Path) -> Dict:
    """Extract original Meshy ZIP as-is (read-only source; work copy under dest)."""
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
    # Prefer FBX over GLB; prefer names containing withSkin / APose / TPose / Rest
    def score(p: Path) -> Tuple[int, str]:
        n = p.name.lower()
        s = 0
        if p.suffix.lower() == ".fbx":
            s += 100
        if "withskin" in n or "with_skin" in n:
            s += 50
        if "walking" in n:
            s += 10  # acceptable; REST forced later
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
    gates["UNUSED_ASSET"] = "FAIL" if banned else "PASS"
    if banned:
        notes.append(f"Banned prior asset: {banned}")

    gates["TEXTURES_PRESENT"] = "PASS" if int(extract_info.get("textureCount") or 0) > 0 else "FAIL"
    if gates["TEXTURES_PRESENT"] == "FAIL":
        notes.append("No textures found in ZIP")

    hard = ["ZIP_PRESENT", "MODEL_PRESENT", "UNUSED_ASSET"]
    # Textures soft-warn for eligibility hard fail only if zero models; texture absence → still try but note
    fails = [k for k in hard if gates.get(k) == "FAIL"]
    # Texture missing alone → ASSET_INELIGIBLE (user required textures in original ZIP)
    if gates["TEXTURES_PRESENT"] == "FAIL":
        fails.append("TEXTURES_PRESENT")

    return {
        "gates": gates,
        "notes": notes,
        "modelSha256": model_sha,
        "modelPath": str(model_path).replace("\\", "/") if model_path else None,
        "verdict": "PASS" if not fails else "ASSET_INELIGIBLE",
        "fails": fails,
    }


def scene_structural_eligibility() -> Dict:
    """After clean import + REST: armature + skinned mesh required."""
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


def face_eye_eligibility(mesh_name: str = "") -> Dict:
    """Face/eyes identifiable via frozen Gate1 — failure ⇒ ASSET_INELIGIBLE."""
    from ..gate1.face_basis_validator import validate_face_basis
    from ..gate1.universal_face_basis import build_universal_face_basis

    notes: List[str] = []
    try:
        basis = build_universal_face_basis(mesh_name=mesh_name or "")
    except Exception as exc:  # noqa: BLE001
        return {
            "gates": {"FACE_BASIS_BUILD": "FAIL"},
            "notes": [f"Face basis build failed: {exc}"],
            "verdict": "ASSET_INELIGIBLE",
            "fails": ["FACE_BASIS_BUILD"],
        }

    report = validate_face_basis(basis, determinism_profiles=None)
    # For holdout eligibility we care about face/eyes evaluability, not full Gate1 lock re-cert
    critical = [
        "HEAD_LOCAL_AXES_STABLE",
        "FACE_FORWARD_RESOLVED",
        "EYE_REGIONS_RESOLVED",
    ]
    gates = {k: report.get("gates", {}).get(k, "FAIL") for k in critical}
    fails = [k for k, v in gates.items() if v != "PASS"]
    if fails:
        notes.append("Face or both eyes not evaluable")
    return {
        "gates": gates,
        "notes": notes,
        "faceReportVerdict": report.get("verdict"),
        "meshName": basis.mesh_name,
        "verdict": "PASS" if not fails else "ASSET_INELIGIBLE",
        "fails": fails,
    }
