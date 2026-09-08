"""Gate 10 holdout asset eligibility."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .parameters import (
    BANNED_MODEL_SHA256,
    BANNED_NAME_SUBSTRINGS,
    BANNED_ZIP_SHA256,
    HOLDOUT_ZIP_SHA256,
    SIBLING_ZIP_SHA256,
)


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
    models = sorted(list(dest.rglob("*.fbx")) + list(dest.rglob("*.FBX")))
    textures = sorted(
        list(dest.rglob("*.png"))
        + list(dest.rglob("*.jpg"))
        + list(dest.rglob("*.jpeg"))
        + list(dest.rglob("*.tga"))
    )
    return {
        "extractDir": str(dest).replace("\\", "/"),
        "modelPaths": [str(p).replace("\\", "/") for p in models],
        "textureCount": len(textures),
        "zipSha256": sha256_file(zip_path),
    }


def pick_formal_bow_model(extract_info: Dict) -> Optional[Path]:
    paths = [Path(p) for p in extract_info.get("modelPaths") or []]
    if not paths:
        return None

    def score(p: Path) -> Tuple[int, str]:
        n = p.name.lower()
        s = 0
        if "formal_bow" in n or "formalbow" in n:
            s += 200
        if "withskin" in n or "with_skin" in n:
            s += 50
        if "biped" in n:
            s += 20
        if "bow" in n:
            s += 10
        return (-s, str(p).lower())

    return sorted(paths, key=score)[0]


def pre_import_eligibility(zip_path: Path, extract_info: Dict, model_path: Optional[Path]) -> Dict:
    notes: List[str] = []
    gates: Dict[str, str] = {}
    zip_sha = extract_info.get("zipSha256") or sha256_file(zip_path)

    gates["ZIP_PRESENT"] = "PASS" if Path(zip_path).exists() else "FAIL"
    gates["ZIP_SHA_MATCH"] = "PASS" if zip_sha == HOLDOUT_ZIP_SHA256 else "FAIL"
    if gates["ZIP_SHA_MATCH"] == "FAIL":
        notes.append(f"holdout ZIP SHA mismatch: {zip_sha}")

    if zip_sha in SIBLING_ZIP_SHA256:
        gates["SIBLING_ZIP_MIX"] = "FAIL"
        notes.append(f"sibling ZIP mixed into official holdout: {SIBLING_ZIP_SHA256[zip_sha]}")
    else:
        gates["SIBLING_ZIP_MIX"] = "PASS"

    banned_zip = BANNED_ZIP_SHA256.get(zip_sha)
    gates["UNUSED_ZIP"] = "FAIL" if banned_zip else "PASS"
    if banned_zip:
        notes.append(f"banned prior ZIP: {banned_zip}")

    gates["MODEL_PRESENT"] = "PASS" if model_path is not None else "FAIL"
    model_sha = sha256_file(model_path) if model_path else ""
    banned_model = BANNED_MODEL_SHA256.get(model_sha)
    name_hit = None
    if model_path is not None:
        low = model_path.name.lower()
        for sub in BANNED_NAME_SUBSTRINGS:
            if sub in low:
                name_hit = sub
                break
    # Lightning Pilot / aibaeby names are allowed
    gates["UNUSED_MODEL"] = "FAIL" if banned_model or name_hit else "PASS"
    if banned_model:
        notes.append(f"banned prior model: {banned_model}")
    if name_hit:
        notes.append(f"banned name substring: {name_hit}")

    formal = bool(model_path and ("formal_bow" in model_path.name.lower() or "formalbow" in model_path.name.lower()))
    gates["FORMAL_BOW_WITHSKIN"] = "PASS" if formal and model_path and "withskin" in model_path.name.lower() else "FAIL"
    if gates["FORMAL_BOW_WITHSKIN"] == "FAIL":
        notes.append("Formal Bow withSkin FBX required")

    gates["TEXTURES_PRESENT"] = "PASS" if int(extract_info.get("textureCount") or 0) > 0 else "FAIL"
    if gates["TEXTURES_PRESENT"] == "FAIL":
        notes.append("textures missing — original Meshy package required")

    fails = [k for k, v in gates.items() if v == "FAIL"]
    return {
        "gates": gates,
        "fails": fails,
        "ok": not fails,
        "notes": notes,
        "zipSha256": zip_sha,
        "modelSha256": model_sha,
        "modelPath": str(model_path).replace("\\", "/") if model_path else "",
    }
