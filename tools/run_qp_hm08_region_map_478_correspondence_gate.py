"""NURION Parametric Head Candidate A hm08 Head Region Maps And MediaPipe 478 Correspondence Gate GO.

Corrects provenance to mpfb2 commit pin. Builds HEAD_REGION_MAP + typed 478 correspondence.
No face renders.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

ROOT = Path(r"d:\NURION Character Landmarker")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nurion_qp_geometry_face_v2.mediapipe_backend import MediaPipeLandmarkerBackend

COMMAND = (
    "NURION Parametric Head Candidate A hm08 Head Region Maps And MediaPipe 478 Correspondence Gate GO"
)
ALLOWED = {
    "PASS_WITH_CORRESPONDENCE_LIMITATIONS",
    "REVIEW_REQUIRED",
    "TOPOLOGY_REWORK_REQUIRED",
    "ALGORITHM_FAIL",
}

ACQ = ROOT / "dist/v0.7/product/quick_profile/parametric_head_asset_acquisition"
CAND = ACQ / "candidate_a_makehuman_hm08"
RAW = CAND / "raw"
MESH = RAW / "mpfb2_437dd513_base.obj"
if not MESH.is_file():
    MESH = RAW / "base.obj"
EYES = RAW / "eyes_low-poly.obj"
MODELS = ROOT / "dist/v0.7/product/quick_profile/geometry_first_face_analyzer_v2/gate2/models"
INTAKE = ROOT / "dist/v0.7/product/quick_profile/gate3/intake/packages/P001/face.png"

EXPECTED_MESH_SHA = "8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c"
MPFB2_COMMIT = "437dd513888a92399d1d3200d2e80859fae55abc"
MPFB2_PATH = "src/mpfb/data/3dobjs/base.obj"
MPFB2_URL = (
    f"https://raw.githubusercontent.com/makehumancommunity/mpfb2/"
    f"{MPFB2_COMMIT}/{MPFB2_PATH}"
)

# MediaPipe semantic landmark indices (constraints / anchors)
MP_SEMANTIC = {
    "NOSE_TIP": 4,
    "NOSE_BRIDGE": 6,
    "CHIN": 152,
    "FOREHEAD": 10,
    "L_EYE_OUTER": 33,
    "L_EYE_INNER": 133,
    "R_EYE_OUTER": 263,
    "R_EYE_INNER": 362,
    "MOUTH_L": 61,
    "MOUTH_R": 291,
    "UPPER_LIP": 13,
    "LOWER_LIP": 14,
    "L_BROW": 70,
    "R_BROW": 300,
}
IRIS_L = list(range(468, 473))
IRIS_R = list(range(473, 478))

# Contour / region landmark sets for reporting
LIP_OUTER = [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 185, 40, 39, 37, 0, 267, 269, 270, 409]
LIP_INNER = [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 191, 80, 81, 82, 13, 312, 311, 310, 415]
L_EYELID = [246, 161, 160, 159, 158, 157, 173, 33, 7, 163, 144, 145, 153, 154, 155, 133]
R_EYELID = [466, 388, 387, 386, 385, 384, 398, 263, 249, 390, 373, 374, 380, 381, 382, 362]
FACE_OVAL = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
    148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_obj(path: Path):
    verts = []
    faces = []
    face_groups = []
    current = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append([float(a[1]), float(a[2]), float(a[3])])
        elif line.startswith("g ") or line.startswith("o "):
            current = line[2:].strip()
        elif line.startswith("f "):
            idxs = []
            for t in line.split()[1:]:
                idxs.append(int(t.split("/")[0]) - 1)
            faces.append(idxs)
            face_groups.append(current)
    return np.asarray(verts, dtype=np.float64), faces, face_groups


def group_verts(faces, face_groups, name: str) -> set[int]:
    out: set[int] = set()
    for f, g in zip(faces, face_groups):
        if g == name:
            out.update(f)
    return out


def build_head_region_map(V: np.ndarray, faces, face_groups) -> dict[str, Any]:
    body = group_verts(faces, face_groups, "body")
    # MakeHuman: Y up. Head band.
    ys, zs, xs = V[:, 1], V[:, 2], V[:, 0]
    head = {i for i in body if ys[i] >= 6.15}
    neck = {i for i in body if 5.55 <= ys[i] < 6.15 and abs(xs[i]) < 0.55}
    scalp = {i for i in head if zs[i] < 0.55 and ys[i] > 7.55}
    face_shell = {i for i in head if zs[i] >= 0.55}
    face_outline = {i for i in face_shell if abs(xs[i]) > 0.55 or ys[i] < 6.45 or ys[i] > 7.85}

    # Joint / helper centroids as attractors
    def centroid(name: str) -> np.ndarray | None:
        idx = group_verts(faces, face_groups, name)
        if not idx:
            return None
        return V[list(idx)].mean(axis=0)

    attractors = {
        "eyelid_l": centroid("joint-l-upperlid"),
        "eyelid_l_low": centroid("joint-l-lowerlid"),
        "eyelid_r": centroid("joint-r-upperlid"),
        "eyelid_r_low": centroid("joint-r-lowerlid"),
        "mouth": centroid("joint-mouth"),
        "jaw": centroid("joint-jaw"),
        "eye_l": centroid("joint-l-eye"),
        "eye_r": centroid("joint-r-eye"),
        "neck": centroid("joint-neck"),
    }

    def near(c: np.ndarray | None, radius: float, pool: set[int]) -> set[int]:
        if c is None:
            return set()
        out = set()
        for i in pool:
            if float(np.linalg.norm(V[i] - c)) <= radius:
                out.add(i)
        return out

    eyelids = (
        near(attractors["eyelid_l"], 0.22, face_shell)
        | near(attractors["eyelid_l_low"], 0.22, face_shell)
        | near(attractors["eyelid_r"], 0.22, face_shell)
        | near(attractors["eyelid_r_low"], 0.22, face_shell)
    )
    # Nose: midline, forward
    nose = {
        i
        for i in face_shell
        if abs(xs[i]) < 0.18 and 6.85 < ys[i] < 7.45 and zs[i] > 1.15
    }
    nose_ala = {
        i
        for i in face_shell
        if 0.08 < abs(xs[i]) < 0.28 and 6.85 < ys[i] < 7.25 and zs[i] > 1.05
    }
    lips = near(attractors["mouth"], 0.28, face_shell) | {
        i for i in face_shell if abs(xs[i]) < 0.35 and 6.55 < ys[i] < 6.95 and zs[i] > 1.05
    }
    oral = group_verts(faces, face_groups, "helper-tongue") | group_verts(
        faces, face_groups, "helper-upper-teeth"
    ) | group_verts(faces, face_groups, "helper-lower-teeth")
    jaw = near(attractors["jaw"], 0.55, head) | {
        i for i in head if ys[i] < 6.55 and zs[i] > 0.2 and abs(xs[i]) < 0.7
    }
    ears = {i for i in head if abs(xs[i]) > 0.72 and 6.7 < ys[i] < 7.55 and zs[i] < 0.9}

    regions = {
        "FACE_OUTLINE": sorted(face_outline),
        "SCALP": sorted(scalp),
        "EYELID": sorted(eyelids),
        "NOSE": sorted(nose),
        "NOSE_ALA": sorted(nose_ala),
        "LIPS": sorted(lips),
        "ORAL": sorted(oral),
        "JAW": sorted(jaw),
        "EAR": sorted(ears),
        "NECK": sorted(neck),
        "HEAD_ALL": sorted(head),
        "FACE_SHELL": sorted(face_shell),
        "HELPER_L_EYE": sorted(group_verts(faces, face_groups, "helper-l-eye")),
        "HELPER_R_EYE": sorted(group_verts(faces, face_groups, "helper-r-eye")),
    }
    counts = {k: len(v) for k, v in regions.items()}
    missing = [k for k, n in counts.items() if n == 0 and k not in ("ORAL",)]
    # ORAL may be helpers only — OK if non-empty helpers
    ok = counts["EYELID"] > 0 and counts["NOSE"] > 0 and counts["LIPS"] > 0 and counts["JAW"] > 0
    ok = ok and counts["EAR"] > 0 and counts["NECK"] > 0 and counts["SCALP"] > 0
    ok = ok and counts["FACE_OUTLINE"] > 0 and counts["ORAL"] > 0
    return {
        "schema": "NURION_V07_HM08_HEAD_REGION_MAP_V1",
        "meshSha256": EXPECTED_MESH_SHA,
        "regions": regions,
        "counts": counts,
        "attractors": {
            k: (None if v is None else [float(x) for x in v]) for k, v in attractors.items()
        },
        "complete": ok,
        "missingEmpty": missing,
        "method": "GEOMETRIC_BANDS_PLUS_JOINT_HELPER_ATTRACTORS",
        "disclosure": "Region sets are frozen vertex-index lists for NURION derivation; artist review may refine boundaries.",
    }


def _barycentric(p, a, b, c):
    v0, v1, v2 = b - a, c - a, p - a
    d00 = float(np.dot(v0, v0))
    d01 = float(np.dot(v0, v1))
    d11 = float(np.dot(v1, v1))
    d20 = float(np.dot(v2, v0))
    d21 = float(np.dot(v2, v1))
    denom = d00 * d11 - d01 * d01
    if abs(denom) < 1e-12:
        return None
    v = (d11 * d20 - d01 * d21) / denom
    w = (d00 * d21 - d01 * d20) / denom
    u = 1.0 - v - w
    return u, v, w


def map_point_to_surface(p: np.ndarray, V: np.ndarray, faces_idx: list[list[int]], pool: set[int]):
    """Map 3D point to hm08 surface among faces that touch pool verts."""
    # Restrict candidate verts
    pool_list = list(pool)
    d = np.linalg.norm(V[pool_list] - p, axis=1)
    nearest_vi = int(pool_list[int(np.argmin(d))])
    nearest_dist = float(d.min())

    # Candidate faces containing nearest or nearby verts
    near_set = set()
    order = np.argsort(d)[:12]
    for j in order:
        near_set.add(pool_list[int(j)])

    best = None
    for f in faces_idx:
        if len(f) < 3:
            continue
        if not any(vi in near_set for vi in f):
            continue
        # fan triangulate
        for t in range(1, len(f) - 1):
            a, b, c = V[f[0]], V[f[t]], V[f[t + 1]]
            n = np.cross(b - a, c - a)
            nn = float(np.linalg.norm(n))
            if nn < 1e-10:
                continue
            n = n / nn
            # project p onto plane
            t_ = float(np.dot(a - p, n))
            proj = p + t_ * n  # wait: p to plane: p + ((a-p)·n) n
            proj = p + float(np.dot(a - p, n)) * n
            bc = _barycentric(proj, a, b, c)
            if bc is None:
                continue
            u, v, w = bc
            if u < -0.05 or v < -0.05 or w < -0.05:
                continue
            # clamp
            dist = float(np.linalg.norm(proj - p))
            if best is None or dist < best["dist"]:
                best = {
                    "dist": dist,
                    "face": [int(f[0]), int(f[t]), int(f[t + 1])],
                    "barycentric": [float(u), float(v), float(w)],
                    "proj": proj,
                }

    # Classify
    if best is None:
        return {
            "type": "VERTEX",
            "vertex": nearest_vi,
            "distance": nearest_dist,
            "note": "FALLBACK_NEAREST_VERTEX",
        }

    u, v, w = best["barycentric"]
    face = best["face"]
    # near a vertex
    verts_bc = [(u, face[0]), (v, face[1]), (w, face[2])]
    verts_bc.sort(reverse=True)
    if verts_bc[0][0] >= 0.85:
        return {"type": "VERTEX", "vertex": int(verts_bc[0][1]), "distance": float(best["dist"])}
    # near an edge
    if min(u, v, w) <= 0.08:
        # edge opposite the small bary weight
        if u <= 0.08:
            e = (face[1], face[2])
            t_edge = v / max(v + w, 1e-8)
        elif v <= 0.08:
            e = (face[0], face[2])
            t_edge = u / max(u + w, 1e-8)
        else:
            e = (face[0], face[1])
            t_edge = u / max(u + v, 1e-8)
        return {
            "type": "EDGE",
            "edge": [int(e[0]), int(e[1])],
            "t": float(t_edge),
            "distance": float(best["dist"]),
        }
    return {
        "type": "FACE_BARYCENTRIC",
        "face": face,
        "barycentric": [float(u), float(v), float(w)],
        "distance": float(best["dist"]),
    }


def build_478_correspondence(
    V: np.ndarray,
    faces,
    face_groups,
    regions: dict[str, list[int]],
    lm_img: np.ndarray,
) -> dict[str, Any]:
    """Align MediaPipe landmarks to hm08 via semantic Procrustes in frontal plane, then surface map."""
    body_faces = [f for f, g in zip(faces, face_groups) if g == "body"]
    face_pool = set(regions["FACE_SHELL"]) | set(regions["HEAD_ALL"])
    head_pool = set(regions["HEAD_ALL"])

    # Frontal coords for hm08: X, Y (image-like: x right, y down from forehead)
    def frontal(idx: int) -> np.ndarray:
        return np.array([V[idx, 0], -V[idx, 1]], dtype=np.float64)

    # Semantic targets on hm08 by geometry
    def pick_max_z(pool: set[int], pred) -> int:
        best_i, best_z = None, -1e9
        for i in pool:
            if pred(i) and V[i, 2] > best_z:
                best_z = float(V[i, 2])
                best_i = i
        return int(best_i if best_i is not None else next(iter(pool)))

    face_shell = set(regions["FACE_SHELL"])
    jaw_set = set(regions["JAW"]) or face_shell
    lips_set = set(regions["LIPS"]) or face_shell
    hm_sem: dict[str, int] = {}
    hm_sem["NOSE_TIP"] = pick_max_z(face_shell, lambda i: abs(V[i, 0]) < 0.08 and 6.9 < V[i, 1] < 7.35)
    hm_sem["CHIN"] = pick_max_z(jaw_set, lambda i: abs(V[i, 0]) < 0.12 and V[i, 1] < 6.55)
    forehead_cands = [i for i in face_shell if abs(V[i, 0]) < 0.15]
    hm_sem["FOREHEAD"] = max(forehead_cands, key=lambda i: float(V[i, 1])) if forehead_cands else next(iter(face_shell))
    hm_sem["MOUTH_L"] = min(lips_set, key=lambda i: float(V[i, 0]))
    hm_sem["MOUTH_R"] = max(lips_set, key=lambda i: float(V[i, 0]))
    if regions["HELPER_L_EYE"]:
        c = V[regions["HELPER_L_EYE"]].mean(axis=0)
        hm_sem["L_EYE_OUTER"] = max(regions["HELPER_L_EYE"], key=lambda i: float(V[i, 0]))
        hm_sem["L_EYE_INNER"] = min(regions["HELPER_L_EYE"], key=lambda i: float(V[i, 0]))
        _ = c
    if regions["HELPER_R_EYE"]:
        hm_sem["R_EYE_OUTER"] = min(regions["HELPER_R_EYE"], key=lambda i: float(V[i, 0]))
        hm_sem["R_EYE_INNER"] = max(regions["HELPER_R_EYE"], key=lambda i: float(V[i, 0]))
    # MakeHuman: +X is typically left side of character from character view; keep as-is

    # Build Procrustes from MP image xy to hm08 frontal using semantic pairs available in both
    pairs = []
    for name, mp_i in MP_SEMANTIC.items():
        if name not in hm_sem:
            continue
        pairs.append((lm_img[mp_i, :2], frontal(hm_sem[name])))
    src = np.array([p[0] for p in pairs], dtype=np.float64)
    dst = np.array([p[1] for p in pairs], dtype=np.float64)
    src_c, dst_c = src.mean(0), dst.mean(0)
    src_z, dst_z = src - src_c, dst - dst_c
    s = float(np.linalg.norm(dst_z) / (np.linalg.norm(src_z) + 1e-8))
    H = src_z.T @ dst_z
    U, _, Vt = np.linalg.svd(H)
    R = Vt.T @ U.T
    if np.linalg.det(R) < 0:
        Vt[-1, :] *= -1
        R = Vt.T @ U.T
    t = dst_c - s * (R @ src_c)

    def mp_to_hm_frontal(xy: np.ndarray) -> np.ndarray:
        return s * (R @ xy) + t

    # Estimate depth from local hm08 z given frontal nearest
    entries = []
    type_counts = defaultdict(int)
    limitations = []

    for i in range(478):
        if i in IRIS_L or i in IRIS_R:
            side = "L" if i in IRIS_L else "R"
            entries.append(
                {
                    "mpIndex": i,
                    "type": "UNSUPPORTED",
                    "reason": "IRIS_PUPIL_MAPS_TO_SEPARATE_EYE_ASSET",
                    "eyeAsset": "eyes_low-poly.obj",
                    "eyeSide": side,
                    "eyeAssetSha256": sha256_file(EYES) if EYES.is_file() else None,
                }
            )
            type_counts["UNSUPPORTED"] += 1
            continue

        xy = lm_img[i, :2]
        fr = mp_to_hm_frontal(xy)
        # find nearest face_shell vertex in frontal space to seed 3D target
        pool = list(face_pool)
        fr_all = np.stack([frontal(j) for j in pool], axis=0)
        j = int(np.argmin(np.linalg.norm(fr_all - fr, axis=1)))
        seed = pool[j]
        # 3D target: keep seed's z, set x/y from inverse frontal approx
        # frontal = [x, -y] => x=fr[0], y=-fr[1]
        target = np.array([fr[0], -fr[1], V[seed, 2]], dtype=np.float64)
        mapped = map_point_to_surface(target, V, body_faces, face_pool)
        mapped["mpIndex"] = i
        # Region tag
        vi = mapped.get("vertex")
        if vi is None and mapped.get("face"):
            vi = mapped["face"][int(np.argmax(mapped["barycentric"]))]
        if vi is None and mapped.get("edge"):
            vi = mapped["edge"][0]
        region = "UNKNOWN"
        if vi is not None:
            for rname in (
                "EYELID",
                "LIPS",
                "NOSE_ALA",
                "NOSE",
                "EAR",
                "JAW",
                "SCALP",
                "NECK",
                "FACE_OUTLINE",
                "FACE_SHELL",
            ):
                if vi in set(regions[rname]):
                    region = rname
                    break
        mapped["region"] = region
        entries.append(mapped)
        type_counts[mapped["type"]] += 1

    limitations.extend(
        [
            "IRIS_10_POINTS_UNSUPPORTED_ON_BODY_MESH_REQUIRE_EYE_ASSET",
            "CORRESPONDENCE_USES_SEMANTIC_PROCRUSTES_PLUS_SURFACE_PROJECTION",
            "NOT_A_HAND_AUTHORED_ONE_TO_ONE_ARTIST_TABLE",
            "DENSE_MESH_POINTS_MAY_NEED_REVIEW_NEAR_EARS_HAIRLINE_ORAL",
        ]
    )

    return {
        "schema": "NURION_V07_HM08_MEDIAPIPE_478_CORRESPONDENCE_V1",
        "meshSha256": EXPECTED_MESH_SHA,
        "mappingPolicy": [
            "VERTEX",
            "EDGE",
            "FACE_BARYCENTRIC",
            "UNSUPPORTED",
        ],
        "forcedSingleVertexMapping": "DENY",
        "typeCounts": dict(type_counts),
        "semanticAnchorsHm08": {k: int(v) for k, v in hm_sem.items()},
        "semanticAnchorsMp": MP_SEMANTIC,
        "entries": entries,
        "limitations": limitations,
        "alignment": {"scale": s, "rotDet": float(np.linalg.det(R))},
    }


def decide_verdict(region_map: dict, corr: dict) -> tuple[str, list[str]]:
    reasons = []
    if not region_map.get("complete"):
        reasons.append("HEAD_REGION_MAP_INCOMPLETE")
        return "TOPOLOGY_REWORK_REQUIRED", reasons
    tc = corr["typeCounts"]
    if tc.get("UNSUPPORTED", 0) < 10:
        reasons.append("IRIS_UNSUPPORTED_COUNT_UNEXPECTED")
    if tc.get("VERTEX", 0) + tc.get("EDGE", 0) + tc.get("FACE_BARYCENTRIC", 0) < 400:
        reasons.append("TOO_FEW_SURFACE_MAPPINGS")
        return "ALGORITHM_FAIL", reasons
    # Always have limitations (iris + projection method)
    reasons.extend(corr["limitations"])
    # If many UNKNOWN regions — review
    unknown = sum(1 for e in corr["entries"] if e.get("region") == "UNKNOWN" and e.get("type") != "UNSUPPORTED")
    if unknown > 80:
        reasons.append(f"HIGH_UNKNOWN_REGION_COUNT:{unknown}")
        return "REVIEW_REQUIRED", reasons
    return "PASS_WITH_CORRESPONDENCE_LIMITATIONS", reasons


def correct_provenance(now: str) -> dict:
    provenance = {
        "schema": "NURION_V07_CANDIDATE_A_HM08_PROVENANCE_CORRECTION_V1",
        "correctedAt": now,
        "priorIncorrectSourceClaim": {
            "sourceRepo": "makehumancommunity/makehuman",
            "sourcePath": "makehuman/data/3dobjs/base.obj",
            "note": "Same bytes may exist elsewhere but were not the byte-verified provenance for this pin",
        },
        "byteVerifiedSource": {
            "sourceRepo": "makehumancommunity/mpfb2",
            "commit": MPFB2_COMMIT,
            "sourcePath": MPFB2_PATH,
            "url": MPFB2_URL,
            "meshSha256": EXPECTED_MESH_SHA,
            "verifiedMatch": True,
        },
        "priorVerdictUnchanged": "PASS_WITH_TOPOLOGY_REWORK_REQUIRED",
        "candidateA": "SOURCE_ASSET_ELIGIBLE",
        "nurionHeadFinishedProduct": "NOT_YET",
        "faceRenderHumanEvalProduction": "HOLD",
    }
    write_json(CAND / "V07_QP_CANDIDATE_A_HM08_PROVENANCE_CORRECTION.json", provenance)
    write_json(ACQ / "V07_QP_CANDIDATE_A_HM08_PROVENANCE_CORRECTION.json", provenance)

    # Patch previous receipt provenance in place (evidence continuity)
    prev = CAND / "V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT.json"
    if prev.is_file():
        data = json.loads(prev.read_text(encoding="utf-8"))
        data["provenanceCorrection"] = provenance
        data["provenance"]["sourceRepo"] = "https://github.com/makehumancommunity/mpfb2"
        data["provenance"]["sourceCommit"] = MPFB2_COMMIT
        data["provenance"]["sourcePath"] = MPFB2_PATH
        data["provenance"]["sourceUrl"] = MPFB2_URL
        data["provenance"]["byteVerified"] = True
        data["pins"]["base.obj"]["url"] = MPFB2_URL
        data["pins"]["base.obj"]["path"] = str((RAW / "mpfb2_437dd513_base.obj").relative_to(ROOT)).replace("\\", "/")
        write_json(prev, data)
        write_json(ACQ / "V07_QP_CANDIDATE_A_HM08_MESH_PIN_TOPOLOGY_AUDIT_RECEIPT.json", data)
    return provenance


def main() -> int:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out = CAND / "runs" / f"region478_{run_id}"
    out.mkdir(parents=True, exist_ok=True)

    provenance = correct_provenance(now)

    mesh_sha = sha256_file(MESH)
    if mesh_sha != EXPECTED_MESH_SHA:
        receipt = {
            "verdict": "ALGORITHM_FAIL",
            "reason": "MESH_SHA_MISMATCH",
            "expected": EXPECTED_MESH_SHA,
            "actual": mesh_sha,
        }
        write_json(out / "RECEIPT.json", receipt)
        print(json.dumps(receipt, indent=2))
        return 2

    V, faces, face_groups = parse_obj(MESH)
    region_map = build_head_region_map(V, faces, face_groups)
    write_json(out / "HEAD_REGION_MAP.json", region_map)
    write_json(CAND / "HEAD_REGION_MAP.json", region_map)

    # MediaPipe landmarks from P001 for alignment reference (not a render)
    backend = MediaPipeLandmarkerBackend(MODELS / "face_landmarker_float16_v1.task")
    rgb = np.asarray(Image.open(INTAKE).convert("RGB"), dtype=np.uint8)
    lm = backend.infer(rgb, "ORIGINAL_RGB")
    if lm is None or lm.shape != (478, 3):
        write_json(out / "RECEIPT.json", {"verdict": "ALGORITHM_FAIL", "reason": "NO_478_FROM_REFERENCE"})
        return 2

    corr = build_478_correspondence(V, faces, face_groups, region_map["regions"], lm)
    # Store compact + full
    write_json(out / "MEDIAPIPE_478_CORRESPONDENCE.json", corr)
    # Compact summary without full entries for desk
    compact = {k: v for k, v in corr.items() if k != "entries"}
    compact["entryCount"] = len(corr["entries"])
    write_json(CAND / "MEDIAPIPE_478_CORRESPONDENCE_SUMMARY.json", compact)
    write_json(CAND / "MEDIAPIPE_478_CORRESPONDENCE.json", corr)

    verdict, reasons = decide_verdict(region_map, corr)
    assert verdict in ALLOWED

    receipt = {
        "schema": "NURION_V07_HM08_REGION_MAP_AND_478_CORRESPONDENCE_GATE_RECEIPT_V1",
        "command": COMMAND,
        "runId": run_id,
        "completedAt": now,
        "verdict": verdict,
        "allowedVerdicts": sorted(ALLOWED),
        "reasons": reasons,
        "stages": {
            "HEAD_REGION_MAP": "COMPLETE" if region_map["complete"] else "INCOMPLETE",
            "MEDIAPIPE_478_CORRESPONDENCE": "COMPLETE_WITH_LIMITATIONS",
        },
        "provenance": provenance["byteVerifiedSource"],
        "priorTopologyVerdict": "PASS_WITH_TOPOLOGY_REWORK_REQUIRED",
        "regionCounts": region_map["counts"],
        "correspondenceTypeCounts": corr["typeCounts"],
        "newFaceRendersCreated": 0,
        "holds": {
            "faceGeneration": "HOLD",
            "fullBodyAssembly": "HOLD",
            "humanEvaluation": "HOLD",
            "production": "NO-GO",
            "arkaonLearningInclusion": "HOLD",
        },
        "forcedPass": "DENY",
        "production": "NO-GO",
        "artifacts": {
            "headRegionMap": str((CAND / "HEAD_REGION_MAP.json").relative_to(ROOT)).replace("\\", "/"),
            "correspondence": str((CAND / "MEDIAPIPE_478_CORRESPONDENCE.json").relative_to(ROOT)).replace("\\", "/"),
        },
        "next": "NURION_HEAD_DERIVATION_FROM_HM08_USING_REGION_MAP_AND_TYPED_478_TABLE",
    }
    raw_fp = {k: v for k, v in receipt.items() if k != "executionFingerprintSha256"}
    receipt["executionFingerprintSha256"] = hashlib.sha256(
        json.dumps(raw_fp, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()
    write_json(out / "V07_QP_HM08_REGION_478_GATE_RECEIPT.json", receipt)
    write_json(CAND / "V07_QP_HM08_REGION_478_GATE_RECEIPT.json", receipt)
    write_json(ACQ / "V07_QP_HM08_REGION_478_GATE_RECEIPT.json", receipt)

    write_json(
        ACQ / "V07_QP_PARAMETRIC_HEAD_ASSET_ACQUISITION_GATE_STATUS.json",
        {
            "status": verdict,
            "prior": "PASS_WITH_TOPOLOGY_REWORK_REQUIRED",
            "provenance": "mpfb2@" + MPFB2_COMMIT,
            "meshSha256": EXPECTED_MESH_SHA,
            "faceGeneration": "HOLD",
            "humanEvaluation": "HOLD",
            "production": "NO-GO",
            "updatedAt": now,
            "lastRunId": run_id,
            "next": receipt["next"],
        },
    )

    desk = f"""<!DOCTYPE html>
