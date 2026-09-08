"""Fuse geometry + multiview + symmetry into FACE_GEOMETRY_CORRECTED."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from mathutils import Vector

from ..landmark_engine import LandmarkPoint
from ..leak_guard import assert_no_gt_parameters, generation_scope
from ..sources import FACE_GEOMETRY_CORRECTED
from ..transform_normalize import (
    WorldMeshView,
    build_world_mesh_view,
    nearest_on_mesh,
    point_inside_or_on_mesh,
)
from .geometry_detect import detect_face_geometry_candidates
from .keys import ALPHA1_CORE_KEYS
from .multiview import collect_multiview_candidates, fuse_multiview_with_geometry
from .parameters import FACE_ALPHA1_PARAMETERS
from .region import FaceRegionResult, evaluate_face_region
from .spaces import HeadFrame


@dataclass
class FaceCorrectionResult:
    landmarks: Dict[str, LandmarkPoint]
    region: FaceRegionResult
    corrected: List[str] = field(default_factory=list)
    rejected_outside: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    lr_swaps: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema": "NURION_FACE_CORRECTION_RESULT",
            "corrected": list(self.corrected),
            "rejectedOutside": list(self.rejected_outside),
            "missing": list(self.missing),
            "lrSwaps": list(self.lr_swaps),
            "notes": list(self.notes),
            "eligibility": self.region.to_dict(),
        }


def _enforce_laterality(landmarks: Dict[str, LandmarkPoint], frame: HeadFrame) -> List[str]:
    swaps: List[str] = []
    for base in ("eye.center", "eye.inner", "eye.outer", "mouth.corner", "ear.center"):
        l_name, r_name = f"{base}.L", f"{base}.R"
        if l_name not in landmarks or r_name not in landmarks:
            continue
        lx = frame.to_local(landmarks[l_name].position).x
        rx = frame.to_local(landmarks[r_name].position).x
        if lx < rx:
            # Swap positions — L should be +X in our head frame convention.
            lp, rp = landmarks[l_name].position.copy(), landmarks[r_name].position.copy()
            landmarks[l_name].position = rp
            landmarks[r_name].position = lp
            swaps.append(base)
    return swaps


def _mirror_pair(landmarks: Dict[str, LandmarkPoint], frame: HeadFrame, base: str) -> None:
    l_name, r_name = f"{base}.L", f"{base}.R"
    if l_name in landmarks and r_name in landmarks:
        ll = frame.to_local(landmarks[l_name].position)
        rl = frame.to_local(landmarks[r_name].position)
        # Average absolute x / y / z for soft symmetry.
        ax = (abs(ll.x) + abs(rl.x)) * 0.5
        ay = (ll.y + rl.y) * 0.5
        az = (ll.z + rl.z) * 0.5
        landmarks[l_name].position = frame.to_world(Vector((ax, ay, az)))
        landmarks[r_name].position = frame.to_world(Vector((-ax, ay, az)))
        for n in (l_name, r_name):
            ev = dict(landmarks[n].evidence or {})
            ev["symmetryApplied"] = True
            landmarks[n].evidence = ev


def correct_face_landmarks(
    mesh_obj,
    *,
    view: Optional[WorldMeshView] = None,
    body: Optional[dict] = None,
    forward_axis: str = "+Y",
    core_only: bool = True,
    **kwargs,
) -> FaceCorrectionResult:
    """Generate FACE_GEOMETRY_CORRECTED landmarks. Never accepts GT kwargs."""
    assert_no_gt_parameters(**kwargs)
    view = view or build_world_mesh_view(mesh_obj)
    region = evaluate_face_region(
        mesh_obj, view=view, body=body, forward_axis=forward_axis
    )
    if not region.eligible or region.headFrame is None:
        return FaceCorrectionResult(
            landmarks={},
            region=region,
            missing=list(ALPHA1_CORE_KEYS),
            notes=["Face region ineligible — detection aborted"],
        )

    frame = region.headFrame
    with generation_scope("correct_face_landmarks"):
        geom = detect_face_geometry_candidates(view, region)
        hits = collect_multiview_candidates(view, frame, geom)
        fused = fuse_multiview_with_geometry(geom, hits, frame)
        swaps = _enforce_laterality(fused, frame)
        for pair in ("eye.center", "eye.inner", "eye.outer", "mouth.corner", "ear.center"):
            _mirror_pair(fused, frame, pair)

        # Centerline features: zero local X.
        for name in ("nose.tip", "mouth.center", "chin"):
            if name not in fused:
                continue
            loc = frame.to_local(fused[name].position)
            loc.x = 0.0
            fused[name].position = frame.to_world(loc)

        corrected: Dict[str, LandmarkPoint] = {}
        rejected: List[str] = []
        for name, lp in fused.items():
            if core_only and name not in ALPHA1_CORE_KEYS:
                continue
            pos = lp.position
            if not point_inside_or_on_mesh(view, pos):
                near, _, dist = nearest_on_mesh(view, pos)
                # Ears/surface landmarks may sit slightly outside — allow larger snap.
                snap_lim = frame.head_height * (0.12 if name.startswith("ear.") else 0.05)
                if near is not None and dist <= snap_lim:
                    pos = near
                else:
                    rejected.append(name)
                    continue
            views = list((lp.evidence or {}).get("views") or [])
            if not views:
                views = list(FACE_ALPHA1_PARAMETERS["multiview"]["views"][:3])
            conf = min(0.95, max(0.45, lp.confidence + 0.08))
            evidence = dict(lp.evidence or {})
            evidence.update(
                {
                    "method": evidence.get("method") or FACE_ALPHA1_PARAMETERS["methods"]["fusion"],
                    "views": views,
                    "candidateCount": int(evidence.get("candidateCount") or evidence.get("multiviewCandidateCount") or 1),
                    "insideMesh": True,
                    "fusion": FACE_ALPHA1_PARAMETERS["methods"]["fusion"],
                }
            )
            if name.endswith(".L") and name[:-2] + ".R" in fused:
                other = fused[name[:-2] + ".R"].position
                evidence["symmetryDeltaMm"] = round(abs(frame.to_local(pos).x + frame.to_local(other).x) * 1000.0, 3)
            corrected[name] = LandmarkPoint(
                name=name,
                position=pos,
                source=FACE_GEOMETRY_CORRECTED,
                confidence=conf,
                side=lp.side,
                evidence=evidence,
            )

        # Recover missing L/R partner by mirroring the surviving side.
        for base in ("eye.center", "eye.inner", "eye.outer", "mouth.corner", "ear.center"):
            l_name, r_name = f"{base}.L", f"{base}.R"
            if l_name in corrected and r_name not in corrected:
                loc = frame.to_local(corrected[l_name].position)
                pos = frame.to_world(Vector((-abs(loc.x), loc.y, loc.z)))
                near, _, _ = nearest_on_mesh(view, pos)
                if near is not None:
                    pos = near
                if point_inside_or_on_mesh(view, pos):
                    src = corrected[l_name]
                    corrected[r_name] = LandmarkPoint(
                        name=r_name,
                        position=pos,
                        source=FACE_GEOMETRY_CORRECTED,
                        confidence=max(0.4, src.confidence - 0.05),
                        side="R",
                        evidence={"method": "MIRROR_FROM_L_V1", "from": l_name, "insideMesh": True},
                    )
            elif r_name in corrected and l_name not in corrected:
                loc = frame.to_local(corrected[r_name].position)
                pos = frame.to_world(Vector((abs(loc.x), loc.y, loc.z)))
                near, _, _ = nearest_on_mesh(view, pos)
                if near is not None:
                    pos = near
                if point_inside_or_on_mesh(view, pos):
                    src = corrected[r_name]
                    corrected[l_name] = LandmarkPoint(
                        name=l_name,
                        position=pos,
                        source=FACE_GEOMETRY_CORRECTED,
                        confidence=max(0.4, src.confidence - 0.05),
                        side="L",
                        evidence={"method": "MIRROR_FROM_R_V1", "from": r_name, "insideMesh": True},
                    )

        missing = [k for k in ALPHA1_CORE_KEYS if k not in corrected]
        return FaceCorrectionResult(
            landmarks=corrected,
            region=region,
            corrected=sorted(corrected.keys()),
            rejected_outside=rejected,
            missing=missing,
            lr_swaps=swaps,
            notes=[
                f"Alpha1 core detection: {len(corrected)}/{len(ALPHA1_CORE_KEYS)}",
                f"Eyeball meshes: {region.eyeballObjects}",
            ],
        )
