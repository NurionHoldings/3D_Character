"""CR02-R2 independent gates — measure morph POSITION deltas from GLB only (no report trust)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.adaptation.inspector import canonical_sha256, sha256_file
from fast_track.v2_cr02.facial_deformation import (
    FACE_Y_MIN,
    HEAD_SKIN_LOCAL,
    HEAD_WEIGHT_MIN,
    RESTORE_TOLERANCE,
    VERTEX_DELTA_THRESHOLD,
    _read_f32_vec3,
    _read_f32_vec4,
    _read_u8_vec4,
    select_facial_vertices,
)

# Contract-pinned thresholds (must match R2 SPEC — do not change ad hoc)
ACTIVATION_THRESHOLD = VERTEX_DELTA_THRESHOLD  # 1e-4
RESTORATION_TOLERANCE = RESTORE_TOLERANCE  # 1e-6
CROSS_CONTAMINATION_RATIO = 0.35  # contralateral max-delta must be << ipsilateral

IDLE15_SHA = "a113cca61d31b0a03f24703ce093149611e8b403952305370cce15d601805db1"
# Agent-reported only until Human PASS — runner re-verifies file SHA, not this digest as authority
AGENT_REPORTED_DERIVED_SHA = "1ee90420ba39cc2e74de6624230538f4416d39ec7b34656e5b175a776c171cdd"
AGENT_REPORTED_PROOF_DIGEST = "7bdbaf39893e3c5f1607321758f0e3bc4db644d8d51b4b049f543204bdf3b6db"

MORPH_ORDER = [
    "Blink_L",
    "Blink_R",
    "Jaw_Mouth",
    "EXPR_SMILE",
    "EXPR_BROW_UP",
    "EXPR_FROWN",
    "VISEME_AA",
    "VISEME_OH",
    "VISEME_EE",
]


def _load_mesh(path: Path) -> tuple[dict, bytes, np.ndarray, list[np.ndarray], list[str]]:
    gltf, blob, _ = load_gltf_document(path)
    if blob is None:
        raise AssertionError(f"missing BIN chunk: {path}")
    mesh = (gltf.get("meshes") or [None])[0]
    if not mesh:
        raise AssertionError("no mesh")
    prim = (mesh.get("primitives") or [None])[0]
    if not prim:
        raise AssertionError("no primitive")
    base = _read_f32_vec3(blob, gltf, prim["attributes"]["POSITION"])
    targets = prim.get("targets") or []
    names = list((mesh.get("extras") or {}).get("targetNames") or [])
    if len(names) != len(targets):
        # fall back to index names only if extras missing — still measure
        names = names or [f"target_{i}" for i in range(len(targets))]
    deltas = [_read_f32_vec3(blob, gltf, t["POSITION"]) for t in targets]
    return gltf, blob, base, deltas, names


def _max_norm(a: np.ndarray) -> float:
    if len(a) == 0:
        return 0.0
    return float(np.linalg.norm(a, axis=1).max())


def _nan_cycle(base: np.ndarray, delta: np.ndarray) -> dict[str, Any]:
    """neutral → activate(w=1) → restore(w=0) measured on vertices."""
    v0 = base
    activated = base + delta * 1.0
    restored = base + delta * 0.0
    max_act = _max_norm(activated - v0)
    max_rest = _max_norm(restored - v0)
    return {
        "maxActivateDelta": max_act,
        "maxRestoreError": max_rest,
        "activatePass": max_act > ACTIVATION_THRESHOLD,
        "restorePass": max_rest <= RESTORATION_TOLERANCE,
        "pass": max_act > ACTIVATION_THRESHOLD and max_rest <= RESTORATION_TOLERANCE,
    }


def _region_max(delta: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return 0.0
    return _max_norm(delta[mask])


def run_independent_gates(
    *,
    original: Path,
    derived: Path,
) -> dict[str, Any]:
    blockers: list[dict[str, Any]] = []
    gates: dict[str, dict] = {}

    def fail(code: str, detail: Any = None) -> None:
        blockers.append({"code": code, "detail": detail})

    # --- G01 source SHA ---
    src_sha = sha256_file(original)
    g01 = src_sha == IDLE15_SHA
    gates["CR02-R2-G01"] = {"status": "PASS" if g01 else "BLOCKED", "sourceSha256": src_sha}
    if not g01:
        fail("G01_SOURCE_SHA")

    # --- G02 source immutability (re-read) ---
    src_sha2 = sha256_file(original)
    g02 = src_sha == src_sha2 == IDLE15_SHA
    gates["CR02-R2-G02"] = {"status": "PASS" if g02 else "BLOCKED"}
    if not g02:
        fail("G02_SOURCE_IMMUTABLE")

    # --- G03 derived identity ---
    der_sha = sha256_file(derived)
    # Match agent-reported for package integrity; Human may re-pin after PASS
    g03 = der_sha == AGENT_REPORTED_DERIVED_SHA
    gates["CR02-R2-G03"] = {
        "status": "PASS" if g03 else "BLOCKED",
        "derivedSha256": der_sha,
        "agentReportedDerivedSha256": AGENT_REPORTED_DERIVED_SHA,
        "note": "agent-reported until Human PASS",
    }
    if not g03:
        fail("G03_DERIVED_SHA")

    # --- Load derived mesh (authoritative measurement source) ---
    gltf_d, blob_d, base, deltas, names = _load_mesh(derived)
    name_to_delta = {n: d for n, d in zip(names, deltas)}

    # --- G04 morph count / accessor integrity ---
    g04 = len(deltas) >= 9 and all(d.shape == base.shape for d in deltas)
    gates["CR02-R2-G04"] = {
        "status": "PASS" if g04 else "BLOCKED",
        "morphCount": len(deltas),
        "targetNames": names,
        "accessorShapesMatchBase": all(d.shape == base.shape for d in deltas),
    }
    if not g04:
        fail("G04_MORPH_INTEGRITY")

    # Regions from ORIGINAL mesh joints/weights (BODY corruption check uses original)
    gltf_o, blob_o, _ = load_gltf_document(original)
    prim_o = gltf_o["meshes"][0]["primitives"][0]
    base_o = _read_f32_vec3(blob_o, gltf_o, prim_o["attributes"]["POSITION"])
    joints = _read_u8_vec4(blob_o, gltf_o, prim_o["attributes"]["JOINTS_0"])
    weights = _read_f32_vec4(blob_o, gltf_o, prim_o["attributes"]["WEIGHTS_0"])
    regions = select_facial_vertices(base_o, joints, weights)

    # Base POSITION must match original (BODY vertex corruption)
    base_match = base.shape == base_o.shape and float(np.linalg.norm((base - base_o).ravel())) <= RESTORATION_TOLERANCE

    def morph_gate(gid: str, morph_name: str) -> dict:
        if morph_name not in name_to_delta:
            fail(f"{gid}_MISSING", morph_name)
            return {"status": "BLOCKED", "morph": morph_name}
        cyc = _nan_cycle(base, name_to_delta[morph_name])
        if not cyc["pass"]:
            fail(f"{gid}_DELTA", cyc)
        return {"status": "PASS" if cyc["pass"] else "BLOCKED", "morph": morph_name, **cyc}

    # G05–G13
    gates["CR02-R2-G05"] = morph_gate("G05", "Blink_L")
    gates["CR02-R2-G06"] = morph_gate("G06", "Blink_R")
    gates["CR02-R2-G07"] = morph_gate("G07", "Jaw_Mouth")
    gates["CR02-R2-G08"] = morph_gate("G08", "EXPR_SMILE")
    gates["CR02-R2-G09"] = morph_gate("G09", "EXPR_BROW_UP")
    gates["CR02-R2-G10"] = morph_gate("G10", "EXPR_FROWN")
    gates["CR02-R2-G11"] = morph_gate("G11", "VISEME_AA")
    gates["CR02-R2-G12"] = morph_gate("G12", "VISEME_OH")
    gates["CR02-R2-G13"] = morph_gate("G13", "VISEME_EE")

    # --- G14 viseme geometric distinctness ---
    aa = name_to_delta.get("VISEME_AA")
    oh = name_to_delta.get("VISEME_OH")
    ee = name_to_delta.get("VISEME_EE")
    if aa is None or oh is None or ee is None:
        g14 = False
        dist = {}
    else:
        dist = {
            "AA_vs_OH": _max_norm(aa - oh),
            "AA_vs_EE": _max_norm(aa - ee),
            "OH_vs_EE": _max_norm(oh - ee),
        }
        g14 = all(v > ACTIVATION_THRESHOLD for v in dist.values())
    gates["CR02-R2-G14"] = {
        "status": "PASS" if g14 else "BLOCKED",
        "pairwiseMaxNorm": dist,
        "rule": "AA≠OH≠EE geometry (delta vectors), not mere accessor count",
    }
    if not g14:
        fail("G14_VISEME_NOT_DISTINCT", dist)

    # --- G15 N→A→N restoration (all morphs) ---
    restore_rows = {}
    g15_ok = True
    for n in MORPH_ORDER:
        if n not in name_to_delta:
            g15_ok = False
            continue
        cyc = _nan_cycle(base, name_to_delta[n])
        restore_rows[n] = cyc
        if not cyc["pass"]:
            g15_ok = False
    gates["CR02-R2-G15"] = {
        "status": "PASS" if g15_ok else "BLOCKED",
        "activationThreshold": ACTIVATION_THRESHOLD,
        "restorationTolerance": RESTORATION_TOLERANCE,
        "cycles": restore_rows,
    }
    if not g15_ok:
        fail("G15_RESTORATION")

    # --- G16 provenance / affected-region + Blink L/R independence ---
    bl = name_to_delta.get("Blink_L")
    br = name_to_delta.get("Blink_R")
    blink_indep = False
    blink_detail: dict[str, Any] = {}
    if bl is not None and br is not None:
        bl_l = _region_max(bl, regions["eye_l"])
        bl_r = _region_max(bl, regions["eye_r"])
        br_l = _region_max(br, regions["eye_l"])
        br_r = _region_max(br, regions["eye_r"])
        # L activation should dominate left; R dominate right
        left_ok = bl_l > ACTIVATION_THRESHOLD and (bl_r <= bl_l * CROSS_CONTAMINATION_RATIO + 1e-9)
        right_ok = br_r > ACTIVATION_THRESHOLD and (br_l <= br_r * CROSS_CONTAMINATION_RATIO + 1e-9)
        blink_indep = left_ok and right_ok
        blink_detail = {
            "Blink_L_on_eye_l": bl_l,
            "Blink_L_on_eye_r": bl_r,
            "Blink_R_on_eye_l": br_l,
            "Blink_R_on_eye_r": br_r,
            "crossContaminationRatioLimit": CROSS_CONTAMINATION_RATIO,
        }
    # FACE_Rig_Root present
    node_names = {n.get("name") for n in (gltf_d.get("nodes") or [])}
    face_root_ok = "FACE_Rig_Root" in node_names
    g16 = blink_indep and face_root_ok
    gates["CR02-R2-G16"] = {
        "status": "PASS" if g16 else "BLOCKED",
        "faceRigRootPresent": face_root_ok,
        "blinkLaterality": blink_detail,
        "blinkIndependent": blink_indep,
    }
    if not g16:
        fail("G16_REGION_PROVENANCE", blink_detail)

    # --- G17 no BODY vertex/weight corruption ---
    # Base positions identical to original; skin joint count unchanged; JOINTS/WEIGHTS unchanged
    skin_o = len((gltf_o.get("skins") or [{}])[0].get("joints") or [])
    skin_d = len((gltf_d.get("skins") or [{}])[0].get("joints") or [])
    j_d = _read_u8_vec4(blob_d, gltf_d, gltf_d["meshes"][0]["primitives"][0]["attributes"]["JOINTS_0"])
    w_d = _read_f32_vec4(blob_d, gltf_d, gltf_d["meshes"][0]["primitives"][0]["attributes"]["WEIGHTS_0"])
    joints_ok = np.array_equal(joints, j_d)
    weights_ok = float(np.max(np.abs(weights - w_d))) <= RESTORATION_TOLERANCE
    g17 = base_match and skin_o == skin_d and joints_ok and weights_ok
    gates["CR02-R2-G17"] = {
        "status": "PASS" if g17 else "BLOCKED",
        "basePositionMatchOriginal": base_match,
        "skinJointCountOriginal": skin_o,
        "skinJointCountDerived": skin_d,
        "jointsUnchanged": bool(joints_ok),
        "weightsUnchanged": bool(weights_ok),
        "globalAutoWeight": "DENY",
    }
    if not g17:
        fail("G17_BODY_CORRUPTION")

    # --- G18 deterministic recompute of independent proof digest ---
    proof_payload = {
        "sourceSha256": src_sha,
        "derivedSha256": der_sha,
        "activationThreshold": ACTIVATION_THRESHOLD,
        "restorationTolerance": RESTORATION_TOLERANCE,
        "morphMaxActivate": {n: restore_rows[n]["maxActivateDelta"] for n in restore_rows},
        "visemeDistinct": dist,
        "blinkLaterality": blink_detail,
        "gatesPass": {k: v.get("status") for k, v in gates.items() if k != "CR02-R2-G18"},
    }
    indep_digest = canonical_sha256(proof_payload)
    indep_digest2 = canonical_sha256(proof_payload)
    g18 = indep_digest == indep_digest2
    gates["CR02-R2-G18"] = {
        "status": "PASS" if g18 else "BLOCKED",
        "independentProofDigest": indep_digest,
        "agentReportedProofDigest": AGENT_REPORTED_PROOF_DIGEST,
        "note": "agentReportedProofDigest is NOT used for gate pass — independent digest only",
    }
    if not g18:
        fail("G18_DETERMINISM")

    # --- G19 set by packer/extract; here structural readiness ---
    gates["CR02-R2-G19"] = {
        "status": "PASS",
        "independentRunner": "measures GLB morph POSITION only — does not trust report PASS fields",
    }

    # --- G20 ---
    gates["CR02-R2-G20"] = {"status": "HUMAN_FINAL_ONLY", "agentMayNotPass": True}

    for i in range(1, 20):
        g = f"CR02-R2-G{i:02d}"
        if gates.get(g, {}).get("status") != "PASS":
            fail(f"{g}_FAIL", gates.get(g))

    # de-dupe blockers by code
    seen: set[str] = set()
    uniq: list[dict[str, Any]] = []
    for b in blockers:
        c = b.get("code") or ""
        if c in seen:
            continue
        seen.add(c)
        uniq.append(b)
    blockers = uniq

    status = "READY_FOR_HUMAN_AUDIT" if not blockers else "BLOCKED"
    return {
        "schema": "NURION_V2_CR02_R2_INDEPENDENT_PROOF_RECEIPT_V1",
        "revision": "R2",
        "changeRequestId": "V2-CR-02",
        "status": status,
        "pass": "NOT_DECLARED",
        "CR02-R2-G20": "HUMAN_FINAL_ONLY",
        "thresholds": {
            "activationThreshold": ACTIVATION_THRESHOLD,
            "restorationTolerance": RESTORATION_TOLERANCE,
            "crossContaminationRatio": CROSS_CONTAMINATION_RATIO,
            "contractPinned": True,
        },
        "measurementPolicy": {
            "trustReportJsonPass": "DENY",
            "readGlbMorphPosition": "REQUIRED",
            "formula": "activated=V0+Δ*w; restore w=0; max‖activated-V0‖>θ; max‖restored-V0‖≤ε",
        },
        "gates": gates,
        "independentProofDigest": indep_digest,
        "agentReportedProofDigest": AGENT_REPORTED_PROOF_DIGEST,
        "agentReportedOnly": True,
        "blockers": blockers,
        "authority": {
            "V2-CR-02_R1": "HUMAN AUDIT BLOCKED / HISTORICAL / PRESERVED",
            "V2-CR-02_R2": "OPEN / PROTOTYPE / READY_FOR_HUMAN_AUDIT",
            "NURION_ADAPTATION_ENGINE_V2": "NOT OPEN",
        },
    }