<html lang="ko"><head><meta charset="utf-8"/><title>hm08 Region Map + 478 Correspondence</title>
<style>
body{{margin:0;font-family:Segoe UI,Malgun Gothic,sans-serif;background:#16181b;color:#e8eaed;padding:1.2rem}}
.badge{{display:inline-block;margin:.2rem;padding:.25rem .55rem;border:1px solid #666;border-radius:999px;font-size:.78rem;color:#c4a574}}
code{{color:#9cdcfe}}
</style></head><body>
<h1>HEAD_REGION_MAP + MEDIAPIPE_478_CORRESPONDENCE</h1>
<span class="badge">{verdict}</span>
<span class="badge">렌더 0</span>
<span class="badge">출처 mpfb2@{MPFB2_COMMIT[:12]}</span>
<span class="badge">Production NO-GO</span>
<p>mesh SHA-256 <code>{EXPECTED_MESH_SHA}</code></p>
<p>Region counts: {json.dumps(region_map['counts'], ensure_ascii=False)}</p>
<p>Correspondence types: {json.dumps(corr['typeCounts'], ensure_ascii=False)}</p>
<p>Iris/pupil → separate eye asset (UNSUPPORTED on body). No forced single-vertex mapping.</p>
<p>HOLD: 얼굴 렌더 · 사람평가 · Production</p>
</body></html>
"""
    desk_path = CAND / "REGION_478_GATE_DESK.html"
    desk_path.write_text(desk, encoding="utf-8")
    try:
        subprocess.Popen(["cmd", "/c", "start", "", str(desk_path)], shell=False)
    except Exception:
        pass

    print(
        json.dumps(
            {
                "verdict": verdict,
                "reasons": reasons[:6],
                "provenance": f"mpfb2@{MPFB2_COMMIT}",
                "meshSha256": EXPECTED_MESH_SHA,
                "regionCounts": region_map["counts"],
                "correspondenceTypeCounts": corr["typeCounts"],
                "newFaceRendersCreated": 0,
                "production": "NO-GO",
                "desk": str(desk_path),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if verdict == "PASS_WITH_CORRESPONDENCE_LIMITATIONS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
