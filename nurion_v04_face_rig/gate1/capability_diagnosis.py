"""v0.4 Gate 1 orchestrator — Face Asset Capability Diagnosis (mutation = 0)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .mesh_topology import (
    classify_face_body_topology,
    classify_oral_geometry,
    head_weight_linkage,
    invent_shape_keys,
    list_character_meshes,
)
from .mouth_boundary import probe_mouth_boundary
from .parameters import GATE1_PARAMETERS, V03_RC1_SHA256, parameter_hash
from .rig_inventory import invent_face_rig
from .viseme_eligibility import evaluate_viseme_eligibility


def _sha_json(doc: dict) -> str:
    payload = json.dumps(doc, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_v03_unchanged(root: Path) -> Dict:
    pkg = Path(root) / "dist/v0.3/universal_eye/gate7a/package" / "NURION_Universal_Eye_Calibration_v0.3.0-rc.1.zip"
    if not pkg.exists():
        return {"ok": False, "sha256": "", "expected": V03_RC1_SHA256, "notes": ["v0.3 RC.1 missing"]}
    h = hashlib.sha256()
    with pkg.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    digest = h.hexdigest()
    return {
        "ok": digest == V03_RC1_SHA256,
        "sha256": digest,
        "expected": V03_RC1_SHA256,
        "notes": [] if digest == V03_RC1_SHA256 else ["v0.3 hash changed — DENY"],
    }


@dataclass
class Gate1Diagnosis:
    role: str
    asset: str
    capability: Dict
    topology: Dict
    rig: Dict
    viseme: Dict
    gates: Dict
    verdict: str
    notes: List[str] = field(default_factory=list)
    parameter_hash: str = ""
    profile_stable: Dict = field(default_factory=dict)

    def artifacts(self) -> Dict[str, dict]:
        return {
            "FACE_ASSET_CAPABILITY_PROFILE.json": self.capability,
            "FACE_TOPOLOGY_REPORT.json": self.topology,
            "FACE_RIG_INVENTORY.json": self.rig,
            "VISEME_ELIGIBILITY_REPORT.json": self.viseme,
        }


def _stable_slice(cap: dict, topo: dict, rig: dict, vis: dict) -> dict:
    return {
        "faceBodyTopology": topo.get("faceBodyTopology"),
        "faceRegion": topo.get("faceRegion"),
        "existingRigClass": rig.get("existingRigClass"),
        "jawLipCheekBrow": rig.get("jawLipCheekBrow"),
        "shapeKeyCount": (cap.get("shapeKeys") or {}).get("count"),
        "mouthBoundary": (cap.get("mouth") or {}).get("mouthBoundary"),
        "openMouthDeformDensity": (cap.get("mouth") or {}).get("openMouthDeformDensity"),
        "teethClass": ((cap.get("oral") or {}).get("teeth") or {}).get("class"),
        "tongueClass": ((cap.get("oral") or {}).get("tongue") or {}).get("class"),
        "headParent": (cap.get("weights") or {}).get("headParent"),
        "visemePath": vis.get("visemePath"),
        "parameterHash": parameter_hash(),
    }


def diagnose_once(*, mesh_name: str = "", root: Optional[Path] = None) -> Dict:
    """Single read-only diagnosis pass. Does not create rigs or mutate meshes."""
    from nurion_universal_eye.gate1.universal_face_basis import build_universal_face_basis

    root = Path(root) if root else Path(__file__).resolve().parents[2]
    basis = build_universal_face_basis(mesh_name=mesh_name or "")
    mesh = None
    import bpy

    meshes = list_character_meshes()
    for m in meshes:
        if m.name == basis.mesh_name:
            mesh = m
            break
    if mesh is None:
        mesh = bpy.data.objects.get(basis.mesh_name)
    if mesh is None or mesh.type != "MESH":
        raise RuntimeError("Character mesh unresolved")

    axes = basis.axes
    hh = float(axes.head_height)
    topology = classify_face_body_topology(mesh, axes, hh)
    shape_keys = invent_shape_keys(mesh)
    oral = classify_oral_geometry(mesh, axes, hh, GATE1_PARAMETERS["meshNameHints"])
    rig = invent_face_rig()
    head_bones = [b["bone"] for b in rig.get("bones", {}).get("head", [])]
    weights = head_weight_linkage(mesh, head_bones)
    mouth = probe_mouth_boundary(mesh, axes, hh)
    viseme = evaluate_viseme_eligibility(
        rig=rig, shape_keys=shape_keys, mouth=mouth, oral=oral, topology=topology, weights=weights
    )

    eu_vals = [float(er.eye_unit) for er in (basis.eye_regions or {}).values() if er.eye_unit]
    eye_unit = (sum(eu_vals) / len(eu_vals)) if eu_vals else None

    capability = {
        "schema": "NURION_FACE_ASSET_CAPABILITY_PROFILE",
        "version": GATE1_PARAMETERS["version"],
        "meshName": mesh.name,
        "faceBasisMesh": basis.mesh_name,
        "eyeUnit": eye_unit,
        "headHeight": hh,
        "topology": {
            "faceBodyTopology": topology.get("faceBodyTopology"),
            "faceRegion": topology.get("faceRegion"),
            "meshCount": topology.get("meshCount"),
        },
        "existingFaceBones": rig.get("existingFaceBones"),
        "jawLipCheekBrowBones": rig.get("jawLipCheekBrow"),
        "shapeKeys": shape_keys,
        "oral": oral,
        "mouth": mouth,
        "weights": weights,
        "visemePath": viseme.get("visemePath"),
        "characterMutation": 0,
        "createFaceRig": False,
        "createLipSync": False,
        "parameterHash": parameter_hash(),
    }
    return {
        "capability": capability,
        "topology": {
            "schema": "NURION_FACE_TOPOLOGY_REPORT",
            **topology,
            "mouth": mouth,
            "oral": oral,
            "weights": weights,
            "parameterHash": parameter_hash(),
        },
        "rig": {
            "schema": "NURION_FACE_RIG_INVENTORY",
            **rig,
            "shapeKeys": shape_keys,
            "parameterHash": parameter_hash(),
        },
        "viseme": {
            "schema": "NURION_VISEME_ELIGIBILITY_REPORT",
            **viseme,
            "parameterHash": parameter_hash(),
        },
    }


def run_gate1_diagnosis(
    *,
    root: Optional[Path] = None,
    role: str = "DEVELOPMENT",
    asset: str = "tennis",
    mesh_name: str = "",
    runs: int = 3,
    clean_import_cb=None,
) -> Gate1Diagnosis:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    notes: List[str] = []
    v03 = verify_v03_unchanged(root)
    if not v03["ok"]:
        notes.extend(v03["notes"])

    results = []
    for i in range(int(runs)):
        if clean_import_cb is not None:
            clean_import_cb()
        results.append(diagnose_once(mesh_name=mesh_name, root=root))

    stables = [
        _stable_slice(r["capability"], r["topology"], r["rig"], r["viseme"]) for r in results
    ]
    if len(stables) >= 3:
        h0 = _sha_json(stables[0])
        det_ok = all(_sha_json(s) == h0 for s in stables[1:3])
        determinism = "PASS" if det_ok else "FAIL"
        if not det_ok:
            notes.append("3x diagnosis determinism mismatch")
    else:
        determinism = "FAIL"
        notes.append("insufficient determinism runs")

    last = results[-1]
    cap, topo, rig, vis = last["capability"], last["topology"], last["rig"], last["viseme"]

    gates = {
        "FACE_REGION": topo.get("faceRegion", "FAIL"),
        "HEAD_PARENT": (cap.get("weights") or {}).get("headParent", "FAIL"),
        "MOUTH_BOUNDARY": (cap.get("mouth") or {}).get("mouthBoundary", "FAIL"),
        "EXISTING_RIG": "CLASSIFIED" if rig.get("status") == "CLASSIFIED" else "FAIL",
        "SHAPE_KEYS": "INVENTORIED" if (cap.get("shapeKeys") or {}).get("status") == "INVENTORIED" else "FAIL",
        "TEETH_TONGUE": "CLASSIFIED" if (cap.get("oral") or {}).get("status") == "CLASSIFIED" else "FAIL",
        "VISEME_PATH": "SELECTED" if vis.get("status") == "SELECTED" else "FAIL",
        "CHARACTER_MUTATION": 0,
        "V03_HASH": "UNCHANGED" if v03["ok"] else "CHANGED",
        "DETERMINISM_3X": determinism,
    }

    hard = [
        "FACE_REGION",
        "HEAD_PARENT",
        "MOUTH_BOUNDARY",
        "EXISTING_RIG",
        "SHAPE_KEYS",
        "TEETH_TONGUE",
        "VISEME_PATH",
        "DETERMINISM_3X",
    ]
    fails = [k for k in hard if gates.get(k) not in ("RESOLVED", "CLASSIFIED", "INVENTORIED", "SELECTED", "PASS")]
    if gates["CHARACTER_MUTATION"] != 0:
        fails.append("CHARACTER_MUTATION")
    if gates["V03_HASH"] != "UNCHANGED":
        fails.append("V03_HASH")

    verdict = "PASS" if not fails else "FAIL"
    if fails:
        notes.append(f"fails={fails}")

    # Enrich capability with gate summary
    cap = dict(cap)
    cap["gates"] = gates
    cap["verdict"] = verdict
    cap["role"] = role
    cap["asset"] = asset
    cap["v03Rc1Sha256"] = v03["sha256"]
    cap["determinism3x"] = determinism
    cap["stableProfileSha256"] = _sha_json(stables[0]) if stables else ""

    topo = dict(topo)
    topo["gates"] = {"FACE_REGION": gates["FACE_REGION"], "MOUTH_BOUNDARY": gates["MOUTH_BOUNDARY"]}
    rig = dict(rig)
    rig["existingRig"] = gates["EXISTING_RIG"]
    vis = dict(vis)
    vis["visemePathGate"] = gates["VISEME_PATH"]

    return Gate1Diagnosis(
        role=role,
        asset=asset,
        capability=cap,
        topology=topo,
        rig=rig,
        viseme=vis,
        gates=gates,
        verdict=verdict,
        notes=notes,
        parameter_hash=parameter_hash(),
        profile_stable=stables[0] if stables else {},
    )
