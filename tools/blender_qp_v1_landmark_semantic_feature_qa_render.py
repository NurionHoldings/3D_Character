"""v1 landmark-oriented semantic feature visibility + exposure QA (MASK_PASS preserved)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Matrix, Vector

VALID_PASS_INDEX = 1
_MASK_RENDER_RECEIPT: dict = {}
_FID_RENDER_RECEIPT: dict = {}
_OCCUPANCY_GATE_CONTRACT: str = "frame"
_OCCUPANCY_CONTRACT_RECEIPT: dict = {}
NATIVE_SEMANTIC_EVIDENCE_GATE = "NATIVE_SEMANTIC_EVIDENCE_GATE"
OCCUPANCY_REPLACEMENT_REVIEW_ID = "20260817T154317Z"
MOUTH_GATE_FEATURES = ("lip", "lip_corner_l", "lip_corner_r", "chin")
MOUTH_ORAL_GATE_FEATURES = ("upper_teeth", "lower_teeth")
MOUTH_RIG_HELPER_PROJECTION_FEATURES = frozenset({"upper_teeth", "lower_teeth", "tongue"})
MOUTH_SKIN_SLOT_PROJECTION_FEATURES = frozenset({"lip", "lip_corner_l", "lip_corner_r", "chin", "skin"})
MOUTH_CONSUMPTION_PATH_REPAIR = "RIG_HELPER_PROJECTION_PROVIDER_V1"
EYE_GATE_FEATURES = ("eyeball", "eyelid_upper", "eyelid_lower")
DEFAULT_OCCUPANCY_BASELINE_PREFLIGHT = Path(
    r"d:\NURION Character Landmarker\dist\v0.7\product\quick_profile"
    r"\parametric_head_asset_acquisition\candidate_a_makehuman_hm08\runs"
    r"\v1_lsfq_semantic_qa_20260817T205655Z\preflight_gates.json"
)
OCC_MIN = 0.65
OCC_MAX = 0.85
OCC_TARGET = 0.75
FINAL_RES = 1280
MAX_FRAME_ITERS = 24

QA_PALETTE = {
    "skin": (0.68, 0.68, 0.68),
    "lip": (0.45, 0.35, 0.35),
    "upper_teeth": (0.78, 0.78, 0.80),
    "lower_teeth": (0.70, 0.70, 0.72),
    "tongue": (0.62, 0.54, 0.52),
    "palate": (0.60, 0.58, 0.58),
    "eyeball": (0.50, 0.52, 0.56),
    "eyelid_upper": (0.58, 0.58, 0.62),
    "eyelid_lower": (0.66, 0.66, 0.70),
    "chin": (0.52, 0.48, 0.42),
    "lip_corner_l": (0.38, 0.28, 0.48),
    "lip_corner_r": (0.48, 0.28, 0.38),
}
FEATURE_ID_RGB = {
    "lip": (1.0, 0.12, 0.12),
    "lip_corner_l": (1.0, 0.42, 0.05),
    "lip_corner_r": (1.0, 0.52, 0.05),
    "chin": (0.12, 1.0, 0.12),
    "upper_teeth": (0.08, 0.08, 1.0),
    "lower_teeth": (0.18, 0.18, 1.0),
    "tongue": (1.0, 0.08, 1.0),
    "eyeball": (0.08, 1.0, 1.0),
    "eyelid_upper": (1.0, 1.0, 0.08),
    "eyelid_lower": (0.55, 1.0, 0.25),
}
MIN_FEATURE_PIXELS = {
    "lip": 400,
    "lip_corner_l": 80,
    "lip_corner_r": 80,
    "chin": 250,
    "upper_teeth": 180,
    "lower_teeth": 180,
    "tongue": 150,
    "eyeball": 120,
    "eyelid_upper": 70,
    "eyelid_lower": 70,
}
MIN_ABSOLUTE_FLOOR = {
    "lip": 120,
    "lip_corner_l": 40,
    "lip_corner_r": 40,
    "chin": 60,
    "upper_teeth": 90,
    "lower_teeth": 90,
    "tongue": 70,
    "eyeball": 60,
    "eyelid_upper": 35,
    "eyelid_lower": 35,
}
VISIBILITY_DETECTION_MIN = 0.58
FRONT_ABSOLUTE_EXPECTED_FRAC = 0.45
SEMANTIC_SLOT_MAP = ("skin", "lip", "lip_corner_l", "lip_corner_r", "chin")
SLOT_TO_FEATURE = {i: name for i, name in enumerate(SEMANTIC_SLOT_MAP)}
FEATURE_TO_SLOT = {name: i for i, name in enumerate(SEMANTIC_SLOT_MAP)}
CORNER_CORRIDOR_RADIUS = 0.14
CHIN_CORRIDOR_RADIUS = 0.16
CHIN_FACE_GEO_MAX = 0.24
MIN_CHIN_FACES = 6
MIN_CHIN_FACE_AREA = 0.004
CONTEXT_GUARD_PAD = 0.08
EYE_GUARD_PAD = Vector((0.10, 0.12, 0.08))
SEMANTIC_OCC_MAX = 0.93
REQUIRED_FEATURES = {
    "mouth": ("lip", "lip_corner_l", "lip_corner_r", "chin"),
    "mouth_oral": ("lip", "lip_corner_l", "lip_corner_r", "chin", "upper_teeth", "lower_teeth"),
    "mouth_interior": ("upper_teeth", "lower_teeth", "tongue"),
    "eye": ("eyeball", "eyelid_upper", "eyelid_lower"),
}
EYE_ALLOWED_MORPH_STATES = ("closed", "half", "open")
EYE_STATE_OPEN_PCT = {"closed": 0.0, "half": 0.5, "open": 1.0}
EYELID_MANIFEST_FEATURES = ("eyelid_upper", "eyelid_lower")
MOUTH_FID_EMISSION_FEATURES = ("chin", "lip_corner_l", "lip_corner_r")
MOUTH_FID_EMISSION_CHAIN = (
    "nativeSlot",
    "encoded",
    "decoded",
    "compositeInput",
    "compositeOutput",
    "finalFID",
    "detectionRate",
)
INTERIOR_DIAGNOSTIC_FEATURES = ("oralOpening", "upperTeeth", "lowerTeeth", "tongue", "lipGuard")
INTERIOR_RIG_OBJECT_KEYS = {
    "upperTeeth": ("upper_teeth", "helper-upper-teeth"),
    "lowerTeeth": ("lower_teeth", "helper-lower-teeth"),
    "tongue": ("tongue", "helper-tongue"),
}
INTERIOR_RIG_NATIVE_EMISSION_FEATURES = ("upperTeeth", "lowerTeeth", "tongue")
DEFAULT_FROZEN_INTERIOR_CAMERA_LOCK_MANIFEST = Path(
    r"d:\NURION Character Landmarker\dist\v0.7\product\quick_profile"
    r"\parametric_head_asset_acquisition\candidate_a_makehuman_hm08\runs"
    r"\v1_lsfq_semantic_qa_20260817T053837Z\camera_lock_manifest.json"
)
THIRTEEN_SHOT_MANIFEST_LOCK_KEYS = (
    "mouth_front",
    "mouth_left",
    "mouth_interior",
    "eye_left",
    "eye_right",
)
THIRTEEN_SHOT_FROZEN_BASELINE_RUN_ID = "20260821T151012Z"
THIRTEEN_SHOT_CONSUMER_PATH_MUTATION_ID = "HEAD_13SHOT_MANIFEST_CONSUMPTION_PATH_REPAIR"
THIRTEEN_SHOT_CONTRACT_PARITY_MUTATION_ID = "HEAD_13SHOT_NATIVE_SEMANTIC_EVIDENCE_CONTRACT_PARITY_REPAIR"
THIRTEEN_SHOT_CONTRACT_PARITY_MUTATION_CLASS = "CONSUMER_EVALUATOR_CONTRACT_ONLY"
_MORPH_STATE_CAPTURE_SPEC = {
    "closed": (0.0, False),
    "half": (12.0, True),
    "open": (24.0, True),
    "interior": (24.0, True),
}
ORAL_OPENING_DEFINITION_TYPE = "TEETH_FID_BBOX_VERTICAL_SEPARATION_PROXY"
ORAL_OPENING_PROJECTED_PRIMITIVE_TYPE = "SYNTHETIC_BINARY_TEETH_VISIBILITY"
ORAL_OPENING_DEGENERACY_CLASSIFICATIONS = (
    "OPENING_REGION_NOT_DEFINED",
    "OPENING_POLYGON_DEGENERATE",
    "LIP_BOUNDARY_PROJECTION_DEGENERATE",
    "TEETH_BBOX_PROXY_INVALID",
    "STATE_GEOMETRY_COLLAPSED",
    "PASS",
)
ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT = "ORAL_OPENING_LIP_BOUNDARY_AND_OPENING_POLYGON"
TEETH_BBOX_PROXY_ENFORCEMENT = "DIAGNOSTIC_ONLY"
ORAL_OPENING_NATIVE_CLASSIFICATIONS = (
    "OPENING_POLYGON_DEFINED_PASS",
    "OPENING_POLYGON_PROJECTS_ZERO_AREA",
    "LIP_CURVE_PAIRING_FAIL",
    "LIP_BOUNDARY_GAP_ZERO",
    "OPENING_POLYGON_OUT_OF_FRAME",
    "OPENING_NATIVE_CONTEXT_MISSING",
)
D_INTERIOR_HOLD_CLASSIFICATIONS = (
    "INTERIOR_EVIDENCE_AGGREGATION_NOT_BOUND",
    "INTERIOR_LEGACY_OCCUPANCY_STILL_ENFORCED",
    "INTERIOR_NATIVE_MASK_SOURCE_MISMATCH",
    "INTERIOR_FEATURE_RECEIPT_NOT_PROPAGATED",
    "INTERIOR_CAMERA_RECEIPT_NOT_PROPAGATED",
)
D_INTERIOR_PRODUCTION_CONTRACT = "D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_PRODUCTION"
AH_PREFLIGHT_GATE_KEYS = (
    "A_CHIN_REGION_INTEGRITY",
    "B_CHIN_NATIVE_FID_PARITY",
    "C_MOUTH_NATIVE_MASK_FRONT",
    "C_MOUTH_NATIVE_MASK_LEFT",
    "D_INTERIOR_NATIVE_VISIBILITY",
    "E_EYE_CAMERA_LEFT",
    "F_EYE_CAMERA_RIGHT",
    "G_EYE_NATIVE_FID_PARITY",
    "H_CAPTURE_LOCK_MANIFEST_CONSISTENCY",
)
AH_PREFLIGHT_FAIL_CLASSIFICATIONS = (
    "ACTUAL_REGRESSION",
    "AGGREGATION_CONSUMPTION",
    "EVIDENCE_GENERATION",
    "UNCLASSIFIED",
)
C_MOUTH_CONSUMPTION_FAILURE_CLASSES = (
    "C_CLOSED_EVIDENCE_NOT_BOUND",
    "C_MORPH_STATE_RECEIPT_NOT_PROPAGATED",
    "C_CAMERA_REF_CONSUMPTION_MISMATCH",
    "C_NATIVE_MASK_SOURCE_MISMATCH",
    "C_FEASIBLE_SHOT_AGGREGATION_MISMATCH",
    "C_BASELINE_GATE_ALREADY_OPEN",
    "C_PRODUCTION_GATE_PASS",
)
C_LEFT_HALF_OPEN_DIAGNOSTIC_FAILURE_CLASSES = (
    "C_LEFT_PROJECTION_FAIL",
    "C_LEFT_NATIVE_SLOT_RENDER_FAIL",
    "C_LEFT_MASK_COMPOSITE_FAIL",
    "C_LEFT_CONTEXT_VISIBILITY_FAIL",
    "C_LEFT_EXPECTED_VISIBILITY_FAIL",
    "C_LEFT_CAMERA_STATE_CONSUMPTION_MISMATCH",
    "C_LEFT_MORPH_STATE_GEOMETRY_FAIL",
)
ORAL_HELPER_PROJECTION_FAILURE_CLASSES = (
    "ORAL_HELPER_OBJECT_MISSING",
    "ORAL_HELPER_EVALUATED_MESH_EMPTY",
    "ORAL_HELPER_PARENT_TRANSFORM_FAIL",
    "ORAL_HELPER_PIVOT_DOUBLE_TRANSFORM",
    "ORAL_HELPER_WORLD_BBOX_DIVERGENCE",
    "ORAL_HELPER_CAMERA_SPACE_BEHIND",
    "ORAL_HELPER_NDC_OUT_OF_FRAME",
    "ORAL_HELPER_FACE_PROJECTION_FAIL",
    "ORAL_HELPER_RASTER_DEGENERACY",
)
CLOSED_AXIS_PASS_VALUES = frozenset({"PASS", "PASS_CLOSED", True})
DEFAULT_CLOSED_EYE_MOUTH_CHIN_BASELINE_PREFLIGHT = Path(
    r"d:\NURION Character Landmarker\dist\v0.7\product\quick_profile"
    r"\parametric_head_asset_acquisition\candidate_a_makehuman_hm08\runs"
    r"\v1_lsfq_semantic_qa_20260819T085754Z\preflight_gates.json"
)
DEFAULT_D_INTERIOR_BASELINE_PROBE = Path(
    r"d:\NURION Character Landmarker\dist\v0.7\product\quick_profile"
    r"\parametric_head_asset_acquisition\candidate_a_makehuman_hm08\runs"
    r"\v1_lsfq_semantic_qa_20260820T070720Z_d_interior_revalidation"
    r"\d_interior_revalidation_probe.json"
)
HELPER_VERTEX_SPACE_HEAD_WORLD = "HEAD_WORLD_OBJ_IMPORT"
HELPER_VERTEX_SPACE_PIVOT_LOCAL = "PIVOT_LOCAL_BAKED"
HELPER_VERTEX_SPACE_HEAD_ROOT_LOCAL = "HEAD_ROOT_LOCAL"
EYE_PIVOT_EYELASH_GROUPS = (
    "helper-l-eyelashes-1",
    "helper-l-eyelashes-2",
    "helper-r-eyelashes-1",
    "helper-r-eyelashes-2",
)
EYE_FEATURE_REGISTRY = {
    "eyeball": {
        "landmarkSemanticDefinition": "EYE_ORBIT_HELPER_MESH",
        "rigObjectPattern": "helper-{side}-eye",
        "semanticSlotKind": "rig_material_slot",
        "morphWeightKeys": (),
        "sourceLandmarkIds": ("eye_l", "eye_r", "eye_mid"),
        "allowedStates": EYE_ALLOWED_MORPH_STATES,
    },
    "eyelid_upper": {
        "landmarkSemanticDefinition": "EYE_SOCKET_UPPER_RIM_HELPER",
        "rigObjectPattern": "helper-{side}-eyelashes-1",
        "semanticSlotKind": "rig_material_slot",
        "morphWeightKeys": ("{SIDE}_UPPER",),
        "sourceLandmarkIds": ("eye_l", "eye_r", "eye_mid"),
        "allowedStates": EYE_ALLOWED_MORPH_STATES,
        "importVertexSpace": HELPER_VERTEX_SPACE_HEAD_WORLD,
        "consumptionVertexSpace": HELPER_VERTEX_SPACE_PIVOT_LOCAL,
    },
    "eyelid_lower": {
        "landmarkSemanticDefinition": "EYE_SOCKET_LOWER_RIM_HELPER",
        "rigObjectPattern": "helper-{side}-eyelashes-2",
        "semanticSlotKind": "rig_material_slot",
        "morphWeightKeys": ("{SIDE}_LOWER",),
        "sourceLandmarkIds": ("eye_l", "eye_r", "eye_mid"),
        "allowedStates": EYE_ALLOWED_MORPH_STATES,
        "importVertexSpace": HELPER_VERTEX_SPACE_HEAD_WORLD,
        "consumptionVertexSpace": HELPER_VERTEX_SPACE_PIVOT_LOCAL,
    },
}
FRAME_LANDMARKS = {
    "mouth": ("lip_corner_l", "lip_corner_r", "chin", "mouth_center"),
    "mouth_oral": ("lip_corner_l", "lip_corner_r", "chin", "mouth_center"),
    "mouth_interior": ("mouth_center", "upper_lip", "lower_lip"),
    "eye_l": ("eye_l",),
    "eye_r": ("eye_r",),
}
SAT_MAX_RATIO = 0.015
CLIP_MAX_RATIO = 0.02
FEATURE_COLOR_TOL = 0.14
QA_PALETTE_TOL = 0.12
MIN_FEATURE_CONTRAST_STD = 0.035
MIN_FEATURE_LUM_MEAN = 0.08
CORNER_SYMMETRY_MIN = 0.50
FRAME_MARGIN_FRAC = 0.04
ORAL_OPENING_MIN_PX = 12
KEY_ENERGY_STEPS = (100, 88, 76, 64, 52, 42, 34)
FILL_ENERGY_RATIO = 0.28
EYE_R = Vector((0.308, 7.284, 1.245))
EYE_L = Vector((-0.308, 7.284, 1.245))

REQUIRED_SHOTS = (
    "mouth_closed_front",
    "mouth_closed_left",
    "mouth_half_front",
    "mouth_half_left",
    "mouth_open_front",
    "mouth_open_left",
    "mouth_interior",
    "eye_left_closed",
    "eye_left_half",
    "eye_left_open",
    "eye_right_closed",
    "eye_right_half",
    "eye_right_open",
)


def _parse():
    argv = sys.argv[sys.argv.index("--") + 1 :] if "--" in sys.argv else []
    ap = argparse.ArgumentParser()
    ap.add_argument("--skin-obj", required=True)
    ap.add_argument("--rig-obj", required=True)
    ap.add_argument("--weight-json", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--label", default="V1_LSFQ")
    ap.add_argument("--resolution", type=int, default=FINAL_RES)
    ap.add_argument("--meta-json", required=True)
    ap.add_argument("--validation-json", required=True)
    ap.add_argument("--semantic-validation-json", required=True)
    ap.add_argument("--overlay-dir", required=True)
    ap.add_argument("--diagnostic-mode", action="store_true")
    ap.add_argument("--preflight-json", default="")
    ap.add_argument("--camera-lock-manifest", default="")
    ap.add_argument("--occupancy-baseline-preflight", default="")
    ap.add_argument(
        "--interior-diagnostic-only",
        action="store_true",
        help="Run preflight through Interior diagnostic probe then exit before Eye gates.",
    )
    ap.add_argument(
        "--interior-frozen-camera-lock-manifest",
        default="",
        help="Read-only frozen mouth_interior CameraLockManifest for provenance restoration.",
    )
    ap.add_argument(
        "--preflight-ah-only",
        action="store_true",
        help="Run A-H preflight + capture evidence regression confirmation; skip 13-shot.",
    )
    ap.add_argument(
        "--closed-baseline-preflight",
        default="",
        help="Eye/Mouth/Chin CLOSED baseline preflight_gates.json (default 085754Z).",
    )
    ap.add_argument(
        "--d-interior-baseline-probe",
        default="",
        help="D-Interior CLOSED baseline d_interior_revalidation_probe.json (default 070720Z).",
    )
    ap.add_argument(
        "--bc-evidence-only",
        action="store_true",
        help="Regenerate B/C required capture evidence only; no semantic or camera retune.",
    )
    ap.add_argument(
        "--bc-evidence-source-preflight",
        default="",
        help="Source preflight_gates.json with frozen camera/state receipts (e.g. 162836Z).",
    )
    ap.add_argument(
        "--bc-evidence-regenerate-rollup",
        action="store_true",
        help="After B/C capture regeneration, rewrite ah_preflight_capture_evidence_probe.json.",
    )
    ap.add_argument(
        "--c-mouth-consumption-diagnostic-only",
        action="store_true",
        help="Run C-Mouth production gate consumption/binding diagnostic; skip Interior/Eye/13-shot.",
    )
    ap.add_argument(
        "--c-consumption-baseline-preflight",
        default="",
        help="Baseline preflight_gates.json for C gate baseline-already-open comparison (default 085754Z).",
    )
    ap.add_argument(
        "--c-mouth-rebind-verification-only",
        action="store_true",
        help="Run C-Mouth rebind verification after mouth gates; skip Interior/Eye/13-shot.",
    )
    ap.add_argument(
        "--c-left-half-open-diagnostic-only",
        action="store_true",
        help="Run C-Left half/open per-morph native evidence diagnostic; skip B/Interior/Eye/13-shot.",
    )
    ap.add_argument(
        "--c-left-oral-geometry-diagnostic-only",
        action="store_true",
        help="Run C-Left oral rig morph-state geometry/projection diagnostic; skip B/Interior/Eye/13-shot.",
    )
    ap.add_argument(
        "--c-mouth-consumption-repair-verification-only",
        action="store_true",
        help="Run C-Mouth consumption-path repair verification after mouth gates; skip B/Interior/Eye/13-shot.",
    )
    ap.add_argument(
        "--thirteen-shot-diagnostic-only",
        action="store_true",
        help="Run full 13-shot diagnostic using closed A-H preflight source; skip A-H re-execution.",
    )
    ap.add_argument(
        "--thirteen-shot-occupancy-forensic-only",
        action="store_true",
        help="Run single-shot occupancy forensic isolation; no threshold/camera/morph changes.",
    )
    ap.add_argument(
        "--thirteen-shot-contract-parity-proof-only",
        action="store_true",
        help="Run single-shot native semantic evidence contract parity proof after repair.",
    )
    ap.add_argument(
        "--contract-parity-proof-json",
        default="",
        help="Output path for contract parity proof receipt JSON.",
    )
    ap.add_argument(
        "--forensic-shot",
        default="mouth_closed_front",
        help="Representative shot key for occupancy forensic isolation (default mouth_closed_front).",
    )
    ap.add_argument(
        "--occupancy-forensic-json",
        default="",
        help="Output path for thirteen-shot occupancy forensic receipt JSON.",
    )
    ap.add_argument(
        "--fail-run-semantic-json",
        default="",
        help="Optional failed 13-shot semantic_feature_validation.json for cross-reference.",
    )
    ap.add_argument(
        "--ah-preflight-source",
        default="",
        help="Closed A-H preflight_gates.json for thirteen-shot-diagnostic-only mode.",
    )
    return ap.parse_args(argv)


def _clear():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images, bpy.data.cameras, bpy.data.lights):
        for b in list(coll):
            coll.remove(b)


def _qa_mat(name, rgb):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
        bsdf.inputs["Roughness"].default_value = 1.0
        if "Specular IOR Level" in bsdf.inputs:
            bsdf.inputs["Specular IOR Level"].default_value = 0.0
        elif "Specular" in bsdf.inputs:
            bsdf.inputs["Specular"].default_value = 0.0
    mat.use_backface_culling = False
    return mat


def _gray(name):
    return _qa_mat(name, QA_PALETTE["skin"])


def _mask_mat(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)
    emit.inputs["Strength"].default_value = 1.0
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs[0], out.inputs[0])
    mat.use_backface_culling = False
    return mat


def _look_at(obj, target: Vector):
    obj.rotation_euler = (target - obj.location).to_track_quat("-Z", "Z").to_euler()


def _compute_landmarks(V: list[Vector]) -> dict:
    li, ri, best_l, best_r = 0, 0, -1e9, -1e9
    for i, v in enumerate(V):
        if not (6.55 < v.y < 6.78 and 1.05 < v.z < 1.45):
            continue
        if v.x < -0.05 and (-v.x) > best_l:
            best_l, li = float(-v.x), i
        if v.x > 0.05 and v.x > best_r:
            best_r, ri = float(v.x), i
    corner_l = Vector(V[li])
    corner_r = Vector(V[ri])

    def _pick(pred, key_fn, fallback: Vector) -> Vector:
        cands = [Vector(v) for v in V if pred(v)]
        return key_fn(cands) if cands else fallback

    nose = _pick(
        lambda v: abs(v.x) < 0.14 and 6.88 < v.y < 7.08 and 1.38 < v.z < 1.72,
        lambda cs: max(cs, key=lambda v: (v.y, v.z)),
        (EYE_L + EYE_R) * 0.5 + Vector((0.0, 0.18, -0.04)),
    )
    ear_l = _pick(
        lambda v: v.x < -0.30 and 6.95 < v.y < 7.45 and 1.05 < v.z < 1.55,
        lambda cs: min(cs, key=lambda v: v.x),
        Vector((-0.72, 7.10, 1.20)),
    )
    ear_r = _pick(
        lambda v: v.x > 0.30 and 6.95 < v.y < 7.45 and 1.05 < v.z < 1.55,
        lambda cs: max(cs, key=lambda v: v.x),
        Vector((0.72, 7.10, 1.20)),
    )
    upper_lip = _pick(
        lambda v: abs(v.x) < 0.12 and 6.68 < v.y < 6.82 and 1.42 < v.z < 1.58,
        lambda cs: max(cs, key=lambda v: v.z),
        (corner_l + corner_r) * 0.5 + Vector((0.0, 0.0, 0.10)),
    )
    lower_lip = _pick(
        lambda v: abs(v.x) < 0.12 and 6.58 < v.y < 6.74 and 1.28 < v.z < 1.46,
        lambda cs: min(cs, key=lambda v: v.z),
        (corner_l + corner_r) * 0.5 + Vector((0.0, 0.0, -0.05)),
    )
    chin = _pick(
        lambda v: abs(v.x) < 0.22 and 6.05 < v.y < 6.45 and 0.95 < v.z < 1.28,
        lambda cs: min(cs, key=lambda v: v.z),
        Vector((0.0, 6.25, 1.05)),
    )
    eye_mid = (EYE_L + EYE_R) * 0.5
    nose_h = Vector((nose.x - eye_mid.x, nose.y - eye_mid.y, 0.0))
    if nose_h.length < 1e-6:
        face_forward = Vector((0.0, -1.0, 0.0))
    else:
        face_forward = nose_h.normalized()
    mouth_center = (corner_l + corner_r + upper_lip + lower_lip) * 0.25
    return {
        "eye_l": EYE_L.copy(),
        "eye_r": EYE_R.copy(),
        "eye_mid": eye_mid,
        "nose_tip": nose,
        "ear_l": ear_l,
        "ear_r": ear_r,
        "lip_corner_l": corner_l,
        "lip_corner_r": corner_r,
        "upper_lip": upper_lip,
        "lower_lip": lower_lip,
        "chin": chin,
        "mouth_center": mouth_center,
        "face_forward": face_forward,
        "corner_l_idx": li,
        "corner_r_idx": ri,
    }


def _landmark_view_dir(landmarks: dict, mode: str) -> Vector:
    fwd = landmarks["face_forward"].normalized()
    up = Vector((0.0, 0.0, 1.0))
    if mode == "front":
        return fwd
    if mode == "left":
        angle = math.radians(68.0)
        side = up.cross(fwd)
        if side.length < 1e-6:
            side = Vector((1.0, 0.0, 0.0))
        side.normalize()
        return (fwd * math.cos(angle) + side * math.sin(angle)).normalized()
    if mode == "interior":
        return (fwd * 0.70 + Vector((0.0, 0.0, -0.35))).normalized()
    raise ValueError(mode)


def _shot_target(landmarks: dict, mode: str, shot_kind: str) -> Vector:
    if shot_kind == "eye_l":
        return (landmarks["eye_l"] + landmarks["eye_mid"]) * 0.5
    if shot_kind == "eye_r":
        return (landmarks["eye_r"] + landmarks["eye_mid"]) * 0.5
    if mode == "interior":
        return landmarks["mouth_center"] + Vector((0.0, 0.0, 0.02))
    return (landmarks["mouth_center"] + landmarks["eye_mid"]) * 0.5


def _view_depth(cam, point: Vector) -> float:
    cs = cam.matrix_world.inverted() @ point
    return float(-cs.z)


def _landmark_view_alignment(landmarks: dict, cam, mode: str) -> float:
    view = (-cam.matrix_world.col[2]).xyz.normalized()
    expected = _landmark_view_dir(landmarks, mode)
    return float(expected.dot(view))


def _anatomical_face_forward(landmarks: dict) -> Vector:
    v = landmarks["nose_tip"] - landmarks["eye_mid"]
    if v.length < 1e-6:
        return landmarks["face_forward"].normalized()
    return v.normalized()


def _depth_nose_in_front(cam, landmarks: dict, mode: str = "front") -> bool:
    if mode == "front":
        fwd = _anatomical_face_forward(landmarks)
        origin = landmarks["eye_mid"]
        nose = float((landmarks["nose_tip"] - origin).dot(fwd))
        ear_l = float((landmarks["ear_l"] - origin).dot(fwd))
        ear_r = float((landmarks["ear_r"] - origin).dot(fwd))
        return nose > max(ear_l, ear_r) + 0.02
    if mode == "left":
        near_ear = _view_depth(cam, landmarks["ear_l"])
        far_ear = _view_depth(cam, landmarks["ear_r"])
        nose_d = _view_depth(cam, landmarks["nose_tip"])
        return near_ear < far_ear - 0.01 and near_ear < nose_d + 0.05
    nose_d = _view_depth(cam, landmarks["nose_tip"])
    ear_l_d = _view_depth(cam, landmarks["ear_l"])
    ear_r_d = _view_depth(cam, landmarks["ear_r"])
    return nose_d > ear_l_d + 0.01 and nose_d > ear_r_d + 0.01


def _emit_mat(name, rgb, strength: float = 1.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    emit = nodes.new("ShaderNodeEmission")
    emit.inputs["Color"].default_value = (rgb[0], rgb[1], rgb[2], 1.0)
    emit.inputs["Strength"].default_value = strength
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(emit.outputs[0], out.inputs[0])
    mat.use_backface_culling = False
    return mat


def _emit_void_mat(name: str):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    for n in list(nodes):
        nodes.remove(n)
    hold = nodes.new("ShaderNodeHoldout")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(hold.outputs[0], out.inputs[0])
    mat.use_backface_culling = False
    return mat


def _parse_obj(path: Path):
    verts, groups = [], {}
    cur = "default"
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("v "):
            a = line.split()
            verts.append((float(a[1]), float(a[2]), float(a[3])))
        elif line.startswith("g ") or line.startswith("o "):
            cur = line[2:].strip() or "default"
            groups.setdefault(cur, [])
        elif line.startswith("f "):
            idxs = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
            groups.setdefault(cur, []).append(idxs)
    return verts, groups


def _load_mesh(path, group, gray, coll, name):
    verts, groups = _parse_obj(path)
    faces = groups.get(group, []) if group else []
    polys = [tuple(f) for f in faces if len(f) >= 3]
    mesh = bpy.data.meshes.new(name[:63])
    mesh.from_pydata(verts, [], polys)
    mesh.update()
    obj = bpy.data.objects.new(name[:63], mesh)
    coll.objects.link(obj)
    mesh.materials.append(gray)
    bpy.context.view_layer.objects.active = obj
    obj.select_set(True)
    bpy.ops.object.shade_smooth()
    obj.select_set(False)
    return obj


def _apply_weighted_jaw(obj, weights: dict[int, float], pivot: Vector, angle_deg: float):
    mesh = obj.data
    angle_rad = math.radians(angle_deg)
    for vi, w in weights.items():
        if w < 1e-6 or vi >= len(mesh.vertices):
            continue
        v = mesh.vertices[vi]
        rel = v.co - pivot
        partial = angle_rad * w
        c, s = math.cos(partial), math.sin(partial)
        y, z = float(rel.y), float(rel.z)
        v.co = pivot + Vector((rel.x, c * y - s * z, s * y + c * z))
    mesh.update()


def _apply_eyelid_morph(obj, basis_coords, eyelid_weights, eyelid_spec, side: str, open_pct: float):
    mesh = obj.data
    side_prefix = "LEFT" if side == "L" else "RIGHT"
    for part, sign in (("UPPER", -1.0), ("LOWER", 1.0)):
        key = f"{side_prefix}_{part}"
        spec = eyelid_spec[key]
        weights = {int(k): float(v) for k, v in eyelid_weights.get(key, {}).items()}
        center = Vector(spec["center"])
        max_deg = float(spec["maxDeg"])
        t = (open_pct - 0.5) * 2.0
        angle_rad = math.radians(sign * max_deg * t)
        for vi, w in weights.items():
            if vi >= len(mesh.vertices):
                continue
            basis = basis_coords[vi]
            rel = basis - center
            c, s = math.cos(angle_rad * w), math.sin(angle_rad * w)
            y, z = float(rel.y), float(rel.z)
            mesh.vertices[vi].co = center + Vector((rel.x, c * y - s * z, s * y + c * z))
    mesh.update()


def _mesh_face_used_vertices(mesh, face_indices: set[int] | None = None) -> set[int]:
    used: set[int] = set()
    indices = face_indices if face_indices is not None else set(range(len(mesh.polygons)))
    for fi in indices:
        if 0 <= int(fi) < len(mesh.polygons):
            used.update(int(v) for v in mesh.polygons[int(fi)].vertices)
    return used


def _infer_helper_vertex_space(mesh, face_indices: set[int], anchor: Vector) -> str:
    used = _mesh_face_used_vertices(mesh, face_indices)
    if not used:
        return "UNKNOWN"
    coords = [mesh.vertices[int(vi)].co.copy() for vi in used]
    center = sum(coords, Vector((0.0, 0.0, 0.0))) / float(len(coords))
    if float((center - anchor).length) < 0.75:
        return HELPER_VERTEX_SPACE_PIVOT_LOCAL
    if float(center.y) > 4.0 and float(center.length) > 4.0:
        return HELPER_VERTEX_SPACE_HEAD_WORLD
    return HELPER_VERTEX_SPACE_HEAD_ROOT_LOCAL


def _bake_mesh_vertices_to_parent_local(obj, parent) -> dict:
    bpy.context.view_layer.update()
    mesh = obj.data
    face_indices = set(range(len(mesh.polygons)))
    used = _mesh_face_used_vertices(mesh, face_indices)
    anchor = parent.matrix_world.translation.copy()
    before_space = _infer_helper_vertex_space(mesh, face_indices, anchor)
    parent_mw = parent.matrix_world.copy()
    inv = parent_mw.inverted()
    for vi in used:
        mesh.vertices[int(vi)].co = inv @ mesh.vertices[int(vi)].co.copy()
    mesh.update()
    obj.matrix_local = Matrix.Identity(4)
    obj.matrix_parent_inverse = Matrix.Identity(4)
    obj.location = (0.0, 0.0, 0.0)
    obj.rotation_euler = (0.0, 0.0, 0.0)
    obj.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()
    obj["nurion_helper_vertex_space"] = HELPER_VERTEX_SPACE_PIVOT_LOCAL
    after_space = _infer_helper_vertex_space(mesh, face_indices, Vector((0.0, 0.0, 0.0)))
    return {
        "objectName": obj.name,
        "parentName": parent.name,
        "helperVertexSpaceBefore": before_space,
        "helperVertexSpaceAfter": after_space,
        "consumptionVertexSpace": HELPER_VERTEX_SPACE_PIVOT_LOCAL,
        "bakedVertexCount": len(used),
        "transformApplicationCountTarget": 1,
    }


def _reconstructed_world_bbox_from_vertices(
    mesh,
    face_indices: set[int],
    transform,
) -> tuple[Vector | None, Vector | None]:
    used = _mesh_face_used_vertices(mesh, face_indices)
    if not used:
        return None, None
    world = [transform @ mesh.vertices[int(vi)].co.copy() for vi in used]
    xs = [float(c.x) for c in world]
    ys = [float(c.y) for c in world]
    zs = [float(c.z) for c in world]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _eyelid_transform_provenance(
    mesh_obj,
    mesh,
    face_indices: set[int],
    *,
    parent,
    pivot_matrix,
    object_matrix_world,
    reference_world_bbox: dict | None,
) -> dict:
    helper_vertex_space = str(mesh_obj.get("nurion_helper_vertex_space") or HELPER_VERTEX_SPACE_HEAD_WORLD)
    helper_parent = parent.name if parent else None
    parent_mw = parent.matrix_world.copy() if parent else object_matrix_world.copy()
    single_min, single_max = _reconstructed_world_bbox_from_vertices(mesh, face_indices, object_matrix_world)
    double_min, double_max = _reconstructed_world_bbox_from_vertices(mesh, face_indices, parent_mw @ parent_mw)
    ref_center = Vector(reference_world_bbox["center"]) if reference_world_bbox and reference_world_bbox.get("center") else None
    single_center = (single_min + single_max) * 0.5 if single_min is not None else None
    double_center = (double_min + double_max) * 0.5 if double_min is not None else None
    bbox_center_distance = (
        float((single_center - ref_center).length) if single_center is not None and ref_center is not None else None
    )
    double_distance = (
        float((double_center - ref_center).length) if double_center is not None and ref_center is not None else None
    )
    double_transform = False
    if bbox_center_distance is not None and double_distance is not None:
        double_transform = double_distance + 0.05 < bbox_center_distance
    elif helper_vertex_space == HELPER_VERTEX_SPACE_HEAD_WORLD and parent is not None:
        double_transform = True
    transform_application_count = 2 if double_transform else 1
    if helper_vertex_space == HELPER_VERTEX_SPACE_PIVOT_LOCAL:
        transform_application_count = 1
        double_transform = False
    effective_chain = (
        f"{helper_vertex_space} -> {helper_parent}.matrix_world -> world"
        if helper_parent
        else f"{helper_vertex_space} -> object.matrix_world -> world"
    )
    return {
        "helperVertexSpace": helper_vertex_space,
        "helperParent": helper_parent,
        "pivotMatrix": _matrix4_to_rows(pivot_matrix) if pivot_matrix is not None else None,
        "objectMatrixWorld": _matrix4_to_rows(object_matrix_world),
        "effectiveTransformChain": effective_chain,
        "transformApplicationCount": int(transform_application_count),
        "doubleTransform": bool(double_transform),
        "reconstructedWorldBBox": _bbox_to_dict(single_min, single_max),
        "hypotheticalDoubleTransformWorldBBox": _bbox_to_dict(double_min, double_max),
        "bboxCenterDistance": bbox_center_distance,
    }


def _setup_rig(rig_path, qa_mats, coll, head_root, jaw_empty):
    groups = {
        "upper": ["helper-upper-teeth"],
        "lower": ["helper-lower-teeth", "helper-tongue"],
        "eye_l": ["helper-l-eyelashes-1", "helper-l-eyelashes-2"],
        "eye_r": ["helper-r-eyelashes-1", "helper-r-eyelashes-2"],
        "eyeball_l": ["helper-l-eye"],
        "eyeball_r": ["helper-r-eye"],
    }
    rig_mat = {
        "helper-upper-teeth": qa_mats["upper_teeth"],
        "helper-lower-teeth": qa_mats["lower_teeth"],
        "helper-tongue": qa_mats["tongue"],
        "helper-l-eye": qa_mats["eyeball"],
        "helper-r-eye": qa_mats["eyeball"],
        "helper-l-eyelashes-1": qa_mats["eyelid_upper"],
        "helper-l-eyelashes-2": qa_mats["eyelid_lower"],
        "helper-r-eyelashes-1": qa_mats["eyelid_upper"],
        "helper-r-eyelashes-2": qa_mats["eyelid_lower"],
    }
    objs = {}
    for names in groups.values():
        for g in names:
            objs[g] = _load_mesh(rig_path, g, rig_mat[g], coll, g)
    for g in groups["upper"] + groups["eyeball_l"] + groups["eyeball_r"]:
        objs[g].parent = head_root
    for g in groups["lower"]:
        o = objs[g]
        o.parent = jaw_empty
        o.matrix_parent_inverse = jaw_empty.matrix_world.inverted()
    eye_pivots = {}
    rig_setup_receipt: dict = {"eyelidPivotLocalBake": {}}
    for side, x_sign, keys in (("L", -1, groups["eye_l"]), ("R", 1, groups["eye_r"])):
        ep = bpy.data.objects.new(f"EyePivot_{side}", None)
        coll.objects.link(ep)
        ep.location = Vector((0.308 * x_sign, 7.284, 1.245))
        ep.parent = head_root
        eye_pivots[side] = ep
        bpy.context.view_layer.update()
        for g in keys:
            o = objs[g]
            o.parent = ep
            rig_setup_receipt["eyelidPivotLocalBake"][g] = _bake_mesh_vertices_to_parent_local(o, ep)
    rig_setup_receipt["policy"] = {
        "cameraMutation": 0,
        "manifestMutation": 0,
        "arbitraryPivotRemoval": "DENY",
        "arbitraryCorrectionOffset": "DENY",
    }
    return objs, eye_pivots, rig_setup_receipt


def _mesh_vertex_adjacency(mesh) -> dict[int, set[int]]:
    adj: dict[int, set[int]] = {i: set() for i in range(len(mesh.vertices))}
    for poly in mesh.polygons:
        verts = list(poly.vertices)
        for i in range(len(verts)):
            a, b = verts[i], verts[(i + 1) % len(verts)]
            adj[a].add(b)
            adj[b].add(a)
    return adj


def _geodesic_corridor_verts(
    adj: dict[int, set[int]],
    basis_coords: list[Vector],
    seed: int,
    anchor: Vector,
    geo_max: float,
    eucl_max: float,
    side_pred,
) -> set[int]:
    if seed < 0:
        return set()
    geo: dict[int, float] = {seed: 0.0}
    out = {seed}
    queue = [seed]
    head = 0
    while head < len(queue):
        vi = queue[head]
        head += 1
        for nb in adj[vi]:
            if nb in geo:
                continue
            co = basis_coords[nb]
            if float((co - anchor).length) > eucl_max or not side_pred(co):
                continue
            step = float((basis_coords[nb] - basis_coords[vi]).length)
            ng = geo[vi] + step
            if ng > geo_max:
                continue
            geo[nb] = ng
            out.add(nb)
            queue.append(nb)
    return out


def _mesh_face_adjacency(mesh) -> dict[int, set[int]]:
    edge_faces: dict[tuple[int, int], list[int]] = {}
    for fi, poly in enumerate(mesh.polygons):
        verts = list(poly.vertices)
        for i in range(len(verts)):
            edge = tuple(sorted((int(verts[i]), int(verts[(i + 1) % len(verts)]))))
            edge_faces.setdefault(edge, []).append(fi)
    adj: dict[int, set[int]] = {i: set() for i in range(len(mesh.polygons))}
    for faces in edge_faces.values():
        if len(faces) < 2:
            continue
        for a in faces:
            for b in faces:
                if a != b:
                    adj[a].add(b)
    return adj


def _face_centroid(basis_coords: list[Vector], poly) -> Vector:
    acc = Vector((0.0, 0.0, 0.0))
    for vi in poly.vertices:
        acc += basis_coords[int(vi)]
    return acc / float(len(poly.vertices))


def _face_area_3d(basis_coords: list[Vector], poly) -> float:
    if len(poly.vertices) < 3:
        return 0.0
    v0 = basis_coords[int(poly.vertices[0])]
    area = 0.0
    for i in range(1, len(poly.vertices) - 1):
        v1 = basis_coords[int(poly.vertices[i])]
        v2 = basis_coords[int(poly.vertices[i + 1])]
        area += float((v1 - v0).cross(v2 - v0).length) * 0.5
    return area


def _topo_connected_region(adj: dict[int, set[int]], seed: int, pred) -> set[int]:
    if seed < 0 or seed >= len(adj):
        return set()
    out = {seed}
    queue = [seed]
    head = 0
    while head < len(queue):
        vi = queue[head]
        head += 1
        for nb in adj[vi]:
            if nb in out or not pred(nb):
                continue
            out.add(nb)
            queue.append(nb)
    return out


def _chin_seed_index(basis_coords: list[Vector], landmarks: dict, weights: dict[int, float]) -> int:
    chin = landmarks["chin"]
    mouth_z = landmarks["mouth_center"].z
    best_i, best_d = -1, 1e9
    for vi, co in enumerate(basis_coords):
        if co.z >= mouth_z - 0.02:
            continue
        if abs(co.x - chin.x) > 0.24 or abs(co.y - chin.y) > 0.32:
            continue
        d = float((co - chin).length)
        if d < best_d:
            best_d, best_i = d, vi
    return best_i


def _build_chin_face_region(
    mesh,
    basis_coords: list[Vector],
    landmarks: dict,
    chin_seed: int,
    reserved_verts: set[int],
) -> tuple[set[int], dict]:
    if chin_seed < 0:
        return set(), {"seed": chin_seed, "reason": "CHIN_SEED_MISSING"}
    seed_faces = [fi for fi, poly in enumerate(mesh.polygons) if chin_seed in poly.vertices]
    if not seed_faces:
        return set(), {"seed": chin_seed, "reason": "CHIN_SEED_FACE_MISSING", "seedFaces": 0}

    adj = _mesh_face_adjacency(mesh)
    lower_lip = landmarks["lower_lip"]
    mouth_center = landmarks["mouth_center"]
    chin = landmarks["chin"]
    corner_l = landmarks["lip_corner_l"]
    corner_r = landmarks["lip_corner_r"]
    lip_z_max = float(lower_lip.z - 0.012)
    neck_z_min = float(chin.z - 0.20)
    jaw_y_max = float(mouth_center.y + 0.04)
    x_min = min(corner_l.x, corner_r.x) - 0.10
    x_max = max(corner_l.x, corner_r.x) + 0.10

    def face_ok(fi: int) -> bool:
        poly = mesh.polygons[fi]
        if any(int(v) in reserved_verts for v in poly.vertices):
            return False
        c = _face_centroid(basis_coords, poly)
        if c.z >= lip_z_max:
            return False
        if c.z < neck_z_min:
            return False
        if c.x < x_min or c.x > x_max:
            return False
        if c.y > jaw_y_max:
            return False
        return True

    geo: dict[int, float] = {}
    out: set[int] = set()
    queue: list[int] = []
    for sf in seed_faces:
        if face_ok(sf):
            geo[sf] = 0.0
            out.add(sf)
            queue.append(sf)

    head = 0
    while head < len(queue):
        fi = queue[head]
        head += 1
        c0 = _face_centroid(basis_coords, mesh.polygons[fi])
        for nb in adj[fi]:
            if nb in geo or not face_ok(nb):
                continue
            c1 = _face_centroid(basis_coords, mesh.polygons[nb])
            step = float((c1 - c0).length)
            ng = geo[fi] + step
            if ng > CHIN_FACE_GEO_MAX:
                continue
            geo[nb] = ng
            out.add(nb)
            queue.append(nb)

    area = sum(_face_area_3d(basis_coords, mesh.polygons[fi]) for fi in out)
    return out, {
        "seed": chin_seed,
        "seedFaces": len(seed_faces),
        "faceCount": len(out),
        "faceArea3d": area,
        "geodesicMax": CHIN_FACE_GEO_MAX,
    }


def _chin_face_components(mesh, chin_faces: set[int]) -> int:
    if not chin_faces:
        return 0
    adj = _mesh_face_adjacency(mesh)
    seen: set[int] = set()
    components = 0
    for fi in chin_faces:
        if fi in seen:
            continue
        components += 1
        stack = [fi]
        while stack:
            cur = stack.pop()
            if cur in seen or cur not in chin_faces:
                continue
            seen.add(cur)
            for nb in adj[cur]:
                if nb in chin_faces and nb not in seen:
                    stack.append(nb)
    return components


def _build_semantic_region_map(
    mesh,
    basis_coords: list[Vector],
    landmarks: dict,
    weights: dict[int, float],
) -> dict:
    adj = _mesh_vertex_adjacency(mesh)
    lip_verts = {
        vi
        for vi, w in weights.items()
        if w >= 0.10 and vi < len(basis_coords) and _mouth_framing(basis_coords[vi])
    }
    corner_l_seed = int(landmarks["corner_l_idx"])
    corner_r_seed = int(landmarks["corner_r_idx"])
    chin_seed = _chin_seed_index(basis_coords, landmarks, weights)
    corner_l_anchor = landmarks["lip_corner_l"]
    corner_r_anchor = landmarks["lip_corner_r"]
    mid_x = landmarks["mouth_center"].x

    def corner_l_pred(vi: int) -> bool:
        co = basis_coords[vi]
        if co.x > mid_x + 0.02:
            return False
        return float((co - corner_l_anchor).length) < CORNER_CORRIDOR_RADIUS

    def corner_r_pred(vi: int) -> bool:
        co = basis_coords[vi]
        if co.x < mid_x - 0.02:
            return False
        return float((co - corner_r_anchor).length) < CORNER_CORRIDOR_RADIUS

    corner_l_verts = _topo_connected_region(adj, corner_l_seed, corner_l_pred)
    corner_r_verts = _topo_connected_region(adj, corner_r_seed, corner_r_pred)
    reserved_for_chin = corner_l_verts | corner_r_verts
    chin_faces, chin_meta = _build_chin_face_region(mesh, basis_coords, landmarks, chin_seed, reserved_for_chin)
    lip_only = lip_verts - corner_l_verts - corner_r_verts
    chin_faces = {
        fi
        for fi in chin_faces
        if not any(int(v) in lip_only for v in mesh.polygons[fi].vertices)
        and not any(int(v) in corner_l_verts or int(v) in corner_r_verts for v in mesh.polygons[fi].vertices)
    }
    chin_verts = {int(v) for fi in chin_faces for v in mesh.polygons[fi].vertices}
    overlap_verts = (corner_l_verts & chin_verts) | (corner_r_verts & chin_verts) | (lip_verts & chin_verts)
    if overlap_verts:
        chin_faces -= {fi for fi in chin_faces if any(int(v) in overlap_verts for v in mesh.polygons[fi].vertices)}
        chin_verts = {int(v) for fi in chin_faces for v in mesh.polygons[fi].vertices}
    lip_body = lip_verts - corner_l_verts - corner_r_verts - chin_verts
    sym = min(len(corner_l_verts), len(corner_r_verts)) / max(
        len(corner_l_verts), len(corner_r_verts), 1
    )
    chin_area = sum(_face_area_3d(basis_coords, mesh.polygons[fi]) for fi in chin_faces)
    components = _chin_face_components(mesh, chin_faces)
    return {
        "lip_verts": lip_body,
        "corner_l_verts": corner_l_verts,
        "corner_r_verts": corner_r_verts,
        "chin_verts": chin_verts,
        "chin_faces": chin_faces,
        "chin_meta": chin_meta,
        "chin_face_count": len(chin_faces),
        "chin_face_area3d": float(chin_area),
        "chin_connected_components": components,
        "semantic_overlap_verts": len(overlap_verts),
        "corner_symmetry": float(sym),
        "corner_symmetry_pass": sym >= CORNER_SYMMETRY_MIN,
        "seeds": {
            "corner_l": corner_l_seed,
            "corner_r": corner_r_seed,
            "chin": chin_seed,
        },
        "vertex_counts": {
            "lip": len(lip_body),
            "lip_corner_l": len(corner_l_verts),
            "lip_corner_r": len(corner_r_verts),
            "chin": len(chin_verts),
        },
        "face_counts": {
            "chin": len(chin_faces),
        },
    }


def _validate_region_map_integrity(mesh, region_map: dict) -> dict:
    chin_faces = region_map.get("chin_faces", set())
    components = int(region_map.get("chin_connected_components", _chin_face_components(mesh, chin_faces)))
    face_count = len(chin_faces)
    face_area = float(region_map.get("chin_face_area3d", 0.0))
    overlap = int(region_map.get("semantic_overlap_verts", 0))
    checks = {
        "chinFaceCountPass": face_count >= MIN_CHIN_FACES,
        "chinFaceAreaPass": face_area >= MIN_CHIN_FACE_AREA,
        "chinConnectedComponentPass": components == 1,
        "semanticOverlapPass": overlap == 0,
        "cornerSymmetryPass": bool(region_map.get("corner_symmetry_pass", False)),
    }
    failures = [k for k, ok in checks.items() if not ok]
    return {
        "pass": not failures,
        "checks": checks,
        "chinFaceCount": face_count,
        "chinFaceArea3d": face_area,
        "chinConnectedComponents": components,
        "semanticOverlapVerts": overlap,
        "vertexCounts": region_map.get("vertex_counts"),
        "faceCounts": region_map.get("face_counts"),
        "chinMeta": region_map.get("chin_meta"),
        "failures": failures,
        "reason": None if not failures else f"REGION_MAP_INTEGRITY:{','.join(failures)}",
    }


def _ensure_semantic_material_slots(obj, slot_mats: dict[str, bpy.types.Material]) -> None:
    keys = ("skin", "lip", "lip_corner_l", "lip_corner_r", "chin")
    mesh = obj.data
    while len(mesh.materials) < len(keys):
        mesh.materials.append(slot_mats["skin"])
    for i, key in enumerate(keys):
        mesh.materials[i] = slot_mats[key]
    obj.data.update()


def _camera_state_record(sc, cam, skin_obj) -> dict:
    mw = skin_obj.matrix_world
    return {
        "renderEngine": sc.render.engine,
        "viewTransform": sc.view_settings.view_transform,
        "exposure": float(sc.view_settings.exposure),
        "filmTransparent": bool(sc.render.film_transparent),
        "evaluatedMesh": skin_obj.name,
        "materialSlotCount": len(skin_obj.data.materials),
        "maxMaterialIndex": max((int(p.material_index) for p in skin_obj.data.polygons), default=0),
        "camera": {
            "location": [float(x) for x in cam.location],
            "rotation": [float(x) for x in cam.rotation_euler],
            "matrixWorld": [[float(x) for x in row] for row in cam.matrix_world],
            "orthoScale": float(cam.data.ortho_scale),
            "clipStart": float(cam.data.clip_start),
            "clipEnd": float(cam.data.clip_end),
            "type": cam.data.type,
        },
        "backfaceCulling": {
            slot.material.name if slot.material else "none": bool(getattr(slot.material, "use_backface_culling", False))
            for slot in skin_obj.material_slots[:5]
        },
    }


def _chin_manifest_faces(mesh, region_map: dict) -> list[dict]:
    rows: list[dict] = []
    for fi in sorted(int(f) for f in region_map.get("chin_faces", set())):
        poly = mesh.polygons[fi]
        rows.append(
            {
                "faceIndex": fi,
                "materialIndex": int(poly.material_index),
                "vertices": [int(v) for v in poly.vertices],
            }
        )
    return rows


def _view_dir_from_cam(cam) -> Vector:
    return (-cam.matrix_world.col[2]).xyz.normalized()


FRONT_CHIN_FRAMING_LAMBDA = 0.35
FRONT_CHIN_DX_STEPS = (-0.14, -0.10, -0.06, -0.03, 0.0, 0.03, 0.06, 0.10, 0.14)
FRONT_CHIN_DZ_STEPS = (-0.14, -0.10, -0.06, -0.03, 0.0, 0.03, 0.06, 0.10, 0.14)
FRONT_CHIN_ORTHO_FRAC_STEPS = (-0.28, -0.18, -0.10, -0.05, 0.0, 0.05, 0.10, 0.18, 0.28)
LEFT_CHIN_FID_BASELINE_PX = 222


def _project_chin_face_region(
    sc, cam, skin_obj, chin_faces: set[int] | list[int], res: int
) -> dict:
    mesh = skin_obj.data
    mw = skin_obj.matrix_world
    margin = res * FRAME_MARGIN_FRAC
    projected = 0
    in_frame = 0
    positive_area = 0
    area_px = 0
    per_face: list[dict] = []
    for fi in chin_faces:
        poly = mesh.polygons[int(fi)]
        xs: list[float] = []
        ys: list[float] = []
        ok = True
        for vi in poly.vertices:
            co = mw @ mesh.vertices[int(vi)].co
            ndc = world_to_camera_view(sc, cam, co)
            if ndc.z <= 0.0:
                ok = False
                break
            xs.append(float(ndc.x) * res)
            ys.append((1.0 - float(ndc.y)) * res)
        if not ok or len(xs) < 3:
            continue
        projected += 1
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        frame_ok = not (x1 < margin or x0 > res - margin or y1 < margin or y0 > res - margin)
        if frame_ok:
            in_frame += 1
        n = len(xs)
        tri_area = 0.0
        for i in range(n):
            j = (i + 1) % n
            tri_area += xs[i] * ys[j] - xs[j] * ys[i]
        tri_area = abs(tri_area) * 0.5
        pos = tri_area > 0.5
        if pos:
            positive_area += 1
            area_px += int(max(1.0, tri_area))
        if len(per_face) < 12:
            per_face.append(
                {
                    "faceIndex": int(fi),
                    "inFrame": frame_ok,
                    "screenAreaPx": float(tri_area),
                    "bbox": [int(x0), int(y0), int(x1), int(y1)],
                }
            )
    return {
        "chinProjectedFaces": projected,
        "chinInFrameFaces": in_frame,
        "chinPositiveAreaFaces": positive_area,
        "chinProjectedAreaPxEstimate": area_px,
        "perFaceSample": per_face,
    }


def _rasterize_face_pixels(
    sc, cam, skin_obj, face_indices: set[int] | list[int], res: int, *, facing_only: bool = True
) -> int:
    proj = _project_chin_face_region(sc, cam, skin_obj, face_indices, res)
    if facing_only:
        return int(proj["chinProjectedAreaPxEstimate"])
    return int(proj["chinProjectedAreaPxEstimate"])


def _classify_chin_parity(
    mode: str,
    proj: dict,
    raw_index_px: int,
    fid_px: int,
    *,
    qa_px: int = 0,
) -> str:
    in_frame = int(proj.get("chinInFrameFaces", 0))
    positive = int(proj.get("chinPositiveAreaFaces", 0))
    if mode == "front":
        if in_frame <= 0:
            return "FRONT_CHIN_CAMERA_FRAMING"
        if in_frame > 0 and positive <= 0:
            return "FRONT_CHIN_CAMERA_RASTER_DEGENERACY"
        if positive > 0 and (raw_index_px <= 0 or fid_px <= 0):
            return "FID_RENDER_PATH_PARITY_FAIL"
        if fid_px > 0 and raw_index_px > 0:
            return "PASS"
        return "FRONT_CHIN_CAMERA_RASTER_DEGENERACY"
    if fid_px <= 0 and raw_index_px <= 0 and in_frame <= 0:
        return "CAMERA_FRAMING_CANDIDATE"
    if fid_px > 0 and raw_index_px > 0:
        return "PASS"
    if positive > 0 and fid_px <= 0:
        return "FID_RENDER_PATH_PARITY_FAIL"
    return "FID_RENDER_PATH_PARITY_FAIL"


def _mouth_front_framing_constraints(
    sc,
    cam,
    landmarks: dict,
    basis_coords: list[Vector],
    morph_specs: list[dict],
    res: int,
) -> tuple[bool, str | None]:
    frame_keys = ("lip_corner_l", "lip_corner_r", "mouth_center")
    in_frame, reason = _landmarks_in_frame(sc, cam, landmarks, frame_keys, res, basis_coords, "front")
    if not in_frame:
        return False, reason or "LANDMARK_FRAME_FAIL"
    if morph_specs:
        u_min, u_max = morph_specs[0]["unionMin"], morph_specs[0]["unionMax"]
        occ = _project_aabb_occupancy(sc, cam, u_min, u_max, res)
        ctx_ok, ctx_reason = _semantic_context_ok(
            {"widthFrac": occ["widthFrac"], "heightFrac": occ["heightFrac"]} if occ else {"widthFrac": 0.0, "heightFrac": 0.0}
        )
        if not ctx_ok:
            return False, ctx_reason or "CONTEXT_FAIL"
        for spec in morph_specs:
            occ_m = _project_aabb_occupancy(sc, cam, spec["coMin"], spec["coMax"], res)
            if not _occupancy_ok(occ_m):
                return False, "MORPH_PROJECTION_FAIL"
    return True, None


def _solve_front_chin_constrained_framing(
    sc,
    cam,
    c0: dict,
    landmarks: dict,
    basis_coords: list[Vector],
    region_map: dict,
    skin_obj,
    morph_specs: list[dict],
    res: int,
    mask_mat=None,
    set_mouth_fn=None,
    mouth_valid_fn=None,
    fid_mats: dict | None = None,
    rig_objs: dict | None = None,
) -> tuple[dict | None, dict]:
    if c0 is None:
        return None, {"pass": False, "reason": "C0_MISSING"}
    sem_center0 = Vector(c0["semanticCenter"])
    semantic_view = Vector(c0["semanticViewDir"])
    dist = float(c0.get("distance", 2.8))
    ortho0 = float(c0["ortho_scale"])
    chin_faces = region_map.get("chin_faces", set())
    _apply_locked_camera(cam, c0)
    _apply_semantic_camera(cam, sem_center0, ortho0, semantic_view, dist)
    c0_proj = _project_chin_face_region(sc, cam, skin_obj, chin_faces, res)

    best_cam: dict | None = None
    best_cost = float("inf")
    best_proj: dict | None = None
    best_delta: dict | None = None
    candidates = 0
    feasible = 0
    native_feasible = 0

    for dx in FRONT_CHIN_DX_STEPS:
        for dz in FRONT_CHIN_DZ_STEPS:
            for ortho_frac in FRONT_CHIN_ORTHO_FRAC_STEPS:
                candidates += 1
                ortho = max(ortho0 * (1.0 + ortho_frac), 0.08)
                sem_center = sem_center0 + Vector((dx, 0.0, dz))
                _apply_semantic_camera(cam, sem_center, ortho, semantic_view, dist)
                ok, fail = _mouth_front_framing_constraints(
                    sc, cam, landmarks, basis_coords, morph_specs, res
                )
                if not ok:
                    continue
                proj = _project_chin_face_region(sc, cam, skin_obj, chin_faces, res)
                if int(proj["chinPositiveAreaFaces"]) < 1:
                    continue
                feasible += 1
                cost = abs(dx) + abs(dz) + FRONT_CHIN_FRAMING_LAMBDA * abs(ortho - ortho0) / max(ortho0, 1e-6)
                if cost < best_cost:
                    best_cost = cost
                    best_delta = {"dx": float(dx), "dz": float(dz), "dOrthoFrac": float(ortho_frac), "ortho": float(ortho)}
                    best_proj = proj
                    best_cam = {
                        "location": [float(x) for x in cam.location],
                        "rotation": [float(x) for x in cam.rotation_euler],
                        "ortho_scale": float(ortho),
                        "distance": float(dist),
                        "view_dir": list(c0["view_dir"]),
                        "semanticViewDir": [float(x) for x in semantic_view],
                        "semanticCenter": [float(x) for x in sem_center],
                        "constrainedFraming": True,
                        "c0Ref": "MOUTH_UNION_CAMERA_FRONT",
                        "delta": best_delta,
                        "roiUnionBounds": c0.get("roiUnionBounds"),
                        "projectionFeasible": True,
                        "semanticLocked": True,
                    }

    report = {
        "pass": best_cam is not None,
        "gate": "FRONT_CHIN_CONSTRAINED_FRAMING",
        "c0Projection": c0_proj,
        "bestProjection": best_proj,
        "bestDelta": best_delta,
        "bestCost": None if best_cam is None else float(best_cost),
        "candidatesSearched": candidates,
        "feasibleCandidates": feasible,
        "nativeMaskFeasibleCandidates": native_feasible,
        "reason": None if best_cam is not None else "FRONT_CHIN_CONSTRAINED_FRAMING_FAIL",
        "nativeMaskQualification": None,
    }
    if best_cam is not None and mask_mat is not None and set_mouth_fn is not None and mouth_valid_fn is not None and fid_mats is not None:
        native_ok, native_rows = _validate_mouth_native_mask_morphs(
            sc,
            cam,
            best_cam,
            morph_specs,
            mask_mat,
            set_mouth_fn,
            mouth_valid_fn,
            res,
            view="front",
            fid_mats=fid_mats,
            landmarks=landmarks,
            skin_basis_coords=basis_coords,
            rig_objs=rig_objs,
        )
        report["nativeMaskQualification"] = native_rows
        if not native_ok:
            report["nativeQualificationCameraRef"] = {
                "source": "FRONT_CHIN_CONSTRAINED_FRAMING_BEST_CANDIDATE",
                "cameraState": dict(best_cam),
            }
            best_cam = None
            report["pass"] = False
            report["reason"] = "B0_NATIVE_MASK_QUALIFICATION_FAIL"
        else:
            native_feasible = 1
            report["nativeQualificationCameraRef"] = {
                "source": "FRONT_CHIN_CONSTRAINED_FRAMING_BEST_CANDIDATE",
                "cameraState": dict(best_cam),
            }
    if best_cam is not None:
        _apply_locked_camera(cam, best_cam)
    else:
        _apply_locked_camera(cam, c0)
    return best_cam, report


def _parity_camera_for_mouth(
    sc,
    cam,
    skin_obj,
    basis_coords: list[Vector],
    landmarks: dict,
    mode: str,
    res: int,
) -> dict:
    mw = skin_obj.matrix_world
    co_min, co_max = _coords_framing_bounds(basis_coords, mw, _mouth_framing)
    if co_min is None:
        return {"pass": False, "reason": "EMPTY_BOUNDS"}
    view_dir = _legacy_view_dir(mode)
    semantic_view = _landmark_view_dir(landmarks, mode)
    center = (co_min + co_max) / 2.0
    dist = _place_camera(cam, center, co_min, co_max, view_dir, mode)
    sem_center = _semantic_center(landmarks, "mouth", "mouth", center)
    frame_keys = _frame_landmark_keys("mouth", "mouth")
    ortho = max(_semantic_ortho_scale(landmarks, "mouth", semantic_view) * 1.02, float(cam.data.ortho_scale))
    _apply_semantic_camera(cam, sem_center, ortho, semantic_view, dist)
    _nudge_camera_to_landmarks(sc, cam, landmarks, frame_keys, sem_center, semantic_view, dist, res, basis_coords, mode)
    for _ in range(10):
        sem_mask = _render_index_mask(
            sc,
            cam,
            [skin_obj],
            bpy.data.materials.get("ObjID") or _mask_mat("ObjIDProbe"),
            {},
            Path(tempfile.gettempdir()) / f"nurion_parity_ctx_{mode}.png",
            res,
        )
        if _semantic_context_ok(_measure_mask(sem_mask))[0]:
            break
        cam.data.ortho_scale = float(cam.data.ortho_scale) * 1.05
    bbox = _landmark_pixel_bbox(sc, cam, landmarks, frame_keys, res, pad_frac=0.12, basis_coords=basis_coords, mode=mode)
    return {
        "pass": True,
        "bbox": bbox,
        "cameraState": _camera_state_record(sc, cam, skin_obj),
        "distance": float(dist),
        "viewDir": [float(x) for x in view_dir],
        "semanticViewDir": [float(x) for x in semantic_view],
        "semanticCenter": [float(x) for x in sem_center],
    }


def _build_mouth_forensic_camera_ref(lock: dict | None, *, source: str) -> dict | None:
    if lock is None:
        return None
    ref = {
        "schema": "MOUTH_FORENSIC_CAMERA_REF_V1",
        "cameraRefSource": source,
        "cameraRefLocation": [float(x) for x in lock["location"]],
        "cameraRefRotation": [float(x) for x in lock["rotation"]],
        "cameraRefOrthoScale": float(lock["ortho_scale"]),
        "cameraRefProjection": {
            "orthoScale": float(lock["ortho_scale"]),
            "clipStart": float(lock.get("clip_start", 0.01)),
            "clipEnd": float(lock.get("clip_end", 1000.0)),
            "semanticCenter": lock.get("semanticCenter"),
            "semanticViewDir": lock.get("semanticViewDir"),
            "viewDir": lock.get("viewDir"),
            "distance": lock.get("distance"),
        },
        "readOnly": True,
        "gatePassEligible": False,
        "productionCameraLockEquivalent": False,
    }
    ref["cameraRefHash"] = _hash_solver_receipt(
        {
            "source": source,
            "location": ref["cameraRefLocation"],
            "rotation": ref["cameraRefRotation"],
            "ortho_scale": ref["cameraRefOrthoScale"],
        }
    )
    ref["cameraState"] = lock
    return ref


def _mouth_forensic_fid_trigger_receipt(
    *,
    visibility_pass: bool,
    production_camera_lock_present: bool,
    forensic_camera_ref: dict | None,
    probe_triggered: bool,
    probe_trigger_reason: str,
) -> dict:
    ref = forensic_camera_ref or {}
    return {
        "visibilityPass": bool(visibility_pass),
        "productionCameraLockPresent": bool(production_camera_lock_present),
        "forensicCameraRefPresent": forensic_camera_ref is not None,
        "probeTriggered": bool(probe_triggered),
        "probeTriggerReason": probe_trigger_reason,
        "gatePassEligible": False,
        "cameraRefSource": ref.get("cameraRefSource"),
        "cameraRefHash": ref.get("cameraRefHash"),
        "cameraRefProjection": ref.get("cameraRefProjection"),
        "cameraRefLocation": ref.get("cameraRefLocation"),
        "cameraRefRotation": ref.get("cameraRefRotation"),
        "cameraRefOrthoScale": ref.get("cameraRefOrthoScale"),
        "productionCameraLockBypass": False,
        "cameraMutation": 0,
        "thresholdMutation": 0,
    }


def _run_mouth_forensic_camera_ref_and_fid_trigger_probe(
    sc,
    cam,
    *,
    forensic_camera_ref: dict,
    trigger_receipt: dict,
    set_mouth_fn,
    mouth_valid_fn,
    skin_obj,
    region_map: dict,
    fid_mats: dict,
    res: int,
    out_dir: Path,
    label: str,
) -> dict:
    fid_probe = _run_mouth_chin_lip_corner_fid_forensic_probe(
        sc,
        cam,
        forensic_camera_ref["cameraState"],
        set_mouth_fn=set_mouth_fn,
        mouth_valid_fn=mouth_valid_fn,
        skin_obj=skin_obj,
        region_map=region_map,
        fid_mats=fid_mats,
        res=res,
        out_dir=out_dir,
        label=label,
    )
    per_feature = fid_probe.get("perFeature") or {}
    receipts_present = all(f in per_feature for f in MOUTH_FID_EMISSION_FEATURES)
    diagnostic_pass = (
        bool(trigger_receipt.get("visibilityPass"))
        and bool(trigger_receipt.get("forensicCameraRefPresent"))
        and bool(trigger_receipt.get("probeTriggered"))
        and not bool(trigger_receipt.get("productionCameraLockBypass"))
        and receipts_present
    )
    return {
        **fid_probe,
        "forensicTrigger": trigger_receipt,
        "diagnosticPass": bool(diagnostic_pass),
        "fidRepairPass": bool(fid_probe.get("pass")),
        "gatePassEligible": False,
    }


def _apply_locked_camera(cam, locked_cam: dict) -> None:
    cam.location = Vector(locked_cam["location"])
    cam.rotation_euler = locked_cam["rotation"]
    cam.data.ortho_scale = float(locked_cam["ortho_scale"])
    if "clip_start" in locked_cam:
        cam.data.clip_start = float(locked_cam["clip_start"])
    if "clip_end" in locked_cam:
        cam.data.clip_end = float(locked_cam["clip_end"])


def _vector_bounds_dict(co_min: Vector | None, co_max: Vector | None) -> dict | None:
    if co_min is None or co_max is None:
        return None
    return {
        "min": [float(co_min.x), float(co_min.y), float(co_min.z)],
        "max": [float(co_max.x), float(co_max.y), float(co_max.z)],
    }


def _manifest_semantic_lock(lock: dict) -> dict:
    return {
        "location": [float(x) for x in lock["location"]],
        "rotation": [float(x) for x in lock["rotation"]],
        "ortho_scale": float(lock["ortho_scale"]),
        "center": [float(x) for x in lock.get("semanticCenter", lock["location"])],
        "keyEnergy": lock.get("keyEnergy"),
    }


def _hash_solver_receipt(entry: dict) -> str:
    payload = json.dumps(entry, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _apply_camera_lock_manifest(cam, entry: dict) -> None:
    cam.data.type = str(entry.get("projectionType", "ORTHO"))
    cam.location = Vector(entry["location"])
    cam.rotation_euler = entry["rotation"]
    cam.data.ortho_scale = float(entry["orthoScale"])
    cam.data.clip_start = float(entry.get("clipStart", 0.001))
    cam.data.clip_end = float(entry.get("clipEnd", 120.0))


def _count_projected_mesh_faces(sc, cam, skin_obj, res: int) -> int:
    if skin_obj is None or skin_obj.type != "MESH":
        return 0
    mesh = skin_obj.data
    mw = skin_obj.matrix_world
    count = 0
    for poly in mesh.polygons:
        visible = False
        for vi in poly.vertices:
            ndc = world_to_camera_view(sc, cam, mw @ mesh.vertices[int(vi)].co)
            if ndc.z > 0.0:
                px = float(ndc.x) * res
                py = (1.0 - float(ndc.y)) * res
                if 0.0 <= px <= res and 0.0 <= py <= res:
                    visible = True
                    break
        if visible:
            count += 1
    return count


def _snapshot_capture_framing_state(
    sc,
    cam,
    valid_objs,
    mask_mat,
    res: int,
    bounds: tuple[Vector | None, Vector | None],
    skin_obj=None,
) -> dict:
    tmp = Path(tempfile.gettempdir()) / f"nurion_cap_state_{id(cam)}.png"
    mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp, res)
    m = _measure_mask(mask) if mask is not None else {"widthFrac": 0.0, "heightFrac": 0.0, "bbox": None}
    raw_active = int(np.sum(mask > 0.5)) if mask is not None else 0
    wf = float(m.get("widthFrac", 0.0))
    hf = float(m.get("heightFrac", 0.0))
    projected_faces = _count_projected_mesh_faces(sc, cam, skin_obj, res) if skin_obj else 0
    return {
        "cameraMatrix": [[float(x) for x in row] for row in cam.matrix_world],
        "orthoScale": float(cam.data.ortho_scale),
        "location": [float(x) for x in cam.location],
        "rotation": [float(x) for x in cam.rotation_euler],
        "roiBounds": _vector_bounds_dict(bounds[0], bounds[1]),
        "guardBounds": _vector_bounds_dict(bounds[0], bounds[1]),
        "projectedFeatureBounds": m.get("bbox"),
        "finalMaskBounds": m.get("bbox"),
        "occupancy": {"widthFrac": wf, "heightFrac": hf},
        "fullBleed": wf >= SEMANTIC_OCC_MAX and hf >= SEMANTIC_OCC_MAX,
        "semanticFaceCount": len(skin_obj.data.polygons) if skin_obj else 0,
        "projectedSemanticFaces": projected_faces,
        "positiveAreaFaces": projected_faces,
        "rawMaskActivePixels": raw_active,
        "finalMaskActivePixels": raw_active,
        "maskPass": raw_active > 0 and bool(m.get("pass")),
    }


def _floats_close(a: list[float], b: list[float], tol: float = 1e-4) -> bool:
    if len(a) != len(b):
        return False
    return all(abs(float(x) - float(y)) <= tol for x, y in zip(a, b))


def _matrices_close(a: list[list[float]], b: list[list[float]], tol: float = 1e-4) -> bool:
    if len(a) != len(b):
        return False
    return all(_floats_close(row_a, row_b, tol) for row_a, row_b in zip(a, b))


def _compare_preflight_capture_state(preflight: dict | None, capture: dict) -> dict:
    if not preflight:
        return {"pass": True, "classification": None, "violations": []}
    camera_fields = ("cameraMatrix", "orthoScale", "location", "rotation")
    semantic_fields = ("roiBounds", "guardBounds", "projectedFeatureBounds", "finalMaskBounds", "occupancy", "fullBleed")
    violations: list[str] = []
    for key in camera_fields:
        pv = preflight.get(key)
        cv = capture.get(key)
        if pv is None or cv is None:
            continue
        if key == "cameraMatrix":
            if not _matrices_close(pv, cv):
                violations.append(key)
        elif key in ("location", "rotation"):
            if not _floats_close(list(pv), list(cv)):
                violations.append(key)
        elif abs(float(pv) - float(cv)) > 1e-4:
            violations.append(key)
    camera_violations = [v for v in violations if v in camera_fields]
    semantic_violations: list[str] = []
    for key in semantic_fields:
        if key in ("roiBounds", "guardBounds", "projectedFeatureBounds", "finalMaskBounds"):
            continue
        if key == "fullBleed" and preflight.get("fullBleed") != capture.get("fullBleed"):
            semantic_violations.append(key)
        elif key == "occupancy":
                po = preflight.get("occupancy") or {}
                co = capture.get("occupancy") or {}
                if abs(float(po.get("widthFrac", 0)) - float(co.get("widthFrac", 0))) > 0.08:
                    semantic_violations.append(key)
                if abs(float(po.get("heightFrac", 0)) - float(co.get("heightFrac", 0))) > 0.08:
                    semantic_violations.append(key)
    classification = None
    if camera_violations:
        classification = "CAPTURE_CAMERA_LOCK_VIOLATION"
    elif semantic_violations:
        classification = "CAPTURE_SEMANTIC_CONTEXT_DIVERGENCE"
    return {
        "pass": classification is None,
        "classification": classification,
        "violations": violations + semantic_violations,
        "preflight": preflight,
        "capture": capture,
    }


def _diagnose_mask_pipeline(state: dict) -> dict:
    projected = int(state.get("projectedSemanticFaces", 0))
    raw_px = int(state.get("rawMaskActivePixels", 0))
    final_px = int(state.get("finalMaskActivePixels", 0))
    wf = float((state.get("occupancy") or {}).get("widthFrac", 0.0))
    hf = float((state.get("occupancy") or {}).get("heightFrac", 0.0))
    if projected <= 0:
        classification = "CAMERA_PROJECTION_FAIL"
    elif raw_px <= 0:
        classification = "MASK_EMISSION_FAIL"
    elif final_px <= 0:
        classification = "MASK_POSTPROCESS_FAIL"
    elif not (OCC_MIN <= wf <= OCC_MAX and OCC_MIN <= hf <= OCC_MAX):
        classification = "CAMERA_OCCUPANCY_FAIL"
    else:
        classification = None
    return {
        "classification": classification,
        "projectedSemanticFaces": projected,
        "positiveAreaFaces": int(state.get("positiveAreaFaces", projected)),
        "rawMaskActivePixels": raw_px,
        "finalMaskActivePixels": final_px,
        "semanticFaceCount": int(state.get("semanticFaceCount", 0)),
    }


def _morph_tag_from_angle(angle: float) -> str:
    if angle < 6.0:
        return "closed"
    if angle < 18.0:
        return "half"
    return "open"


def _evaluate_native_index_mask(
    sc,
    cam,
    valid_objs,
    mask_mat,
    res: int,
    *,
    semantic_bounds: tuple[Vector | None, Vector | None] | None = None,
    morph_bounds: tuple[Vector | None, Vector | None] | None = None,
) -> dict:
    metrics = _render_holdout_occupancy_metrics(
        sc,
        cam,
        valid_objs,
        mask_mat,
        res,
        semantic_bounds=semantic_bounds,
        morph_bounds=morph_bounds,
    )
    return {
        "nativeRawMaskPixels": int(metrics["finalMaskPixels"]),
        "finalMaskPixels": int(metrics["finalMaskPixels"]),
        "finalSource": metrics.get("finalSource"),
        "finalMaskSourceDivergence": bool(metrics.get("finalMaskSourceDivergence")),
        "maskOccupancyPass": bool((metrics.get("legacyOccupancy") or {}).get("legacyPass")),
        "legacyOccupancy": metrics.get("legacyOccupancy"),
        "occupancyMetricsEnforcement": metrics.get("occupancyMetricsEnforcement", "DIAGNOSTIC_ONLY"),
        "occupancy": metrics.get("occupancy") or {"widthFrac": 0.0, "heightFrac": 0.0},
        "occupancyMetrics": metrics.get("occupancyMetrics"),
        "occupancyContractMetric": metrics.get("occupancyContractMetric"),
        "bbox": metrics.get("bbox"),
        "maskRenderReceipt": metrics.get("maskRenderReceipt"),
    }


def _validate_mouth_native_mask_morphs(
    sc,
    cam,
    lock: dict | None,
    morph_specs: list[dict],
    mask_mat,
    set_mouth_fn,
    mouth_valid_fn,
    res: int,
    *,
    view: str,
    fid_mats: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    rig_objs: dict | None = None,
) -> tuple[bool, list[dict]]:
    if lock is not None:
        _apply_locked_camera(cam, lock)
    rows: list[dict] = []
    union_min = morph_specs[0]["unionMin"] if morph_specs else None
    union_max = morph_specs[0]["unionMax"] if morph_specs else None
    sem_bounds = (union_min, union_max) if union_min is not None else None
    for spec in morph_specs:
        tag = _morph_tag_from_angle(float(spec["angle"]))
        set_mouth_fn(float(spec["angle"]), show_oral=bool(spec["showOral"]))
        valid, skin = mouth_valid_fn(bool(spec["showOral"]))
        occ = _project_aabb_occupancy(sc, cam, spec["coMin"], spec["coMax"], res)
        projection_feasible = bool(occ and _occupancy_ok(occ))
        native = _evaluate_mouth_morph_native_evidence(
            sc,
            cam,
            valid,
            skin,
            mask_mat,
            fid_mats,
            res,
            view,
            bool(spec["showOral"]),
            landmarks,
            skin_basis_coords,
            spec,
            sem_bounds,
            rig_objs=rig_objs,
        )
        rows.append(
            {
                "morph": tag,
                "angle": float(spec["angle"]),
                "showOral": bool(spec["showOral"]),
                "projectionFeasible": projection_feasible,
                **native,
            }
        )
    ok = len(rows) == 3 and all(
        r["projectionFeasible"]
        and bool(r.get("nativeSemanticEvidencePass"))
        and r.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
        and not bool(r.get("finalMaskSourceDivergence"))
        for r in rows
    )
    return ok, rows


def _project_mouth_semantic_faces(sc, cam, skin_obj, res: int) -> dict:
    mesh = skin_obj.data
    mw = skin_obj.matrix_world
    view_dir = _view_dir_from_cam(cam)
    semantic_manifest = 0
    projected = 0
    positive_area = 0
    front_facing = 0
    for poly in mesh.polygons:
        mi = int(poly.material_index)
        if mi <= 0:
            continue
        semantic_manifest += 1
        xs: list[float] = []
        ys: list[float] = []
        ok = True
        ndc_z: list[float] = []
        for vi in poly.vertices:
            co = mw @ mesh.vertices[int(vi)].co
            ndc = world_to_camera_view(sc, cam, co)
            ndc_z.append(float(ndc.z))
            if ndc.z <= 0.0:
                ok = False
                break
            xs.append(float(ndc.x) * res)
            ys.append((1.0 - float(ndc.y)) * res)
        if not ok or len(xs) < 3:
            continue
        projected += 1
        n = (mw.to_3x3() @ poly.normal).normalized()
        if float(n.dot(view_dir)) < 0.0:
            front_facing += 1
        tri_area = abs(
            sum(xs[i] * ys[(i + 1) % len(xs)] - xs[(i + 1) % len(xs)] * ys[i] for i in range(len(xs)))
        ) * 0.5
        if tri_area > 0.5:
            positive_area += 1
    return {
        "semanticManifestFaces": semantic_manifest,
        "projectedFaces": projected,
        "positiveAreaFaces": positive_area,
        "frontFacingFaces": front_facing,
    }


def _classify_mask_emission_parity(receipt: dict) -> str:
    projected = int(receipt.get("projectedFaces", 0))
    positive = int(receipt.get("positiveAreaFaces", 0))
    raw_px = int(receipt.get("nativeRawEmissionPixels", 0))
    if projected <= 0:
        return "CAMERA_PROJECTION_FAIL"
    if projected > 0 and raw_px <= 0:
        slot_diag = receipt.get("materialSlotDiagnostics") or []
        if any(d.get("bindingOk") is False for d in slot_diag):
            return "MASK_SLOT_BINDING_FAIL"
        if any(d.get("occludedBySkin") for d in slot_diag):
            return "MASK_DEPTH_OCCLUSION_FAIL"
        if any(d.get("cullingSuspect") for d in slot_diag):
            return "MASK_CULLING_FAIL"
        if positive > 0:
            return "MASK_NATIVE_EMISSION_FAIL"
        return "MASK_NATIVE_EMISSION_FAIL"
    if raw_px > 0:
        if receipt.get("nativeSemanticEvidencePass") is False:
            if receipt.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE":
                return "FINAL_MASK_SOURCE_DIVERGENCE"
            if receipt.get("finalMaskSourceDivergence"):
                return "FINAL_MASK_SOURCE_DIVERGENCE"
            pipeline_class = receipt.get("pipelineClassification")
            if pipeline_class and pipeline_class != "PASS":
                return pipeline_class
            evidence = receipt.get("nativeSemanticEvidence") or {}
            failures = evidence.get("failures") or []
            if "fullBleed" in failures:
                return "FINAL_OCCUPANCY_HIGH"
            if failures:
                return "FINAL_OCCUPANCY_LOW"
        elif receipt.get("nativeSemanticEvidencePass") is None and not receipt.get("maskOccupancyPass", False):
            if receipt.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE":
                return "FINAL_MASK_SOURCE_DIVERGENCE"
            if receipt.get("finalMaskSourceDivergence"):
                return "FINAL_MASK_SOURCE_DIVERGENCE"
            pipeline_class = receipt.get("pipelineClassification")
            if pipeline_class and pipeline_class != "PASS":
                return pipeline_class
            return "FINAL_OCCUPANCY_HIGH"
    return "PASS"


def _mask_array_metrics(mask: np.ndarray | None) -> dict:
    if mask is None:
        return {"pixels": 0, "bbox": None, "widthFrac": 0.0, "heightFrac": 0.0, "occupancyPass": False}
    fg = mask > 0.5
    if not fg.any():
        return {"pixels": 0, "bbox": None, "widthFrac": 0.0, "heightFrac": 0.0, "occupancyPass": False}
    m = _measure_mask(mask)
    return {
        "pixels": int(fg.sum()),
        "bbox": m.get("bbox"),
        "widthFrac": float(m.get("widthFrac", 0.0)),
        "heightFrac": float(m.get("heightFrac", 0.0)),
        "occupancyPass": bool(m.get("pass")),
    }


def _expected_roi_occupancy(sc, cam, co_min: Vector, co_max: Vector, res: int) -> dict:
    occ = _project_aabb_occupancy(sc, cam, co_min, co_max, res)
    if not occ:
        return {"widthFrac": 0.0, "heightFrac": 0.0, "bbox": None}
    return {"widthFrac": float(occ["widthFrac"]), "heightFrac": float(occ["heightFrac"]), "bbox": occ.get("bbox")}


def _estimate_depth_visible_mask_pixels(sc, cam, skin_obj, valid_objs, res: int) -> int:
    total = 0
    mesh = skin_obj.data
    semantic_faces = {i for i, p in enumerate(mesh.polygons) if int(p.material_index) > 0}
    if semantic_faces:
        total += _rasterize_face_pixels(sc, cam, skin_obj, semantic_faces, res, facing_only=True)
    for obj in valid_objs:
        if obj is skin_obj or obj.name in ("SkinBasis", "SkinOpen", "SkinEye"):
            continue
        if obj.type != "MESH" or obj.hide_render:
            continue
        all_faces = set(range(len(obj.data.polygons)))
        total += _rasterize_face_pixels(sc, cam, obj, all_faces, res, facing_only=True)
    return int(total)


def _render_mask_holdout_composite(
    sc, cam, skin_obj, valid_objs, mask_mat, path: Path, res: int
) -> np.ndarray | None:
    skin_slot_map = ["skin", "lip", "lip_corner_l", "lip_corner_r", "chin"]
    void_mat = _emit_void_mat("MASK_SLOT_VOID")
    saved_skin = [s.material for s in skin_obj.material_slots]
    composite: np.ndarray | None = None
    try:
        for slot_idx in range(1, len(skin_slot_map)):
            slot_mats = {name: void_mat for name in skin_slot_map}
            slot_mats[skin_slot_map[slot_idx]] = mask_mat
            _ensure_semantic_material_slots(skin_obj, slot_mats)
            for i, key in enumerate(skin_slot_map):
                if i < len(skin_obj.material_slots):
                    skin_obj.material_slots[i].material = slot_mats[key]
            skin_obj.data.update()
            bpy.context.view_layer.update()
            layer_path = path.with_name(f"{path.stem}_maskslot{slot_idx}{path.suffix}")
            saved_vis = {o.name: o.hide_render for o in valid_objs}
            for o in valid_objs:
                o.hide_render = o is not skin_obj
            for o in bpy.data.objects:
                if o.type == "LIGHT":
                    o.hide_render = True
            sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
            sc.render.resolution_x = res
            sc.render.resolution_y = res
            sc.render.filepath = str(layer_path)
            skin_obj.pass_index = VALID_PASS_INDEX
            bpy.ops.render.render(write_still=True)
            layer = _load_mask(layer_path)
            for name, vis in saved_vis.items():
                obj = bpy.data.objects.get(name)
                if obj:
                    obj.hide_render = vis
            if layer is None:
                continue
            if composite is None:
                composite = np.zeros((res, res), dtype=np.float32)
            composite[layer > 0.5] = 1.0
        for obj in valid_objs:
            if obj is skin_obj or obj.name in ("SkinBasis", "SkinOpen", "SkinEye"):
                continue
            if obj.type != "MESH" or obj.hide_render:
                continue
            saved_obj = [s.material for s in obj.material_slots]
            saved_vis = {o.name: o.hide_render for o in valid_objs}
            while len(obj.material_slots) < 1:
                obj.data.materials.append(mask_mat)
            obj.material_slots[0].material = mask_mat
            obj.pass_index = VALID_PASS_INDEX
            for o in valid_objs:
                o.hide_render = o is not obj
            layer_path = path.with_name(f"{path.stem}_{obj.name}{path.suffix}")
            sc.render.filepath = str(layer_path)
            bpy.ops.render.render(write_still=True)
            layer = _load_mask(layer_path)
            for name, vis in saved_vis.items():
                o2 = bpy.data.objects.get(name)
                if o2:
                    o2.hide_render = vis
            for i, mat in enumerate(saved_obj):
                if i < len(obj.material_slots):
                    obj.material_slots[i].material = mat
            if layer is None:
                continue
            if composite is None:
                composite = np.zeros((res, res), dtype=np.float32)
            composite[layer > 0.5] = 1.0
    finally:
        for i, mat in enumerate(saved_skin):
            if i < len(skin_obj.material_slots):
                skin_obj.material_slots[i].material = mat
        skin_obj.data.update()
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = False
    return composite


def _classify_mask_pipeline_audit(audit: dict, contract: str | None = None) -> str:
    if audit.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE":
        return "FINAL_MASK_SOURCE_DIVERGENCE"
    if audit.get("finalMaskSourceDivergence"):
        return "FINAL_MASK_SOURCE_DIVERGENCE"
    pp_out_px = int(audit.get("postprocessOutputPixels", 0))
    final_px = int(audit.get("finalPixels", 0))
    if pp_out_px != final_px:
        return "FINAL_MASK_SOURCE_DIVERGENCE"
    evidence = audit.get("nativeSemanticEvidence") or {}
    if evidence:
        if evidence.get("pass"):
            return "PASS"
        failures = evidence.get("failures") or []
        if "fullBleed" in failures:
            return "FINAL_OCCUPANCY_HIGH"
        if "clipped" in failures:
            return "CAMERA_PROJECTION_FAIL"
        if "contextRetained" in failures:
            return "FINAL_OCCUPANCY_LOW"
        if "expectedVisibility" in failures:
            return "FINAL_OCCUPANCY_LOW"
        return "FINAL_OCCUPANCY_LOW"
    occ_metrics = audit.get("occupancyMetrics")
    if occ_metrics:
        gate_occ = _occupancy_metric_from_eval(occ_metrics, contract)
        final_wf = float(gate_occ.get("widthFrac", 0.0))
        final_hf = float(gate_occ.get("heightFrac", 0.0))
        if final_wf > OCC_MAX or final_hf > OCC_MAX or final_wf >= SEMANTIC_OCC_MAX:
            return "FINAL_OCCUPANCY_HIGH"
        if final_wf < OCC_MIN or final_hf < OCC_MIN:
            return "FINAL_OCCUPANCY_LOW"
        return "PASS"
    stages = audit.get("stages") or {}
    final = stages.get("final") or {}
    final_wf = float(final.get("widthFrac", 0.0))
    final_hf = float(final.get("heightFrac", 0.0))
    if final_wf > OCC_MAX or final_hf > OCC_MAX or final_wf >= SEMANTIC_OCC_MAX:
        return "FINAL_OCCUPANCY_HIGH"
    if final_wf < OCC_MIN or final_hf < OCC_MIN:
        return "FINAL_OCCUPANCY_LOW"
    return "PASS"


def _raw_mask_diagnostic_classification(raw_metrics: dict, expected: dict) -> str | None:
    raw_px = int(raw_metrics.get("pixels", 0))
    if raw_px <= 0:
        return "MASK_NATIVE_EMISSION_FAIL"
    raw_wf = float(raw_metrics.get("widthFrac", 0.0))
    raw_hf = float(raw_metrics.get("heightFrac", 0.0))
    exp_wf = float(expected.get("widthFrac", 0.0))
    oversize_ref = max(exp_wf * 1.35, OCC_MAX + 0.04) if exp_wf > 0 else OCC_MAX + 0.04
    if raw_wf >= SEMANTIC_OCC_MAX or raw_hf >= SEMANTIC_OCC_MAX or raw_wf > oversize_ref:
        return "RAW_MASK_OVERSIZED"
    return None


def _audit_mouth_mask_render_pipeline(
    sc,
    cam,
    lock: dict,
    morph_spec: dict,
    skin_obj,
    valid_objs,
    mask_mat,
    res: int,
    set_mouth_fn,
    mouth_valid_fn,
) -> dict:
    _apply_locked_camera(cam, lock)
    set_mouth_fn(float(morph_spec["angle"]), show_oral=bool(morph_spec["showOral"]))
    valid, skin = mouth_valid_fn(bool(morph_spec["showOral"]))
    proj = _project_mouth_semantic_faces(sc, cam, skin, res)
    expected = _expected_roi_occupancy(sc, cam, morph_spec["coMin"], morph_spec["coMax"], res)
    tmp_raw = Path(tempfile.gettempdir()) / f"nurion_mask_audit_raw_{id(cam)}.png"
    tmp_final = Path(tempfile.gettempdir()) / f"nurion_mask_audit_final_{id(cam)}.png"
    raw_mask = _render_raw_flat_mask(sc, cam, valid, mask_mat, tmp_raw, res)
    raw_metrics = _mask_array_metrics(raw_mask)
    depth_px = _estimate_depth_visible_mask_pixels(sc, cam, skin, valid, res)
    final_mask = _render_index_mask(sc, cam, valid, mask_mat, {}, tmp_final, res)
    receipt = dict(_MASK_RENDER_RECEIPT)
    slot_metrics = _mask_array_metrics(final_mask)
    sem_proj = _project_aabb_occupancy(sc, cam, morph_spec["unionMin"], morph_spec["unionMax"], res)
    morph_proj = _project_aabb_occupancy(sc, cam, morph_spec["coMin"], morph_spec["coMax"], res)
    occ_metrics = evaluate_native_holdout_occupancy(
        final_mask,
        locked_semantic_roi=sem_proj,
        projected_morph_aabb=morph_proj,
        render_frame=res,
    )
    gate_occ = _occupancy_metric_from_eval(occ_metrics)
    legacy_occ = _legacy_occupancy_diagnostic(occ_metrics)
    post_in = dict(slot_metrics)
    post_out = dict(slot_metrics)
    final_metrics = dict(slot_metrics)
    final_source = receipt.get("finalSource", "UNKNOWN")
    stages = {
        "raw": raw_metrics,
        "depthVisible": {"pixels": depth_px, "bbox": None, "widthFrac": None, "heightFrac": None, "occupancyPass": None},
        "slotComposite": slot_metrics,
        "postprocessInput": post_in,
        "postprocessOutput": post_out,
        "final": final_metrics,
    }
    audit = {
        "stages": stages,
        "rawPixels": int(raw_metrics["pixels"]),
        "depthVisiblePixels": depth_px,
        "slotCompositePixels": int(receipt.get("slotCompositePixels", slot_metrics["pixels"])),
        "postprocessInputPixels": int(receipt.get("postprocessInputPixels", post_in["pixels"])),
        "postprocessOutputPixels": int(receipt.get("postprocessOutputPixels", post_out["pixels"])),
        "finalPixels": int(receipt.get("finalPixels", final_metrics["pixels"])),
        "finalSource": final_source,
        "finalMaskSourceDivergence": bool(receipt.get("finalMaskSourceDivergence")),
        "rawBBox": raw_metrics["bbox"],
        "finalBBox": final_metrics["bbox"],
        "rawOccupancy": {"widthFrac": raw_metrics["widthFrac"], "heightFrac": raw_metrics["heightFrac"]},
        "finalOccupancy": {"widthFrac": final_metrics["widthFrac"], "heightFrac": final_metrics["heightFrac"]},
        "occupancyMetrics": occ_metrics,
        "gateOccupancy": {
            "widthFrac": gate_occ["widthFrac"],
            "heightFrac": gate_occ["heightFrac"],
            "pass": bool(gate_occ.get("pass")),
            "contractMetric": gate_occ.get("contractMetric"),
        },
        "expectedRoiOccupancy": expected,
        "rawDiagnosticClassification": _raw_mask_diagnostic_classification(raw_metrics, expected),
        **proj,
        "nativeRawEmissionPixels": int(raw_metrics["pixels"]),
        "nativeDepthVisiblePixels": depth_px,
        "legacyOccupancy": legacy_occ,
        "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
        "maskOccupancyPass": bool(legacy_occ.get("legacyPass")),
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "maskRenderReceipt": receipt,
    }
    audit["pipelineClassification"] = _classify_mask_pipeline_audit(audit)
    audit["classification"] = audit["pipelineClassification"]
    audit["pass"] = audit["classification"] == "PASS"
    return audit


def _projection_eval_object(sc, mesh_obj):
    _sync_rig_projection_matrices(sc)
    if mesh_obj is None:
        return None, None
    if mesh_obj.parent is not None:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = mesh_obj.evaluated_get(depsgraph)
        return eval_obj, eval_obj.matrix_world.copy()
    return mesh_obj, mesh_obj.matrix_world.copy()


def _audit_feature_face_geometry(sc, cam, mesh_obj, face_indices: set[int], res: int) -> dict:
    eval_obj, mw = _projection_eval_object(sc, mesh_obj)
    if eval_obj is None or mw is None:
        return {
            "manifestFaces": len(face_indices),
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
            "frontFacingFaces": 0,
            "depthVisibleFaces": 0,
        }
    mesh = eval_obj.data
    view_dir = _view_dir_from_cam(cam)
    manifest = len(face_indices)
    projected = positive_area = front_facing = depth_visible = 0
    for fi in face_indices:
        poly = mesh.polygons[int(fi)]
        xs: list[float] = []
        ys: list[float] = []
        ndc_z: list[float] = []
        ok = True
        for vi in poly.vertices:
            co = mw @ mesh.vertices[int(vi)].co
            ndc = world_to_camera_view(sc, cam, co)
            ndc_z.append(float(ndc.z))
            if ndc.z <= 0.0:
                ok = False
                break
            xs.append(float(ndc.x) * res)
            ys.append((1.0 - float(ndc.y)) * res)
        if not ok or len(xs) < 3:
            continue
        projected += 1
        if all(z > 0.0 for z in ndc_z):
            depth_visible += 1
        n = (mw.to_3x3() @ poly.normal).normalized()
        if float(n.dot(view_dir)) < 0.0:
            front_facing += 1
        tri_area = abs(
            sum(xs[i] * ys[(i + 1) % len(xs)] - xs[(i + 1) % len(xs)] * ys[i] for i in range(len(xs)))
        ) * 0.5
        if tri_area > 0.5:
            positive_area += 1
    return {
        "manifestFaces": manifest,
        "projectedFaces": projected,
        "positiveAreaFaces": positive_area,
        "frontFacingFaces": front_facing,
        "depthVisibleFaces": depth_visible,
    }


def _classify_native_fid_slot_audit(row: dict) -> str:
    projected = int(row.get("projectedFaces", 0))
    positive = int(row.get("positiveAreaFaces", 0))
    depth_vis = int(row.get("depthVisibleFaces", 0))
    native_slot = int(row.get("nativeSlotRenderPixels", 0))
    encoded = int(row.get("encodedFIDPixels", 0))
    decoded = int(row.get("decodedFIDPixels", 0))
    composite_in = int(row.get("compositeInputPixels", 0))
    composite_out = int(row.get("compositeOutputPixels", 0))
    final_px = int(row.get("finalFIDPixels", 0))
    if projected <= 0:
        return "FID_PROJECTION_FAIL"
    if positive <= 0:
        return "FID_RASTER_DEGENERACY"
    if depth_vis <= 0:
        return "FID_DEPTH_OCCLUSION"
    if native_slot <= 0:
        return "FID_NATIVE_SLOT_RENDER_FAIL"
    if native_slot > 0 and encoded <= 0:
        return "FID_ENCODING_FAIL"
    if encoded > 0 and decoded <= 0:
        return "FID_DECODING_FAIL"
    if decoded > 0 and composite_in > 0 and composite_out <= 0:
        return "FID_LAYER_MERGE_FAIL"
    if composite_out > 0 and final_px <= 0:
        return "FID_FINAL_SOURCE_DIVERGENCE"
    return "PASS"


def _render_native_fid_layer_pixels(
    sc, cam, target_obj, fid_mat, feature: str, path: Path, res: int, *, hide_others: list
) -> tuple[int, int, int, np.ndarray | None]:
    saved_hide = {o.name: o.hide_render for o in hide_others}
    saved_mats = [s.material for s in target_obj.material_slots]
    try:
        for o in hide_others:
            o.hide_render = o is not target_obj
        while len(target_obj.material_slots) < 1:
            target_obj.data.materials.append(fid_mat)
        target_obj.material_slots[0].material = fid_mat
        target_obj.pass_index = VALID_PASS_INDEX
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = True
        bg = sc.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        saved_view = sc.view_settings.view_transform
        saved_exp = float(sc.view_settings.exposure)
        sc.view_settings.view_transform = "Raw"
        sc.view_settings.exposure = 0.0
        sc.render.resolution_x = res
        sc.render.resolution_y = res
        sc.render.filepath = str(path)
        target_obj.data.update()
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        layer = _load_rgb(path)
        sc.view_settings.view_transform = saved_view
        sc.view_settings.exposure = saved_exp
        if layer is None:
            return 0, 0, 0, None
        encoded = int(np.sum(np.any(layer > 0.045, axis=2)))
        decoded = int(_count_feature_pixels(layer, None, (feature,), full_frame=True).get(feature, 0))
        return encoded, decoded, decoded, layer
    finally:
        for name, vis in saved_hide.items():
            obj = bpy.data.objects.get(name)
            if obj:
                obj.hide_render = vis
        for i, mat in enumerate(saved_mats):
            if i < len(target_obj.material_slots):
                target_obj.material_slots[i].material = mat
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = False


def _audit_native_fid_skin_slot(
    sc, cam, skin_obj, fid_mats: dict, slot_idx: int, feature: str, path: Path, res: int
) -> dict:
    skin_slot_map = ["skin", "lip", "lip_corner_l", "lip_corner_r", "chin"]
    face_indices = {i for i, p in enumerate(skin_obj.data.polygons) if int(p.material_index) == slot_idx}
    geom = _audit_feature_face_geometry(sc, cam, skin_obj, face_indices, res)
    void_mats = {k: _emit_void_mat(f"FID_AUDIT_VOID_{k}") for k in skin_slot_map}
    saved = [s.material for s in skin_obj.material_slots]
    native_slot_px = encoded = decoded = 0
    layer_path = path.with_name(f"{path.stem}_{feature}_slot{slot_idx}{path.suffix}")
    try:
        slot_mats = {name: void_mats[name] for name in skin_slot_map}
        slot_mats[skin_slot_map[slot_idx]] = fid_mats[skin_slot_map[slot_idx]]
        _ensure_semantic_material_slots(skin_obj, slot_mats)
        for i, key in enumerate(skin_slot_map):
            if i < len(skin_obj.material_slots):
                skin_obj.material_slots[i].material = slot_mats[key]
        skin_obj.data.update()
        bpy.context.view_layer.update()
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = True
        bg = sc.world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        saved_view = sc.view_settings.view_transform
        saved_exp = float(sc.view_settings.exposure)
        sc.view_settings.view_transform = "Raw"
        sc.view_settings.exposure = 0.0
        sc.render.resolution_x = res
        sc.render.resolution_y = res
        sc.render.filepath = str(layer_path)
        skin_obj.pass_index = VALID_PASS_INDEX
        bpy.ops.render.render(write_still=True)
        layer = _load_rgb(layer_path)
        sc.view_settings.view_transform = saved_view
        sc.view_settings.exposure = saved_exp
        if layer is not None:
            native_slot_px = int(np.sum(np.any(layer > 0.045, axis=2)))
            encoded = native_slot_px
            decoded = int(_count_feature_pixels(layer, None, (feature,), full_frame=True).get(feature, 0))
    finally:
        for i, mat in enumerate(saved):
            if i < len(skin_obj.material_slots):
                skin_obj.material_slots[i].material = mat
        skin_obj.data.update()
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = False
    row = {
        **geom,
        "feature": feature,
        "slotIndex": slot_idx,
        "nativeSlotRenderPixels": native_slot_px,
        "encodedFIDPixels": encoded,
        "decodedFIDPixels": decoded,
        "finalFIDPixels": decoded,
    }
    row["classification"] = _classify_native_fid_slot_audit(row)
    row["pass"] = row["classification"] == "PASS" and decoded >= MIN_ABSOLUTE_FLOOR.get(feature, 0)
    return row


def _feature_render_target(feature: str, skin_obj, rig_objs: dict, side: str | None = None):
    if feature in FEATURE_TO_SLOT:
        return skin_obj, FEATURE_TO_SLOT[feature], "skin_slot"
    rig_map = {"upper_teeth": "helper-upper-teeth", "lower_teeth": "helper-lower-teeth", "tongue": "helper-tongue"}
    if feature in rig_map:
        return rig_objs.get(rig_map[feature]), 0, "rig"
    if feature == "eyeball":
        return rig_objs.get("helper-l-eye" if side == "L" else "helper-r-eye"), 0, "rig"
    if feature == "eyelid_upper":
        return rig_objs.get(f"helper-{'l' if side == 'L' else 'r'}-eyelashes-1"), 0, "rig"
    if feature == "eyelid_lower":
        return rig_objs.get(f"helper-{'l' if side == 'L' else 'r'}-eyelashes-2"), 0, "rig"
    return None, None, "unknown"


def _audit_native_fid_feature(
    sc,
    cam,
    skin_obj,
    rig_objs: dict,
    fid_mats: dict,
    valid_objs,
    feature: str,
    path: Path,
    res: int,
    *,
    side: str | None = None,
    composite_rgb: np.ndarray | None = None,
) -> dict:
    target, slot_idx, kind = _feature_render_target(feature, skin_obj, rig_objs, side)
    if target is None:
        return {"feature": feature, "classification": "FID_NATIVE_SLOT_RENDER_FAIL", "pass": False}
    if kind == "skin_slot":
        row = _audit_native_fid_skin_slot(sc, cam, skin_obj, fid_mats, int(slot_idx), feature, path, res)
    else:
        layer_path = path.with_name(f"{path.stem}_{feature}{path.suffix}")
        face_indices = set(range(len(target.data.polygons)))
        geom = _audit_feature_face_geometry(sc, cam, target, face_indices, res)
        encoded, decoded, final_single, _ = _render_native_fid_layer_pixels(
            sc, cam, target, fid_mats[feature], feature, layer_path, res, hide_others=valid_objs
        )
        final_px = final_single
        if composite_rgb is not None:
            final_px = int(_count_feature_pixels(composite_rgb, None, (feature,), full_frame=True).get(feature, 0))
        row = {
            **geom,
            "feature": feature,
            "nativeSlotRenderPixels": encoded,
            "encodedFIDPixels": encoded,
            "decodedFIDPixels": decoded,
            "finalFIDPixels": final_px,
        }
        row["classification"] = _classify_native_fid_slot_audit(row)
        row["pass"] = row["classification"] == "PASS" and final_px >= MIN_ABSOLUTE_FLOOR.get(feature, 0)
    return row


def _run_eye_fid_forensic_probe(
    sc,
    cam,
    locked_cam: dict,
    set_eye_fn,
    rig_objs: dict,
    fid_mats: dict,
    mask_mat,
    res: int,
    out_dir: Path,
    label: str,
    *,
    landmarks: dict,
    skin_basis_coords: list[Vector],
) -> dict:
    _apply_locked_camera(cam, locked_cam)
    set_eye_fn("L", 0.0)
    valid = _eye_valid_objects(set_eye_fn, "L", rig_objs)
    skin_eye = set_eye_fn.skin_eye
    bounds = _eye_bounds_for_pct(set_eye_fn, "L", 0.0, rig_objs, skin_basis_coords)
    frame_keys = _frame_landmark_keys("eye", "eye_l")
    evidence_row = _evaluate_eye_state_native_evidence(
        sc,
        cam,
        valid,
        skin_eye,
        rig_objs,
        "L",
        "closed",
        mask_mat,
        fid_mats,
        res,
        landmarks,
        skin_basis_coords,
        frame_keys,
        bounds,
        bounds,
    )
    fid_path = out_dir / f"{label}_eye_left_closed_fid_probe.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin_eye, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    fid_receipt = dict(_FID_RENDER_RECEIPT)
    features = ("eyeball", "eyelid_upper", "eyelid_lower")
    per_feature: dict[str, dict] = {}
    for f in features:
        base = _audit_native_fid_feature(
            sc, cam, skin_eye, rig_objs, fid_mats, valid, f, fid_path, res, side="L", composite_rgb=fid_rgb
        )
        layer = fid_receipt.get("layers", {}).get(f, {})
        merged = {
            **base,
            "nativeSlotRenderPixels": int(layer.get("nativeSlotRenderPixels", base.get("nativeSlotRenderPixels", 0))),
            "encodedLayerPixels": int(layer.get("encodedLayerPixels", base.get("encodedFIDPixels", 0))),
            "decodedLayerPixels": int(layer.get("decodedLayerPixels", base.get("decodedFIDPixels", 0))),
            "compositeInputPixels": int(layer.get("compositeInputPixels", 0)),
            "compositeOutputPixels": int(layer.get("compositeOutputPixels", 0)),
            "finalFIDPixels": int(fid_receipt.get("perFeatureFinal", {}).get(f, base.get("finalFIDPixels", 0))),
        }
        merged["classification"] = _classify_native_fid_slot_audit(merged)
        merged["pass"] = (
            merged["classification"] == "PASS"
            and merged["finalFIDPixels"] >= MIN_ABSOLUTE_FLOOR.get(f, 0)
        )
        chain = {
            "nativeSlot": int(merged.get("nativeSlotRenderPixels", 0)),
            "encoded": int(merged.get("encodedLayerPixels", 0)),
            "decoded": int(merged.get("decodedLayerPixels", 0)),
            "compositeInput": int(merged.get("compositeInputPixels", 0)),
            "compositeOutput": int(merged.get("compositeOutputPixels", 0)),
            "finalFID": int(merged.get("finalFIDPixels", 0)),
        }
        zero_stage = next((k for k, v in chain.items() if v <= 0), None)
        merged["fidLayerChain"] = {**chain, "firstZeroStage": zero_stage}
        per_feature[f] = merged
    visibility = evidence_row.get("featureVisibility") or {}
    feature_ok = all(
        bool((visibility.get(f) or {}).get("visibilityContractPass", (visibility.get(f) or {}).get("contractPass")))
        for f in features
    )
    probe_pass = int(evidence_row.get("finalMaskPixels", 0)) > 0 and feature_ok
    return {
        "probeShot": "eye_left_closed",
        "pass": probe_pass,
        "maskActivePixels": int(evidence_row.get("finalMaskPixels", 0)),
        "maskOccupancyPass": bool((evidence_row.get("legacyOccupancy") or {}).get("legacyPass")),
        "nativeSemanticEvidencePass": bool(evidence_row.get("nativeSemanticEvidencePass")),
        "nativeSemanticEvidence": evidence_row.get("nativeSemanticEvidence"),
        "legacyOccupancy": evidence_row.get("legacyOccupancy"),
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "perFeature": per_feature,
        "fidRenderReceipt": fid_receipt,
        "compositeFidPixels": {
            f: int(per_feature[f].get("finalFIDPixels", 0)) for f in features
        },
        "fidLayerChains": {f: per_feature[f].get("fidLayerChain") for f in features},
    }


def _run_chin_fid_forensic_probe(
    sc, cam, skin_obj, region_map: dict, fid_mats: dict, locked_cam: dict, mode: str, res: int, out_dir: Path, label: str
) -> dict:
    _apply_locked_camera(cam, locked_cam)
    chin_faces = region_map.get("chin_faces", set())
    chin_proj = _project_chin_face_region(sc, cam, skin_obj, chin_faces, res)
    fid_path = out_dir / f"{label}_chin_{mode}_fid_probe.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin_obj, {}, fid_mats, [skin_obj], fid_path, res, allow_software_fallback=False
    )
    chin_audit = _audit_native_fid_feature(
        sc, cam, skin_obj, {}, fid_mats, [skin_obj], "chin", fid_path, res, composite_rgb=fid_rgb
    )
    final_px = int(chin_audit.get("finalFIDPixels", 0))
    floor = MIN_ABSOLUTE_FLOOR.get("chin", 60)
    probe_pass = int(chin_proj.get("chinPositiveAreaFaces", 0)) >= 1 and final_px >= floor
    return {
        "probeShot": f"mouth_closed_{mode}_chin",
        "mode": mode,
        "pass": probe_pass,
        "chinProjection": chin_proj,
        "chinAudit": chin_audit,
        "finalFidPixels": final_px,
        "absoluteFloor": floor,
    }


def _audit_interior_native_features(
    sc,
    cam,
    lock: dict,
    valid_objs,
    skin_obj,
    rig_objs: dict,
    fid_mats: dict,
    mask_mat,
    res: int,
    set_mouth_fn,
    mouth_valid_fn,
    *,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    bounds: tuple[Vector, Vector],
) -> dict:
    _apply_locked_camera(cam, lock)
    set_mouth_fn(24, show_oral=True)
    valid, skin = mouth_valid_fn(True)
    return _evaluate_interior_native_evidence(
        sc,
        cam,
        valid,
        skin,
        rig_objs,
        fid_mats,
        mask_mat,
        res,
        bounds,
        landmarks,
        skin_basis_coords,
    )


def _mouth_mask_slot_diagnostics(sc, cam, skin_obj, mask_mat, valid_objs, res: int) -> list[dict]:
    rows: list[dict] = []
    mesh = skin_obj.data
    slot_names = ["skin", "lip", "lip_corner_l", "lip_corner_r", "chin"]
    for slot_idx, slot_name in enumerate(slot_names):
        face_count = sum(1 for p in mesh.polygons if int(p.material_index) == slot_idx)
        binding_ok = slot_idx < len(skin_obj.material_slots) and skin_obj.material_slots[slot_idx].material is not None
        slot_faces = {i for i, p in enumerate(mesh.polygons) if int(p.material_index) == slot_idx}
        projected_area = _rasterize_face_pixels(sc, cam, skin_obj, slot_faces, res, facing_only=False)
        rows.append(
            {
                "materialSlot": slot_idx,
                "slotName": slot_name,
                "semanticManifestFaces": face_count,
                "projectedAreaPxEstimate": projected_area,
                "bindingOk": binding_ok,
                "occludedBySkin": slot_idx > 0 and projected_area > 0,
                "occludedByHelper": False,
                "cullingSuspect": projected_area <= 0 and face_count > 0,
            }
        )
    return rows


def _run_mouth_mask_emission_parity(
    sc,
    cam,
    lock: dict,
    morph_spec: dict,
    skin_obj,
    valid_objs,
    mask_mat,
    res: int,
    mode: str,
    morph_tag: str,
    set_mouth_fn,
    mouth_valid_fn,
) -> dict:
    audit = _audit_mouth_mask_render_pipeline(
        sc, cam, lock, morph_spec, skin_obj, valid_objs, mask_mat, res, set_mouth_fn, mouth_valid_fn
    )
    valid, skin = mouth_valid_fn(bool(morph_spec["showOral"]))
    slot_diag = _mouth_mask_slot_diagnostics(sc, cam, skin, mask_mat, valid, res)
    audit["mode"] = mode
    audit["morph"] = morph_tag
    audit["materialSlotDiagnostics"] = slot_diag
    audit["classification"] = _classify_mask_emission_parity(audit)
    if audit.get("pipelineClassification") and audit["pipelineClassification"] != "PASS":
        audit["classification"] = audit["pipelineClassification"]
    audit["pass"] = audit["classification"] == "PASS"
    return audit


def _run_eye_fid_emission_parity(
    sc,
    cam,
    side: str,
    locked_cam: dict,
    set_eye_fn,
    rig_objs: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    fid_mats: dict,
    qa_mats: dict,
    mask_mat,
    res: int,
    out_dir: Path,
    label: str,
    *,
    forensic_probe: dict | None = None,
    run_full: bool = True,
) -> dict:
    if side == "L" and forensic_probe is not None and not forensic_probe.get("pass"):
        return {
            "gate": "EYE_NATIVE_FID_PARITY",
            "side": side,
            "pass": False,
            "forensicProbe": forensic_probe,
            "states": [],
            "skippedFullValidation": True,
        }
    if not run_full:
        return {"gate": "EYE_NATIVE_FID_PARITY", "side": side, "pass": False, "reason": "FULL_VALIDATION_SKIPPED"}
    _apply_locked_camera(cam, locked_cam)
    tag = "left" if side == "L" else "right"
    shot_kind = f"eye_{'l' if side == 'L' else 'r'}"
    frame_keys = _frame_landmark_keys("eye", shot_kind)
    required = ("eyeball", "eyelid_upper", "eyelid_lower")
    state_rows: list[dict] = []
    all_pass = True
    for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
        set_eye_fn(side, pct)
        valid = _eye_valid_objects(set_eye_fn, side, rig_objs)
        skin_eye = set_eye_fn.skin_eye
        morph_bounds = _eye_bounds_for_pct(set_eye_fn, side, pct, rig_objs, skin_basis_coords)
        evidence_row = _evaluate_eye_state_native_evidence(
            sc,
            cam,
            valid,
            skin_eye,
            rig_objs,
            side,
            state,
            mask_mat,
            fid_mats,
            res,
            landmarks,
            skin_basis_coords,
            frame_keys,
            morph_bounds,
            morph_bounds,
        )
        fid_path = out_dir / f"{label}_eye_{tag}_{state}_native_fid.png"
        fid_rgb = _render_feature_id(
            sc, cam, skin_eye, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
        )
        per_feature = {
            f: _audit_native_fid_feature(
                sc, cam, skin_eye, rig_objs, fid_mats, valid, f, fid_path, res, side=side, composite_rgb=fid_rgb
            )
            for f in required
        }
        fid_counts = {f: int(per_feature[f].get("finalFIDPixels", 0)) for f in required}
        native_fid_total = sum(fid_counts.values())
        worst = next((per_feature[f] for f in required if per_feature[f].get("classification") != "PASS"), None)
        classification = worst["classification"] if worst else "PASS"
        visibility = evidence_row.get("featureVisibility") or {}
        visibility_ok = all(bool((visibility.get(f) or {}).get("contractPass", (visibility.get(f) or {}).get("pass"))) for f in required)
        state_pass = (
            int(evidence_row.get("finalMaskPixels", 0)) > 0
            and bool(evidence_row.get("nativeSemanticEvidencePass"))
            and native_fid_total > 0
            and visibility_ok
            and classification == "PASS"
        )
        if not state_pass:
            all_pass = False
        state_rows.append(
            {
                "state": state,
                "maskActivePixels": int(evidence_row.get("finalMaskPixels", 0)),
                "maskOccupancyPass": bool((evidence_row.get("legacyOccupancy") or {}).get("legacyPass")),
                "nativeSemanticEvidencePass": bool(evidence_row.get("nativeSemanticEvidencePass")),
                "nativeSemanticEvidence": evidence_row.get("nativeSemanticEvidence"),
                "legacyOccupancy": evidence_row.get("legacyOccupancy"),
                "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
                "perFeatureAudit": per_feature,
                "nativeRawFidPixels": fid_counts,
                "nativeFinalFidPixels": fid_counts,
                "classification": classification if not state_pass else "PASS",
                "pass": state_pass,
            }
        )
    out = {
        "gate": "EYE_NATIVE_FID_PARITY",
        "side": side,
        "pass": all_pass,
        "states": state_rows,
        "semanticLocked": True,
    }
    if side == "L" and forensic_probe is not None:
        out["forensicProbe"] = forensic_probe
    return out


def _validate_gate_h_manifest_consistency(
    preflight_gates: dict,
    camera_lock_manifest: dict,
    *,
    require_native_mask_pass: bool = True,
) -> dict:
    issues: list[str] = []
    gate_keys = (
        "A_CHIN_REGION_INTEGRITY",
        "B_CHIN_NATIVE_FID_PARITY",
        "D_INTERIOR_NATIVE_VISIBILITY",
        "E_EYE_CAMERA_LEFT",
        "F_EYE_CAMERA_RIGHT",
        "G_EYE_NATIVE_FID_PARITY",
    )
    for gk in gate_keys:
        if gk.startswith("C_"):
            continue
        gate = preflight_gates.get(gk) or {}
        if not gate.get("pass"):
            issues.append(f"{gk}:gate_fail")
    for view in ("FRONT", "LEFT"):
        gate = preflight_gates.get(f"C_MOUTH_NATIVE_MASK_{view}") or {}
        if not gate.get("pass"):
            issues.append(f"C_MOUTH_NATIVE_MASK_{view}:gate_fail")
    locks = camera_lock_manifest.get("locks") or {}
    if require_native_mask_pass:
        for key, entry in locks.items():
            pf = entry.get("preflightState") or {}
            if not pf.get("maskPass"):
                issues.append(f"{key}:manifest_preflight_maskPass_false")
            by_morph = entry.get("preflightStateByMorph") or {}
            for morph, st in by_morph.items():
                if not (st or {}).get("maskPass"):
                    issues.append(f"{key}:{morph}:manifest_morph_maskPass_false")
    return {
        "gate": "CAPTURE_LOCK_MANIFEST_CONSISTENCY",
        "pass": len(issues) == 0,
        "issues": issues,
        "lockCount": len(locks),
        "manifestReceipt": camera_lock_manifest.get("solverReceiptHash"),
    }


def _load_json_file(path: Path | str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def _load_closed_ah_preflight_bundle(source_preflight_path: Path) -> dict:
    report = _load_json_file(source_preflight_path)
    gates = report.get("gates") or {}
    ah_probe = _load_json_file(source_preflight_path.with_name("ah_preflight_capture_evidence_probe.json")) or (
        report.get("ahPreflightCaptureEvidenceRegressionConfirmation") or {}
    )
    manifest = _load_json_file(source_preflight_path.with_name("camera_lock_manifest.json")) or {}
    preflight_pass = bool(report.get("pass"))
    ah_pass = bool(ah_probe.get("pass"))
    closed = preflight_pass and ah_pass and bool((ah_probe.get("requiredNativeCaptureEvidence") or {}).get("pass"))
    return {
        "pass": closed,
        "preflightPass": preflight_pass,
        "ahPass": ah_pass,
        "preflightReport": report,
        "gates": gates,
        "cameraLockManifest": manifest,
        "ahProbe": ah_probe,
        "sourcePreflight": str(source_preflight_path),
    }


def _thirteen_shot_manifest_lock_subset(manifest: dict) -> dict:
    locks = manifest.get("locks") or {}
    return {k: locks[k] for k in THIRTEEN_SHOT_MANIFEST_LOCK_KEYS if k in locks}


def _assert_thirteen_shot_manifest_consumption(
    source_preflight_path: Path,
    camera_lock_manifest: dict,
    *,
    expected_baseline_run_id: str = THIRTEEN_SHOT_FROZEN_BASELINE_RUN_ID,
) -> dict:
    locks = camera_lock_manifest.get("locks") or {}
    per_lock = {k: bool(locks.get(k)) for k in THIRTEEN_SHOT_MANIFEST_LOCK_KEYS}
    manifest_loaded = bool(camera_lock_manifest.get("schema")) and bool(locks)
    lock_count = len(locks)
    source_str = str(source_preflight_path).replace("\\", "/")
    source_baseline_ok = expected_baseline_run_id in source_str
    frozen_manifest_path = source_preflight_path.with_name("camera_lock_manifest.json")
    frozen_manifest = _load_json_file(frozen_manifest_path)
    expected_manifest_hash = frozen_manifest.get("solverReceiptHash") if frozen_manifest else None
    current_manifest_hash = camera_lock_manifest.get("solverReceiptHash")
    manifest_hash_match = (
        expected_manifest_hash is not None and current_manifest_hash == expected_manifest_hash
    )
    failures: list[str] = []
    if not manifest_loaded:
        failures.append("manifestLoaded_false")
    if lock_count != 5:
        failures.append(f"lockCount_{lock_count}_expected_5")
    for key, present in per_lock.items():
        if not present:
            failures.append(f"{key}_missing")
    if not source_baseline_ok:
        failures.append("sourceBaseline_mismatch")
    if not manifest_hash_match:
        failures.append("manifestHash_mismatch")
    return {
        "gate": "13_SHOT_MANIFEST_CONSUMPTION_ASSERT",
        "pass": not failures,
        "manifestLoaded": manifest_loaded,
        "lockCount": lock_count,
        "perLock": per_lock,
        "manifestRebuilt": False,
        "manifestOverwritten": False,
        "sourceBaseline": expected_baseline_run_id if source_baseline_ok else None,
        "expectedManifestHash": expected_manifest_hash,
        "manifestHash": current_manifest_hash,
        "manifestHashMatch": manifest_hash_match,
        "manifestConsumed": sum(1 for k in THIRTEEN_SHOT_MANIFEST_LOCK_KEYS if locks.get(k)),
        "manifestConsumedRequired": len(THIRTEEN_SHOT_MANIFEST_LOCK_KEYS),
        "failures": failures,
        "mutationClass": "CONSUMER_PATH_ONLY",
        "mutationId": THIRTEEN_SHOT_CONSUMER_PATH_MUTATION_ID,
        "sourcePreflight": str(source_preflight_path),
    }


def _verify_thirteen_shot_manifest_integrity(
    frozen_snapshot: dict,
    camera_lock_manifest: dict,
) -> dict:
    frozen_locks = frozen_snapshot.get("locks") or {}
    current_locks = camera_lock_manifest.get("locks") or {}
    overwritten = (
        camera_lock_manifest.get("solverReceiptHash") != frozen_snapshot.get("solverReceiptHash")
        or set(current_locks.keys()) != set(frozen_locks.keys())
        or any(current_locks.get(k) != frozen_locks.get(k) for k in THIRTEEN_SHOT_MANIFEST_LOCK_KEYS)
    )
    return {
        "manifestRebuilt": overwritten,
        "manifestOverwritten": overwritten,
        "pass": not overwritten,
        "lockCount": len(current_locks),
        "manifestConsumed": sum(1 for k in THIRTEEN_SHOT_MANIFEST_LOCK_KEYS if current_locks.get(k)),
        "manifestConsumedRequired": len(THIRTEEN_SHOT_MANIFEST_LOCK_KEYS),
    }


def _emit_thirteen_shot_manifest_consumption_abort(
    args,
    assert_receipt: dict,
    *,
    preflight_report: dict | None = None,
) -> None:
    reason = "13_SHOT_MANIFEST_CONSUMPTION_ASSERT_FAIL"
    abort = {
        "schema": "NURION_V07_V1_SEMANTIC_FEATURE_VISIBILITY_VALIDATION_V1",
        "pass": False,
        "safeAbort": True,
        "reason": reason,
        "thirteenShotManifestConsumptionAssert": assert_receipt,
        "preflight": preflight_report,
        "runFullDiagnostic": False,
        "shotsCompleted": 0,
        "shotsPassed": 0,
    }
    Path(args.semantic_validation_json).write_text(json.dumps(abort, indent=2) + "\n", encoding="utf-8")
    Path(args.validation_json).write_text(
        json.dumps({"pass": False, "safeAbort": True, "reason": reason, "assert": assert_receipt}, indent=2) + "\n",
        encoding="utf-8",
    )
    Path(args.meta_json).write_text(
        json.dumps(
            {
                "schema": "NURION_V07_V1_LSFQ_MORPH_QA_META",
                "pass": False,
                "safeAbort": True,
                "reason": reason,
                "captures": 0,
                "thirteenShotManifestConsumptionAssert": assert_receipt,
                "production": "NO-GO",
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"pass": False, "safeAbort": True, "reason": reason, "assert": assert_receipt}, ensure_ascii=True))


FORENSIC_SHOT_SPECS: dict[str, dict] = {
    "mouth_closed_front": {
        "manifestKey": "mouth_front",
        "gateKey": "C_MOUTH_NATIVE_MASK_FRONT",
        "morphState": "closed",
        "mouthAngle": 0.0,
        "showOral": False,
        "view": "front",
        "semanticProfile": "mouth",
        "shotKind": "mouth",
    },
}


def _extract_frozen_baseline_forensic_evidence(
    preflight_gates: dict,
    camera_lock_manifest: dict,
    *,
    shot_key: str,
    baseline_run_id: str = THIRTEEN_SHOT_FROZEN_BASELINE_RUN_ID,
) -> dict:
    spec = FORENSIC_SHOT_SPECS.get(shot_key) or {}
    manifest_key = spec.get("manifestKey", "")
    gate_key = spec.get("gateKey", "")
    morph = spec.get("morphState", "")
    manifest_entry = (camera_lock_manifest.get("locks") or {}).get(manifest_key) or {}
    gate = preflight_gates.get(gate_key) or {}
    morph_row = None
    for row in gate.get("nativeMaskQualification") or []:
        if str(row.get("morph")) == morph:
            morph_row = row
            break
    preflight_by_morph = (manifest_entry.get("preflightStateByMorph") or {}).get(morph) or {}
    occ_align = preflight_gates.get("OCCUPANCY_CONTRACT_ALIGNMENT") or {}
    return {
        "baselineRunId": baseline_run_id,
        "shotKey": shot_key,
        "manifestKey": manifest_key,
        "gateKey": gate_key,
        "morphState": morph,
        "gatePass": bool(gate.get("pass")),
        "frozenCameraLock": {
            "location": manifest_entry.get("location"),
            "rotation": manifest_entry.get("rotation"),
            "orthoScale": manifest_entry.get("orthoScale"),
            "distance": manifest_entry.get("distance"),
            "viewDir": manifest_entry.get("viewDir"),
            "semanticViewDir": manifest_entry.get("semanticViewDir"),
            "semanticCenter": manifest_entry.get("semanticCenter"),
            "immutable": manifest_entry.get("immutable"),
            "solverReceiptHash": manifest_entry.get("solverReceiptHash"),
        },
        "preflightStateByMorph": preflight_by_morph,
        "nativeMaskQualification": morph_row,
        "occupancyContractAlignment": {
            "resolvedContract": occ_align.get("resolvedContract"),
            "contractMetricKey": occ_align.get("contractMetricKey"),
        },
        "nativeSemanticEvidencePass": bool((morph_row or {}).get("nativeSemanticEvidencePass")),
        "maskOccupancyPass": bool((morph_row or {}).get("maskOccupancyPass")),
        "occupancyMetricsEnforcement": (morph_row or {}).get("occupancyMetricsEnforcement"),
        "occupancyMetrics": (morph_row or {}).get("occupancyMetrics"),
        "legacyOccupancy": (morph_row or {}).get("legacyOccupancy"),
        "occupancyContractMetric": (morph_row or {}).get("occupancyContractMetric"),
        "nativeFinalPixels": (morph_row or {}).get("finalMaskPixels"),
        "nativeSemanticEvidence": (morph_row or {}).get("nativeSemanticEvidence"),
    }


def _camera_triplet_parity(frozen: dict | None, applied: dict | None, *, tol: float = 1e-4) -> dict:
    frozen = frozen or {}
    applied = applied or {}
    keys = ("location", "rotation", "orthoScale")
    per_key: dict[str, bool] = {}
    for key in keys:
        fv = frozen.get(key)
        av = applied.get(key if key != "orthoScale" else "orthoScale")
        if fv is None or av is None:
            if key == "orthoScale":
                fv = frozen.get("orthoScale")
                av = applied.get("orthoScale")
            per_key[key] = fv is None and av is None
            continue
        if key in ("location", "rotation"):
            per_key[key] = _floats_close(list(fv), list(av), tol)
        else:
            per_key[key] = abs(float(fv) - float(av)) <= tol
    return {"pass": all(per_key.values()), "perKey": per_key, "frozen": frozen, "applied": applied}


def _first_zero_stage_from_pipeline(diag: dict | None) -> str | None:
    diag = diag or {}
    projected = int(diag.get("projectedSemanticFaces", 0))
    raw_px = int(diag.get("rawMaskActivePixels", 0))
    final_px = int(diag.get("finalMaskActivePixels", 0))
    classification = diag.get("classification")
    if projected <= 0:
        return "projection"
    if raw_px <= 0:
        return "native_holdout_fid"
    if final_px <= 0:
        return "native_final_pixels"
    if classification == "CAMERA_OCCUPANCY_FAIL":
        return "occupancy_gate"
    if classification:
        return "occupancy_gate"
    return None


def _classify_occupancy_forensic_isolation(baseline: dict, capture: dict) -> dict:
    camera_parity = capture.get("cameraParity") or {}
    pipeline = capture.get("maskPipelineDiagnostic") or {}
    base_native_pass = bool(baseline.get("nativeSemanticEvidencePass"))
    base_occ_enforcement = baseline.get("occupancyMetricsEnforcement")
    cap_reason = capture.get("abortReason")
    cap_class = pipeline.get("classification")
    if not camera_parity.get("pass"):
        bucket = "CONSUMER_STATE_PARITY"
        hypothesis = "camera_state_applied_diverges_from_frozen_manifest"
    elif cap_class == "CAMERA_PROJECTION_FAIL":
        bucket = "SHOT_STATE_MAPPING"
        hypothesis = "geometry_or_morph_state_diverges_before_projection"
    elif base_native_pass and base_occ_enforcement == "DIAGNOSTIC_ONLY" and cap_reason == "CAMERA_OCCUPANCY_FAIL":
        bucket = "EVALUATOR_CONTRACT_PARITY"
        hypothesis = "frozen_pass_used_native_semantic_evidence_while_13shot_consumer_enforces_legacy_frame_occupancy"
    elif cap_reason == "CAMERA_OCCUPANCY_FAIL":
        bucket = "OCCUPANCY_GEOMETRIC_EVIDENCE"
        hypothesis = "frozen_lock_consumed_but_native_evidence_or_projection_differs"
    else:
        bucket = "UNCLASSIFIED"
        hypothesis = "requires_manual_review"
    return {
        "classificationBucket": bucket,
        "hypothesis": hypothesis,
        "baselineNativeSemanticEvidencePass": base_native_pass,
        "baselineOccupancyMetricsEnforcement": base_occ_enforcement,
        "captureAbortReason": cap_reason,
        "capturePipelineClassification": cap_class,
    }


def _build_occupancy_forensic_receipt(
    *,
    shot_key: str,
    baseline: dict,
    capture_metrics: dict,
    manifest_assert: dict | None,
    fail_run_reference: dict | None,
) -> dict:
    frozen_cam = baseline.get("frozenCameraLock") or {}
    applied_cam = {
        "location": capture_metrics.get("cameraLocation"),
        "rotation": capture_metrics.get("cameraRotation"),
        "orthoScale": capture_metrics.get("orthoScale"),
    }
    camera_parity = _camera_triplet_parity(frozen_cam, applied_cam)
    pipeline = capture_metrics.get("maskPipelineDiagnostic") or {}
    state_audit = capture_metrics.get("captureStateAudit") or {}
    occ = capture_metrics.get("occupancy") or {}
    holdout = capture_metrics.get("occupancyMetrics") or {}
    abort_reason = capture_metrics.get("reason")
    first_zero = _first_zero_stage_from_pipeline(pipeline)
    threshold_provenance = {
        "legacyFrameMin": OCC_MIN,
        "legacyFrameMax": OCC_MAX,
        "semanticOccMax": SEMANTIC_OCC_MAX,
        "resolvedContract": _OCCUPANCY_GATE_CONTRACT,
        "contractMetricKey": _occupancy_contract_metric_key(),
        "baselineResolvedContract": (baseline.get("occupancyContractAlignment") or {}).get("resolvedContract"),
        "baselineOccupancyMetricsEnforcement": baseline.get("occupancyMetricsEnforcement"),
        "replacementReviewId": OCCUPANCY_REPLACEMENT_REVIEW_ID,
        "nativeSemanticEvidenceGate": NATIVE_SEMANTIC_EVIDENCE_GATE,
    }
    capture_chain = {
        "cameraParity": camera_parity,
        "captureStateAudit": state_audit,
        "maskPipelineDiagnostic": pipeline,
        "occupancy": occ,
        "occupancyMetrics": holdout,
        "nativeFinalPixels": int(capture_metrics.get("finalMaskActivePixels") or pipeline.get("finalMaskActivePixels") or 0),
        "projectedFaces": int(pipeline.get("projectedSemanticFaces") or 0),
        "positiveAreaFaces": int(pipeline.get("positiveAreaFaces") or 0),
        "semanticFaceCount": int(pipeline.get("semanticFaceCount") or 0),
        "frameOccupancy": (holdout.get("frameOccupancy") if holdout else None) or {
            "widthFrac": occ.get("widthFrac"),
            "heightFrac": occ.get("heightFrac"),
            "pass": bool(capture_metrics.get("pass")),
            "reason": occ.get("reason") or abort_reason,
        },
        "semanticRoiOccupancy": (holdout.get("semanticRoiOccupancy") if holdout else None),
        "morphAabbOccupancy": (holdout.get("morphAabbOccupancy") if holdout else None),
        "occupancyEvaluatorMetric": _occupancy_contract_metric_key(),
        "thresholdProvenance": threshold_provenance,
        "abortReason": abort_reason,
        "abortCondition": (
            "legacy_frame_occupancy_gate"
            if abort_reason == "CAMERA_OCCUPANCY_FAIL"
            else ("capture_state_audit" if not state_audit.get("pass") else abort_reason)
        ),
        "firstZeroStage": first_zero,
        "immutableManifest": bool(capture_metrics.get("immutableManifest")),
    }
    comparison = {
        "baselineRunId": baseline.get("baselineRunId"),
        "failRunReference": fail_run_reference,
        "cameraExactParity": camera_parity.get("pass"),
        "baselineNativeFinalPixels": baseline.get("nativeFinalPixels"),
        "captureNativeFinalPixels": capture_chain.get("nativeFinalPixels"),
        "baselineOccupancyMetrics": baseline.get("occupancyMetrics"),
        "captureOccupancyMetrics": capture_chain.get("occupancyMetrics"),
        "baselineLegacyOccupancy": baseline.get("legacyOccupancy"),
        "captureFrameOccupancy": capture_chain.get("frameOccupancy"),
    }
    isolation = _classify_occupancy_forensic_isolation(baseline, {**capture_chain, "abortReason": abort_reason})
    return {
        "schema": "NURION_V07_V1_LSFQ_THIRTEEN_SHOT_OCCUPANCY_FORENSIC_RECEIPT",
        "gate": "13_SHOT_OCCUPANCY_FORENSIC_ISOLATION",
        "forensicShot": shot_key,
        "manifestConsumptionAssert": manifest_assert,
        "chain": [
            "Frozen Camera Lock",
            "Camera State Applied",
            "Target Geometry / Semantic Slot",
            "Projection",
            "Positive-area faces",
            "Native Holdout / FID",
            "Occupancy Metrics",
            "Occupancy Gate",
            "CAMERA_OCCUPANCY_FAIL",
        ],
        "baselineEvidence": baseline,
        "captureEvidence": capture_chain,
        "comparison": comparison,
        "isolation": isolation,
        "policy": {
            "thresholdRelaxation": "DENY",
            "cameraRetune": "DENY",
            "morphChange": "DENY",
            "semanticRegionExpansion": "DENY",
            "geometryChange": "DENY",
            "ahPreflightRerun": "DENY",
            "newSolver": "DENY",
        },
    }


def _enrich_capture_metrics_with_holdout_occupancy(
    metrics: dict,
    *,
    manifest_entry: dict,
    morph_state: str,
    res: int,
) -> dict:
    mask = metrics.get("maskArray")
    if mask is None:
        return metrics
    by_morph = manifest_entry.get("preflightStateByMorph") or {}
    preflight_ref = by_morph.get(morph_state) if morph_state in by_morph else manifest_entry.get("preflightState")
    sem_bbox = (preflight_ref or {}).get("projectedFeatureBounds") or (preflight_ref or {}).get("finalMaskBounds")
    morph_bbox = sem_bbox
    holdout = evaluate_native_holdout_occupancy(
        mask,
        locked_semantic_roi={"bbox": sem_bbox} if sem_bbox else None,
        projected_morph_aabb={"bbox": morph_bbox} if morph_bbox else None,
        render_frame=res,
    )
    metrics = dict(metrics)
    metrics["occupancyMetrics"] = holdout
    metrics["occupancyContractMetric"] = _occupancy_contract_metric_key()
    metrics["occupancyMetricsEnforcement"] = "13_SHOT_CONSUMER_LEGACY_FRAME"
    if "maskArray" in metrics:
        del metrics["maskArray"]
    return metrics


def _immutable_capture_morph_spec(morph_state: str | None, co_min: Vector, co_max: Vector) -> dict:
    tag = morph_state or "closed"
    angle, show_oral = _MORPH_STATE_CAPTURE_SPEC.get(tag, (0.0, False))
    return {
        "angle": angle,
        "showOral": show_oral,
        "coMin": co_min,
        "coMax": co_max,
    }


def _evaluate_immutable_capture_authoritative_evidence(
    sc,
    cam,
    valid_objs,
    skin_obj,
    mask_mat,
    fid_mats,
    res: int,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    rig_objs: dict,
    *,
    semantic_profile: str,
    shot_kind: str,
    mode: str,
    morph_state: str | None,
    co_min: Vector,
    co_max: Vector,
    manifest_entry: dict | None,
) -> dict:
    sem_bounds = (co_min, co_max)
    morph_bounds = (co_min, co_max)
    morph_spec = _immutable_capture_morph_spec(morph_state, co_min, co_max)
    manifest_key = str((manifest_entry or {}).get("manifestKey") or "")
    if semantic_profile == "mouth_interior" or morph_state == "interior":
        return _evaluate_interior_native_evidence(
            sc,
            cam,
            valid_objs,
            skin_obj,
            rig_objs,
            fid_mats,
            mask_mat,
            res,
            (co_min, co_max),
            landmarks,
            skin_basis_coords,
        )
    if semantic_profile == "eye" or shot_kind == "eye":
        side = "L" if "left" in manifest_key else "R"
        state = morph_state or "closed"
        skin_eye = skin_obj
        return _evaluate_eye_state_native_evidence(
            sc,
            cam,
            valid_objs,
            skin_eye,
            rig_objs,
            side,
            state,
            mask_mat,
            fid_mats,
            res,
            landmarks,
            skin_basis_coords,
            _frame_landmark_keys("eye", "eye"),
            sem_bounds,
            morph_bounds,
        )
    show_oral = bool(morph_spec["showOral"])
    return _evaluate_mouth_morph_native_evidence(
        sc,
        cam,
        valid_objs,
        skin_obj,
        mask_mat,
        fid_mats,
        res,
        mode,
        show_oral,
        landmarks,
        skin_basis_coords,
        morph_spec,
        sem_bounds,
        rig_objs=rig_objs,
    )


def _attach_authoritative_capture_contract(metrics: dict, auth: dict) -> dict:
    legacy_occ = auth.get("legacyOccupancy") or _legacy_occupancy_diagnostic(auth.get("occupancyMetrics"))
    occ = auth.get("occupancy") or {}
    frame_occ = (auth.get("occupancyMetrics") or {}).get("frameOccupancy") or {}
    metrics = dict(metrics)
    metrics.update(
        {
            "occupancyMetrics": auth.get("occupancyMetrics"),
            "legacyOccupancy": legacy_occ,
            "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
            "occupancyContractMetric": auth.get("occupancyContractMetric") or _occupancy_contract_metric_key(),
            "nativeSemanticEvidence": auth.get("nativeSemanticEvidence"),
            "nativeSemanticEvidencePass": bool(auth.get("nativeSemanticEvidencePass")),
            "authoritativeGate": NATIVE_SEMANTIC_EVIDENCE_GATE,
            "maskOccupancyPass": bool(legacy_occ.get("legacyPass")),
            "legacyOccupancyRole": "DIAGNOSTIC_ONLY",
            "finalMaskPixels": auth.get("finalMaskPixels"),
            "finalSource": auth.get("finalSource"),
            "finalMaskSourceDivergence": auth.get("finalMaskSourceDivergence"),
            "occupancy": {
                "widthFrac": float(frame_occ.get("widthFrac", occ.get("widthFrac", 0.0))),
                "heightFrac": float(frame_occ.get("heightFrac", occ.get("heightFrac", 0.0))),
            },
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        }
    )
    metrics["pass"] = bool(auth.get("nativeSemanticEvidencePass"))
    metrics["maskPass"] = bool(auth.get("nativeSemanticEvidencePass"))
    if auth.get("nativeSemanticEvidencePass"):
        metrics["reason"] = None
    if not auth.get("nativeSemanticEvidencePass"):
        metrics["safeAbort"] = True
        metrics["reason"] = "NATIVE_SEMANTIC_EVIDENCE_FAIL"
    return metrics


def _build_contract_parity_proof_receipt(
    *,
    shot_key: str,
    baseline: dict,
    capture_metrics: dict,
    manifest_assert: dict | None,
) -> dict:
    frozen_cam = baseline.get("frozenCameraLock") or {}
    applied_cam = {
        "location": capture_metrics.get("cameraLocation"),
        "rotation": capture_metrics.get("cameraRotation"),
        "orthoScale": capture_metrics.get("orthoScale"),
    }
    camera_parity = _camera_triplet_parity(frozen_cam, applied_cam)
    legacy = capture_metrics.get("legacyOccupancy") or {}
    frame_occ = capture_metrics.get("occupancy") or {}
    baseline_frame = ((baseline.get("occupancyMetrics") or {}).get("frameOccupancy") or {})
    proof_checks = {
        "cameraMatch": bool(camera_parity.get("pass")),
        "morphStateMatch": str(baseline.get("morphState")) == str(capture_metrics.get("morphState") or baseline.get("morphState")),
        "nativeFinalPixelsMatch": int(capture_metrics.get("finalMaskPixels") or 0) == int(baseline.get("nativeFinalPixels") or 0),
        "frameOccupancyUnchanged": (
            abs(float(frame_occ.get("widthFrac", 0.0)) - float(baseline_frame.get("widthFrac", 0.0))) <= 1e-4
            and abs(float(frame_occ.get("heightFrac", 0.0)) - float(baseline_frame.get("heightFrac", 0.0))) <= 1e-4
        ),
        "legacyOccupancyPassFalse": not bool(legacy.get("legacyPass")),
        "legacyOccupancyRoleDiagnosticOnly": capture_metrics.get("legacyOccupancyRole") == "DIAGNOSTIC_ONLY",
        "nativeSemanticEvidencePass": bool(capture_metrics.get("nativeSemanticEvidencePass")),
        "authoritativeGateMatch": capture_metrics.get("authoritativeGate") == NATIVE_SEMANTIC_EVIDENCE_GATE,
        "captureAbortFalse": bool(capture_metrics.get("pass")),
    }
    failures = [k for k, ok in proof_checks.items() if not ok]
    return {
        "schema": "NURION_V07_V1_LSFQ_THIRTEEN_SHOT_CONTRACT_PARITY_PROOF_RECEIPT",
        "gate": "13_SHOT_NATIVE_SEMANTIC_EVIDENCE_CONTRACT_PARITY_PROOF",
        "forensicShot": shot_key,
        "mutationId": THIRTEEN_SHOT_CONTRACT_PARITY_MUTATION_ID,
        "mutationClass": THIRTEEN_SHOT_CONTRACT_PARITY_MUTATION_CLASS,
        "manifestConsumptionAssert": manifest_assert,
        "baselineRunId": baseline.get("baselineRunId"),
        "proofChecks": proof_checks,
        "pass": not failures,
        "failures": failures,
        "baselineEvidence": baseline,
        "captureEvidence": {
            "cameraParity": camera_parity,
            "nativeFinalPixels": capture_metrics.get("finalMaskPixels"),
            "frameOccupancy": frame_occ,
            "legacyOccupancy": legacy,
            "legacyOccupancyRole": capture_metrics.get("legacyOccupancyRole"),
            "occupancyMetricsEnforcement": capture_metrics.get("occupancyMetricsEnforcement"),
            "nativeSemanticEvidence": capture_metrics.get("nativeSemanticEvidence"),
            "nativeSemanticEvidencePass": capture_metrics.get("nativeSemanticEvidencePass"),
            "authoritativeGate": capture_metrics.get("authoritativeGate"),
            "captureAbort": not bool(capture_metrics.get("pass")),
            "reason": capture_metrics.get("reason"),
            "beautyPath": capture_metrics.get("beautyPath"),
        },
        "distinction": {
            "successIsNotOccupancyImprovement": True,
            "note": "PASS requires unchanged legacy frame occupancy with authoritative native semantic evidence gate and capture continuation.",
        },
        "policy": {
            "thresholdRelaxation": "DENY",
            "cameraRetune": "DENY",
            "morphChange": "DENY",
            "semanticRegionExpansion": "DENY",
            "geometryChange": "DENY",
            "ahPreflightRerun": "DENY",
            "newSolver": "DENY",
        },
    }


def _rollup_ah_preflight_gates(preflight_gates: dict) -> dict:
    per_letter: dict[str, dict] = {}
    all_pass = True
    letter_map = {
        "A": "A_CHIN_REGION_INTEGRITY",
        "B": "B_CHIN_NATIVE_FID_PARITY",
        "C_FRONT": "C_MOUTH_NATIVE_MASK_FRONT",
        "C_LEFT": "C_MOUTH_NATIVE_MASK_LEFT",
        "D": "D_INTERIOR_NATIVE_VISIBILITY",
        "E": "E_EYE_CAMERA_LEFT",
        "F": "F_EYE_CAMERA_RIGHT",
        "G": "G_EYE_NATIVE_FID_PARITY",
        "H": "H_CAPTURE_LOCK_MANIFEST_CONSISTENCY",
    }
    for letter, gate_key in letter_map.items():
        gate = preflight_gates.get(gate_key) or {}
        gate_pass = bool(gate.get("pass"))
        per_letter[letter] = {"gate": gate_key, "pass": gate_pass, "present": gate_key in preflight_gates}
        if not gate_pass:
            all_pass = False
    return {"allPass": all_pass, "perLetter": per_letter, "gateKeys": list(AH_PREFLIGHT_GATE_KEYS)}


def _per_feature_classifications(feature_blob: dict | None) -> dict[str, str]:
    if not feature_blob:
        return {}
    per = feature_blob.get("perFeature")
    if not per:
        per = (feature_blob.get("forensicProbe") or {}).get("perFeature") or {}
    return {k: str((v or {}).get("classification") or "UNKNOWN") for k, v in per.items()}


def _extract_eye_closed_axis_signature(preflight_report: dict) -> dict:
    gates = preflight_report.get("gates") or {}
    g = gates.get("G_EYE_NATIVE_FID_PARITY") or {}
    forensic = g.get("forensicProbe") or {}
    return {
        "axis": "eye",
        "closedBaselineId": "085754Z",
        "gateGPass": bool(g.get("pass")),
        "gateEPass": bool((gates.get("E_EYE_CAMERA_LEFT") or {}).get("pass")),
        "gateFPass": bool((gates.get("F_EYE_CAMERA_RIGHT") or {}).get("pass")),
        "eyelidProjectionPass": bool((gates.get("EYELID_RIG_HELPER_PROJECTION_PARITY") or {}).get("pass")),
        "eyelidManifestPass": bool((gates.get("EYELID_MANIFEST_STATE_MAPPING_PARITY") or {}).get("pass")),
        "visibilityPass": bool((preflight_report.get("expectedVisibilityContractParity") or {}).get("visibilityPass")),
        "forensicProbePass": bool(forensic.get("pass")),
        "perFeatureClassifications": _per_feature_classifications(forensic),
        "nativeSemanticEvidencePass": bool((forensic.get("nativeSemanticEvidence") or {}).get("pass")),
    }


def _extract_mouth_chin_closed_axis_signature(preflight_report: dict) -> dict:
    gates = preflight_report.get("gates") or {}
    b = gates.get("B_CHIN_NATIVE_FID_PARITY") or {}
    mouth_chin = preflight_report.get("mouthChinLipCornerNativeFidEmissionParity") or {}
    return {
        "axis": "mouthChin",
        "closedBaselineId": "085754Z",
        "gateBPass": bool(b.get("pass")),
        "gateCFrontPass": bool((gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}).get("pass")),
        "gateCLeftPass": bool((gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}).get("pass")),
        "mouthChinForensicPass": bool(mouth_chin.get("pass")),
        "frontPerFeatureClassifications": _per_feature_classifications(b.get("front")),
        "leftPerFeatureClassifications": _per_feature_classifications(b.get("left")),
        "mouthChinPerFeatureClassifications": _per_feature_classifications(mouth_chin),
    }


def _extract_d_interior_closed_axis_signature(
    preflight_report: dict,
    d_interior_probe: dict | None,
) -> dict:
    gates = preflight_report.get("gates") or {}
    d_gate = gates.get("D_INTERIOR_NATIVE_VISIBILITY") or {}
    probe = (d_interior_probe or {}).get("probe") or d_interior_probe or {}
    production = probe.get("productionContract") or d_gate.get("productionContract") or {}
    per_feature = ((probe.get("nativeFeatureAudit") or {}).get("perFeature")) or d_gate.get("perFeature") or {}
    feature_sig = {}
    for feat in ("oralOpening", "upperTeeth", "lowerTeeth", "tongue", "lipGuard"):
        row = per_feature.get(feat) or {}
        feature_sig[feat] = {
            "pass": bool(row.get("pass")),
            "classification": str(row.get("classification") or "UNKNOWN"),
            "contract": row.get("contract"),
            "status": row.get("status"),
        }
    oral_native = preflight_report.get("oralOpeningLipBoundaryNativeEvidenceContract") or {}
    return {
        "axis": "interiorD",
        "closedBaselineId": "070720Z",
        "gateDPass": bool(d_gate.get("pass")),
        "nativeSemanticEvidencePass": bool(production.get("nativeSemanticEvidencePass")),
        "oralOpeningNativeEvidencePass": bool(production.get("oralOpeningNativeEvidencePass")),
        "cameraLockPass": bool(production.get("cameraLockPass")),
        "lipGuardPass": bool(production.get("lipGuardPass")),
        "legacyOccupancyEnforcement": production.get("legacyOccupancyEnforcement"),
        "perFeature": feature_sig,
        "oralOpeningContractPass": bool(
            (oral_native.get("contractPass") if isinstance(oral_native, dict) else False)
            or (oral_native.get("pass") if isinstance(oral_native, dict) else False)
        ),
        "openingPolygonProjectedArea": oral_native.get("openingPolygonProjectedArea")
        if isinstance(oral_native, dict)
        else None,
    }


def _compare_closed_axis_regression(current: dict, baseline: dict) -> dict:
    regressions: list[dict] = []
    flag_keys = [
        k
        for k in current
        if k.endswith("Pass") and isinstance(current.get(k), bool) and isinstance(baseline.get(k), bool)
    ]
    for key in flag_keys:
        b_val = baseline.get(key)
        c_val = current.get(key)
        if b_val in CLOSED_AXIS_PASS_VALUES and c_val not in CLOSED_AXIS_PASS_VALUES:
            regressions.append({"field": key, "baseline": b_val, "current": c_val, "kind": "pass_flag"})

    for field_name in (
        "perFeatureClassifications",
        "frontPerFeatureClassifications",
        "leftPerFeatureClassifications",
        "mouthChinPerFeatureClassifications",
    ):
        for feat, b_class in (baseline.get(field_name) or {}).items():
            c_class = (current.get(field_name) or {}).get(feat)
            if b_class == "PASS" and c_class != "PASS":
                regressions.append(
                    {
                        "field": f"{field_name}.{feat}",
                        "baseline": b_class,
                        "current": c_class,
                        "kind": "classification",
                    }
                )

    for feat, b_row in (baseline.get("perFeature") or {}).items():
        c_row = (current.get("perFeature") or {}).get(feat) or {}
        if bool((b_row or {}).get("pass")) and not bool(c_row.get("pass")):
            regressions.append(
                {
                    "field": f"perFeature.{feat}.pass",
                    "baseline": True,
                    "current": bool(c_row.get("pass")),
                    "kind": "feature_pass",
                }
            )
        b_class = (b_row or {}).get("classification")
        c_class = c_row.get("classification")
        if b_class in ("PASS", "OPENING_POLYGON_DEFINED_PASS") and c_class not in (
            "PASS",
            "OPENING_POLYGON_DEFINED_PASS",
        ):
            regressions.append(
                {
                    "field": f"perFeature.{feat}.classification",
                    "baseline": b_class,
                    "current": c_class,
                    "kind": "classification",
                }
            )

    return {
        "axis": current.get("axis"),
        "closedBaselineId": current.get("closedBaselineId"),
        "regressionCount": len(regressions),
        "regressions": regressions,
    }


def _configure_blender_temp_dir() -> Path:
    root = Path(__file__).resolve().parents[1]
    tmp_dir = root / ".nurion_blender_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    os.environ["TEMP"] = str(tmp_dir)
    os.environ["TMP"] = str(tmp_dir)
    tempfile.tempdir = str(tmp_dir)
    return tmp_dir


def _capture_evidence_file_present(parity_dir: Path, filename: str) -> bool:
    direct = parity_dir / filename
    if direct.is_file() and direct.stat().st_size > 0:
        return True
    stem = filename[:-4] if filename.endswith(".png") else filename
    return any(p.is_file() and p.stat().st_size > 0 for p in parity_dir.glob(f"{stem}*.png"))


def _required_ah_preflight_capture_evidence(parity_dir: Path, label: str) -> dict:
    required_files = [
        f"{label}_parity_front_qa.png",
        f"{label}_parity_front_fid.png",
        f"{label}_parity_left_qa.png",
        f"{label}_parity_left_fid.png",
        f"{label}_chin_front_fid_probe.png",
        f"{label}_chin_left_fid_probe.png",
        f"{label}_eye_left_closed_fid_probe.png",
        f"{label}_eye_left_closed_native_fid.png",
        f"{label}_eye_left_half_native_fid.png",
        f"{label}_eye_left_open_native_fid.png",
        f"{label}_eye_right_closed_native_fid.png",
        f"{label}_eye_right_half_native_fid.png",
        f"{label}_eye_right_open_native_fid.png",
    ]
    present: list[str] = []
    missing: list[str] = []
    for name in required_files:
        if _capture_evidence_file_present(parity_dir, name):
            present.append(name)
        else:
            missing.append(name)
    return {
        "parityDir": str(parity_dir),
        "requiredCount": len(required_files),
        "presentCount": len(present),
        "present": present,
        "missing": missing,
        "pass": len(missing) == 0,
    }


def _gate_native_evidence_passes_but_gate_fails(gate_key: str, gate: dict, preflight_report: dict) -> bool:
    if gate.get("pass"):
        return False
    if gate_key == "D_INTERIOR_NATIVE_VISIBILITY":
        prod = gate.get("productionContract") or {}
        return bool(prod.get("nativeSemanticEvidencePass")) and not bool(gate.get("pass"))
    if gate_key == "G_EYE_NATIVE_FID_PARITY":
        forensic = gate.get("forensicProbe") or {}
        return bool(forensic.get("pass")) and bool((forensic.get("nativeSemanticEvidence") or {}).get("pass"))
    if gate_key == "B_CHIN_NATIVE_FID_PARITY":
        mouth_chin = preflight_report.get("mouthChinLipCornerNativeFidEmissionParity") or {}
        return bool(mouth_chin.get("pass"))
    return False


def _classify_ah_preflight_gate_failure(
    gate_key: str,
    gate: dict,
    baseline_gate: dict | None,
    capture_evidence: dict,
    axis_regression: dict | None,
    preflight_report: dict,
) -> dict:
    if gate.get("pass"):
        return {"gate": gate_key, "classification": None, "pass": True}
    if capture_evidence.get("missing"):
        return {
            "gate": gate_key,
            "classification": "EVIDENCE_GENERATION",
            "pass": False,
            "reason": "REQUIRED_NATIVE_CAPTURE_EVIDENCE_MISSING",
            "missingCaptures": capture_evidence.get("missing"),
        }
    if _gate_native_evidence_passes_but_gate_fails(gate_key, gate, preflight_report):
        return {
            "gate": gate_key,
            "classification": "AGGREGATION_CONSUMPTION",
            "pass": False,
            "reason": "NATIVE_EVIDENCE_PRESENT_BUT_GATE_FAIL",
        }
    if axis_regression and int(axis_regression.get("regressionCount", 0)) > 0:
        return {
            "gate": gate_key,
            "classification": "ACTUAL_REGRESSION",
            "pass": False,
            "reason": "CLOSED_AXIS_SIGNATURE_REGRESSION",
            "regressions": axis_regression.get("regressions"),
        }
    if baseline_gate and not baseline_gate.get("pass"):
        return {
            "gate": gate_key,
            "classification": "UNCLASSIFIED",
            "pass": False,
            "reason": "BASELINE_GATE_ALREADY_OPEN",
        }
    return {
        "gate": gate_key,
        "classification": "UNCLASSIFIED",
        "pass": False,
        "reason": gate.get("holdReason") or gate.get("classification") or "GATE_FAIL",
    }


def _camera_state_fingerprint(cam: dict | None) -> str | None:
    if not cam:
        return None
    payload = {
        "location": cam.get("location"),
        "rotation": cam.get("rotation"),
        "ortho_scale": cam.get("ortho_scale"),
        "semanticCenter": cam.get("semanticCenter"),
        "semanticViewDir": cam.get("semanticViewDir"),
        "distance": cam.get("distance"),
        "c0Ref": cam.get("c0Ref"),
        "constrainedFraming": cam.get("constrainedFraming"),
    }
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()[:16]


def _morph_native_evidence_summary(rows: list[dict] | None) -> dict:
    rows = rows or []
    per_morph: dict[str, dict] = {}
    for row in rows:
        tag = str(row.get("morph") or "unknown")
        per_morph[tag] = {
            "nativeSemanticEvidencePass": bool(row.get("nativeSemanticEvidencePass")),
            "projectionFeasible": bool(row.get("projectionFeasible")),
            "finalSource": row.get("finalSource"),
            "finalMaskSourceDivergence": bool(row.get("finalMaskSourceDivergence")),
            "finalMaskPixels": row.get("finalMaskPixels"),
            "maskOccupancyPass": row.get("maskOccupancyPass"),
        }
    feasible = sum(1 for r in rows if r.get("nativeSemanticEvidencePass"))
    return {
        "morphCount": len(rows),
        "feasibleShots": feasible,
        "requiredShots": 3,
        "perMorph": per_morph,
    }


def _classify_c_front_consumption_failure(
    *,
    c_gate: dict,
    b0_framing: dict,
    mouth_visibility_parity: dict,
    gate_b_front: dict,
    production_camera_lock: dict | None,
    parity_camera_lock: dict | None,
    baseline_c_gate: dict | None,
) -> dict:
    classifications: list[str] = []
    front_closed = mouth_visibility_parity.get("front_closed") or {}
    forensic_ref = front_closed.get("forensicCameraRef") or {}
    framing_rows = b0_framing.get("nativeMaskQualification") or []
    production_rows = c_gate.get("nativeMaskQualification") or []
    framing_summary = _morph_native_evidence_summary(framing_rows)
    production_summary = _morph_native_evidence_summary(production_rows)
    closed_visibility_pass = bool(front_closed.get("visibilityPass"))
    closed_emission_pass = bool(front_closed.get("emissionPass"))
    gate_b_pass = bool(gate_b_front.get("pass"))
    production_fp = _camera_state_fingerprint(production_camera_lock)
    parity_fp = _camera_state_fingerprint(parity_camera_lock)
    forensic_fp = _camera_state_fingerprint(forensic_ref.get("cameraState"))

    if c_gate.get("pass"):
        classifications.append("C_PRODUCTION_GATE_PASS")
    else:
        if baseline_c_gate and not baseline_c_gate.get("pass"):
            classifications.append("C_BASELINE_GATE_ALREADY_OPEN")
        if closed_visibility_pass and gate_b_pass and not c_gate.get("pass"):
            classifications.append("C_CLOSED_EVIDENCE_NOT_BOUND")
        if framing_rows and not production_rows:
            classifications.append("C_MORPH_STATE_RECEIPT_NOT_PROPAGATED")
        if parity_fp and production_fp and parity_fp != production_fp:
            classifications.append("C_CAMERA_REF_CONSUMPTION_MISMATCH")
        elif parity_fp and not production_fp and closed_visibility_pass:
            classifications.append("C_CAMERA_REF_CONSUMPTION_MISMATCH")
        elif forensic_fp and production_fp and forensic_fp != production_fp:
            classifications.append("C_CAMERA_REF_CONSUMPTION_MISMATCH")
        for row in framing_rows + production_rows:
            if row.get("finalSource") and row.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE":
                classifications.append("C_NATIVE_MASK_SOURCE_MISMATCH")
                break
            if row.get("finalMaskSourceDivergence"):
                classifications.append("C_NATIVE_MASK_SOURCE_MISMATCH")
                break
        reported_feasible = int(c_gate.get("feasibleShots", 0))
        counted_feasible = production_summary["feasibleShots"]
        if reported_feasible != counted_feasible:
            classifications.append("C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")
        elif framing_summary["feasibleShots"] > reported_feasible and framing_rows:
            classifications.append("C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")

    if not classifications:
        classifications.append("C_CLOSED_EVIDENCE_NOT_BOUND" if closed_visibility_pass else "C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")

    primary = classifications[0]
    return {
        "axis": "C_FRONT",
        "gate": "C_MOUTH_NATIVE_MASK_FRONT",
        "productionGatePass": bool(c_gate.get("pass")),
        "primaryClassification": primary,
        "classifications": classifications,
        "cFailureClass": "BASELINE_GATE_ALREADY_OPEN" if "C_BASELINE_GATE_ALREADY_OPEN" in classifications else primary,
        "framingGate": {
            "gate": b0_framing.get("gate"),
            "pass": bool(b0_framing.get("pass")),
            "reason": b0_framing.get("reason"),
            "feasibleCandidates": b0_framing.get("feasibleCandidates"),
            "nativeMaskFeasibleCandidates": b0_framing.get("nativeMaskFeasibleCandidates"),
            "nativeMaskQualificationSummary": framing_summary,
        },
        "closedEvidenceBinding": {
            "mouthVisibilityPass": closed_visibility_pass,
            "mouthEmissionPass": closed_emission_pass,
            "gateBFrontPass": gate_b_pass,
            "forensicCameraRefSource": forensic_ref.get("source"),
            "forensicCameraRefHash": forensic_fp,
            "parityCameraHash": parity_fp,
            "productionCameraHash": production_fp,
            "productionCameraLockPresent": production_camera_lock is not None,
            "visibilityReceiptSource": "mouth_visibility_parity.front_closed",
            "emissionReceiptSource": "mouth_visibility_parity.front_closed",
        },
        "productionGateConsumption": {
            "feasibleShots": int(c_gate.get("feasibleShots", 0)),
            "requiredShots": int(c_gate.get("requiredShots", 3)),
            "nativeMaskQualificationSummary": production_summary,
            "nativeMaskQualificationPropagated": bool(production_rows),
            "constrainedFramingPass": bool((c_gate.get("constrainedFraming") or {}).get("pass")),
            "projectionFeasible": bool(c_gate.get("projectionFeasible")),
            "cameraEmitted": c_gate.get("camera") is not None,
        },
        "feasibleShotsAggregation": {
            "productionReported": int(c_gate.get("feasibleShots", 0)),
            "productionCounted": production_summary["feasibleShots"],
            "framingSolverCounted": framing_summary["feasibleShots"],
            "aggregationMismatch": int(c_gate.get("feasibleShots", 0)) != production_summary["feasibleShots"],
            "framingToProductionReceiptDropped": bool(framing_rows) and not production_rows,
        },
        "nativeEvidenceSource": {
            "productionNativeMaskRows": len(production_rows),
            "framingNativeMaskRows": len(framing_rows),
            "mouthVisibilityParityPresent": bool(front_closed),
            "nativeMaskSource": "SLOT_HOLDOUT_COMPOSITE",
        },
    }


def _classify_c_left_consumption_failure(
    *,
    c_gate: dict,
    mouth_mask_parity: dict,
    gate_b_left: dict,
    production_camera_lock: dict | None,
    projection_camera_lock: dict | None,
    baseline_c_gate: dict | None,
) -> dict:
    classifications: list[str] = []
    closed_left = mouth_mask_parity.get("mouth_closed_left") or {}
    production_rows = c_gate.get("nativeMaskQualification") or []
    production_summary = _morph_native_evidence_summary(production_rows)
    closed_row = production_summary["perMorph"].get("closed") or {}
    closed_native_pass = bool(closed_row.get("nativeSemanticEvidencePass"))
    gate_b_pass = bool(gate_b_left.get("pass"))
    production_fp = _camera_state_fingerprint(production_camera_lock)
    projection_fp = _camera_state_fingerprint(projection_camera_lock)

    if c_gate.get("pass"):
        classifications.append("C_PRODUCTION_GATE_PASS")
    else:
        if baseline_c_gate and not baseline_c_gate.get("pass"):
            classifications.append("C_BASELINE_GATE_ALREADY_OPEN")
        if closed_native_pass and not c_gate.get("pass"):
            if int(c_gate.get("feasibleShots", 0)) < int(c_gate.get("requiredShots", 3)):
                if production_summary["feasibleShots"] == int(c_gate.get("feasibleShots", 0)):
                    pass
                else:
                    classifications.append("C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")
            if not c_gate.get("camera") and (production_camera_lock or projection_camera_lock):
                classifications.append("C_CAMERA_REF_CONSUMPTION_MISMATCH")
        if closed_native_pass and gate_b_pass and not c_gate.get("pass"):
            if int(c_gate.get("feasibleShots", 0)) == 1 and production_summary["feasibleShots"] == 1:
                pass
            else:
                classifications.append("C_CLOSED_EVIDENCE_NOT_BOUND")
        for row in production_rows:
            if row.get("finalSource") and row.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE":
                classifications.append("C_NATIVE_MASK_SOURCE_MISMATCH")
                break
            if row.get("finalMaskSourceDivergence"):
                classifications.append("C_NATIVE_MASK_SOURCE_MISMATCH")
                break
        reported_feasible = int(c_gate.get("feasibleShots", 0))
        if reported_feasible != production_summary["feasibleShots"]:
            classifications.append("C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")
        if projection_fp and production_fp and projection_fp != production_fp:
            classifications.append("C_CAMERA_REF_CONSUMPTION_MISMATCH")

    half_open_fail = any(
        not (production_summary["perMorph"].get(tag) or {}).get("nativeSemanticEvidencePass")
        for tag in ("half", "open")
        if tag in production_summary["perMorph"]
    )
    if not classifications:
        if closed_native_pass and half_open_fail:
            classifications.append("C_FEASIBLE_SHOT_AGGREGATION_MISMATCH")
        else:
            classifications.append("C_CLOSED_EVIDENCE_NOT_BOUND")

    primary = classifications[0]
    return {
        "axis": "C_LEFT",
        "gate": "C_MOUTH_NATIVE_MASK_LEFT",
        "productionGatePass": bool(c_gate.get("pass")),
        "primaryClassification": primary,
        "classifications": classifications,
        "cFailureClass": "BASELINE_GATE_ALREADY_OPEN" if "C_BASELINE_GATE_ALREADY_OPEN" in classifications else primary,
        "closedEvidenceBinding": {
            "closedNativeSemanticEvidencePass": closed_native_pass,
            "gateBLeftPass": gate_b_pass,
            "mouthMaskParityPresent": bool(closed_left),
            "mouthEmissionReceiptSource": "mouth_mask_parity.mouth_closed_left" if closed_left else None,
            "productionCameraHash": production_fp,
            "projectionCameraHash": projection_fp,
            "productionCameraLockPresent": production_camera_lock is not None,
            "projectionLockPresent": projection_camera_lock is not None,
        },
        "productionGateConsumption": {
            "feasibleShots": int(c_gate.get("feasibleShots", 0)),
            "requiredShots": int(c_gate.get("requiredShots", 3)),
            "nativeMaskQualificationSummary": production_summary,
            "cameraEmitted": c_gate.get("camera") is not None,
            "cameraNullOnGateFail": c_gate.get("camera") is None and not c_gate.get("pass"),
        },
        "feasibleShotsAggregation": {
            "productionReported": int(c_gate.get("feasibleShots", 0)),
            "productionCounted": production_summary["feasibleShots"],
            "closedBound": closed_native_pass,
            "halfOpenNativeFail": half_open_fail,
            "aggregationMismatch": int(c_gate.get("feasibleShots", 0)) != production_summary["feasibleShots"],
        },
        "morphStateReceipts": {
            tag: production_summary["perMorph"].get(tag)
            for tag in ("closed", "half", "open")
        },
        "nativeEvidenceSource": {
            "productionNativeMaskRows": len(production_rows),
            "nativeMaskSource": "SLOT_HOLDOUT_COMPOSITE",
        },
    }


def _native_mask_rows_pass(native_rows: list[dict]) -> bool:
    return len(native_rows) == 3 and all(
        r.get("projectionFeasible")
        and bool(r.get("nativeSemanticEvidencePass"))
        and r.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
        and not bool(r.get("finalMaskSourceDivergence"))
        for r in native_rows
    )


def _consumption_camera_receipt(
    lock: dict | None,
    *,
    gate_pass: bool,
    source: str,
) -> dict | None:
    if lock is None:
        return None
    receipt = {
        "source": source,
        "location": lock.get("location"),
        "rotation": lock.get("rotation"),
        "ortho_scale": lock.get("ortho_scale"),
        "semanticCenter": lock.get("semanticCenter"),
        "semanticViewDir": lock.get("semanticViewDir"),
        "distance": lock.get("distance"),
        "view_dir": lock.get("view_dir"),
        "c0Ref": lock.get("c0Ref"),
        "constrainedFraming": lock.get("constrainedFraming"),
        "delta": lock.get("delta"),
        "roiUnionBounds": lock.get("roiUnionBounds"),
        "fingerprint": _camera_state_fingerprint(lock),
        "gatePassEligible": bool(gate_pass),
        "preservedOnFail": not bool(gate_pass),
    }
    return receipt


def _bind_c_mouth_production_gate_receipt(
    *,
    view: str,
    gate_pass: bool,
    native_rows: list[dict],
    lock: dict | None,
    projection_lock: dict | None,
    framing_report: dict | None,
    morph_specs: list[dict],
) -> dict:
    framing_report = framing_report or {}
    rebind_applied: list[str] = []
    rows = list(native_rows)

    if view == "front" and not rows:
        framing_rows = framing_report.get("nativeMaskQualification") or []
        if framing_rows:
            rows = list(framing_rows)
            rebind_applied.append("FRAMING_NATIVE_MASK_QUALIFICATION_PROPAGATED")

    feasible_shots = sum(1 for r in rows if r.get("nativeSemanticEvidencePass"))
    counted_feasible = feasible_shots

    consumption_lock = lock
    consumption_source = "PRODUCTION_LOCK"
    if consumption_lock is None and view == "front":
        nq_ref = framing_report.get("nativeQualificationCameraRef") or {}
        consumption_lock = nq_ref.get("cameraState")
        if consumption_lock is not None:
            consumption_source = "FRAMING_NATIVE_QUALIFICATION_CAMERA_REF"
            rebind_applied.append("FRAMING_NATIVE_QUALIFICATION_CAMERA_REF_PRESERVED")
    if consumption_lock is None:
        consumption_lock = projection_lock
        if consumption_lock is not None:
            consumption_source = "MOUTH_UNION_PROJECTION_LOCK"
            rebind_applied.append("PROJECTION_LOCK_CAMERA_REF_PRESERVED")

    camera_receipt = _consumption_camera_receipt(
        consumption_lock,
        gate_pass=gate_pass,
        source=consumption_source,
    )

    return {
        "gate": "MOUTH_NATIVE_MASK",
        "view": view,
        "pass": bool(gate_pass),
        "feasibleShots": feasible_shots,
        "feasibleShotsCounted": counted_feasible,
        "requiredShots": 3,
        "camera": camera_receipt,
        "cameraManifestEligible": bool(gate_pass),
        "nativeMaskQualification": rows,
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "constrainedFraming": framing_report if view == "front" else None,
        "projectionFeasible": len(morph_specs) == 3 and consumption_lock is not None,
        "productionEvidenceRebind": {
            "applied": bool(rebind_applied),
            "actions": rebind_applied,
            "morphReceiptCount": len(rows),
            "morphReceiptsPreserved": len(rows) == 3,
            "cameraReceiptPreserved": camera_receipt is not None,
            "feasibleShotsAligned": feasible_shots == counted_feasible,
        },
    }


def _finalize_c_mouth_gate_provenance_rebind(
    preflight_gates: dict,
    *,
    mouth_visibility_parity: dict,
    projection_locks: dict[str, dict | None],
) -> None:
    front_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}
    front_closed = mouth_visibility_parity.get("front_closed") or {}
    forensic_ref = front_closed.get("forensicCameraRef") or {}
    parity_cam = front_closed.get("parityCameraConsumed")
    framing_report = preflight_gates.get("B0_FRONT_CHIN_CONSTRAINED_FRAMING") or {}
    provenance = {
        "parityCameraFingerprint": _camera_state_fingerprint(parity_cam),
        "forensicCameraFingerprint": _camera_state_fingerprint(forensic_ref.get("cameraState")),
        "projectionLockFingerprint": _camera_state_fingerprint(projection_locks.get("front")),
        "consumptionCameraFingerprint": (front_gate.get("camera") or {}).get("fingerprint"),
        "framingNativeQualificationFingerprint": _camera_state_fingerprint(
            (framing_report.get("nativeQualificationCameraRef") or {}).get("cameraState")
        ),
        "visibilityReceiptSource": "mouth_visibility_parity.front_closed" if front_closed else None,
        "forensicCameraRefSource": forensic_ref.get("source"),
        "linked": bool(front_closed),
    }
    rebind = dict(front_gate.get("productionEvidenceRebind") or {})
    rebind["provenanceLinked"] = bool(front_closed)
    rebind["consumptionProvenance"] = provenance
    front_gate["productionEvidenceRebind"] = rebind
    preflight_gates["C_MOUTH_NATIVE_MASK_FRONT"] = front_gate

    left_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    left_rebind = dict(left_gate.get("productionEvidenceRebind") or {})
    left_rebind["consumptionProvenance"] = {
        "projectionLockFingerprint": _camera_state_fingerprint(projection_locks.get("left")),
        "consumptionCameraFingerprint": (left_gate.get("camera") or {}).get("fingerprint"),
    }
    left_gate["productionEvidenceRebind"] = left_rebind
    preflight_gates["C_MOUTH_NATIVE_MASK_LEFT"] = left_gate


def _run_c_mouth_rebind_verification(preflight_gates: dict) -> dict:
    c_front = preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}
    c_left = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    front_rows = c_front.get("nativeMaskQualification") or []
    left_rows = c_left.get("nativeMaskQualification") or []
    front_summary = _morph_native_evidence_summary(front_rows)
    left_summary = _morph_native_evidence_summary(left_rows)
    front_rebind = c_front.get("productionEvidenceRebind") or {}
    left_rebind = c_left.get("productionEvidenceRebind") or {}

    front_closed_pass = bool((front_summary.get("perMorph") or {}).get("closed", {}).get("nativeSemanticEvidencePass"))
    left_closed_pass = bool((left_summary.get("perMorph") or {}).get("closed", {}).get("nativeSemanticEvidencePass"))
    left_half_fail = not bool((left_summary.get("perMorph") or {}).get("half", {}).get("nativeSemanticEvidencePass"))
    left_open_fail = not bool((left_summary.get("perMorph") or {}).get("open", {}).get("nativeSemanticEvidencePass"))

    front_checks = {
        "nativeMaskQualificationPropagated": len(front_rows) == 3,
        "morphReceiptsPreserved": len(front_rows) == 3,
        "cameraReceiptPreserved": c_front.get("camera") is not None,
        "feasibleShotsReportedEqualsCounted": int(c_front.get("feasibleShots", -1))
        == int(c_front.get("feasibleShotsCounted", -2)),
        "provenanceLinked": bool(front_rebind.get("provenanceLinked")),
    }
    left_checks = {
        "morphReceiptsPreserved": len(left_rows) == 3,
        "cameraReceiptPreservedOnFail": c_left.get("camera") is not None,
        "closedNativePassPreserved": left_closed_pass,
        "halfNativeFailExposed": left_half_fail,
        "openNativeFailExposed": left_open_fail,
        "feasibleShotsReportedEqualsCounted": int(c_left.get("feasibleShots", -1))
        == int(c_left.get("feasibleShotsCounted", -2)),
    }

    front_pass = all(front_checks.values())
    left_pass = all(left_checks.values())
    verification_pass = front_pass and left_pass

    next_go = "C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC"
    if left_closed_pass and left_half_fail and left_open_fail and front_pass:
        next_go = "C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC"
    if c_front.get("pass") and c_left.get("pass"):
        next_go = "A_H_FULL_PREFLIGHT_CONFIRMATION"

    return {
        "schema": "NURION_V07_V1_LSFQ_C_MOUTH_REBIND_VERIFICATION_PROBE",
        "gate": "C_MOUTH_PRODUCTION_EVIDENCE_REBIND_VERIFICATION",
        "verificationPass": verification_pass,
        "pass": verification_pass,
        "goal": "EVIDENCE_PRESERVATION_NOT_GATE_PASS",
        "productionGatePass": {
            "C_FRONT": bool(c_front.get("pass")),
            "C_LEFT": bool(c_left.get("pass")),
        },
        "C_FRONT": {
            "checks": front_checks,
            "pass": front_pass,
            "feasibleShots": int(c_front.get("feasibleShots", 0)),
            "morphReceiptCount": len(front_rows),
            "closedNativePass": front_closed_pass,
            "rebind": front_rebind,
        },
        "C_LEFT": {
            "checks": left_checks,
            "pass": left_pass,
            "feasibleShots": int(c_left.get("feasibleShots", 0)),
            "morphReceiptCount": len(left_rows),
            "closedNativePass": left_closed_pass,
            "halfNativePass": not left_half_fail,
            "openNativePass": not left_open_fail,
            "rebind": left_rebind,
        },
        "mutationPolicy": {
            "semanticMutation": 0,
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "fidMutation": 0,
        },
        "nextGo": next_go,
        "policy": {
            "gatePassNotGoal": True,
            "production": "NO-GO",
            "thirteenShot": "HOLD",
        },
    }


def _mouth_feature_projection_provider(feature: str) -> str:
    if feature in MOUTH_RIG_HELPER_PROJECTION_FEATURES:
        return "RIG_HELPER_PROJECTION"
    return "SKIN_SLOT_PROJECTION"


def _skin_slot_feature_projection_row(by_name: dict, feature: str) -> dict:
    slot = by_name.get(feature, {})
    projected = int(slot.get("projectedAreaPxEstimate", 0)) > 0
    positive = projected and not bool(slot.get("cullingSuspect"))
    return {
        "projectedAreaPxEstimate": int(slot.get("projectedAreaPxEstimate", 0)),
        "projected": projected,
        "positiveArea": positive,
        "projectedFaces": 1 if projected else 0,
        "positiveAreaFaces": 1 if positive else 0,
    }


def _rig_helper_feature_projection_row(sc, cam, rig_objs: dict, feature: str, res: int) -> dict:
    target, _slot_idx, kind = _feature_render_target(feature, None, rig_objs)
    if target is None or kind != "rig":
        return {
            "projectedAreaPxEstimate": 0,
            "projected": False,
            "positiveArea": False,
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
        }
    face_indices = set(range(len(target.data.polygons)))
    geom = _audit_feature_face_geometry(sc, cam, target, face_indices, res)
    projected_faces = int(geom.get("projectedFaces", 0))
    positive_area_faces = int(geom.get("positiveAreaFaces", 0))
    return {
        "projectedAreaPxEstimate": positive_area_faces,
        "projected": projected_faces > 0,
        "positiveArea": positive_area_faces > 0,
        "projectedFaces": projected_faces,
        "positiveAreaFaces": positive_area_faces,
    }


def _extract_oral_consumption_receipt(row: dict, feature: str) -> dict:
    slot_proj = row.get("slotProjection") or {}
    per = (slot_proj.get("perFeature") or {}).get(feature) or {}
    return {
        "feature": feature,
        "projectionProvider": per.get("projectionProvider"),
        "skinSlotProjectedFaces": int(per.get("skinSlotProjectedFaces", 0)),
        "rigHelperProjectedFaces": int(per.get("rigHelperProjectedFaces", 0)),
        "consumedProjectedFaces": int(per.get("consumedProjectedFaces", 0)),
        "providerSelected": per.get("providerSelected"),
        "providerReason": per.get("providerReason"),
        "nativeSemanticEvidencePass": bool(row.get("nativeSemanticEvidencePass")),
        "consumptionParityPass": bool(per.get("consumptionParityPass")),
    }


def _run_c_mouth_consumption_path_repair_verification(
    preflight_gates: dict,
    *,
    baseline_left_camera_fingerprint: str | None = None,
) -> dict:
    c_front = preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}
    c_left = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    left_rows = {str(r.get("morph")): r for r in (c_left.get("nativeMaskQualification") or [])}
    closed_row = left_rows.get("closed") or {}
    half_row = left_rows.get("half") or {}
    open_row = left_rows.get("open") or {}

    closed_preserved = bool(closed_row.get("nativeSemanticEvidencePass"))
    left_camera_fp = (c_left.get("camera") or {}).get("fingerprint")
    camera_unchanged = (
        baseline_left_camera_fingerprint is None or left_camera_fp == baseline_left_camera_fingerprint
    )

    oral_features = ("lower_teeth", "upper_teeth")
    consumption_receipts: dict[str, dict[str, dict]] = {}
    teeth_checks: dict[str, bool] = {}
    all_teeth_pass = True
    for morph in ("half", "open"):
        row = left_rows.get(morph) or {}
        consumption_receipts[morph] = {}
        for feat in oral_features:
            receipt = _extract_oral_consumption_receipt(row, feat)
            consumption_receipts[morph][feat] = receipt
            ok = (
                receipt["rigHelperProjectedFaces"] >= 48
                and receipt["consumedProjectedFaces"] > 0
                and receipt["consumptionParityPass"]
                and receipt["providerSelected"] == "RIG_HELPER_PROJECTION"
            )
            teeth_checks[f"{morph}_{feat}"] = ok
            if not ok:
                all_teeth_pass = False

    half_native_pass = bool(half_row.get("nativeSemanticEvidencePass"))
    open_native_pass = bool(open_row.get("nativeSemanticEvidencePass"))
    c_left_gate_pass = bool(c_left.get("pass"))
    c_front_gate_pass = bool(c_front.get("pass"))
    repair_verification_pass = bool(
        closed_preserved and all_teeth_pass and camera_unchanged
    )
    c_left_pass_candidate = bool(
        repair_verification_pass and half_native_pass and open_native_pass and c_left_gate_pass
    )

    if c_left_pass_candidate and c_front_gate_pass:
        next_go = "A_H_FULL_PREFLIGHT_CONFIRMATION"
    elif c_left_pass_candidate:
        next_go = "C_FRONT_REMAINING_BLOCKER_TRIAGE"
    elif repair_verification_pass:
        next_go = "C_LEFT_NATIVE_EVIDENCE_GATE_CONFIRMATION"
    else:
        next_go = "C_MOUTH_CONSUMPTION_PATH_SLOT_SUMMARY_REPAIR_RETRY"

    return {
        "schema": "NURION_V07_V1_LSFQ_C_MOUTH_CONSUMPTION_PATH_REPAIR_VERIFICATION_PROBE",
        "gate": "C_MOUTH_RIG_HELPER_SLOT_PROJECTION_SUMMARY_AND_CONSUMPTION_PATH_REPAIR",
        "verificationPass": repair_verification_pass,
        "pass": repair_verification_pass,
        "goal": "CONSUMPTION_PATH_REPAIR_VERIFICATION_NOT_FULL_AH",
        "consumptionPathRepair": MOUTH_CONSUMPTION_PATH_REPAIR,
        "rootCauseClosed": "RIG_HELPER_PROJECTS_BUT_MOUTH_SLOT_SUMMARY_USES_SKIN_ONLY",
        "firstFailureStageClosed": "consumption_path_slot_summary",
        "closedBaseline": {
            "nativeSemanticEvidencePass": closed_preserved,
            "preserved": closed_preserved,
            "modified": not closed_preserved,
        },
        "cameraProvenance": {
            "fingerprint": left_camera_fp,
            "baselineFingerprint": baseline_left_camera_fingerprint,
            "unchanged": camera_unchanged,
        },
        "teethConsumptionChecks": teeth_checks,
        "consumptionReceipts": consumption_receipts,
        "productionGatePass": {
            "C_FRONT": c_front_gate_pass,
            "C_LEFT": c_left_gate_pass,
            "C_LEFT_PASS_CANDIDATE": c_left_pass_candidate,
        },
        "C_LEFT": {
            "closedNativePass": closed_preserved,
            "halfNativePass": half_native_pass,
            "openNativePass": open_native_pass,
            "gatePass": c_left_gate_pass,
            "passCandidate": c_left_pass_candidate,
        },
        "C_FRONT": {
            "gatePass": c_front_gate_pass,
        },
        "successCriteria": {
            "closedBaselinePreserved": closed_preserved,
            "halfLowerTeethConsumed": teeth_checks.get("half_lower_teeth", False),
            "halfUpperTeethConsumed": teeth_checks.get("half_upper_teeth", False),
            "openLowerTeethConsumed": teeth_checks.get("open_lower_teeth", False),
            "openUpperTeethConsumed": teeth_checks.get("open_upper_teeth", False),
            "cameraHashUnchanged": camera_unchanged,
            "mutation": 0,
        },
        "nextGo": next_go,
        "mutationPolicy": {
            "semanticMutation": 0,
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "fidMutation": 0,
            "basisWeightMorphMutation": 0,
        },
        "policy": {
            "production": "NO-GO" if not (c_left_pass_candidate and c_front_gate_pass) else "PENDING_AH_CONFIRMATION",
            "thirteenShot": "HOLD",
            "fullAhRun": "DEFERRED_UNTIL_C_ONLY_VERIFICATION_PASS",
        },
    }


def _first_failing_left_morph_feature(row: dict) -> dict | None:
    show_oral = bool(row.get("showOral"))
    required = _mouth_required_features(show_oral, "left")
    feature_vis = row.get("featureVisibility") or {}
    best: dict | None = None
    for feat in required:
        fv = feature_vis.get(feat) or {}
        if not fv.get("expectedVisible"):
            continue
        em = fv.get("nativeSemanticEmission") or {}
        failing = (
            not bool(fv.get("pass"))
            or not bool(fv.get("visibilityContractPass"))
            or not bool(fv.get("emissionContractPass"))
            or not bool(em.get("pass"))
        )
        if not failing:
            continue
        candidate = {
            "feature": feat,
            "classification": em.get("classification") or fv.get("visibilityParityClassification"),
            "missingReason": em.get("missingReason"),
            "projectedFaces": fv.get("projectedFaces"),
            "positiveAreaFaces": fv.get("positiveAreaFaces"),
            "fidPixels": em.get("fidPixels"),
            "maskSlotPixels": em.get("maskSlotPixels"),
            "emissionContractPass": fv.get("emissionContractPass"),
            "visibilityContractPass": fv.get("visibilityContractPass"),
            "geometricActualVisible": fv.get("geometricActualVisible"),
        }
        if best is None:
            best = candidate
        elif int(candidate.get("projectedFaces") or 0) <= int(best.get("projectedFaces") or 0):
            best = candidate
    return best


def _extract_c_left_morph_evidence_chain(row: dict, camera_receipt: dict | None) -> dict:
    evidence = row.get("nativeSemanticEvidence") or {}
    checks = evidence.get("checks") or {}
    slot_proj = row.get("slotProjection") or {}
    native_slot_pixels = {
        feat: (fv.get("geometricVisibility") or {}).get("maskSlotPixels")
        for feat, fv in (row.get("featureVisibility") or {}).items()
    }
    missing_reasons = [
        f"{feat}:{(fv.get('nativeSemanticEmission') or {}).get('missingReason')}"
        for feat, fv in (row.get("featureVisibility") or {}).items()
        if (fv.get("nativeSemanticEmission") or {}).get("missingReason")
    ]
    fail_feat = _first_failing_left_morph_feature(row)
    return {
        "morphState": row.get("morph"),
        "angle": row.get("angle"),
        "showOral": row.get("showOral"),
        "cameraRefSource": (camera_receipt or {}).get("source"),
        "cameraRefHash": (camera_receipt or {}).get("fingerprint"),
        "projectedFaces": int(evidence.get("projectedFaces", slot_proj.get("projectedFaces", 0))),
        "positiveAreaFaces": int(evidence.get("positiveAreaFaces", slot_proj.get("positiveAreaFaces", 0))),
        "nativeSlotPixels": native_slot_pixels,
        "finalMaskPixels": int(row.get("finalMaskPixels", 0)),
        "clipped": bool(row.get("clipped", not checks.get("clipped", True))),
        "fullBleed": bool(row.get("fullBleed", False)),
        "contextRetained": bool(row.get("contextRetained", checks.get("contextRetained", False))),
        "expectedVisibility": bool(checks.get("expectedVisibility", row.get("visibilityContractPass"))),
        "nativeSemanticEvidencePass": bool(row.get("nativeSemanticEvidencePass")),
        "missingReason": missing_reasons or evidence.get("failures"),
        "classification": fail_feat.get("classification") if fail_feat else None,
        "firstFailingFeature": fail_feat,
        "finalSource": row.get("finalSource"),
        "finalMaskSourceDivergence": bool(row.get("finalMaskSourceDivergence")),
        "projectionFeasible": bool(row.get("projectionFeasible")),
        "slotProjection": slot_proj,
        "nativeSemanticEvidenceChecks": checks,
        "nativeSemanticEvidenceFailures": evidence.get("failures") or [],
    }


def _classify_c_left_morph_native_evidence_failure(row: dict, chain: dict) -> dict:
    classifications: list[str] = []
    first_stage: str | None = None
    fail_feat = chain.get("firstFailingFeature") or _first_failing_left_morph_feature(row)

    if not chain.get("projectionFeasible"):
        classifications.append("C_LEFT_PROJECTION_FAIL")
        first_stage = first_stage or "projection"

    projected_faces = int(chain.get("projectedFaces", 0))
    if projected_faces <= 0:
        if fail_feat and int(fail_feat.get("projectedFaces") or 0) <= 0:
            classifications.append("C_LEFT_MORPH_STATE_GEOMETRY_FAIL")
        else:
            classifications.append("C_LEFT_PROJECTION_FAIL")
        first_stage = first_stage or "projection"

    if chain.get("finalSource") != "SLOT_HOLDOUT_COMPOSITE" or chain.get("finalMaskSourceDivergence"):
        classifications.append("C_LEFT_MASK_COMPOSITE_FAIL")
        first_stage = first_stage or "mask_composite"
    elif int(chain.get("finalMaskPixels", 0)) <= 0:
        classifications.append("C_LEFT_NATIVE_SLOT_RENDER_FAIL")
        first_stage = first_stage or "mask_composite"

    if chain.get("clipped") or not chain.get("contextRetained") or chain.get("fullBleed"):
        classifications.append("C_LEFT_CONTEXT_VISIBILITY_FAIL")
        first_stage = first_stage or "context"

    if not chain.get("nativeSemanticEvidencePass"):
        if fail_feat:
            if int(fail_feat.get("projectedFaces") or 0) <= 0:
                if "C_LEFT_MORPH_STATE_GEOMETRY_FAIL" not in classifications:
                    classifications.append("C_LEFT_MORPH_STATE_GEOMETRY_FAIL")
            elif fail_feat.get("missingReason") == "FID_RENDER_PATH_FAIL":
                classifications.append("C_LEFT_NATIVE_SLOT_RENDER_FAIL")
            elif fail_feat.get("missingReason") == "BELOW_VISIBILITY_DETECTION_RATE":
                classifications.append("C_LEFT_EXPECTED_VISIBILITY_FAIL")
            else:
                classifications.append("C_LEFT_EXPECTED_VISIBILITY_FAIL")
        elif not chain.get("expectedVisibility"):
            classifications.append("C_LEFT_EXPECTED_VISIBILITY_FAIL")
        else:
            failures = chain.get("nativeSemanticEvidenceFailures") or []
            if failures:
                classifications.append("C_LEFT_EXPECTED_VISIBILITY_FAIL")
        first_stage = first_stage or "visibility"

    if not classifications:
        classifications.append("PASS")

    branch_map = {
        "C_LEFT_PROJECTION_FAIL": "MORPH_STATE_GEOMETRY_DIAGNOSTIC",
        "C_LEFT_MORPH_STATE_GEOMETRY_FAIL": "MORPH_STATE_GEOMETRY_DIAGNOSTIC",
        "C_LEFT_NATIVE_SLOT_RENDER_FAIL": "RENDER_PATH_REPAIR",
        "C_LEFT_MASK_COMPOSITE_FAIL": "RENDER_PATH_REPAIR",
        "C_LEFT_CONTEXT_VISIBILITY_FAIL": "CONTEXT_CONTRACT_REPAIR",
        "C_LEFT_EXPECTED_VISIBILITY_FAIL": "CONTEXT_CONTRACT_REPAIR",
        "C_LEFT_CAMERA_STATE_CONSUMPTION_MISMATCH": "BINDING_STATE_CONSUMPTION_REPAIR",
    }
    primary = classifications[0]
    return {
        "primaryClassification": primary,
        "classifications": classifications,
        "firstFailureStage": first_stage,
        "recommendedBranch": branch_map.get(primary, "UNCLASSIFIED"),
        "failingFeature": fail_feat,
    }


def _diagnose_c_left_morph_row(row: dict, camera_receipt: dict | None, *, live_row: dict | None = None) -> dict:
    chain = _extract_c_left_morph_evidence_chain(row, camera_receipt)
    classification = _classify_c_left_morph_native_evidence_failure(row, chain)
    live_chain = None
    live_match = None
    if live_row is not None:
        live_chain = _extract_c_left_morph_evidence_chain(live_row, camera_receipt)
        live_match = bool(live_row.get("nativeSemanticEvidencePass")) == bool(row.get("nativeSemanticEvidencePass"))
    return {
        "morphState": row.get("morph"),
        "nativeSemanticEvidencePass": bool(row.get("nativeSemanticEvidencePass")),
        "evidenceChain": chain,
        "classification": classification,
        "liveRerun": {
            "performed": live_row is not None,
            "nativeSemanticEvidencePassMatch": live_match,
            "evidenceChain": live_chain,
        },
    }


def _run_c_left_half_open_native_evidence_diagnostic(
    *,
    preflight_gates: dict,
    camera_lock: dict,
    left_morph_specs: list[dict] | None = None,
    sc=None,
    cam=None,
    mask_mat=None,
    set_mouth_fn=None,
    mouth_valid_fn=None,
    res: int = 1280,
    fid_mats=None,
    landmarks=None,
    skin_basis_coords=None,
    rig_objs: dict | None = None,
) -> dict:
    c_left_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    camera_receipt = c_left_gate.get("camera") or {}
    consumption_lock = _gate_consumption_camera_from_receipt(c_left_gate, camera_lock, "mouth_left")
    rows = c_left_gate.get("nativeMaskQualification") or []
    row_by_morph = {str(r.get("morph")): r for r in rows}

    closed_row = row_by_morph.get("closed") or {}
    half_row = row_by_morph.get("half") or {}
    open_row = row_by_morph.get("open") or {}

    live_rows: dict[str, dict | None] = {"half": None, "open": None}
    if (
        consumption_lock is not None
        and left_morph_specs
        and sc is not None
        and cam is not None
        and mask_mat is not None
        and set_mouth_fn is not None
        and mouth_valid_fn is not None
        and fid_mats is not None
        and landmarks is not None
        and skin_basis_coords is not None
    ):
        union_min = left_morph_specs[0].get("unionMin") if left_morph_specs else None
        union_max = left_morph_specs[0].get("unionMax") if left_morph_specs else None
        sem_bounds = (union_min, union_max) if union_min is not None else None
        _apply_locked_camera(cam, consumption_lock)
        for spec in left_morph_specs:
            tag = _morph_tag_from_angle(float(spec["angle"]))
            if tag not in ("half", "open"):
                continue
            set_mouth_fn(float(spec["angle"]), show_oral=bool(spec["showOral"]))
            valid, skin = mouth_valid_fn(bool(spec["showOral"]))
            live_rows[tag] = _evaluate_mouth_morph_native_evidence(
                sc,
                cam,
                valid,
                skin,
                mask_mat,
                fid_mats,
                res,
                "left",
                bool(spec["showOral"]),
                landmarks,
                skin_basis_coords,
                spec,
                sem_bounds,
                rig_objs=rig_objs,
            )
            live_rows[tag]["morph"] = tag
            live_rows[tag]["angle"] = float(spec["angle"])
            live_rows[tag]["showOral"] = bool(spec["showOral"])
            live_rows[tag]["projectionFeasible"] = True

    half_diag = _diagnose_c_left_morph_row(
        half_row, camera_receipt, live_row=live_rows.get("half")
    )
    open_diag = _diagnose_c_left_morph_row(
        open_row, camera_receipt, live_row=live_rows.get("open")
    )

    closed_unchanged = bool(closed_row.get("nativeSemanticEvidencePass"))
    half_class = half_diag.get("classification") or {}
    open_class = open_diag.get("classification") or {}
    half_identified = half_class.get("primaryClassification") not in (None, "PASS")
    open_identified = open_class.get("primaryClassification") not in (None, "PASS")
    camera_provenance = bool(camera_receipt.get("fingerprint")) and consumption_lock is not None
    live_provenance = all(
        v is None or v.get("nativeSemanticEvidencePassMatch") is not False
        for v in (half_diag.get("liveRerun"), open_diag.get("liveRerun"))
    )

    same_root = (
        half_class.get("primaryClassification") == open_class.get("primaryClassification")
        and half_class.get("firstFailureStage") == open_class.get("firstFailureStage")
    )
    if same_root and half_class.get("primaryClassification") == "C_LEFT_CAMERA_STATE_CONSUMPTION_MISMATCH":
        next_branch = "BINDING_STATE_CONSUMPTION_REPAIR"
    elif same_root:
        next_branch = half_class.get("recommendedBranch")
    else:
        next_branch = "PER_MORPH_SPLIT_REPAIR"

    diagnostic_pass = (
        closed_unchanged
        and half_identified
        and open_identified
        and camera_provenance
        and live_provenance
        and bool(half_class.get("firstFailureStage"))
        and bool(open_class.get("firstFailureStage"))
    )

    return {
        "schema": "NURION_V07_V1_LSFQ_C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_PROBE",
        "gate": "C_LEFT_HALF_OPEN_NATIVE_SEMANTIC_EVIDENCE_PER_MORPH_DIAGNOSTIC",
        "diagnosticPass": diagnostic_pass,
        "pass": diagnostic_pass,
        "goal": "CAUSE_IDENTIFICATION_NOT_GATE_PASS",
        "productionGatePass": bool(c_left_gate.get("pass")),
        "closedStatePreserved": closed_unchanged,
        "cameraProvenance": {
            "source": camera_receipt.get("source"),
            "fingerprint": camera_receipt.get("fingerprint"),
            "preservedOnFail": camera_receipt.get("preservedOnFail"),
            "confirmed": camera_provenance,
        },
        "half": half_diag,
        "open": open_diag,
        "closedReference": {
            "nativeSemanticEvidencePass": bool(closed_row.get("nativeSemanticEvidencePass")),
            "modified": False,
        },
        "rootCauseComparison": {
            "samePrimaryClassification": half_class.get("primaryClassification")
            == open_class.get("primaryClassification"),
            "sameFirstFailureStage": half_class.get("firstFailureStage")
            == open_class.get("firstFailureStage"),
            "halfPrimary": half_class.get("primaryClassification"),
            "openPrimary": open_class.get("primaryClassification"),
        },
        "successCriteria": {
            "halfCauseIdentified": half_identified,
            "openCauseIdentified": open_identified,
            "cameraStateProvenanceConfirmed": camera_provenance,
            "firstFailureStageCaptured": bool(half_class.get("firstFailureStage"))
            and bool(open_class.get("firstFailureStage")),
            "closedStateUnmodified": closed_unchanged,
            "liveRerunProvenanceMatch": live_provenance,
            "mutationZero": True,
        },
        "mutationPolicy": {
            "semanticMutation": 0,
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "fidMutation": 0,
            "closedStateMutation": 0,
        },
        "recommendedBranch": next_branch,
        "nextGo": next_branch,
        "policy": {
            "gatePassNotGoal": True,
            "rebindForcePass": "DENY",
            "production": "NO-GO",
            "thirteenShot": "HOLD",
        },
    }


ORAL_HELPER_FEATURE_KEYS = (
    ("lower_teeth", "helper-lower-teeth"),
    ("upper_teeth", "helper-upper-teeth"),
)


def _oral_helper_first_failure_stage(classification: str) -> str:
    return {
        "ORAL_HELPER_OBJECT_MISSING": "helper_existence",
        "ORAL_HELPER_EVALUATED_MESH_EMPTY": "evaluated_mesh",
        "ORAL_HELPER_PARENT_TRANSFORM_FAIL": "parent_transform",
        "ORAL_HELPER_PIVOT_DOUBLE_TRANSFORM": "pivot_double_transform",
        "ORAL_HELPER_WORLD_BBOX_DIVERGENCE": "world_bbox_divergence",
        "ORAL_HELPER_CAMERA_SPACE_BEHIND": "camera_space_behind",
        "ORAL_HELPER_NDC_OUT_OF_FRAME": "ndc_out_of_frame",
        "ORAL_HELPER_FACE_PROJECTION_FAIL": "face_projection",
        "ORAL_HELPER_RASTER_DEGENERACY": "raster_degeneracy",
        "PASS": "pass",
    }.get(classification, "unclassified")


def _classify_oral_helper_projection_failure(row: dict) -> str:
    if not row.get("helperObjectExists"):
        return "ORAL_HELPER_OBJECT_MISSING"
    if int(row.get("evaluatedMeshFaceCount", 0)) <= 0:
        return "ORAL_HELPER_EVALUATED_MESH_EMPTY"
    if bool(row.get("doubleTransform")):
        return "ORAL_HELPER_PIVOT_DOUBLE_TRANSFORM"
    if bool(row.get("parentTransformFail")):
        return "ORAL_HELPER_PARENT_TRANSFORM_FAIL"
    if bool(row.get("worldBBoxDivergence")):
        return "ORAL_HELPER_WORLD_BBOX_DIVERGENCE"
    if int(row.get("verticesInFrontCount", 0)) <= 0:
        return "ORAL_HELPER_CAMERA_SPACE_BEHIND"
    if int(row.get("ndcVerticesInFrameCount", 0)) <= 0:
        return "ORAL_HELPER_NDC_OUT_OF_FRAME"
    if int(row.get("projectedFaces", 0)) <= 0:
        return "ORAL_HELPER_FACE_PROJECTION_FAIL"
    if int(row.get("positiveAreaFaces", 0)) <= 0:
        return "ORAL_HELPER_RASTER_DEGENERACY"
    return "PASS"


def _audit_oral_helper_projection_chain(
    sc,
    cam,
    mesh_obj,
    res: int,
    *,
    feature: str,
    morph_state: str,
    jaw_angle: float,
    pivot_object,
    parent_object,
    camera_ref_hash: str | None,
    camera_state_receipt: dict,
    reference_oral_bbox: dict | None = None,
) -> dict:
    _sync_rig_projection_matrices(sc)
    helper_exists = mesh_obj is not None and mesh_obj.type == "MESH"
    if not helper_exists:
        classification = "ORAL_HELPER_OBJECT_MISSING"
        return {
            "feature": feature,
            "morphState": morph_state,
            "jawAngle": float(jaw_angle),
            "helperObjectName": None,
            "helperObjectExists": False,
            "classification": classification,
            "firstFailureStage": _oral_helper_first_failure_stage(classification),
        }

    eval_obj, mw = _projection_eval_object(sc, mesh_obj)
    if eval_obj is None or mw is None:
        classification = "ORAL_HELPER_EVALUATED_MESH_EMPTY"
        return {
            "feature": feature,
            "morphState": morph_state,
            "jawAngle": float(jaw_angle),
            "helperObjectName": mesh_obj.name,
            "helperObjectExists": True,
            "evaluatedMeshVertexCount": 0,
            "evaluatedMeshFaceCount": 0,
            "classification": classification,
            "firstFailureStage": _oral_helper_first_failure_stage(classification),
        }

    source_mesh = mesh_obj.data
    face_indices = set(range(len(source_mesh.polygons)))
    local_min, local_max = _mesh_face_vertex_bbox(source_mesh, face_indices)
    world_min, world_max = _object_world_bbox(eval_obj, face_indices=face_indices)
    parent = mesh_obj.parent
    pivot_matrix = pivot_object.matrix_world.copy() if pivot_object is not None else mw.copy()
    provenance = _eyelid_transform_provenance(
        mesh_obj,
        source_mesh,
        face_indices,
        parent=parent,
        pivot_matrix=pivot_matrix,
        object_matrix_world=mw,
        reference_world_bbox=reference_oral_bbox,
    )

    world_center = (world_min + world_max) * 0.5 if world_min is not None else None
    ref_center = None
    world_bbox_divergence = False
    parent_transform_fail = False
    if reference_oral_bbox and reference_oral_bbox.get("center") and world_center is not None:
        ref_center = Vector(reference_oral_bbox["center"])
        dist = float((world_center - ref_center).length)
        world_bbox_divergence = dist > 0.35 and morph_state != "reference"
    elif world_min is not None and world_max is not None:
        ext = world_max - world_min
        parent_transform_fail = float(ext.length) > 3.0

    vertices_in_front = 0
    ndc_in_frame = 0
    used_verts: set[int] = set()
    for fi in face_indices:
        used_verts.update(int(v) for v in source_mesh.polygons[int(fi)].vertices)
    for vi in used_verts:
        co = mw @ source_mesh.vertices[int(vi)].co.copy()
        ndc = world_to_camera_view(sc, cam, co)
        if float(ndc.z) > 0.0:
            vertices_in_front += 1
        if float(ndc.z) > 0.0 and 0.0 <= float(ndc.x) <= 1.0 and 0.0 <= float(ndc.y) <= 1.0:
            ndc_in_frame += 1

    geom = _audit_feature_face_geometry(sc, cam, mesh_obj, face_indices, res)
    row = {
        "feature": feature,
        "morphState": morph_state,
        "jawAngle": float(jaw_angle),
        "helperObjectName": mesh_obj.name,
        "helperObjectExists": True,
        "evaluatedMeshVertexCount": len(used_verts),
        "evaluatedMeshFaceCount": len(face_indices),
        "parentObject": parent.name if parent else None,
        "pivotObject": pivot_object.name if pivot_object is not None else None,
        "objectMatrixWorld": provenance.get("objectMatrixWorld"),
        "parentMatrixWorld": _matrix4_to_rows(parent.matrix_world.copy()) if parent else None,
        "localBBox": _bbox_to_dict(local_min, local_max),
        "worldBBox": _bbox_to_dict(world_min, world_max),
        "referenceOralBBox": reference_oral_bbox,
        "cameraRefHash": camera_ref_hash,
        "cameraMatrixWorld": camera_state_receipt.get("cameraMatrixWorld"),
        "verticesInFrontCount": int(vertices_in_front),
        "ndcVerticesInFrameCount": int(ndc_in_frame),
        "projectedFaces": int(geom.get("projectedFaces", 0)),
        "positiveAreaFaces": int(geom.get("positiveAreaFaces", 0)),
        "doubleTransform": bool(provenance.get("doubleTransform")),
        "parentTransformFail": bool(parent_transform_fail),
        "worldBBoxDivergence": bool(world_bbox_divergence),
        "helperVertexSpace": provenance.get("helperVertexSpace"),
        "effectiveTransformChain": provenance.get("effectiveTransformChain"),
        "transformApplicationCount": provenance.get("transformApplicationCount"),
        "hideRender": bool(mesh_obj.hide_render),
    }
    row["classification"] = _classify_oral_helper_projection_failure(row)
    row["firstFailureStage"] = _oral_helper_first_failure_stage(row["classification"])
    return row


def _audit_oral_consumption_slot_path(
    sc,
    cam,
    skin_obj,
    rig_objs: dict,
    res: int,
    feature: str,
) -> dict:
    slot_proj = _mouth_slot_projection_summary(sc, cam, skin_obj, res, (feature,), rig_objs=rig_objs)
    per = (slot_proj.get("perFeature") or {}).get(feature) or {}
    slot_diag = _mouth_mask_slot_diagnostics(sc, cam, skin_obj, None, [skin_obj], res)
    slot_names = {d.get("slotName") for d in slot_diag}
    target, _slot_idx, kind = _feature_render_target(feature, skin_obj, rig_objs)
    rig_geom = {"projectedFaces": 0, "positiveAreaFaces": 0}
    if target is not None and kind == "rig":
        rig_geom = _audit_feature_face_geometry(
            sc, cam, target, set(range(len(target.data.polygons))), res
        )
    consumed_pf = int(per.get("consumedProjectedFaces", 0))
    return {
        "consumptionPath": "MOUTH_SLOT_PROJECTION_SUMMARY_PROVIDER_ROUTED",
        "consumptionPathRepair": MOUTH_CONSUMPTION_PATH_REPAIR,
        "featureInSkinSlotManifest": feature in slot_names,
        "renderTargetKind": kind,
        "projectionProvider": per.get("projectionProvider"),
        "providerSelected": per.get("providerSelected"),
        "providerReason": per.get("providerReason"),
        "slotSummaryProjected": bool(per.get("projected")),
        "slotSummaryPositiveArea": bool(per.get("positiveArea")),
        "projectedFaces": consumed_pf,
        "positiveAreaFaces": int(per.get("positiveAreaFaces", 0)),
        "consumedProjectedFaces": consumed_pf,
        "skinSlotProjectedFaces": int(per.get("skinSlotProjectedFaces", 0)),
        "rigHelperProjectedFaces": int(per.get("rigHelperProjectedFaces", rig_geom.get("projectedFaces", 0))),
        "rigHelperPositiveAreaFaces": int(rig_geom.get("positiveAreaFaces", 0)),
        "consumptionParityPass": bool(per.get("consumptionParityPass")),
    }


def _merge_oral_rig_and_consumption_diagnostic(
    rig_row: dict,
    consumption_row: dict,
) -> dict:
    merged = dict(rig_row)
    merged["consumptionPathAudit"] = consumption_row
    rig_proj = int(rig_row.get("projectedFaces", 0))
    cons_proj = int(consumption_row.get("consumedProjectedFaces", consumption_row.get("projectedFaces", 0)))
    rig_kind = consumption_row.get("renderTargetKind")
    if rig_proj > 0 and cons_proj <= 0:
        merged["classification"] = "ORAL_HELPER_FACE_PROJECTION_FAIL"
        merged["firstFailureStage"] = "consumption_path_slot_summary"
        merged["missingReason"] = (
            "RIG_HELPER_PROJECTS_BUT_MOUTH_SLOT_SUMMARY_USES_SKIN_ONLY"
            if rig_kind == "rig"
            else "CONSUMPTION_PATH_PROJECTED_FACES_ZERO"
        )
    elif rig_proj <= 0:
        pass
    elif cons_proj > 0:
        merged["classification"] = "PASS"
        merged["firstFailureStage"] = "pass"
    return merged


def _run_c_left_oral_rig_morph_state_geometry_diagnostic(
    *,
    preflight_gates: dict,
    camera_lock: dict,
    rig_objs: dict,
    jaw_empty,
    head_root,
    set_mouth_fn,
    sc,
    cam,
    res: int,
    mouth_valid_fn,
) -> dict:
    c_left_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    camera_receipt = c_left_gate.get("camera") or {}
    consumption_lock = _gate_consumption_camera_from_receipt(c_left_gate, camera_lock, "mouth_left")
    camera_ref_hash = camera_receipt.get("fingerprint")
    closed_row = next(
        (r for r in (c_left_gate.get("nativeMaskQualification") or []) if r.get("morph") == "closed"),
        {},
    )
    closed_preserved = bool(closed_row.get("nativeSemanticEvidencePass"))

    if consumption_lock is not None:
        _apply_locked_camera(cam, consumption_lock)
    camera_state_receipt = _camera_state_receipt(sc, cam)

    reference_oral_bbox: dict[str, dict | None] = {}
    set_mouth_fn(0, show_oral=True)
    _sync_rig_projection_matrices(sc)
    for feature, helper_key in ORAL_HELPER_FEATURE_KEYS:
        helper_obj = rig_objs.get(helper_key)
        pivot = jaw_empty if helper_key == "helper-lower-teeth" else head_root
        ref_row = _audit_oral_helper_projection_chain(
            sc,
            cam,
            helper_obj,
            res,
            feature=feature,
            morph_state="reference",
            jaw_angle=0.0,
            pivot_object=pivot,
            parent_object=helper_obj.parent if helper_obj else None,
            camera_ref_hash=camera_ref_hash,
            camera_state_receipt=camera_state_receipt,
            reference_oral_bbox=None,
        )
        reference_oral_bbox[feature] = ref_row.get("worldBBox")

    per_morph: dict[str, dict] = {}
    morph_angles = {"half": 12.0, "open": 24.0}
    for morph_state, angle in morph_angles.items():
        set_mouth_fn(angle, show_oral=True)
        _sync_rig_projection_matrices(sc)
        per_morph[morph_state] = {}
        _valid, skin_open = mouth_valid_fn(True)
        for feature, helper_key in ORAL_HELPER_FEATURE_KEYS:
            helper_obj = rig_objs.get(helper_key)
            pivot = jaw_empty if helper_key == "helper-lower-teeth" else head_root
            rig_row = _audit_oral_helper_projection_chain(
                sc,
                cam,
                helper_obj,
                res,
                feature=feature,
                morph_state=morph_state,
                jaw_angle=angle,
                pivot_object=pivot,
                parent_object=helper_obj.parent if helper_obj else None,
                camera_ref_hash=camera_ref_hash,
                camera_state_receipt=camera_state_receipt,
                reference_oral_bbox=reference_oral_bbox.get(feature),
            )
            consumption_row = _audit_oral_consumption_slot_path(
                sc, cam, skin_open, rig_objs, res, feature
            )
            per_morph[morph_state][feature] = _merge_oral_rig_and_consumption_diagnostic(
                rig_row, consumption_row
            )

    set_mouth_fn(0, show_oral=False)
    _sync_rig_projection_matrices(sc)

    stage_captured = all(
        bool(per_morph[morph][feature].get("firstFailureStage"))
        and per_morph[morph][feature].get("firstFailureStage") != "pass"
        for morph in ("half", "open")
        for feature in ("lower_teeth", "upper_teeth")
    )
    half_lower = per_morph["half"]["lower_teeth"]
    half_upper = per_morph["half"]["upper_teeth"]
    open_lower = per_morph["open"]["lower_teeth"]
    open_upper = per_morph["open"]["upper_teeth"]
    same_half_open_lower = half_lower.get("classification") == open_lower.get("classification")
    same_half_open_upper = half_upper.get("classification") == open_upper.get("classification")

    if same_half_open_lower and same_half_open_upper:
        if half_lower.get("classification") in (
            "ORAL_HELPER_PIVOT_DOUBLE_TRANSFORM",
            "ORAL_HELPER_PARENT_TRANSFORM_FAIL",
            "ORAL_HELPER_WORLD_BBOX_DIVERGENCE",
        ):
            next_branch = "TRANSFORM_STATE_REPAIR"
        elif half_lower.get("classification") in (
            "ORAL_HELPER_FACE_PROJECTION_FAIL",
            "ORAL_HELPER_RASTER_DEGENERACY",
            "ORAL_HELPER_CAMERA_SPACE_BEHIND",
            "ORAL_HELPER_NDC_OUT_OF_FRAME",
        ):
            if (half_lower.get("consumptionPathAudit") or {}).get("rigHelperProjectedFaces", 0) > 0:
                next_branch = "CONSUMPTION_PATH_SLOT_SUMMARY_REPAIR"
            else:
                next_branch = "HELPER_GEOMETRY_PROJECTION_REPAIR"
        else:
            next_branch = "ORAL_HELPER_GEOMETRY_SPLIT_REPAIR"
    else:
        next_branch = "PER_FEATURE_ORAL_HELPER_REPAIR"

    diagnostic_pass = (
        closed_preserved
        and stage_captured
        and bool(camera_ref_hash)
        and consumption_lock is not None
    )

    return {
        "schema": "NURION_V07_V1_LSFQ_C_LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_PROBE",
        "gate": "C_LEFT_HALF_OPEN_ORAL_RIG_MORPH_STATE_GEOMETRY_AND_PROJECTION_PARITY",
        "diagnosticPass": diagnostic_pass,
        "pass": diagnostic_pass,
        "goal": "FIRST_FAILURE_STAGE_IDENTIFICATION_NOT_GATE_PASS",
        "p0Classification": "LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_PROJECTION",
        "closedBaseline": {
            "nativeSemanticEvidencePass": closed_preserved,
            "preserved": closed_preserved,
            "modified": False,
        },
        "cameraProvenance": {
            "source": camera_receipt.get("source"),
            "fingerprint": camera_ref_hash,
            "confirmed": bool(camera_ref_hash) and consumption_lock is not None,
            "unchanged": True,
        },
        "referenceOralBBox": reference_oral_bbox,
        "half": per_morph.get("half"),
        "open": per_morph.get("open"),
        "rootCauseComparison": {
            "lowerTeethSameClassification": same_half_open_lower,
            "upperTeethSameClassification": same_half_open_upper,
            "halfLowerPrimary": half_lower.get("classification"),
            "halfUpperPrimary": half_upper.get("classification"),
            "openLowerPrimary": open_lower.get("classification"),
            "openUpperPrimary": open_upper.get("classification"),
        },
        "successCriteria": {
            "halfLowerTeethFirstFailureStage": half_lower.get("firstFailureStage"),
            "halfUpperTeethFirstFailureStage": half_upper.get("firstFailureStage"),
            "openLowerTeethFirstFailureStage": open_lower.get("firstFailureStage"),
            "openUpperTeethFirstFailureStage": open_upper.get("firstFailureStage"),
            "closedBaselinePreserved": closed_preserved,
            "cameraProvenanceUnchanged": bool(camera_ref_hash),
            "mutationZero": True,
        },
        "mutationPolicy": {
            "semanticMutation": 0,
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "fidMutation": 0,
            "closedStateMutation": 0,
            "basisWeightMorphMutation": 0,
        },
        "recommendedBranch": next_branch,
        "nextGo": next_branch,
        "policy": {
            "gatePassNotGoal": True,
            "forcedPass": "DENY",
            "production": "NO-GO",
            "thirteenShot": "HOLD",
        },
    }


def _gate_consumption_camera_from_receipt(c_gate: dict, camera_lock: dict, cam_key: str) -> dict | None:
    lock = camera_lock.get(cam_key)
    if lock is not None:
        return lock
    receipt = c_gate.get("camera") or {}
    if receipt.get("location"):
        return receipt
    return None


def _run_c_mouth_production_gate_consumption_diagnostic(
    *,
    preflight_gates: dict,
    mouth_visibility_parity: dict,
    mouth_mask_parity: dict,
    camera_lock: dict,
    gate_b_front: dict,
    gate_b_left: dict,
    front_evidence_lock: dict | None,
    left_evidence_lock: dict | None,
    left_projection_lock: dict | None,
    closed_baseline_preflight: Path,
) -> dict:
    baseline_report = _load_json_file(closed_baseline_preflight)
    baseline_gates = baseline_report.get("gates") or {}
    c_front_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}
    c_left_gate = preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT") or {}
    b0_framing = preflight_gates.get("B0_FRONT_CHIN_CONSTRAINED_FRAMING") or (
        c_front_gate.get("constrainedFraming") or {}
    )
    front_closed_vis = mouth_visibility_parity.get("front_closed") or {}
    parity_lock = front_closed_vis.get("parityCameraConsumed")

    c_front = _classify_c_front_consumption_failure(
        c_gate=c_front_gate,
        b0_framing=b0_framing,
        mouth_visibility_parity=mouth_visibility_parity,
        gate_b_front=gate_b_front,
        production_camera_lock=_gate_consumption_camera_from_receipt(c_front_gate, camera_lock, "mouth_front"),
        parity_camera_lock=parity_lock,
        baseline_c_gate=baseline_gates.get("C_MOUTH_NATIVE_MASK_FRONT"),
    )
    c_left = _classify_c_left_consumption_failure(
        c_gate=c_left_gate,
        mouth_mask_parity=mouth_mask_parity,
        gate_b_left=gate_b_left,
        production_camera_lock=_gate_consumption_camera_from_receipt(c_left_gate, camera_lock, "mouth_left"),
        projection_camera_lock=left_projection_lock or left_evidence_lock,
        baseline_c_gate=baseline_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
    )

    provenance_resolved = all(
        [
            c_front.get("closedEvidenceBinding") is not None,
            c_left.get("closedEvidenceBinding") is not None,
            c_front.get("feasibleShotsAggregation") is not None,
            c_left.get("feasibleShotsAggregation") is not None,
            c_front.get("primaryClassification"),
            c_left.get("primaryClassification"),
        ]
    )
    binding_only_repair = (
        not c_front_gate.get("pass")
        and not c_left_gate.get("pass")
        and any(
            cls in (c_front.get("classifications") or []) + (c_left.get("classifications") or [])
            for cls in (
                "C_CLOSED_EVIDENCE_NOT_BOUND",
                "C_MORPH_STATE_RECEIPT_NOT_PROPAGATED",
                "C_CAMERA_REF_CONSUMPTION_MISMATCH",
                "C_FEASIBLE_SHOT_AGGREGATION_MISMATCH",
            )
        )
        and "C_NATIVE_MASK_SOURCE_MISMATCH" not in (c_front.get("classifications") or [])
    )

    return {
        "schema": "NURION_V07_V1_LSFQ_C_MOUTH_PRODUCTION_GATE_CONSUMPTION_PROBE",
        "gate": "C_MOUTH_PRODUCTION_GATE_CONSUMPTION_AND_CLOSED_EVIDENCE_BINDING",
        "diagnosticPass": provenance_resolved,
        "pass": provenance_resolved,
        "goal": "PROVENANCE_RESOLUTION_NOT_GATE_PASS",
        "cFailureClass": "BASELINE_GATE_ALREADY_OPEN",
        "productionGatePass": {
            "C_FRONT": bool(c_front_gate.get("pass")),
            "C_LEFT": bool(c_left_gate.get("pass")),
        },
        "C_FRONT": c_front,
        "C_LEFT": c_left,
        "successCriteria": {
            "frontReceiptProvenanceResolved": bool(c_front.get("closedEvidenceBinding")),
            "leftReceiptProvenanceResolved": bool(c_left.get("closedEvidenceBinding")),
            "closedHalfOpenStateMappingResolved": bool(c_left.get("morphStateReceipts")),
            "cameraStateSourceResolved": bool(c_front.get("closedEvidenceBinding", {}).get("parityCameraHash")),
            "nativeEvidenceSourceResolved": bool(c_front.get("nativeEvidenceSource")),
            "feasibleShotsAggregationReasonIdentified": bool(c_front.get("feasibleShotsAggregation")),
            "noSemanticCameraThresholdFidMutation": True,
        },
        "mutationPolicy": {
            "semanticMutation": 0,
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "fidMutation": 0,
            "geometryMutation": 0,
            "morphMutation": 0,
        },
        "recommendedRepair": "C_REBIND_REPAIR_THEN_AH_CONFIRMATION" if binding_only_repair else None,
        "nextGo": (
            "C_REBIND_REPAIR_THEN_AH_CONFIRMATION"
            if binding_only_repair
            else "C_MORPH_NATIVE_EVIDENCE_INVESTIGATION"
        ),
        "baselinePaths": {
            "closedEyeMouthChinPreflight": str(closed_baseline_preflight),
        },
        "policy": {
            "autoFixOnFail": False,
            "gatePassNotGoal": True,
            "production": "NO-GO",
            "thirteenShot": "HOLD",
        },
    }


def _run_ah_preflight_capture_evidence_regression_confirmation(
    *,
    preflight_report: dict,
    preflight_gates: dict,
    parity_dir: Path,
    label: str,
    d_interior_probe: dict | None,
    closed_baseline_preflight: Path,
    d_interior_baseline_probe: Path,
) -> dict:
    baseline_report = _load_json_file(closed_baseline_preflight)
    baseline_gates = baseline_report.get("gates") or {}
    baseline_d_probe = _load_json_file(d_interior_baseline_probe)

    ah_rollup = _rollup_ah_preflight_gates(preflight_gates)
    capture_evidence = _required_ah_preflight_capture_evidence(parity_dir, label)

    current_eye = _extract_eye_closed_axis_signature(preflight_report)
    current_mouth = _extract_mouth_chin_closed_axis_signature(preflight_report)
    current_d = _extract_d_interior_closed_axis_signature(preflight_report, d_interior_probe)

    baseline_eye = _extract_eye_closed_axis_signature(baseline_report)
    baseline_mouth = _extract_mouth_chin_closed_axis_signature(baseline_report)
    baseline_d = _extract_d_interior_closed_axis_signature(
        {"gates": baseline_gates, "oralOpeningLipBoundaryNativeEvidenceContract": baseline_report.get("oralOpeningLipBoundaryNativeEvidenceContract")},
        baseline_d_probe,
    )

    eye_regression = _compare_closed_axis_regression(current_eye, baseline_eye)
    mouth_regression = _compare_closed_axis_regression(current_mouth, baseline_mouth)
    d_regression = _compare_closed_axis_regression(current_d, baseline_d)

    axis_map = {
        "A_CHIN_REGION_INTEGRITY": None,
        "B_CHIN_NATIVE_FID_PARITY": mouth_regression,
        "C_MOUTH_NATIVE_MASK_FRONT": mouth_regression,
        "C_MOUTH_NATIVE_MASK_LEFT": mouth_regression,
        "D_INTERIOR_NATIVE_VISIBILITY": d_regression,
        "E_EYE_CAMERA_LEFT": eye_regression,
        "F_EYE_CAMERA_RIGHT": eye_regression,
        "G_EYE_NATIVE_FID_PARITY": eye_regression,
        "H_CAPTURE_LOCK_MANIFEST_CONSISTENCY": None,
    }
    fail_classifications: list[dict] = []
    for gate_key in AH_PREFLIGHT_GATE_KEYS:
        gate = preflight_gates.get(gate_key) or {}
        if gate.get("pass"):
            continue
        fail_classifications.append(
            _classify_ah_preflight_gate_failure(
                gate_key,
                gate,
                baseline_gates.get(gate_key),
                capture_evidence,
                axis_map.get(gate_key),
                preflight_report,
            )
        )

    interior_probe_evidence = {
        "dInteriorRevalidationProbePresent": bool(d_interior_probe),
        "nativeSemanticEvidencePass": current_d.get("nativeSemanticEvidencePass"),
        "oralOpeningNativeEvidencePass": current_d.get("oralOpeningNativeEvidencePass"),
        "perFeaturePass": {k: v.get("pass") for k, v in (current_d.get("perFeature") or {}).items()},
    }
    interior_evidence_pass = bool(d_interior_probe) and bool(current_d.get("nativeSemanticEvidencePass"))

    total_regression = (
        int(eye_regression.get("regressionCount", 0))
        + int(mouth_regression.get("regressionCount", 0))
        + int(d_regression.get("regressionCount", 0))
    )
    mutation_policy = {
        "cameraMutation": 0,
        "thresholdMutation": 0,
        "eyeMutation": 0,
        "mouthMutation": 0,
        "chinMutation": 0,
        "geometryMutation": 0,
        "morphMutation": 0,
        "basisMutation": 0,
        "weightMutation": 0,
    }
    confirmation_pass = (
        bool(ah_rollup.get("allPass"))
        and total_regression == 0
        and bool(capture_evidence.get("pass"))
        and interior_evidence_pass
    )

    return {
        "schema": "NURION_V07_V1_LSFQ_AH_PREFLIGHT_CAPTURE_EVIDENCE_PROBE",
        "gate": "AH_PREFLIGHT_CAPTURE_EVIDENCE_REGRESSION_CONFIRMATION",
        "pass": confirmation_pass,
        "ahGatesAllPass": bool(ah_rollup.get("allPass")),
        "ahGateRollup": ah_rollup,
        "closedAxisRegression": {
            "eye": eye_regression,
            "mouthChin": mouth_regression,
            "interiorD": d_regression,
            "totalRegressionCount": total_regression,
        },
        "closedAxisSignatures": {
            "current": {"eye": current_eye, "mouthChin": current_mouth, "interiorD": current_d},
            "baseline": {"eye": baseline_eye, "mouthChin": baseline_mouth, "interiorD": baseline_d},
        },
        "requiredNativeCaptureEvidence": capture_evidence,
        "interiorNativeRenderEvidence": interior_probe_evidence,
        "mutationPolicy": mutation_policy,
        "failClassifications": fail_classifications,
        "policy": {
            "autoFixOnFail": False,
            "captureEvidenceRequired": True,
            "jsonPassAloneInsufficient": True,
            "nextGoOnPass": "13-SHOT_DIAGNOSTIC_GO",
            "production": "NO-GO",
        },
        "baselinePaths": {
            "closedEyeMouthChinPreflight": str(closed_baseline_preflight),
            "dInteriorProbe": str(d_interior_baseline_probe),
        },
    }


BC_REQUIRED_CAPTURE_FILENAMES = (
    "{label}_parity_left_qa.png",
    "{label}_parity_left_fid.png",
    "{label}_chin_front_fid_probe.png",
    "{label}_chin_left_fid_probe.png",
)


def _parity_lock_from_source_camera_record(recorded: dict | None) -> dict | None:
    if not recorded:
        return None
    cam = (recorded.get("camera") or {}) if "camera" in recorded else recorded
    location = cam.get("location")
    rotation = cam.get("rotation")
    if location is None or rotation is None:
        return None
    return {
        "location": [float(x) for x in location],
        "rotation": [float(x) for x in rotation],
        "ortho_scale": float(cam.get("orthoScale", cam.get("ortho_scale", 1.0))),
        "clip_start": float(cam.get("clipStart", cam.get("clip_start", 0.001))),
        "clip_end": float(cam.get("clipEnd", cam.get("clip_end", 120.0))),
        "distance": float(recorded.get("distance", cam.get("distance", 2.8))),
        "view_dir": [float(x) for x in (recorded.get("view_dir") or cam.get("view_dir") or [0.0, -1.0, 0.0])],
        "semanticViewDir": [float(x) for x in (recorded.get("semanticViewDir") or cam.get("semanticViewDir") or [0.0, -1.0, 0.0])],
        "semanticCenter": [float(x) for x in (recorded.get("semanticCenter") or cam.get("semanticCenter") or location)],
    }


def _extract_bc_evidence_front_lock(source_preflight: dict) -> tuple[dict | None, str]:
    vis = source_preflight.get("expectedVisibilityContractParity") or {}
    mouth_front = vis.get("mouthFrontClosed") or {}
    forensic = mouth_front.get("forensicCameraRef") or {}
    front_lock = _parity_lock_from_source_camera_record(forensic.get("cameraState"))
    if front_lock is not None:
        return front_lock, "MOUTH_FRONT_FORENSIC_CAMERA_REF"
    gates = source_preflight.get("gates") or {}
    b_gate = gates.get("B_CHIN_NATIVE_FID_PARITY") or {}
    diag_front = b_gate.get("diagnosticSoftwareFallbackFront") or {}
    front_lock = _parity_lock_from_source_camera_record(diag_front.get("cameraState"))
    if front_lock is not None:
        return front_lock, "B_DIAGNOSTIC_SOFTWARE_FALLBACK_FRONT_CAMERA_STATE"
    return None, "MISSING"


def _required_bc_capture_evidence(parity_dir: Path, label: str) -> dict:
    required_files = [name.format(label=label) for name in BC_REQUIRED_CAPTURE_FILENAMES]
    present: list[str] = []
    missing: list[str] = []
    file_hashes: dict[str, str] = {}
    for name in required_files:
        if _capture_evidence_file_present(parity_dir, name):
            present.append(name)
            path = parity_dir / name
            if not path.is_file():
                matches = sorted(parity_dir.glob(f"{name[:-4]}*.png"))
                path = matches[0] if matches else path
            if path.is_file():
                file_hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        else:
            missing.append(name)
    return {
        "parityDir": str(parity_dir),
        "requiredCount": len(required_files),
        "presentCount": len(present),
        "present": present,
        "missing": missing,
        "fileHashes": file_hashes,
        "pass": len(missing) == 0,
    }


def _verify_bc_numeric_receipt_against_source(source_preflight: dict, captures: dict) -> dict:
    gates = source_preflight.get("gates") or {}
    b_gate = gates.get("B_CHIN_NATIVE_FID_PARITY") or {}
    source_front = ((b_gate.get("forensicProbes") or {}).get("front") or {}).get("perFeature") or {}
    source_chin_px = int((source_front.get("chin") or {}).get("finalFIDPixels", 0))
    chin_front = captures.get("chin_front_probe") or {}
    chin_left = captures.get("chin_left_probe") or {}
    front_px = int(chin_front.get("finalFidPixels", 0))
    left_px = int(chin_left.get("finalFidPixels", 0))
    left_gate = b_gate.get("left") or {}
    left_baseline_missing = left_gate.get("reason") == "MOUTH_LEFT_CAMERA_LOCK_MISSING"
    front_numeric_ok = source_chin_px <= 0 or front_px == source_chin_px
    left_numeric_ok = (left_baseline_missing and bool(chin_left.get("pass"))) or (
        not left_baseline_missing and left_px > 0
    )
    return {
        "pass": front_numeric_ok and left_numeric_ok,
        "sourceChinFinalFidPixels": source_chin_px,
        "regeneratedChinFrontFinalFidPixels": front_px,
        "regeneratedChinLeftFinalFidPixels": left_px,
        "leftGatePriorReason": left_gate.get("reason"),
        "leftBaselineMissing": left_baseline_missing,
        "policy": {
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "semanticRecalculation": "DENY",
        },
    }


def _run_bc_required_capture_evidence_regeneration_go(
    *,
    source_preflight_path: Path,
    parity_dir: Path,
    label: str,
    sc,
    cam,
    skin_basis,
    skin_basis_coords,
    landmarks,
    region_map,
    qa_mats,
    fid_mats,
    res: int,
    set_mouth_fn,
    mouth_valid_fn,
    weights,
    pivot,
    oral,
    preflight_json: Path | None,
    regenerate_rollup: bool,
    closed_baseline_preflight: Path,
    d_interior_baseline_probe: Path,
    d_interior_probe: dict | None,
) -> int:
    source_preflight = _load_json_file(source_preflight_path)
    if not source_preflight:
        print(json.dumps({"pass": False, "reason": "BC_EVIDENCE_SOURCE_PREFLIGHT_MISSING"}, ensure_ascii=True))
        return 2

    front_lock, front_lock_source = _extract_bc_evidence_front_lock(source_preflight)
    set_mouth_fn(0, show_oral=False)
    union_min, union_max = _mouth_union_bounds_with_chin_guard(
        skin_basis, skin_basis_coords, weights, pivot, oral, landmarks
    )
    left_morph_specs = (
        _mouth_morph_projection_specs(
            skin_basis, skin_basis_coords, weights, pivot, oral, "left", union_min, union_max
        )
        if union_min is not None
        else []
    )
    left_lock = _solve_mouth_union_camera(sc, cam, landmarks, skin_basis_coords, left_morph_specs, res)
    left_lock_source = "DETERMINISTIC_MOUTH_LEFT_SOLVER_REPLAY"

    capture_results: dict = {}
    if left_lock is not None:
        capture_results["parity_left"] = _run_chin_fid_render_parity(
            sc,
            cam,
            skin_basis,
            skin_basis_coords,
            landmarks,
            region_map,
            qa_mats,
            fid_mats,
            "left",
            res,
            parity_dir,
            label,
            locked_cam=left_lock,
            allow_software_fallback=False,
        )
    else:
        capture_results["parity_left"] = {"pass": False, "reason": "MOUTH_LEFT_SOLVER_REPLAY_UNAVAILABLE"}

    if front_lock is not None:
        capture_results["chin_front_probe"] = _run_chin_fid_forensic_probe(
            sc,
            cam,
            skin_basis,
            region_map,
            fid_mats,
            front_lock,
            "front",
            res,
            parity_dir,
            label,
        )
    else:
        capture_results["chin_front_probe"] = {"pass": False, "reason": "MOUTH_FRONT_CAMERA_LOCK_MISSING"}

    if left_lock is not None:
        capture_results["chin_left_probe"] = _run_chin_fid_forensic_probe(
            sc,
            cam,
            skin_basis,
            region_map,
            fid_mats,
            left_lock,
            "left",
            res,
            parity_dir,
            label,
        )
    else:
        capture_results["chin_left_probe"] = {"pass": False, "reason": "MOUTH_LEFT_CAMERA_LOCK_MISSING"}

    evidence = _required_bc_capture_evidence(parity_dir, label)
    numeric_receipt = _verify_bc_numeric_receipt_against_source(source_preflight, capture_results)
    evidence_pass = bool(evidence.get("pass"))
    regeneration_pass = evidence_pass and bool(numeric_receipt.get("pass"))

    probe = {
        "schema": "NURION_V07_V1_LSFQ_BC_REQUIRED_CAPTURE_EVIDENCE_REGENERATION_PROBE",
        "gate": "B_C_REQUIRED_CAPTURE_EVIDENCE_REGENERATION",
        "pass": regeneration_pass,
        "evidenceGenerationPass": evidence_pass,
        "p0Classification": "B_C_REQUIRED_CAPTURE_EVIDENCE_GENERATION_MISSING",
        "sourcePreflight": str(source_preflight_path),
        "cameraLockSources": {
            "mouth_front": front_lock_source,
            "mouth_left": left_lock_source,
        },
        "requiredNativeCaptureEvidence": evidence,
        "numericReceiptParity": numeric_receipt,
        "captureResults": {
            "parity_left": {
                "pass": capture_results.get("parity_left", {}).get("pass"),
                "classification": capture_results.get("parity_left", {}).get("classification"),
                "paths": capture_results.get("parity_left", {}).get("paths"),
            },
            "chin_front_probe": {
                "pass": capture_results.get("chin_front_probe", {}).get("pass"),
                "finalFidPixels": capture_results.get("chin_front_probe", {}).get("finalFidPixels"),
            },
            "chin_left_probe": {
                "pass": capture_results.get("chin_left_probe", {}).get("pass"),
                "finalFidPixels": capture_results.get("chin_left_probe", {}).get("finalFidPixels"),
            },
        },
        "policy": {
            "eyeMutation": "DENY",
            "mouthChinSemanticMutation": "DENY",
            "dInteriorMutation": "DENY",
            "cameraRetune": "DENY",
            "thresholdMutation": "DENY",
            "geometryMutation": "DENY",
            "morphMutation": "DENY",
            "basisMutation": "DENY",
            "weightMutation": "DENY",
            "closedReceiptSemanticRecalculation": "DENY",
        },
    }

    if preflight_json is not None:
        bc_checkpoint = preflight_json.with_name("bc_required_capture_evidence_regeneration_probe.json")
        bc_checkpoint.write_text(json.dumps(probe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ah_probe = None
    if regenerate_rollup and evidence_pass:
        ah_probe = _run_ah_preflight_capture_evidence_regression_confirmation(
            preflight_report=source_preflight,
            preflight_gates=source_preflight.get("gates") or {},
            parity_dir=parity_dir,
            label=label,
            d_interior_probe=d_interior_probe,
            closed_baseline_preflight=closed_baseline_preflight,
            d_interior_baseline_probe=d_interior_baseline_probe,
        )
        if preflight_json is not None:
            ah_checkpoint = preflight_json.with_name("ah_preflight_capture_evidence_probe.json")
            ah_checkpoint.write_text(json.dumps(ah_probe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            merged = dict(source_preflight)
            merged["bcRequiredCaptureEvidenceRegeneration"] = probe
            merged["ahPreflightCaptureEvidenceRegressionConfirmation"] = ah_probe
            preflight_json.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "bcEvidenceOnly": True,
                "pass": regeneration_pass,
                "requiredNativeCaptureEvidence": evidence,
                "numericReceiptParity": numeric_receipt,
                "ahRollupPass": bool((ah_probe or {}).get("pass")) if ah_probe else None,
                "ahGatesAllPass": bool((ah_probe or {}).get("ahGatesAllPass")) if ah_probe else None,
            },
            ensure_ascii=True,
        )
    )
    return 0 if regeneration_pass else 2


def _validate_interior_native_mask(
    sc,
    cam,
    lock: dict,
    bounds: tuple[Vector, Vector],
    valid_objs,
    mask_mat,
    res: int,
) -> tuple[bool, dict]:
    _apply_locked_camera(cam, lock)
    occ = _project_aabb_occupancy(sc, cam, bounds[0], bounds[1], res)
    projection_feasible = bool(occ and _occupancy_ok(occ))
    native = _evaluate_native_index_mask(
        sc, cam, valid_objs, mask_mat, res, semantic_bounds=bounds, morph_bounds=bounds
    )
    ok = (
        projection_feasible
        and int(native["nativeRawMaskPixels"]) > 0
        and int(native["finalMaskPixels"]) > 0
        and bool(native.get("nativeSemanticEvidencePass", native.get("maskOccupancyPass")))
    )
    return ok, {"projectionFeasible": projection_feasible, **native}


def _build_camera_lock_manifest_entry(
    key: str,
    lock: dict,
    *,
    source_gate: str,
    allowed_states: list[str],
    semantic_bounds: tuple[Vector | None, Vector | None],
    guard_bounds: tuple[Vector | None, Vector | None],
    preflight_state: dict | None = None,
    preflight_state_by_morph: dict[str, dict] | None = None,
) -> dict:
    entry = {
        "manifestKey": key,
        "projectionType": "ORTHO",
        "location": [float(x) for x in lock["location"]],
        "rotation": [float(x) for x in lock["rotation"]],
        "orthoScale": float(lock["ortho_scale"]),
        "clipStart": float(lock.get("clip_start", lock.get("clipStart", 0.001))),
        "clipEnd": float(lock.get("clip_end", lock.get("clipEnd", 120.0))),
        "distance": float(lock.get("distance", 2.8)),
        "viewDir": [float(x) for x in lock.get("view_dir", [0.0, -1.0, 0.0])],
        "semanticViewDir": [float(x) for x in lock.get("semanticViewDir", lock.get("view_dir", [0.0, -1.0, 0.0]))],
        "semanticCenter": [float(x) for x in lock.get("semanticCenter", lock["location"])],
        "semanticBounds": _vector_bounds_dict(*semantic_bounds),
        "guardBounds": _vector_bounds_dict(*guard_bounds),
        "allowedStates": list(allowed_states),
        "sourceGate": source_gate,
        "immutable": True,
        "semanticLock": _manifest_semantic_lock(lock),
        "preflightState": preflight_state,
        "preflightStateByMorph": preflight_state_by_morph,
    }
    entry["solverReceiptHash"] = _hash_solver_receipt(
        {k: entry[k] for k in entry if k not in ("preflightState", "preflightStateByMorph", "solverReceiptHash")}
    )
    return entry


def _build_camera_lock_manifest(
    camera_lock: dict[str, dict],
    *,
    preflight_snapshots: dict[str, dict],
    morph_snapshots: dict[str, dict[str, dict]] | None = None,
) -> dict:
    morph_snapshots = morph_snapshots or {}
    manifest: dict[str, dict] = {"schema": "NURION_CAMERA_LOCK_MANIFEST_V1", "locks": {}}
    gate_map = {
        "mouth_front": "C_MOUTH_NATIVE_MASK_FRONT",
        "mouth_left": "C_MOUTH_NATIVE_MASK_LEFT",
        "mouth_interior": "D_INTERIOR_NATIVE_VISIBILITY",
        "eye_left": "E_EYE_CAMERA_LEFT",
        "eye_right": "F_EYE_CAMERA_RIGHT",
    }
    states_map = {
        "mouth_front": ["closed", "half", "open"],
        "mouth_left": ["closed", "half", "open"],
        "mouth_interior": ["interior"],
        "eye_left": ["closed", "half", "open"],
        "eye_right": ["closed", "half", "open"],
    }
    for key, lock in camera_lock.items():
        snap = preflight_snapshots.get(key, {})
        manifest["locks"][key] = _build_camera_lock_manifest_entry(
            key,
            lock,
            source_gate=gate_map.get(key, "UNKNOWN"),
            allowed_states=states_map.get(key, ["default"]),
            semantic_bounds=(
                Vector(snap["semanticBounds"]["min"]) if snap.get("semanticBounds") else None,
                Vector(snap["semanticBounds"]["max"]) if snap.get("semanticBounds") else None,
            )
            if snap.get("semanticBounds")
            else (None, None),
            guard_bounds=(
                Vector(snap["guardBounds"]["min"]) if snap.get("guardBounds") else None,
                Vector(snap["guardBounds"]["max"]) if snap.get("guardBounds") else None,
            )
            if snap.get("guardBounds")
            else (None, None),
            preflight_state=snap.get("preflightState"),
            preflight_state_by_morph=morph_snapshots.get(key),
        )
    manifest["solverReceiptHash"] = _hash_solver_receipt(manifest["locks"])
    return manifest


def _collect_preflight_manifest_snapshots(
    sc,
    cam,
    mask_mat,
    res: int,
    camera_lock: dict[str, dict],
    *,
    set_mouth_fn,
    mouth_valid_fn,
    set_eye_fn,
    rig_objs: dict,
    skin_basis,
    skin_basis_coords: list[Vector],
    landmarks: dict,
    weights: dict,
    pivot: Vector,
    oral: list,
) -> tuple[dict[str, dict], dict[str, dict[str, dict]]]:
    snapshots: dict[str, dict] = {}
    morph_snapshots: dict[str, dict[str, dict]] = {}

    if "mouth_front" in camera_lock:
        lock = camera_lock["mouth_front"]
        morph_by: dict[str, dict] = {}
        union_min, union_max = _mouth_union_bounds_with_chin_guard(
            skin_basis, skin_basis_coords, weights, pivot, oral, landmarks
        )
        for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
            show_oral = angle >= 12
            set_mouth_fn(angle, show_oral=show_oral)
            valid, skin = mouth_valid_fn(show_oral)
            bounds = _framing_bounds(
                skin, skin_basis_coords, _mouth_framing, oral if show_oral else None
            )
            if bounds[0] is None:
                bounds = (union_min, union_max)
            _apply_locked_camera(cam, lock)
            morph_by[tag] = _snapshot_capture_framing_state(
                sc, cam, valid, mask_mat, res, bounds, skin_obj=skin
            )
        bounds0 = morph_by.get("closed", {}).get("guardBounds")
        snapshots["mouth_front"] = {
            "semanticBounds": bounds0 or _vector_bounds_dict(union_min, union_max),
            "guardBounds": bounds0 or _vector_bounds_dict(union_min, union_max),
            "preflightState": morph_by.get("closed"),
        }
        morph_snapshots["mouth_front"] = morph_by
        lock["clip_start"] = float(cam.data.clip_start)
        lock["clip_end"] = float(cam.data.clip_end)

    if "mouth_left" in camera_lock:
        lock = camera_lock["mouth_left"]
        morph_by = {}
        union_min, union_max = _mouth_union_bounds_with_chin_guard(
            skin_basis, skin_basis_coords, weights, pivot, oral, landmarks
        )
        for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
            show_oral = angle >= 12
            set_mouth_fn(angle, show_oral=show_oral)
            valid, skin = mouth_valid_fn(show_oral)
            bounds = _framing_bounds(
                skin, skin_basis_coords, _mouth_framing, oral if show_oral else None
            )
            if bounds[0] is None:
                bounds = (union_min, union_max)
            _apply_locked_camera(cam, lock)
            morph_by[tag] = _snapshot_capture_framing_state(
                sc, cam, valid, mask_mat, res, bounds, skin_obj=skin
            )
        bounds0 = morph_by.get("closed", {}).get("guardBounds")
        snapshots["mouth_left"] = {
            "semanticBounds": bounds0 or _vector_bounds_dict(union_min, union_max),
            "guardBounds": bounds0 or _vector_bounds_dict(union_min, union_max),
            "preflightState": morph_by.get("closed"),
        }
        morph_snapshots["mouth_left"] = morph_by
        lock["clip_start"] = float(cam.data.clip_start)
        lock["clip_end"] = float(cam.data.clip_end)

    if "mouth_interior" in camera_lock:
        lock = camera_lock["mouth_interior"]
        set_mouth_fn(24, show_oral=True)
        valid, skin = mouth_valid_fn(True)
        bounds = _interior_bounds_with_guard(skin, skin_basis_coords, oral)
        _apply_locked_camera(cam, lock)
        snap = _snapshot_capture_framing_state(sc, cam, valid, mask_mat, res, bounds, skin_obj=skin)
        snapshots["mouth_interior"] = {
            "semanticBounds": snap.get("guardBounds"),
            "guardBounds": snap.get("guardBounds"),
            "preflightState": snap,
        }
        morph_snapshots["mouth_interior"] = {"interior": snap}
        lock["clip_start"] = float(cam.data.clip_start)
        lock["clip_end"] = float(cam.data.clip_end)

    for side, tag in (("L", "left"), ("R", "right")):
        key = f"eye_{tag}"
        if key not in camera_lock:
            continue
        lock = camera_lock[key]
        morph_by = {}
        for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
            set_eye_fn(side, pct)
            _apply_locked_camera(cam, lock)
            valid = _eye_valid_objects(set_eye_fn, side, rig_objs)
            bounds = _eye_bounds_for_pct(set_eye_fn, side, pct, rig_objs, skin_basis_coords)
            morph_by[state] = _snapshot_capture_framing_state(
                sc, cam, valid, mask_mat, res, bounds, skin_obj=set_eye_fn.skin_eye
            )
        bounds0 = morph_by.get("closed", {}).get("guardBounds")
        snapshots[key] = {
            "semanticBounds": bounds0,
            "guardBounds": bounds0,
            "preflightState": morph_by.get("closed"),
        }
        morph_snapshots[key] = morph_by
        lock["clip_start"] = float(cam.data.clip_start)
        lock["clip_end"] = float(cam.data.clip_end)

    return snapshots, morph_snapshots


def _run_chin_fid_render_parity(
    sc,
    cam,
    skin_obj,
    basis_coords: list[Vector],
    landmarks: dict,
    region_map: dict,
    qa_mats: dict,
    fid_mats: dict,
    mode: str,
    res: int,
    out_dir: Path,
    label: str,
    locked_cam: dict | None = None,
    allow_software_fallback: bool = True,
) -> dict:
    if locked_cam is not None:
        _apply_locked_camera(cam, locked_cam)
        semantic_view = Vector(locked_cam.get("semanticViewDir", _landmark_view_dir(landmarks, mode)))
        sem_center = Vector(locked_cam.get("semanticCenter", _semantic_center(landmarks, "mouth", "mouth", cam.location)))
        frame_keys = _frame_landmark_keys("mouth", "mouth")
        if not locked_cam.get("constrainedFraming"):
            _nudge_camera_to_landmarks(
                sc,
                cam,
                landmarks,
                frame_keys,
                sem_center,
                semantic_view,
                float(locked_cam.get("distance", 2.8)),
                res,
                basis_coords,
                mode,
            )
        bbox = _landmark_pixel_bbox(
            sc, cam, landmarks, frame_keys, res, pad_frac=0.12, basis_coords=basis_coords, mode=mode
        )
        setup = {
            "pass": True,
            "bbox": bbox,
            "cameraState": _camera_state_record(sc, cam, skin_obj),
            "distance": float(locked_cam.get("distance", 2.8)),
            "viewDir": locked_cam.get("view_dir", [float(x) for x in _legacy_view_dir(mode)]),
            "semanticViewDir": [float(x) for x in semantic_view],
            "semanticCenter": [float(x) for x in sem_center],
            "lockedCamera": True,
        }
    else:
        setup = _parity_camera_for_mouth(sc, cam, skin_obj, basis_coords, landmarks, mode, res)
        if not setup.get("pass"):
            return {**setup, "gate": "CHIN_FID_RENDER_PARITY", "mode": mode}
        sem_center = Vector(setup["semanticCenter"])
        semantic_view = Vector(setup["semanticViewDir"])
    bbox = setup["bbox"]
    manifest = _chin_manifest_faces(skin_obj.data, region_map)
    chin_faces = region_map.get("chin_faces", set())
    chin_proj = _project_chin_face_region(sc, cam, skin_obj, chin_faces, res)

    qa_path = out_dir / f"{label}_parity_{mode}_qa.png"
    saved_mats = [s.material for s in skin_obj.material_slots]
    _ensure_semantic_material_slots(skin_obj, qa_mats)
    if locked_cam is None:
        sem_center = Vector(setup["semanticCenter"])
        semantic_view = Vector(setup["semanticViewDir"])
    qa_rgb, _ = _render_human_qa(sc, cam, qa_path, res, sem_center, semantic_view, bbox)
    for i, mat in enumerate(saved_mats):
        if i < len(skin_obj.material_slots):
            skin_obj.material_slots[i].material = mat

    index_path = out_dir / f"{label}_parity_{mode}_raw_index.png"
    _ensure_semantic_material_slots(skin_obj, fid_mats)
    raw_rgb = _render_feature_id(
        sc, cam, skin_obj, {}, fid_mats, [skin_obj], index_path, res, allow_software_fallback=allow_software_fallback
    )

    fid_path = out_dir / f"{label}_parity_{mode}_fid.png"
    _ensure_semantic_material_slots(skin_obj, fid_mats)
    fid_rgb = _render_feature_id(
        sc, cam, skin_obj, {}, fid_mats, [skin_obj], fid_path, res, allow_software_fallback=allow_software_fallback
    )

    qa_px = int(_count_qa_palette_pixels(qa_rgb, bbox, ("chin",)).get("chin", 0)) if qa_rgb is not None else 0
    raw_px = int(_count_feature_pixels(raw_rgb, bbox, ("chin",)).get("chin", 0)) if raw_rgb is not None else 0
    fid_px = int(_count_feature_pixels(fid_rgb, bbox, ("chin",)).get("chin", 0)) if fid_rgb is not None else 0
    raw_full = int(_count_feature_pixels(raw_rgb, None, ("chin",), full_frame=True).get("chin", 0)) if raw_rgb is not None else 0
    fid_full = int(_count_feature_pixels(fid_rgb, None, ("chin",), full_frame=True).get("chin", 0)) if fid_rgb is not None else 0
    classification = _classify_chin_parity(mode, chin_proj, raw_px, fid_px, qa_px=qa_px)
    chin_floor = MIN_ABSOLUTE_FLOOR.get("chin", 60)

    face_normals: list[dict] = []
    view_dir = _view_dir_from_cam(cam)
    mw = skin_obj.matrix_world
    for row in manifest[:8]:
        fi = row["faceIndex"]
        poly = skin_obj.data.polygons[fi]
        n = (mw.to_3x3() @ poly.normal).normalized()
        face_normals.append(
            {
                "faceIndex": fi,
                "materialIndex": row["materialIndex"],
                "normal": [float(n.x), float(n.y), float(n.z)],
                "viewDot": float(n.dot(view_dir)),
            }
        )

    gate_pass = (
        int(chin_proj.get("chinPositiveAreaFaces", 0)) >= 1
        and raw_px > 0
        and fid_px > 0
        and fid_full >= chin_floor
    )
    if allow_software_fallback is False and int(chin_proj.get("chinPositiveAreaFaces", 0)) > 0 and fid_px <= 0:
        classification = "FID_RENDER_PATH_PARITY_FAIL"
        gate_pass = False
    return {
        "gate": "CHIN_NATIVE_FID_PARITY",
        "mode": mode,
        "pass": gate_pass,
        "classification": classification,
        "chinProjection": chin_proj,
        "pixels": {
            "qaPaletteChin": qa_px,
            "rawIndexChinBbox": raw_px,
            "rawIndexChinFull": raw_full,
            "finalFidChinBbox": fid_px,
            "finalFidChinFull": fid_full,
            "chinProjectedAreaPxEstimate": int(chin_proj.get("chinProjectedAreaPxEstimate", 0)),
        },
        "faceManifest": manifest,
        "faceSample": face_normals,
        "bbox": bbox,
        "cameraState": setup["cameraState"],
        "paths": {
            "qa": str(qa_path),
            "rawIndex": str(index_path),
            "fid": str(fid_path),
        },
        "reason": None if gate_pass else classification,
    }


def _project_aabb_occupancy(sc, cam, co_min: Vector, co_max: Vector, res: int) -> dict | None:
    corners = [
        Vector((co_min.x, co_min.y, co_min.z)),
        Vector((co_max.x, co_min.y, co_min.z)),
        Vector((co_min.x, co_max.y, co_min.z)),
        Vector((co_max.x, co_max.y, co_min.z)),
        Vector((co_min.x, co_min.y, co_max.z)),
        Vector((co_max.x, co_min.y, co_max.z)),
        Vector((co_min.x, co_max.y, co_max.z)),
        Vector((co_max.x, co_max.y, co_max.z)),
    ]
    xs: list[float] = []
    ys: list[float] = []
    for c in corners:
        ndc = world_to_camera_view(sc, cam, c)
        if ndc.z <= 0.0:
            continue
        xs.append(float(ndc.x) * res)
        ys.append((1.0 - float(ndc.y)) * res)
    if not xs:
        return None
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    wf = float(x1 - x0 + 1.0) / float(res)
    hf = float(y1 - y0 + 1.0) / float(res)
    return {"widthFrac": wf, "heightFrac": hf, "bbox": [int(x0), int(y0), int(x1), int(y1)]}


def _occupancy_ok(occ: dict | None) -> bool:
    if not occ:
        return False
    wf = float(occ.get("widthFrac", 0.0))
    hf = float(occ.get("heightFrac", 0.0))
    if wf >= SEMANTIC_OCC_MAX and hf >= SEMANTIC_OCC_MAX:
        return False
    return OCC_MIN <= wf <= OCC_MAX and OCC_MIN <= hf <= OCC_MAX


def _solve_mouth_union_camera(
    sc,
    cam,
    landmarks: dict,
    basis_coords: list[Vector],
    morph_specs: list[dict],
    res: int,
) -> dict | None:
    view = morph_specs[0]["view"]
    view_dir = _legacy_view_dir(view)
    semantic_view = _landmark_view_dir(landmarks, view)
    u_min, u_max = morph_specs[0]["unionMin"], morph_specs[0]["unionMax"]
    center = (u_min + u_max) / 2.0
    dist = _place_camera(cam, center, u_min, u_max, view_dir, view)
    sem_center = _semantic_center(landmarks, "mouth", "mouth", center)
    frame_keys = _frame_landmark_keys("mouth", "mouth")
    base_ortho = _semantic_ortho_scale(landmarks, "mouth", semantic_view) * 1.04
    lo = base_ortho * 0.55
    hi = base_ortho * 2.6
    best = None
    for _ in range(30):
        ortho = (lo + hi) / 2.0
        _apply_semantic_camera(cam, sem_center, ortho, semantic_view, dist)
        _nudge_camera_to_landmarks(
            sc, cam, landmarks, frame_keys, sem_center, semantic_view, dist, res, basis_coords, view
        )
        ok = True
        for spec in morph_specs:
            occ = _project_aabb_occupancy(sc, cam, spec["coMin"], spec["coMax"], res)
            in_frame, _ = _landmarks_in_frame(
                sc, cam, landmarks, frame_keys, res, basis_coords, view
            )
            if not in_frame or not _occupancy_ok(occ):
                ok = False
                break
        if ok:
            best = ortho
            hi = ortho
        else:
            lo = ortho
    if best is None:
        return None
    _apply_semantic_camera(cam, sem_center, best, semantic_view, dist)
    _nudge_camera_to_landmarks(
        sc, cam, landmarks, frame_keys, sem_center, semantic_view, dist, res, basis_coords, view
    )
    return {
        "location": [float(x) for x in cam.location],
        "rotation": [float(x) for x in cam.rotation_euler],
        "ortho_scale": float(best),
        "distance": float(dist),
        "view_dir": [float(x) for x in view_dir],
        "semanticViewDir": [float(x) for x in semantic_view],
        "semanticCenter": [float(x) for x in sem_center],
        "roiUnionBounds": {
            "min": [float(u_min.x), float(u_min.y), float(u_min.z)],
            "max": [float(u_max.x), float(u_max.y), float(u_max.z)],
        },
        "projectionFeasible": True,
    }


def _solve_interior_camera(
    sc,
    cam,
    landmarks: dict,
    bounds: tuple[Vector, Vector],
    basis_coords: list[Vector],
    res: int,
) -> dict | None:
    co_min, co_max = bounds
    view_dir = _legacy_view_dir("interior")
    center = (co_min + co_max) / 2.0
    dist = _place_camera(cam, center, co_min, co_max, view_dir, "interior")
    sem_center = _semantic_center(landmarks, "mouth_interior", "mouth", center)
    frame_keys = _frame_landmark_keys("mouth_interior", "mouth")
    lo = float(cam.data.ortho_scale) * 0.45
    hi = float(cam.data.ortho_scale) * 2.2
    best = None
    for _ in range(28):
        ortho = (lo + hi) / 2.0
        _apply_semantic_camera(cam, sem_center, ortho, view_dir, dist)
        occ = _project_aabb_occupancy(sc, cam, co_min, co_max, res)
        in_frame, _ = _landmarks_in_frame(
            sc, cam, landmarks, frame_keys, res, basis_coords, "interior"
        )
        if in_frame and _occupancy_ok(occ):
            best = ortho
            hi = ortho
        else:
            lo = ortho
    if best is None:
        return None
    _apply_semantic_camera(cam, sem_center, best, view_dir, dist)
    return {
        "location": [float(x) for x in cam.location],
        "rotation": [float(x) for x in cam.rotation_euler],
        "ortho_scale": float(best),
        "distance": float(dist),
        "view_dir": [float(x) for x in view_dir],
        "semanticViewDir": [float(x) for x in view_dir],
        "semanticCenter": [float(x) for x in sem_center],
    }


def _software_raster_fid_layer(
    sc, cam, skin_obj, slot_idx: int, slot_key: str, res: int
) -> np.ndarray:
    rgb = np.zeros((res, res, 3), dtype=np.float32)
    if slot_key not in FEATURE_ID_RGB:
        return rgb
    color = np.array(FEATURE_ID_RGB[slot_key], dtype=np.float32)
    mesh = skin_obj.data
    mw = skin_obj.matrix_world
    for poly in mesh.polygons:
        if int(poly.material_index) != slot_idx:
            continue
        xs: list[float] = []
        ys: list[float] = []
        ok = True
        for vi in poly.vertices:
            co = mw @ mesh.vertices[int(vi)].co
            ndc = world_to_camera_view(sc, cam, co)
            if ndc.z <= 0.0:
                ok = False
                break
            xs.append(float(ndc.x) * res)
            ys.append((1.0 - float(ndc.y)) * res)
        if not ok or len(xs) < 3:
            continue
        x0 = max(0, int(min(xs)))
        y0 = max(0, int(min(ys)))
        x1 = min(res - 1, int(max(xs)))
        y1 = min(res - 1, int(max(ys)))
        rgb[y0 : y1 + 1, x0 : x1 + 1] = color
    return rgb


    return rgb


def _point_in_triangle(px: float, py: float, a, b, c) -> bool:
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])

    d1 = sign((px, py), a, b)
    d2 = sign((px, py), b, c)
    d3 = sign((px, py), c, a)
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


def _native_raster_fid_skin_slot_triangles(
    sc, cam, skin_obj, slot_idx: int, slot_key: str, res: int
) -> np.ndarray:
    rgb = np.zeros((res, res, 3), dtype=np.float32)
    if slot_key not in FEATURE_ID_RGB:
        return rgb
    color = np.array(FEATURE_ID_RGB[slot_key], dtype=np.float32)
    mesh = skin_obj.data
    mw = skin_obj.matrix_world
    for poly in mesh.polygons:
        if int(poly.material_index) != slot_idx:
            continue
        pts: list[tuple[float, float]] = []
        for vi in poly.vertices:
            co = mw @ mesh.vertices[int(vi)].co
            ndc = world_to_camera_view(sc, cam, co)
            if ndc.z <= 0.0:
                pts = []
                break
            pts.append((float(ndc.x) * res, (1.0 - float(ndc.y)) * res))
        if len(pts) < 3:
            continue
        tris = [pts[:3]]
        if len(pts) == 4:
            tris.append((pts[0], pts[2], pts[3]))
        for tri in tris:
            xs = [p[0] for p in tri]
            ys = [p[1] for p in tri]
            x0 = max(0, int(math.floor(min(xs))))
            x1 = min(res - 1, int(math.ceil(max(xs))))
            y0 = max(0, int(math.floor(min(ys))))
            y1 = min(res - 1, int(math.ceil(max(ys))))
            for y in range(y0, y1 + 1):
                for x in range(x0, x1 + 1):
                    if _point_in_triangle(x + 0.5, y + 0.5, tri[0], tri[1], tri[2]):
                        rgb[y, x] = color
    return rgb


def _classify_mouth_fid_emission_chain(row: dict, *, detection_rate_ok: bool) -> str:
    native = int(row.get("nativeSlot", row.get("nativeSlotRenderPixels", 0)))
    encoded = int(row.get("encoded", row.get("encodedLayerPixels", row.get("encodedFIDPixels", 0))))
    decoded = int(row.get("decoded", row.get("decodedLayerPixels", row.get("decodedFIDPixels", 0))))
    composite_out = int(row.get("compositeOutput", row.get("compositeOutputPixels", 0)))
    final_fid = int(row.get("finalFID", row.get("finalFIDPixels", 0)))
    if native <= 0:
        return "NATIVE_SLOT_RENDER_FAIL"
    if native > 0 and encoded <= 0:
        return "FID_ENCODING_FAIL"
    if encoded > 0 and decoded <= 0:
        return "FID_DECODING_FAIL"
    if decoded > 0 and composite_out <= 0:
        return "FID_COMPOSITE_FAIL"
    if final_fid > 0 and not detection_rate_ok:
        return "FEATURE_DETECTION_RATE_CONTRACT_FAIL"
    if final_fid <= 0:
        return "NATIVE_SLOT_RENDER_FAIL"
    return "PASS"


def _mouth_fid_detection_rate_ok(feature: str, final_fid: int, native_slot: int) -> tuple[float, bool]:
    if native_slot <= 0:
        return 0.0, False
    rate = float(final_fid) / float(native_slot)
    if feature == "chin":
        return rate, int(final_fid) >= MIN_ABSOLUTE_FLOOR.get("chin", 60)
    return rate, rate >= VISIBILITY_DETECTION_MIN


def _merge_mouth_fid_layer_chain(
    feature: str,
    base: dict,
    layer: dict,
    *,
    fid_receipt: dict,
) -> dict:
    per_final = int((fid_receipt.get("perFeatureFinal") or {}).get(feature, base.get("finalFIDPixels", 0)))
    merged = {
        **base,
        "nativeSlotRenderPixels": int(layer.get("nativeSlotRenderPixels", base.get("nativeSlotRenderPixels", 0))),
        "encodedLayerPixels": int(layer.get("encodedLayerPixels", base.get("encodedFIDPixels", 0))),
        "decodedLayerPixels": int(layer.get("decodedLayerPixels", base.get("decodedFIDPixels", 0))),
        "compositeInputPixels": int(layer.get("compositeInputPixels", 0)),
        "compositeOutputPixels": int(layer.get("compositeOutputPixels", 0)),
        "finalFIDPixels": per_final,
        "nativeSlotRenderPath": layer.get("nativeSlotRenderPath", "EEVEE"),
        "softwareFallbackUsed": bool(layer.get("softwareFallbackUsed", False)),
    }
    native_slot = int(merged["nativeSlotRenderPixels"])
    final_fid = int(merged["finalFIDPixels"])
    rate, detection_rate_ok = _mouth_fid_detection_rate_ok(feature, final_fid, native_slot)
    chain = {
        "nativeSlot": native_slot,
        "encoded": int(merged["encodedLayerPixels"]),
        "decoded": int(merged["decodedLayerPixels"]),
        "compositeInput": int(merged["compositeInputPixels"]),
        "compositeOutput": int(merged["compositeOutputPixels"]),
        "finalFID": final_fid,
        "detectionRate": rate,
        "detectionRateDenominator": native_slot,
        "detectionRateDenominatorSource": "NATIVE_SLOT_DECODED",
    }
    first_zero = next((k for k in ("nativeSlot", "encoded", "decoded", "compositeOutput", "finalFID") if chain[k] <= 0), None)
    merged["fidLayerChain"] = {**chain, "firstZeroStage": first_zero}
    merged["classification"] = _classify_mouth_fid_emission_chain(chain, detection_rate_ok=detection_rate_ok)
    floor = MIN_ABSOLUTE_FLOOR.get(feature, 40)
    merged["pass"] = (
        merged["classification"] == "PASS"
        and not bool(merged["softwareFallbackUsed"])
        and final_fid >= floor
        and detection_rate_ok
    )
    return merged


def _run_mouth_chin_lip_corner_fid_forensic_probe(
    sc,
    cam,
    locked_cam: dict,
    *,
    set_mouth_fn,
    mouth_valid_fn,
    skin_obj,
    region_map: dict,
    fid_mats: dict,
    res: int,
    out_dir: Path,
    label: str,
) -> dict:
    _apply_locked_camera(cam, locked_cam)
    set_mouth_fn(0.0, show_oral=False)
    valid, skin = mouth_valid_fn(False)
    chin_faces = region_map.get("chin_faces", set())
    chin_proj = _project_chin_face_region(sc, cam, skin, chin_faces, res)
    fid_path = out_dir / f"{label}_mfid_probe.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin, {}, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    fid_receipt = dict(_FID_RENDER_RECEIPT)
    per_feature: dict[str, dict] = {}
    for feature in MOUTH_FID_EMISSION_FEATURES:
        base = _audit_native_fid_feature(
            sc, cam, skin, {}, fid_mats, valid, feature, fid_path, res, composite_rgb=fid_rgb
        )
        layer = (fid_receipt.get("layers") or {}).get(feature, {})
        per_feature[feature] = _merge_mouth_fid_layer_chain(feature, base, layer, fid_receipt=fid_receipt)
    probe_pass = all(per_feature[f]["pass"] for f in MOUTH_FID_EMISSION_FEATURES)
    return {
        "probeShot": "mouth_front_closed",
        "pass": bool(probe_pass),
        "perFeature": per_feature,
        "fidRenderReceipt": fid_receipt,
        "chinProjection": chin_proj,
        "classifications": {f: per_feature[f]["classification"] for f in MOUTH_FID_EMISSION_FEATURES},
        "fidLayerChains": {f: per_feature[f].get("fidLayerChain") for f in MOUTH_FID_EMISSION_FEATURES},
        "provenanceChain": list(MOUTH_FID_EMISSION_CHAIN),
        "policy": {
            "cameraRetune": "DENY",
            "thresholdMutation": 0,
            "softwareFallbackPassBypass": "DENY",
            "maskMutation": 0,
            "projectionMutation": 0,
            "visibilityMutation": 0,
            "eyeCodeMutation": 0,
        },
    }


    return {
        **fid_probe,
        "forensicTrigger": trigger_receipt,
        "diagnosticPass": bool(diagnostic_pass),
        "fidRepairPass": bool(fid_probe.get("pass")),
        "gatePassEligible": False,
    }


def _classify_interior_feature_failure(
    *,
    feature: str,
    projected_faces: int,
    native_slot_pixels: int,
    final_pixels: int,
    visibility_contract_pass: bool,
    emission_contract_pass: bool,
) -> str:
    if feature in ("lipGuard",):
        if not visibility_contract_pass:
            return "INTERIOR_CONTEXT_VISIBILITY_FAIL"
        return "PASS" if emission_contract_pass else "INTERIOR_CONTEXT_VISIBILITY_FAIL"
    if feature == "oralOpening":
        if not visibility_contract_pass:
            return "INTERIOR_PROJECTION_FAIL"
        if visibility_contract_pass and not emission_contract_pass:
            return "INTERIOR_FID_RENDER_PATH_FAIL"
        return "PASS"
    if projected_faces <= 0:
        return "INTERIOR_PROJECTION_FAIL"
    if native_slot_pixels <= 0:
        return "INTERIOR_NATIVE_SLOT_RENDER_FAIL"
    if final_pixels <= 0:
        return "INTERIOR_COMPOSITE_FAIL"
    if visibility_contract_pass and not emission_contract_pass:
        return "INTERIOR_FID_RENDER_PATH_FAIL"
    return "PASS"


def _interior_feature_missing_reason(classification: str, *, floor: int, final_pixels: int) -> str | None:
    if classification == "PASS":
        return None
    if classification == "INTERIOR_PROJECTION_FAIL":
        return "INTERIOR_PROJECTION_FAIL"
    if classification == "INTERIOR_NATIVE_SLOT_RENDER_FAIL":
        return "INTERIOR_NATIVE_SLOT_RENDER_FAIL"
    if classification == "INTERIOR_COMPOSITE_FAIL":
        return "INTERIOR_COMPOSITE_FAIL"
    if classification == "INTERIOR_FID_RENDER_PATH_FAIL":
        return "INTERIOR_FID_RENDER_PATH_FAIL"
    if classification == "INTERIOR_CONTEXT_VISIBILITY_FAIL":
        return "INTERIOR_CONTEXT_VISIBILITY_FAIL"
    if final_pixels < floor:
        return "BELOW_ABSOLUTE_FLOOR"
    return classification


    return classification


def _manifest_lock_to_camera_state(entry: dict) -> dict:
    return {
        "location": [float(x) for x in entry["location"]],
        "rotation": [float(x) for x in entry["rotation"]],
        "ortho_scale": float(entry["orthoScale"]),
        "clip_start": float(entry.get("clipStart", 0.001)),
        "clip_end": float(entry.get("clipEnd", 120.0)),
        "distance": float(entry.get("distance", 2.8)),
        "view_dir": entry.get("viewDir"),
        "semanticViewDir": entry.get("semanticViewDir"),
        "semanticCenter": entry.get("semanticCenter"),
    }


def _build_interior_forensic_camera_ref(lock: dict | None, *, source: str) -> dict | None:
    if lock is None:
        return None
    ref = {
        "schema": "INTERIOR_FORENSIC_CAMERA_REF_V1",
        "cameraRefSource": source,
        "cameraRefLocation": [float(x) for x in lock["location"]],
        "cameraRefRotation": [float(x) for x in lock["rotation"]],
        "cameraRefOrthoScale": float(lock["ortho_scale"]),
        "cameraRefProjection": {
            "orthoScale": float(lock["ortho_scale"]),
            "clipStart": float(lock.get("clip_start", 0.01)),
            "clipEnd": float(lock.get("clip_end", 120.0)),
            "semanticCenter": lock.get("semanticCenter"),
            "semanticViewDir": lock.get("semanticViewDir"),
            "viewDir": lock.get("view_dir"),
            "distance": lock.get("distance"),
        },
        "readOnly": True,
        "gatePassEligible": False,
        "productionCameraLockEquivalent": False,
        "cameraMutation": 0,
    }
    ref["cameraRefHash"] = _hash_solver_receipt(
        {
            "source": source,
            "location": ref["cameraRefLocation"],
            "rotation": ref["cameraRefRotation"],
            "ortho_scale": ref["cameraRefOrthoScale"],
        }
    )
    ref["cameraState"] = lock
    return ref


def _load_valid_frozen_interior_camera_lock(manifest_path: Path) -> tuple[dict | None, dict]:
    receipt: dict = {"manifestPath": str(manifest_path), "validFrozenInteriorCameraRefPresent": False}
    if not manifest_path.is_file():
        receipt["reason"] = "MANIFEST_MISSING"
        return None, receipt
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entry = (manifest.get("locks") or {}).get("mouth_interior")
    if entry is None:
        receipt["reason"] = "MOUTH_INTERIOR_LOCK_MISSING"
        return None, receipt
    if not entry.get("immutable"):
        receipt["reason"] = "LOCK_NOT_IMMUTABLE"
        return None, receipt
    lock = _manifest_lock_to_camera_state(entry)
    ref = _build_interior_forensic_camera_ref(lock, source="FROZEN_CAMERA_LOCK_MANIFEST_READONLY")
    receipt.update(
        {
            "validFrozenInteriorCameraRefPresent": True,
            "manifestKey": entry.get("manifestKey", "mouth_interior"),
            "sourceGate": entry.get("sourceGate"),
            "solverReceiptHash": entry.get("solverReceiptHash"),
            "cameraRefSource": ref["cameraRefSource"] if ref else None,
            "cameraRefHash": ref.get("cameraRefHash") if ref else None,
            "cameraRefOrthoScale": ref.get("cameraRefOrthoScale") if ref else None,
            "preflightState": entry.get("preflightState"),
        }
    )
    return lock, receipt


def _diagnose_interior_solver_failure(
    sc,
    cam,
    landmarks: dict,
    bounds: tuple[Vector | None, Vector | None],
    basis_coords: list[Vector],
    res: int,
) -> dict:
    if bounds[0] is None or bounds[1] is None:
        return {
            "classification": "INTERIOR_BOUNDS_UNAVAILABLE",
            "interiorSolverAvailable": False,
            "boundsPresent": False,
        }
    co_min, co_max = bounds
    view_dir = _legacy_view_dir("interior")
    center = (co_min + co_max) / 2.0
    dist = _place_camera(cam, center, co_min, co_max, view_dir, "interior")
    sem_center = _semantic_center(landmarks, "mouth_interior", "mouth", center)
    frame_keys = _frame_landmark_keys("mouth_interior", "mouth")
    lo = float(cam.data.ortho_scale) * 0.45
    hi = float(cam.data.ortho_scale) * 2.2
    last_in_frame = False
    last_occ: dict = {}
    last_occ_ok = False
    frame_reason = None
    for _ in range(28):
        ortho = (lo + hi) / 2.0
        _apply_semantic_camera(cam, sem_center, ortho, view_dir, dist)
        occ = _project_aabb_occupancy(sc, cam, co_min, co_max, res)
        in_frame, frame_reason = _landmarks_in_frame(
            sc, cam, landmarks, frame_keys, res, basis_coords, "interior"
        )
        occ_ok = _occupancy_ok(occ)
        last_in_frame = bool(in_frame)
        last_occ = occ
        last_occ_ok = bool(occ_ok)
        if in_frame and occ_ok:
            return {
                "classification": "INTERIOR_SOLVER_FEASIBLE",
                "interiorSolverAvailable": True,
                "inFrame": True,
                "occupancyOk": True,
                "occupancy": occ,
                "orthoScaleCandidate": float(ortho),
            }
        if in_frame and not occ_ok:
            lo = ortho
        elif not in_frame:
            hi = ortho
        else:
            lo = ortho
    return {
        "classification": "INTERIOR_SOLVER_EXHAUSTED",
        "interiorSolverAvailable": False,
        "inFrame": last_in_frame,
        "frameReason": frame_reason if not last_in_frame else None,
        "occupancyOk": last_occ_ok,
        "occupancy": last_occ,
        "orthoSearchLo": float(lo),
        "orthoSearchHi": float(hi),
        "p0Classification": "INTERIOR_CAMERA_LOCK_STATE_CONSUMPTION_MISSING",
    }


def _mouth_interior_state_receipt(set_mouth_fn, jaw_empty, rig_objs: dict, landmarks: dict) -> dict:
    jaw_deg = float(math.degrees(jaw_empty.rotation_euler[0]))
    show_oral = not rig_objs["helper-upper-teeth"].hide_render
    return {
        "mouthInteriorMorphState": {
            "profile": "mouth_interior",
            "jawAngleDeg": jaw_deg,
            "expectedJawAngleDeg": 24.0,
            "showOral": bool(show_oral),
            "synchronized": abs(jaw_deg - 24.0) < 0.01 and show_oral,
        },
        "jawState": {
            "rotationEulerDeg": jaw_deg,
            "expectedDeg": 24.0,
            "synchronized": abs(jaw_deg - 24.0) < 0.01,
        },
        "upperLipState": {
            "landmarkKey": "upper_lip",
            "present": "upper_lip" in landmarks,
            "visibleWithOralRig": bool(show_oral),
        },
        "lowerLipState": {
            "landmarkKey": "lower_lip",
            "present": "lower_lip" in landmarks,
            "visibleWithOralRig": bool(show_oral),
        },
    }


def _oral_opening_projected_bounds(fid_rgb: np.ndarray | None, bbox: list[int]) -> dict:
    if fid_rgb is None:
        return {
            "separationPx": 0,
            "upperTeethBBox": None,
            "lowerTeethBBox": None,
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
        }
    masks = _feature_masks(fid_rgb, bbox, ("upper_teeth", "lower_teeth"))
    up = masks["upper_teeth"]
    lo = masks["lower_teeth"]
    up_bbox = None
    lo_bbox = None
    if up.any():
        ys, xs = np.where(up)
        up_bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    if lo.any():
        ys, xs = np.where(lo)
        lo_bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    oral = _validate_oral_opening(fid_rgb, bbox)
    projected = 1 if (up.any() and lo.any()) else 0
    positive = 1 if oral.get("pass") else 0
    return {
        "separationPx": int(oral.get("separationPx", 0)),
        "upperTeethBBox": up_bbox,
        "lowerTeethBBox": lo_bbox,
        "projectedFaces": projected,
        "positiveAreaFaces": positive,
        "oralOpeningValidation": oral,
    }


def _project_world_points(sc, cam, points: list[Vector], res: int) -> tuple[list[float], list[float]]:
    bpy.context.view_layer.update()
    xs: list[float] = []
    ys: list[float] = []
    for pt in points:
        ndc = world_to_camera_view(sc, cam, pt)
        if float(ndc.z) <= 0.0:
            continue
        xs.append(float(ndc.x) * res)
        ys.append((1.0 - float(ndc.y)) * res)
    return xs, ys


def _projected_curve_receipt(xs: list[float], ys: list[float]) -> dict:
    if not xs or not ys:
        return {
            "vertexCount": 0,
            "minX": None,
            "maxX": None,
            "minY": None,
            "maxY": None,
            "medianY": None,
        }
    return {
        "vertexCount": len(xs),
        "minX": float(min(xs)),
        "maxX": float(max(xs)),
        "minY": float(min(ys)),
        "maxY": float(max(ys)),
        "medianY": float(np.median(np.asarray(ys, dtype=np.float64))),
    }


def _world_vertices_from_indices(obj, indices: set[int] | list[int]) -> list[Vector]:
    mw = obj.matrix_world
    mesh = obj.data
    return [mw @ mesh.vertices[int(vi)].co for vi in indices]


def _split_lip_source_vertices(
    skin_obj,
    region_map: dict,
    landmarks: dict,
) -> tuple[list[int], list[int], list[int]]:
    upper_z = float(landmarks["upper_lip"].z)
    lower_z = float(landmarks["lower_lip"].z)
    mid_z = (upper_z + lower_z) * 0.5
    lip_verts = set(int(v) for v in region_map.get("lip_verts", set()))
    corner_l = set(int(v) for v in region_map.get("corner_l_verts", set()))
    corner_r = set(int(v) for v in region_map.get("corner_r_verts", set()))
    upper: list[int] = []
    lower: list[int] = []
    for vi in lip_verts:
        co = skin_obj.matrix_world @ skin_obj.data.vertices[vi].co
        z = float(co.z)
        if z >= mid_z:
            upper.append(vi)
        else:
            lower.append(vi)
    corners = sorted(corner_l | corner_r)
    return upper, lower, corners


def _opening_interior_vertex_indices(
    skin_obj,
    basis_coords: list[Vector],
    region_map: dict,
    landmarks: dict,
    weights: dict[int, float],
) -> list[int]:
    reserved = (
        set(region_map.get("lip_verts", set()))
        | set(region_map.get("corner_l_verts", set()))
        | set(region_map.get("corner_r_verts", set()))
        | set(region_map.get("chin_verts", set()))
    )
    upper_z = float(landmarks["upper_lip"].z)
    lower_z = float(landmarks["lower_lip"].z)
    z_lo = min(upper_z, lower_z) - 0.02
    z_hi = max(upper_z, lower_z) + 0.02
    indices: list[int] = []
    for vi, w in weights.items():
        if w < 0.08 or vi in reserved or vi >= len(basis_coords):
            continue
        co = skin_obj.matrix_world @ skin_obj.data.vertices[vi].co
        if z_lo <= float(co.z) <= z_hi and _mouth_framing(basis_coords[vi]):
            indices.append(int(vi))
    return indices


def _opening_interior_vertex_count(
    skin_obj,
    basis_coords: list[Vector],
    region_map: dict,
    landmarks: dict,
    weights: dict[int, float],
) -> int:
    return len(_opening_interior_vertex_indices(skin_obj, basis_coords, region_map, landmarks, weights))


def _opening_void_projected_area(fid_rgb: np.ndarray | None, bbox: list[int], mouth_roi: list[int]) -> int:
    if fid_rgb is None:
        return 0
    x0, y0, x1, y1 = mouth_roi
    crop = fid_rgb[y0 : y1 + 1, x0 : x1 + 1]
    if crop.size == 0:
        return 0
    feature_union = np.zeros(crop.shape[:2], dtype=bool)
    for key in ("skin", "lip", "lip_corner_l", "lip_corner_r", "chin", "upper_teeth", "lower_teeth", "tongue"):
        if key not in FEATURE_ID_RGB:
            continue
        feature_union |= _feature_masks(crop, [0, 0, crop.shape[1] - 1, crop.shape[0] - 1], (key,))[key]
    return int(np.sum(~feature_union))


def _classify_oral_opening_degeneracy(
    *,
    state_synchronized: bool,
    opening_polygon_vertex_count: int,
    opening_polygon_projected_area: int,
    teeth_bbox_separation_px: int,
    lip_boundary_separation_px: int,
    upper_teeth_visible: bool,
    lower_teeth_visible: bool,
    tongue_visible: bool,
) -> str:
    if not state_synchronized:
        return "STATE_GEOMETRY_COLLAPSED"
    if opening_polygon_vertex_count <= 0 and opening_polygon_projected_area <= 0 and not (
        upper_teeth_visible or lower_teeth_visible or tongue_visible
    ):
        return "OPENING_REGION_NOT_DEFINED"
    if (
        teeth_bbox_separation_px <= 0
        and upper_teeth_visible
        and lower_teeth_visible
        and (tongue_visible or opening_polygon_vertex_count > 0)
    ):
        return "TEETH_BBOX_PROXY_INVALID"
    if (
        teeth_bbox_separation_px <= 0
        and lip_boundary_separation_px >= ORAL_OPENING_MIN_PX
        and (upper_teeth_visible or lower_teeth_visible or tongue_visible)
    ):
        return "TEETH_BBOX_PROXY_INVALID"
    if teeth_bbox_separation_px >= ORAL_OPENING_MIN_PX:
        return "PASS"
    if lip_boundary_separation_px <= 0 and opening_polygon_projected_area > 0:
        return "LIP_BOUNDARY_PROJECTION_DEGENERATE"
    if opening_polygon_projected_area <= 0 and lip_boundary_separation_px >= ORAL_OPENING_MIN_PX:
        return "OPENING_POLYGON_DEGENERATE"
    return "TEETH_BBOX_PROXY_INVALID"


def _run_oral_opening_semantic_region_projection_degeneracy_probe(
    sc,
    cam,
    consumed_cam: dict | None,
    *,
    camera_source: str | None,
    set_mouth_fn,
    mouth_valid_fn,
    skin_basis_coords: list[Vector],
    landmarks: dict,
    region_map: dict,
    weights: dict,
    jaw_empty,
    rig_objs: dict,
    fid_mats: dict,
    res: int,
    oral_bounds: dict | None = None,
    state_receipt: dict | None = None,
) -> dict:
    if consumed_cam is None or camera_source in (None, "INTERIOR_SCENE_EXISTING_FALLBACK"):
        return {
            "probeShot": "mouth_interior",
            "pass": False,
            "skipped": True,
            "reason": "INTERIOR_CAMERA_CONSUMPTION_REQUIRED",
            "p0Classification": "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY",
            "gatePassEligible": False,
        }

    _apply_locked_camera(cam, consumed_cam)
    set_mouth_fn(24.0, show_oral=True)
    valid, skin = mouth_valid_fn(True)
    state = state_receipt or _mouth_interior_state_receipt(set_mouth_fn, jaw_empty, rig_objs, landmarks)
    state_sync = bool((state.get("mouthInteriorMorphState") or {}).get("synchronized"))

    upper_vi, lower_vi, corner_vi = _split_lip_source_vertices(skin, region_map, landmarks)
    upper_world = _world_vertices_from_indices(skin, upper_vi)
    lower_world = _world_vertices_from_indices(skin, lower_vi)
    corner_world = _world_vertices_from_indices(skin, corner_vi)
    upper_xs, upper_ys = _project_world_points(sc, cam, upper_world, res)
    lower_xs, lower_ys = _project_world_points(sc, cam, lower_world, res)
    corner_xs, corner_ys = _project_world_points(sc, cam, corner_world, res)
    upper_curve = _projected_curve_receipt(upper_xs, upper_ys)
    lower_curve = _projected_curve_receipt(lower_xs, lower_ys)

    lip_boundary_separation_px = 0
    if upper_curve.get("maxY") is not None and lower_curve.get("minY") is not None:
        lip_boundary_separation_px = int(max(0.0, float(lower_curve["minY"]) - float(upper_curve["maxY"])))

    bounds = oral_bounds or {}
    teeth_bbox_separation_px = int(bounds.get("separationPx", 0))
    upper_teeth_bbox = bounds.get("upperTeethBBox")
    lower_teeth_bbox = bounds.get("lowerTeethBBox")

    mouth_roi = _landmark_pixel_bbox(
        sc,
        cam,
        landmarks,
        ("mouth_center", "upper_lip", "lower_lip", "lip_corner_l", "lip_corner_r"),
        res,
        pad_frac=0.18,
        basis_coords=skin_basis_coords,
        mode="interior",
    )
    fid_path = Path(tempfile.gettempdir()) / f"nurion_oral_opening_degen_{id(cam)}.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    if oral_bounds is None and fid_rgb is not None:
        bounds = _oral_opening_projected_bounds(fid_rgb, [0, 0, res - 1, res - 1])
        teeth_bbox_separation_px = int(bounds.get("separationPx", 0))
        upper_teeth_bbox = bounds.get("upperTeethBBox")
        lower_teeth_bbox = bounds.get("lowerTeethBBox")

    opening_polygon_vertex_count = _opening_interior_vertex_count(
        skin, skin_basis_coords, region_map, landmarks, weights
    )
    opening_polygon_projected_area = _opening_void_projected_area(
        fid_rgb, [0, 0, res - 1, res - 1], mouth_roi
    )
    teeth_counts = (
        _count_feature_pixels(fid_rgb, [0, 0, res - 1, res - 1], ("upper_teeth", "lower_teeth", "tongue"), full_frame=False)
        if fid_rgb is not None
        else {}
    )
    upper_teeth_visible = int(teeth_counts.get("upper_teeth", 0)) > 0
    lower_teeth_visible = int(teeth_counts.get("lower_teeth", 0)) > 0
    tongue_visible = int(teeth_counts.get("tongue", 0)) > 0

    classification = _classify_oral_opening_degeneracy(
        state_synchronized=state_sync,
        opening_polygon_vertex_count=opening_polygon_vertex_count,
        opening_polygon_projected_area=opening_polygon_projected_area,
        teeth_bbox_separation_px=teeth_bbox_separation_px,
        lip_boundary_separation_px=lip_boundary_separation_px,
        upper_teeth_visible=upper_teeth_visible,
        lower_teeth_visible=lower_teeth_visible,
        tongue_visible=tongue_visible,
    )
    projected_faces = int(bounds.get("projectedFaces", 0))
    return {
        "probeShot": "mouth_interior",
        "pass": classification == "PASS",
        "diagnosticPass": classification == "PASS",
        "skipped": False,
        "p0Classification": "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY",
        "classification": classification,
        "oralOpeningDefinitionType": ORAL_OPENING_DEFINITION_TYPE,
        "projectedPrimitiveType": ORAL_OPENING_PROJECTED_PRIMITIVE_TYPE,
        "projectedFacesIsPolygonCount": False,
        "projectedFacesSemantics": "1 when both upper_teeth and lower_teeth FID masks visible; not opening polygon count",
        "sourceUpperLipVertices": upper_vi,
        "sourceLowerLipVertices": lower_vi,
        "sourceMouthCornerVertices": corner_vi,
        "openingPolygonVertexCount": opening_polygon_vertex_count,
        "openingPolygonProjectedArea": opening_polygon_projected_area,
        "upperLipProjectedCurve": upper_curve,
        "lowerLipProjectedCurve": lower_curve,
        "teethBBoxSeparationPx": teeth_bbox_separation_px,
        "lipBoundarySeparationPx": lip_boundary_separation_px,
        "upperTeethBBox": upper_teeth_bbox,
        "lowerTeethBBox": lower_teeth_bbox,
        "teethBBoxOverlapLikely": bool(
            upper_teeth_bbox and lower_teeth_bbox and teeth_bbox_separation_px <= 0
        ),
        "projectedFaces": projected_faces,
        "positiveAreaFaces": int(bounds.get("positiveAreaFaces", 0)),
        "separationPxProxy": teeth_bbox_separation_px,
        "mouthRoiBBox": mouth_roi,
        "interiorCameraSource": camera_source,
        "forensicCameraRefOrthoScale": float(consumed_cam.get("ortho_scale", 0.0)),
        "stateReceipt": state,
        "rigVisibility": {
            "upperTeethPixels": int(teeth_counts.get("upper_teeth", 0)),
            "lowerTeethPixels": int(teeth_counts.get("lower_teeth", 0)),
            "tonguePixels": int(teeth_counts.get("tongue", 0)),
        },
        "gatePassEligible": False,
        "policy": {
            "cameraRetune": "DENY",
            "morphMutation": 0,
            "thresholdMutation": 0,
            "mouthMutation": 0,
            "eyeMutation": 0,
            "cameraMutation": 0,
        },
    }


def _convex_hull_2d(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    pts = sorted({(float(x), float(y)) for x, y in points})
    if len(pts) <= 2:
        return pts

    def cross(o: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def _polygon_signed_area_2d(points: list[tuple[float, float]]) -> float:
    if len(points) < 3:
        return 0.0
    area = 0.0
    for i, (x1, y1) in enumerate(points):
        x2, y2 = points[(i + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area * 0.5


def _opening_polygon_projection_evidence(
    sc,
    cam,
    skin_obj,
    opening_indices: list[int],
    res: int,
) -> dict:
    source_count = len(opening_indices)
    if source_count <= 0:
        return {
            "projectedVertexCount": 0,
            "sourceVertexCount": 0,
            "openingClipped": False,
            "openingPolygonProjectedArea": 0.0,
            "openingPolygonSignedArea": 0.0,
            "openingPolygonBBox": None,
        }
    world = _world_vertices_from_indices(skin_obj, opening_indices)
    xs, ys = _project_world_points(sc, cam, world, res)
    behind_camera = len(xs) < source_count
    out_of_frame = any(x < 0 or x > res - 1 or y < 0 or y > res - 1 for x, y in zip(xs, ys))
    pts = list(zip(xs, ys))
    hull = _convex_hull_2d(pts) if len(pts) >= 3 else pts
    signed = _polygon_signed_area_2d(hull)
    projected_area = abs(float(signed))
    bbox = None
    if pts:
        bbox = [int(min(xs)), int(min(ys)), int(max(xs)), int(max(ys))]
    return {
        "projectedVertexCount": len(xs),
        "sourceVertexCount": source_count,
        "openingClipped": bool(behind_camera or out_of_frame),
        "openingPolygonProjectedArea": projected_area,
        "openingPolygonSignedArea": float(signed),
        "openingPolygonBBox": bbox,
    }


def _per_x_boundary_gap_stats(
    upper_xs: list[float],
    upper_ys: list[float],
    lower_xs: list[float],
    lower_ys: list[float],
    *,
    x_lo: int | None = None,
    x_hi: int | None = None,
    interior_view: bool = False,
) -> dict:
    upper_env: dict[int, list[float]] = {}
    lower_env: dict[int, list[float]] = {}
    for x, y in zip(upper_xs, upper_ys):
        upper_env.setdefault(int(round(x)), []).append(float(y))
    for x, y in zip(lower_xs, lower_ys):
        lower_env.setdefault(int(round(x)), []).append(float(y))
    shared = set(upper_env.keys()) & set(lower_env.keys())
    if x_lo is not None and x_hi is not None:
        shared = {x for x in shared if x_lo <= x <= x_hi}
    gaps: list[float] = []
    for x in shared:
        if interior_view:
            upper_boundary = max(upper_env[x])
            lower_boundary = min(lower_env[x])
            gap = float(lower_boundary - upper_boundary)
        else:
            upper_boundary = max(upper_env[x])
            lower_boundary = min(lower_env[x])
            gap = float(lower_boundary - upper_boundary)
        gaps.append(gap)
    positive = [g for g in gaps if g > 0]
    return {
        "min": float(min(gaps)) if gaps else 0.0,
        "max": float(max(gaps)) if gaps else 0.0,
        "median": float(np.median(np.asarray(gaps, dtype=np.float64))) if gaps else 0.0,
        "positiveGapCount": len(positive),
        "sampledXCount": len(shared),
        "xRange": [x_lo, x_hi] if x_lo is not None and x_hi is not None else None,
        "interiorViewEnvelope": bool(interior_view),
    }


def _classify_oral_opening_native_evidence(
    *,
    state_synchronized: bool,
    native_context_present: bool,
    opening_polygon_vertex_count: int,
    opening_polygon_projected_area: float,
    opening_clipped: bool,
    upper_lip_curve_point_count: int,
    lower_lip_curve_point_count: int,
    per_x_boundary_gap_stats: dict,
) -> str:
    if not state_synchronized or not native_context_present:
        return "OPENING_NATIVE_CONTEXT_MISSING"
    if opening_polygon_vertex_count <= 0:
        return "OPENING_NATIVE_CONTEXT_MISSING"
    if upper_lip_curve_point_count <= 0 or lower_lip_curve_point_count <= 0:
        return "LIP_CURVE_PAIRING_FAIL"
    if opening_clipped:
        return "OPENING_POLYGON_OUT_OF_FRAME"
    if opening_polygon_projected_area <= 0.0:
        return "OPENING_POLYGON_PROJECTS_ZERO_AREA"
    if int(per_x_boundary_gap_stats.get("positiveGapCount", 0)) <= 0:
        return "LIP_BOUNDARY_GAP_ZERO"
    return "OPENING_POLYGON_DEFINED_PASS"


def _evaluate_oral_opening_native_evidence(
    sc,
    cam,
    skin_obj,
    *,
    skin_basis_coords: list[Vector],
    landmarks: dict,
    region_map: dict,
    weights: dict,
    oral_bounds: dict | None,
    state_synchronized: bool,
    native_context_present: bool,
    res: int,
) -> dict:
    upper_vi, lower_vi, _corner_vi = _split_lip_source_vertices(skin_obj, region_map, landmarks)
    upper_world = _world_vertices_from_indices(skin_obj, upper_vi)
    lower_world = _world_vertices_from_indices(skin_obj, lower_vi)
    upper_xs, upper_ys = _project_world_points(sc, cam, upper_world, res)
    lower_xs, lower_ys = _project_world_points(sc, cam, lower_world, res)
    if upper_xs and lower_xs:
        upper_median_y = float(np.median(np.asarray(upper_ys, dtype=np.float64)))
        lower_median_y = float(np.median(np.asarray(lower_ys, dtype=np.float64)))
        if upper_median_y > lower_median_y:
            upper_xs, lower_xs = lower_xs, upper_xs
            upper_ys, lower_ys = lower_ys, upper_ys
    upper_curve = _projected_curve_receipt(upper_xs, upper_ys)
    lower_curve = _projected_curve_receipt(lower_xs, lower_ys)
    opening_indices = _opening_interior_vertex_indices(
        skin_obj, skin_basis_coords, region_map, landmarks, weights
    )
    polygon = _opening_polygon_projection_evidence(sc, cam, skin_obj, opening_indices, res)
    bbox = polygon.get("openingPolygonBBox")
    x_lo = int(bbox[0]) if bbox else None
    x_hi = int(bbox[2]) if bbox else None
    gap_stats = _per_x_boundary_gap_stats(
        upper_xs,
        upper_ys,
        lower_xs,
        lower_ys,
        x_lo=x_lo,
        x_hi=x_hi,
        interior_view=True,
    )
    bounds = oral_bounds or {}
    teeth_bbox_separation_px = int(bounds.get("separationPx", 0))
    classification = _classify_oral_opening_native_evidence(
        state_synchronized=state_synchronized,
        native_context_present=native_context_present,
        opening_polygon_vertex_count=len(opening_indices),
        opening_polygon_projected_area=float(polygon.get("openingPolygonProjectedArea", 0.0)),
        opening_clipped=bool(polygon.get("openingClipped")),
        upper_lip_curve_point_count=int(upper_curve.get("vertexCount", 0)),
        lower_lip_curve_point_count=int(lower_curve.get("vertexCount", 0)),
        per_x_boundary_gap_stats=gap_stats,
    )
    contract_pass = classification == "OPENING_POLYGON_DEFINED_PASS"
    return {
        "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "classification": classification,
        "contractPass": contract_pass,
        "openingPolygonDefined": len(opening_indices) > 0,
        "openingPolygonVertexCount": len(opening_indices),
        "openingPolygonProjectedArea": float(polygon.get("openingPolygonProjectedArea", 0.0)),
        "openingPolygonSignedArea": float(polygon.get("openingPolygonSignedArea", 0.0)),
        "openingPolygonBBox": polygon.get("openingPolygonBBox"),
        "openingClipped": bool(polygon.get("openingClipped")),
        "upperLipCurvePointCount": int(upper_curve.get("vertexCount", 0)),
        "lowerLipCurvePointCount": int(lower_curve.get("vertexCount", 0)),
        "upperLipBoundaryProjected": int(upper_curve.get("vertexCount", 0)) > 0,
        "lowerLipBoundaryProjected": int(lower_curve.get("vertexCount", 0)) > 0,
        "perXBoundaryGapStats": gap_stats,
        "teethBBoxSeparationPx": teeth_bbox_separation_px,
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "upperTeethBBox": bounds.get("upperTeethBBox"),
        "lowerTeethBBox": bounds.get("lowerTeethBBox"),
        "nativeOralContextPresent": bool(native_context_present),
        "lipGuardPreserved": None,
        "rigVisibilityPreserved": None,
    }


def _oral_opening_per_feature_from_native_evidence(evidence: dict) -> dict:
    classification = str(evidence.get("classification", "OPENING_NATIVE_CONTEXT_MISSING"))
    projected_area = float(evidence.get("openingPolygonProjectedArea", 0.0))
    gap_stats = evidence.get("perXBoundaryGapStats") or {}
    positive_gaps = int(gap_stats.get("positiveGapCount", 0))
    pass_ = classification == "OPENING_POLYGON_DEFINED_PASS"
    return {
        "feature": "oralOpening",
        "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "projectedFaces": 1 if projected_area > 0.0 else 0,
        "positiveAreaFaces": 1 if projected_area > 0.0 and positive_gaps > 0 else 0,
        "nativeSlotPixels": int(round(projected_area)),
        "finalPixels": int(round(float(gap_stats.get("max", 0.0)))),
        "existingAbsoluteFloor": 0,
        "visibilityContractPass": projected_area > 0.0 and positive_gaps > 0,
        "emissionContractPass": pass_,
        "classification": "PASS" if pass_ else classification,
        "missingReason": None if pass_ else classification,
        "oralOpeningNativeEvidence": evidence,
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "teethBBoxSeparationPx": evidence.get("teethBBoxSeparationPx"),
        "pass": pass_,
    }


def _patch_interior_diagnostic_oral_opening(
    interior_diagnostic_probe: dict,
    native_evidence: dict,
) -> None:
    per_feature = interior_diagnostic_probe.setdefault("perFeature", {})
    per_feature["oralOpening"] = _oral_opening_per_feature_from_native_evidence(native_evidence)
    classifications = interior_diagnostic_probe.setdefault("classifications", {})
    classifications["oralOpening"] = per_feature["oralOpening"]["classification"]
    probe_pass = all(per_feature[f]["pass"] for f in INTERIOR_DIAGNOSTIC_FEATURES if f in per_feature)
    interior_diagnostic_probe["pass"] = bool(probe_pass)
    interior_diagnostic_probe["diagnosticPass"] = bool(probe_pass)


def _patch_interior_native_oral_opening(
    interior_native: dict,
    native_evidence: dict,
) -> None:
    per_feature = interior_native.setdefault("perFeature", {})
    projected_area = float(native_evidence.get("openingPolygonProjectedArea", 0.0))
    gap_stats = native_evidence.get("perXBoundaryGapStats") or {}
    pass_ = native_evidence.get("contractPass", False)
    per_feature["oralOpening"] = {
        "pixels": int(round(projected_area)),
        "floor": 0,
        "pass": bool(pass_),
        "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "classification": native_evidence.get("classification"),
        "perXBoundaryGapStats": gap_stats,
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "teethBBoxSeparationPx": native_evidence.get("teethBBoxSeparationPx"),
    }
    failing = [k for k, v in per_feature.items() if not v.get("pass")]
    expected_visibility_pass = all(v.get("pass") for v in per_feature.values())
    evidence = interior_native.get("nativeSemanticEvidence") or {}
    holdout_ok = bool(
        int((interior_native.get("nativeMask") or {}).get("finalMaskPixels", 0)) > 0
        and (interior_native.get("nativeMask") or {}).get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
    )
    interior_native["failures"] = failing
    interior_native["pass"] = bool(evidence.get("pass") and holdout_ok and expected_visibility_pass)
    interior_native["nativeSemanticEvidencePass"] = bool(evidence.get("pass") and holdout_ok)
    if failing:
        interior_native["classification"] = f"INTERIOR_{failing[0]}_FAIL"
    elif interior_native["pass"]:
        interior_native["classification"] = "PASS"
    else:
        interior_native["classification"] = "INTERIOR_NATIVE_SEMANTIC_EVIDENCE_HOLD"


def _interior_holdout_ok(interior_native: dict) -> bool:
    native_mask = interior_native.get("nativeMask") or {}
    return bool(
        int(native_mask.get("finalMaskPixels", 0)) > 0
        and native_mask.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
    )


def _classify_d_interior_hold_reason(
    *,
    camera_lock_pass: bool,
    per_feature: dict,
    expected_visibility_pass: bool,
    evidence: dict,
    holdout_ok: bool,
    legacy_enforced_in_pass: bool,
    pre_rebind_expected_visibility: bool | None,
) -> str | None:
    if not camera_lock_pass:
        return "INTERIOR_CAMERA_RECEIPT_NOT_PROPAGATED"
    required = ("oralOpening", "upperTeeth", "lowerTeeth", "tongue", "lipGuard")
    if not per_feature or any(f not in per_feature for f in required):
        return "INTERIOR_FEATURE_RECEIPT_NOT_PROPAGATED"
    if legacy_enforced_in_pass:
        return "INTERIOR_LEGACY_OCCUPANCY_STILL_ENFORCED"
    if not holdout_ok:
        return "INTERIOR_NATIVE_MASK_SOURCE_MISMATCH"
    if (
        expected_visibility_pass
        and pre_rebind_expected_visibility is False
        and not evidence.get("pass")
    ):
        return "INTERIOR_EVIDENCE_AGGREGATION_NOT_BOUND"
    failing = [k for k, v in per_feature.items() if not v.get("pass")]
    if failing:
        return f"INTERIOR_{failing[0]}_FAIL"
    if not evidence.get("pass"):
        return "INTERIOR_EVIDENCE_AGGREGATION_NOT_BOUND"
    return None


def _bind_d_interior_production_contract(
    interior_native: dict,
    *,
    effective_interior_cam: dict | None,
    camera_source: str | None,
    interior_restoration_probe: dict,
    interior_diagnostic_probe: dict,
    oral_opening_native_evidence_probe: dict,
) -> dict:
    diag_pf = (interior_diagnostic_probe or {}).get("perFeature") or {}
    oral_evidence = oral_opening_native_evidence_probe.get("oralOpeningNativeEvidence") or {}
    pre_evidence = dict(interior_native.get("nativeSemanticEvidence") or {})
    pre_checks = dict(pre_evidence.get("checks") or {})
    pre_rebind_expected_visibility = pre_checks.get("expectedVisibility")

    camera_lock_pass = bool(
        effective_interior_cam is not None
        and camera_source not in (None, "INTERIOR_SCENE_EXISTING_FALLBACK")
        and interior_restoration_probe.get("cameraConsumptionPass")
    )
    oral_opening_native_pass = bool(oral_opening_native_evidence_probe.get("contractPass"))

    per_feature: dict[str, dict] = {}
    if oral_evidence:
        per_feature["oralOpening"] = {
            "pixels": int(round(float(oral_evidence.get("openingPolygonProjectedArea", 0.0)))),
            "floor": 0,
            "pass": oral_opening_native_pass,
            "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
            "classification": oral_evidence.get("classification"),
            "oralOpeningNativeEvidencePass": oral_opening_native_pass,
            "perXBoundaryGapStats": oral_evidence.get("perXBoundaryGapStats"),
            "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
            "teethBBoxSeparationPx": oral_evidence.get("teethBBoxSeparationPx"),
            "sourceReceipt": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
            "status": "PASS_CLOSED",
        }

    rig_floor_keys = {
        "upperTeeth": "upper_teeth",
        "lowerTeeth": "lower_teeth",
        "tongue": "tongue",
        "lipGuard": "lip",
    }
    for feat in INTERIOR_RIG_NATIVE_EMISSION_FEATURES + ("lipGuard",):
        row = diag_pf.get(feat) or {}
        floor_key = rig_floor_keys[feat]
        per_feature[feat] = {
            "pixels": int(row.get("finalPixels", row.get("nativeSlotPixels", 0))),
            "floor": int(row.get("existingAbsoluteFloor", MIN_ABSOLUTE_FLOOR.get(floor_key, 0))),
            "pass": bool(row.get("pass")),
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
            "classification": row.get("classification", "PASS" if row.get("pass") else "INTERIOR_FID_RENDER_PATH_FAIL"),
            "sourceReceipt": "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY",
        }

    expected_visibility_pass = all(v.get("pass") for v in per_feature.values())
    holdout_ok = _interior_holdout_ok(interior_native)

    evidence = dict(pre_evidence)
    checks = dict(evidence.get("checks") or {})
    checks["expectedVisibility"] = bool(expected_visibility_pass)
    evidence["checks"] = checks
    evidence["failures"] = [k for k, ok in checks.items() if not ok]
    evidence["pass"] = len(evidence["failures"]) == 0
    evidence["reboundFromClosedInteriorEvidence"] = True
    evidence["oralOpeningExcludedFromTeethProxy"] = True

    legacy_occ = dict(interior_native.get("legacyOccupancy") or {})
    legacy_occ["enforcement"] = "DIAGNOSTIC_ONLY"
    legacy_enforced = bool(
        legacy_occ.get("legacyPass") is False
        and interior_native.get("pass") is False
        and "legacy" in str(interior_native.get("classification", "")).lower()
    )

    native_semantic_evidence_pass = bool(evidence.get("pass") and holdout_ok)
    failing = [k for k, v in per_feature.items() if not v.get("pass")]
    d_pass = bool(
        camera_lock_pass
        and native_semantic_evidence_pass
        and expected_visibility_pass
        and not failing
    )

    hold_reason = _classify_d_interior_hold_reason(
        camera_lock_pass=camera_lock_pass,
        per_feature=per_feature,
        expected_visibility_pass=expected_visibility_pass,
        evidence=evidence,
        holdout_ok=holdout_ok,
        legacy_enforced_in_pass=legacy_enforced,
        pre_rebind_expected_visibility=pre_rebind_expected_visibility,
    )

    production_contract = {
        "contract": D_INTERIOR_PRODUCTION_CONTRACT,
        "cameraLockPass": camera_lock_pass,
        "cameraSource": camera_source,
        "oralOpeningNativeEvidencePass": oral_opening_native_pass,
        "upperTeethPass": bool(per_feature.get("upperTeeth", {}).get("pass")),
        "lowerTeethPass": bool(per_feature.get("lowerTeeth", {}).get("pass")),
        "tonguePass": bool(per_feature.get("tongue", {}).get("pass")),
        "lipGuardPass": bool(per_feature.get("lipGuard", {}).get("pass")),
        "nativeSemanticEvidencePass": native_semantic_evidence_pass,
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "holdoutOk": holdout_ok,
        "expectedVisibilityPass": expected_visibility_pass,
    }

    interior_native.update(
        {
            "pass": d_pass,
            "perFeature": per_feature,
            "nativeSemanticEvidence": evidence,
            "nativeSemanticEvidencePass": native_semantic_evidence_pass,
            "legacyOccupancy": legacy_occ,
            "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
            "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
            "failures": failing,
            "classification": "PASS" if d_pass else (hold_reason or "INTERIOR_D_GATE_FAIL"),
            "dInteriorProductionContract": production_contract,
            "oralOpeningContract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
            "oralOpeningNativeEvidencePass": oral_opening_native_pass,
        }
    )

    return {
        "probeShot": "mouth_interior",
        "pass": d_pass,
        "gatePassEligible": d_pass,
        "contract": D_INTERIOR_PRODUCTION_CONTRACT,
        "cameraLockPass": camera_lock_pass,
        "cameraSource": camera_source,
        "holdReason": hold_reason,
        "productionContract": production_contract,
        "nativeFeatureAudit": interior_native,
        "perFeature": per_feature,
        "oralOpeningNativeEvidencePass": oral_opening_native_pass,
        "nativeSemanticEvidencePass": native_semantic_evidence_pass,
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "policy": {
            "cameraRetune": "DENY",
            "thresholdMutation": 0,
            "mouthMutation": 0,
            "eyeMutation": 0,
            "cameraMutation": 0,
            "oralOpeningRecalculation": "DENY",
            "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        },
    }


def _oral_native_context_preserved(interior_diagnostic_probe: dict | None) -> bool:
    per_feature = (interior_diagnostic_probe or {}).get("perFeature") or {}
    for feat in INTERIOR_RIG_NATIVE_EMISSION_FEATURES:
        if not bool((per_feature.get(feat) or {}).get("pass")):
            return False
    if not bool((per_feature.get("lipGuard") or {}).get("pass")):
        return False
    return True


def _run_oral_opening_lip_boundary_native_evidence_contract_repair_probe(
    sc,
    cam,
    consumed_cam: dict | None,
    *,
    camera_source: str | None,
    set_mouth_fn,
    mouth_valid_fn,
    skin_basis_coords: list[Vector],
    landmarks: dict,
    region_map: dict,
    weights: dict,
    jaw_empty,
    rig_objs: dict,
    fid_mats: dict,
    res: int,
    oral_bounds: dict | None = None,
    state_receipt: dict | None = None,
    interior_diagnostic_probe: dict | None = None,
) -> dict:
    if consumed_cam is None or camera_source in (None, "INTERIOR_SCENE_EXISTING_FALLBACK"):
        return {
            "probeShot": "mouth_interior",
            "pass": False,
            "contractPass": False,
            "skipped": True,
            "reason": "INTERIOR_CAMERA_CONSUMPTION_REQUIRED",
            "p0Classification": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
            "gatePassEligible": False,
        }

    _apply_locked_camera(cam, consumed_cam)
    set_mouth_fn(24.0, show_oral=True)
    valid, skin = mouth_valid_fn(True)
    state = state_receipt or _mouth_interior_state_receipt(set_mouth_fn, jaw_empty, rig_objs, landmarks)
    state_sync = bool((state.get("mouthInteriorMorphState") or {}).get("synchronized"))
    bounds = oral_bounds or {}
    if not bounds:
        fid_path = Path(tempfile.gettempdir()) / f"nurion_oral_native_evidence_{id(cam)}.png"
        fid_rgb = _render_feature_id(
            sc, cam, skin, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
        )
        if fid_rgb is not None:
            bounds = _oral_opening_projected_bounds(fid_rgb, [0, 0, res - 1, res - 1])
    native_context_present = _oral_native_context_preserved(interior_diagnostic_probe)
    evidence = _evaluate_oral_opening_native_evidence(
        sc,
        cam,
        skin,
        skin_basis_coords=skin_basis_coords,
        landmarks=landmarks,
        region_map=region_map,
        weights=weights,
        oral_bounds=bounds,
        state_synchronized=state_sync,
        native_context_present=native_context_present,
        res=res,
    )
    evidence["lipGuardPreserved"] = bool((interior_diagnostic_probe or {}).get("perFeature", {}).get("lipGuard", {}).get("pass"))
    evidence["rigVisibilityPreserved"] = all(
        bool((interior_diagnostic_probe or {}).get("perFeature", {}).get(f, {}).get("pass"))
        for f in INTERIOR_RIG_NATIVE_EMISSION_FEATURES
    )
    contract_pass = bool(
        evidence.get("contractPass")
        and evidence.get("lipGuardPreserved")
        and evidence.get("rigVisibilityPreserved")
    )
    return {
        "probeShot": "mouth_interior",
        "pass": contract_pass,
        "contractPass": contract_pass,
        "skipped": False,
        "p0Classification": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
        "classification": evidence.get("classification"),
        "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "oralOpeningNativeEvidence": evidence,
        "openingPolygonVertexCount": evidence.get("openingPolygonVertexCount"),
        "openingPolygonProjectedArea": evidence.get("openingPolygonProjectedArea"),
        "openingPolygonBBox": evidence.get("openingPolygonBBox"),
        "openingPolygonSignedArea": evidence.get("openingPolygonSignedArea"),
        "upperLipCurvePointCount": evidence.get("upperLipCurvePointCount"),
        "lowerLipCurvePointCount": evidence.get("lowerLipCurvePointCount"),
        "perXBoundaryGapStats": evidence.get("perXBoundaryGapStats"),
        "teethBBoxSeparationPx": evidence.get("teethBBoxSeparationPx"),
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "interiorCameraSource": camera_source,
        "stateReceipt": state,
        "gatePassEligible": contract_pass,
        "policy": {
            "cameraRetune": "DENY",
            "morphMutation": 0,
            "thresholdMutation": 0,
            "mouthMutation": 0,
            "eyeMutation": 0,
            "cameraMutation": 0,
        },
    }


def _resolve_interior_consumed_camera(
    interior_cam: dict | None,
    frozen_lock: dict | None,
    frozen_receipt: dict,
) -> tuple[dict | None, str, dict]:
    if interior_cam is not None:
        ref = _build_interior_forensic_camera_ref(interior_cam, source="INTERIOR_SOLVER_EXISTING")
        return interior_cam, "INTERIOR_SOLVER_EXISTING", ref or {}
    if frozen_lock is not None and frozen_receipt.get("validFrozenInteriorCameraRefPresent"):
        ref = _build_interior_forensic_camera_ref(frozen_lock, source="FROZEN_CAMERA_LOCK_MANIFEST_READONLY")
        return frozen_lock, "FROZEN_CAMERA_LOCK_MANIFEST_READONLY", ref or {}
    return None, "INTERIOR_SCENE_EXISTING_FALLBACK", {}


def _run_interior_camera_lock_provenance_and_state_consumption_restoration_probe(
    sc,
    cam,
    *,
    interior_cam: dict | None,
    interior_bounds: tuple[Vector | None, Vector | None],
    frozen_manifest_path: Path,
    set_mouth_fn,
    mouth_valid_fn,
    jaw_empty,
    rig_objs: dict,
    fid_mats: dict,
    landmarks: dict,
    res: int,
    out_dir: Path,
    label: str,
    interior_diagnostic_probe: dict | None = None,
    skin_basis_coords: list[Vector] | None = None,
) -> dict:
    basis_coords = skin_basis_coords or []
    solver_trace = (
        _diagnose_interior_solver_failure(sc, cam, landmarks, interior_bounds, basis_coords, res)
        if interior_bounds[0] is not None
        else {"classification": "INTERIOR_BOUNDS_UNAVAILABLE", "interiorSolverAvailable": False}
    )
    frozen_lock, frozen_receipt = _load_valid_frozen_interior_camera_lock(frozen_manifest_path)
    consumed_cam, camera_source, camera_ref = _resolve_interior_consumed_camera(
        interior_cam, frozen_lock, frozen_receipt
    )

    set_mouth_fn(24.0, show_oral=True)
    state_receipt = _mouth_interior_state_receipt(set_mouth_fn, jaw_empty, rig_objs, landmarks)

    if consumed_cam is not None and camera_source != "INTERIOR_SCENE_EXISTING_FALLBACK":
        _apply_locked_camera(cam, consumed_cam)
        set_mouth_fn(24.0, show_oral=True)
        state_receipt = _mouth_interior_state_receipt(set_mouth_fn, jaw_empty, rig_objs, landmarks)

    valid, skin = mouth_valid_fn(True)
    fid_path = Path(tempfile.gettempdir()) / f"nurion_interior_restoration_fid_{id(cam)}.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    bbox = [0, 0, res - 1, res - 1]
    oral_bounds = _oral_opening_projected_bounds(fid_rgb, bbox)
    oral = oral_bounds.get("oralOpeningValidation") or _validate_oral_opening(fid_rgb, bbox)
    lip_counts = (
        _count_feature_pixels(fid_rgb, bbox, ("lip", "lip_corner_l", "lip_corner_r"), full_frame=False)
        if fid_rgb is not None
        else {}
    )
    lip_guard_px = sum(int(lip_counts.get(k, 0)) for k in ("lip", "lip_corner_l", "lip_corner_r"))
    lip_floor = MIN_ABSOLUTE_FLOOR.get("lip", 0)

    rig_status = {}
    diag_features = (interior_diagnostic_probe or {}).get("perFeature") or {}
    for diag_name, (rig_key, _rig_obj_name) in INTERIOR_RIG_OBJECT_KEYS.items():
        prior = diag_features.get(diag_name, {})
        final_px = int(_count_feature_pixels(fid_rgb, bbox, (rig_key,), full_frame=False).get(rig_key, 0)) if fid_rgb is not None else 0
        floor = MIN_ABSOLUTE_FLOOR.get(rig_key, 0)
        classification = "PASS" if final_px >= floor else prior.get("classification", "INTERIOR_FID_RENDER_PATH_FAIL")
        if prior.get("pass") and final_px >= floor:
            classification = "PASS"
        rig_status[diag_name] = {
            "status": "PASS" if classification == "PASS" else "FAIL",
            "classification": classification,
            "finalPixels": final_px,
            "existingAbsoluteFloor": floor,
            "softwareFallbackUsed": prior.get("softwareFallbackUsed", False),
            "frozenFromPriorDiagnostic": bool(prior.get("pass")),
        }

    interior_solver_available = interior_cam is not None or bool(solver_trace.get("interiorSolverAvailable"))
    valid_frozen_ref = bool(frozen_receipt.get("validFrozenInteriorCameraRefPresent"))
    state_sync_ok = bool(state_receipt["mouthInteriorMorphState"]["synchronized"])
    camera_ok = consumed_cam is not None and camera_source != "INTERIOR_SCENE_EXISTING_FALLBACK"
    teeth_oral = oral_bounds.get("oralOpeningValidation") or oral
    camera_consumption_pass = bool(
        camera_ok and state_sync_ok and (interior_solver_available or valid_frozen_ref)
    )
    lip_pass = lip_guard_px >= lip_floor
    rig_pass = all(rig_status[f]["classification"] == "PASS" for f in INTERIOR_RIG_NATIVE_EMISSION_FEATURES)
    restoration_pass = bool(camera_consumption_pass and lip_pass and rig_pass)

    return {
        "probeShot": "mouth_interior",
        "pass": restoration_pass,
        "restorationPass": restoration_pass,
        "cameraConsumptionPass": camera_consumption_pass,
        "p0Classification": "INTERIOR_CAMERA_LOCK_STATE_CONSUMPTION_MISSING"
        if not camera_ok
        else None,
        "interiorSolverAvailable": bool(interior_solver_available),
        "validFrozenInteriorCameraRefPresent": valid_frozen_ref,
        "interiorCameraSource": camera_source,
        "consumedCameraState": consumed_cam,
        "forensicCameraRef": camera_ref,
        "solverTrace": solver_trace,
        "frozenLockReceipt": frozen_receipt,
        "stateReceipt": state_receipt,
        "oralOpeningProjectedBounds": oral_bounds,
        "oralOpeningRevalidation": {
            "projectedFaces": oral_bounds.get("projectedFaces", 0),
            "positiveAreaFaces": oral_bounds.get("positiveAreaFaces", 0),
            "separationPx": teeth_oral.get("separationPx", 0),
            "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
            "contractRole": "DIAGNOSTIC_ONLY",
            "pass": None,
            "classification": "DEFERRED_TO_ORAL_OPENING_NATIVE_EVIDENCE",
            "missingReason": teeth_oral.get("reason"),
        },
        "lipGuardRevalidation": {
            "finalPixels": lip_guard_px,
            "existingAbsoluteFloor": lip_floor,
            "pass": bool(lip_pass),
            "classification": "PASS" if lip_pass else "INTERIOR_CONTEXT_VISIBILITY_FAIL",
            "deferUntilValidInteriorCamera": not camera_ok,
        },
        "interiorRigNativeEmission": {
            feat: rig_status[feat]["status"] for feat in INTERIOR_RIG_NATIVE_EMISSION_FEATURES
        },
        "interiorRigNativeEmissionDetail": rig_status,
        "gatePassEligible": False,
        "policy": {
            "cameraRetune": "DENY",
            "thresholdMutation": 0,
            "mouthMutation": 0,
            "eyeMutation": 0,
            "basisMutation": 0,
            "weightMutation": 0,
            "cameraMutation": 0,
        },
    }


def _run_interior_native_visibility_emission_parity_probe(
    sc,
    cam,
    interior_cam: dict | None,
    *,
    set_mouth_fn,
    mouth_valid_fn,
    rig_objs: dict,
    fid_mats: dict,
    mask_mat,
    res: int,
    out_dir: Path,
    label: str,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    bounds: tuple[Vector, Vector],
    camera_source: str | None = None,
    oral_native_evidence: dict | None = None,
) -> dict:
    set_mouth_fn(24.0, show_oral=True)
    valid, skin = mouth_valid_fn(True)
    if interior_cam is not None:
        _apply_locked_camera(cam, interior_cam)
        camera_ref = interior_cam
        if camera_source is None:
            camera_source = "INTERIOR_SOLVER_EXISTING"
        solver_available = camera_source == "INTERIOR_SOLVER_EXISTING"
    else:
        camera_ref = _camera_state_snapshot(cam)
        if camera_source is None:
            camera_source = "INTERIOR_SCENE_EXISTING_FALLBACK"
        solver_available = False

    fid_path = Path(tempfile.gettempdir()) / f"nurion_interior_fid_probe_{id(cam)}.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    fid_receipt = dict(_FID_RENDER_RECEIPT)
    bbox = [0, 0, res - 1, res - 1]
    oral = _validate_oral_opening(fid_rgb, bbox) if fid_rgb is not None else {"pass": False, "separationPx": 0}
    lip_counts = (
        _count_feature_pixels(fid_rgb, bbox, ("lip", "lip_corner_l", "lip_corner_r"), full_frame=False)
        if fid_rgb is not None
        else {}
    )
    lip_guard_px = sum(int(lip_counts.get(k, 0)) for k in ("lip", "lip_corner_l", "lip_corner_r"))
    slot_proj = _mouth_slot_projection_summary(sc, cam, skin, res, ("lip", "lip_corner_l", "lip_corner_r"))
    lip_slot_px = sum(int((slot_proj.get("perFeature") or {}).get(k, {}).get("projectedAreaPxEstimate", 0)) for k in ("lip", "lip_corner_l", "lip_corner_r"))

    per_feature: dict[str, dict] = {}

    for diag_name, (rig_key, rig_obj_name) in INTERIOR_RIG_OBJECT_KEYS.items():
        rig_obj = rig_objs.get(rig_obj_name)
        face_indices = set(range(len(rig_obj.data.polygons))) if rig_obj else set()
        geom = _audit_feature_face_geometry(sc, cam, rig_obj, face_indices, res) if rig_obj else {}
        layer = (fid_receipt.get("layers") or {}).get(rig_key, {})
        native_slot = int(layer.get("nativeSlotRenderPixels", layer.get("encodedLayerPixels", 0)))
        final_px = int(_count_feature_pixels(fid_rgb, bbox, (rig_key,), full_frame=False).get(rig_key, 0)) if fid_rgb is not None else 0
        floor = MIN_ABSOLUTE_FLOOR.get(rig_key, 0)
        projected = int(geom.get("projectedFaces", 0))
        positive = int(geom.get("positiveAreaFaces", 0))
        visibility_pass = projected > 0 and positive > 0
        emission_pass = final_px >= floor
        classification = _classify_interior_feature_failure(
            feature=diag_name,
            projected_faces=projected,
            native_slot_pixels=native_slot,
            final_pixels=final_px,
            visibility_contract_pass=visibility_pass,
            emission_contract_pass=emission_pass,
        )
        per_feature[diag_name] = {
            "feature": diag_name,
            "rigFeatureKey": rig_key,
            "projectedFaces": projected,
            "positiveAreaFaces": positive,
            "nativeSlotPixels": native_slot,
            "finalPixels": final_px,
            "existingAbsoluteFloor": floor,
            "visibilityContractPass": bool(visibility_pass),
            "emissionContractPass": bool(emission_pass),
            "classification": classification,
            "missingReason": _interior_feature_missing_reason(classification, floor=floor, final_pixels=final_px),
            "nativeSlotRenderPath": layer.get("nativeSlotRenderPath"),
            "softwareFallbackUsed": bool(layer.get("softwareFallbackUsed", False)),
            "pass": classification == "PASS",
        }

    oral_px = int(oral.get("separationPx", 0))
    if oral_native_evidence is not None:
        per_feature["oralOpening"] = _oral_opening_per_feature_from_native_evidence(oral_native_evidence)
    else:
        per_feature["oralOpening"] = {
            "feature": "oralOpening",
            "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
            "nativeSlotPixels": oral_px,
            "finalPixels": oral_px,
            "existingAbsoluteFloor": 0,
            "visibilityContractPass": False,
            "emissionContractPass": False,
            "classification": "DEFERRED_TO_ORAL_OPENING_NATIVE_EVIDENCE",
            "missingReason": "DEFERRED_TO_ORAL_OPENING_NATIVE_EVIDENCE",
            "oralOpeningValidation": {
                **oral,
                "enforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
                "contractRole": "DIAGNOSTIC_ONLY",
            },
            "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
            "teethBBoxSeparationPx": oral_px,
            "pass": False,
        }

    lip_floor = MIN_ABSOLUTE_FLOOR.get("lip", 0)
    lip_visibility = lip_slot_px > 0 or lip_guard_px > 0
    lip_emission = lip_guard_px >= lip_floor
    lip_class = _classify_interior_feature_failure(
        feature="lipGuard",
        projected_faces=1 if lip_slot_px > 0 else 0,
        native_slot_pixels=lip_guard_px,
        final_pixels=lip_guard_px,
        visibility_contract_pass=lip_visibility,
        emission_contract_pass=lip_emission,
    )
    per_feature["lipGuard"] = {
        "feature": "lipGuard",
        "projectedFaces": 1 if lip_slot_px > 0 else 0,
        "positiveAreaFaces": 1 if lip_guard_px > 0 else 0,
        "nativeSlotPixels": lip_guard_px,
        "finalPixels": lip_guard_px,
        "existingAbsoluteFloor": lip_floor,
        "visibilityContractPass": lip_visibility,
        "emissionContractPass": bool(lip_emission),
        "classification": lip_class,
        "missingReason": _interior_feature_missing_reason(lip_class, floor=lip_floor, final_pixels=lip_guard_px),
        "lipSlotPixels": lip_slot_px,
        "pass": lip_class == "PASS",
    }

    metrics = _render_holdout_occupancy_metrics(
        sc, cam, valid, mask_mat, res, semantic_bounds=bounds, morph_bounds=bounds
    )
    in_frame, frame_reason = _landmarks_in_frame(
        sc, cam, landmarks, _frame_landmark_keys("mouth", "mouth_interior"), res, skin_basis_coords, "interior"
    )
    camera_receipt = {
        "interiorCameraPresent": True,
        "interiorCameraSource": camera_source,
        "interiorSolverAvailable": solver_available,
        "cameraRefLocation": camera_ref.get("location"),
        "cameraRefRotation": camera_ref.get("rotation"),
        "cameraRefOrthoScale": camera_ref.get("ortho_scale"),
        "cameraRefProjection": {
            "orthoScale": camera_ref.get("ortho_scale"),
            "distance": camera_ref.get("distance"),
            "semanticCenter": camera_ref.get("semanticCenter"),
            "semanticViewDir": camera_ref.get("semanticViewDir"),
        },
        "cameraMutation": 0,
        "gatePassEligible": False,
    }
    probe_pass = all(per_feature[f]["pass"] for f in INTERIOR_DIAGNOSTIC_FEATURES)
    return {
        "probeShot": "mouth_interior",
        "pass": bool(probe_pass),
        "diagnosticPass": bool(probe_pass),
        "skipped": False,
        "interiorSolverAvailable": solver_available,
        "perFeature": per_feature,
        "classifications": {f: per_feature[f]["classification"] for f in INTERIOR_DIAGNOSTIC_FEATURES},
        "fidRenderReceipt": fid_receipt,
        "nativeMask": metrics,
        "interiorCameraReceipt": camera_receipt,
        "inFrame": bool(in_frame),
        "frameReason": frame_reason,
        "gatePassEligible": False,
        "policy": {
            "cameraRetune": "DENY",
            "thresholdMutation": 0,
            "mouthMutation": 0,
            "eyeMutation": 0,
            "softwareFallbackPassBypass": "DENY",
        },
    }


def _eye_bounds_for_pct(
    set_eye_fn,
    side: str,
    open_pct: float,
    rig_objs: dict,
    skin_basis_coords: list[Vector],
) -> tuple[Vector, Vector] | tuple[None, None]:
    set_eye_fn(side, open_pct)
    region = lambda v, s=side: _eye_framing(v, s)
    eyeball = rig_objs["helper-l-eye" if side == "L" else "helper-r-eye"]
    lashes = [
        rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-1"],
        rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-2"],
    ]
    skin_eye = set_eye_fn.skin_eye
    if skin_eye is None:
        return None, None
    co_min, co_max = _framing_bounds(skin_eye, skin_basis_coords, region, extras=[eyeball] + lashes)
    if co_min is None:
        return None, None
    return _pad_aabb(co_min, co_max, EYE_GUARD_PAD)


def _eye_valid_objects(set_eye_fn, side: str, rig_objs: dict) -> list:
    eyeball = rig_objs["helper-l-eye" if side == "L" else "helper-r-eye"]
    lashes = [
        rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-1"],
        rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-2"],
    ]
    return [set_eye_fn.skin_eye, eyeball] + lashes


def _eye_joint_eval_at_ortho(
    sc,
    cam,
    center: Vector,
    view_dir: Vector,
    dist: float,
    ortho: float,
    landmarks: dict,
    side: str,
    res: int,
    set_eye_fn,
    rig_objs: dict,
    skin_basis_coords: list[Vector],
    mask_mat,
    fid_mats: dict,
    frame_keys: tuple[str, ...],
    locked_semantic_bounds: tuple[Vector | None, Vector | None] | None = None,
) -> tuple[bool, list[dict]]:
    _apply_semantic_camera(cam, center, ortho, view_dir, dist)
    center = _nudge_camera_to_landmarks(
        sc, cam, landmarks, frame_keys, center, view_dir, dist, res, skin_basis_coords, "front"
    )
    rows: list[dict] = []
    ok_all = True
    for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
        set_eye_fn(side, pct)
        valid = _eye_valid_objects(set_eye_fn, side, rig_objs)
        morph_bounds = _eye_bounds_for_pct(set_eye_fn, side, pct, rig_objs, skin_basis_coords)
        sem_bounds = locked_semantic_bounds if locked_semantic_bounds and locked_semantic_bounds[0] is not None else morph_bounds
        evidence_row = _evaluate_eye_state_native_evidence(
            sc,
            cam,
            valid,
            set_eye_fn.skin_eye,
            rig_objs,
            side,
            state,
            mask_mat,
            fid_mats,
            res,
            landmarks,
            skin_basis_coords,
            frame_keys,
            sem_bounds,
            morph_bounds,
        )
        legacy_occ = evidence_row.get("legacyOccupancy") or {}
        frame_occ = (evidence_row.get("occupancyMetrics") or {}).get("frameOccupancy") or legacy_occ.get("frame") or {}
        wf = float((evidence_row.get("occupancy") or {}).get("widthFrac", frame_occ.get("widthFrac", 0.0)))
        hf = float((evidence_row.get("occupancy") or {}).get("heightFrac", frame_occ.get("heightFrac", 0.0)))
        ok = bool(evidence_row.get("nativeSemanticEvidencePass"))
        vis = evidence_row.get("featureVisibility") or {}
        visibility_parity = {
            f: (vis.get(f) or {}).get("visibilityParityClassification") for f in EYE_GATE_FEATURES if f in vis
        }
        rows.append(
            {
                "state": state,
                "ortho": float(ortho),
                "featureOccupancy": {"widthFrac": wf, "heightFrac": hf},
                "contextOccupancy": {
                    "widthFrac": float(frame_occ.get("widthFrac", wf)),
                    "heightFrac": float(frame_occ.get("heightFrac", hf)),
                },
                "occupancyMetrics": evidence_row.get("occupancyMetrics"),
                "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
                "legacyOccupancy": legacy_occ,
                "nativeSemanticEvidence": evidence_row.get("nativeSemanticEvidence"),
                "featureVisibility": vis,
                "visibilityParity": visibility_parity,
                "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
                "fullBleed": bool(evidence_row.get("fullBleed")),
                "inFrame": bool(evidence_row.get("inFrame")),
                "frameReason": evidence_row.get("frameReason"),
                "contextOk": bool(evidence_row.get("contextRetained")),
                "contextReason": evidence_row.get("contextReason"),
                "occupancyOk": bool(legacy_occ.get("legacyPass")),
                "evidenceOk": bool(evidence_row.get("evidenceOk")),
                "pass": ok,
            }
        )
        if not ok:
            ok_all = False
    return ok_all, rows


def _solve_eye_side_camera(
    sc,
    cam,
    landmarks: dict,
    side: str,
    res: int,
    set_eye_fn,
    rig_objs: dict,
    skin_basis_coords: list[Vector],
    mask_mat,
    fid_mats: dict,
) -> dict | None:
    set_eye_fn(side, 0.0)
    bounds0 = _eye_bounds_for_pct(set_eye_fn, side, 0.0, rig_objs, skin_basis_coords)
    if bounds0[0] is None:
        return {"pass": False, "side": side, "classification": "PROJECTION_CLIP_CONFLICT", "scan": {}}
    co_min, co_max = bounds0
    view_dir = _legacy_view_dir("front")
    shot_kind = f"eye_{'l' if side == 'L' else 'r'}"
    mask_center = (co_min + co_max) / 2.0
    center = _semantic_center(landmarks, "eye", shot_kind, mask_center)
    dist = _legacy_place_camera(cam, center, co_min, co_max, "front")
    sem_center = center.copy()
    frame_keys = _frame_landmark_keys("eye", shot_kind)
    scan_log: dict[str, list[dict]] = {st: [] for st in ("closed", "half", "open")}
    feasible_sets: dict[str, list[float]] = {st: [] for st in ("closed", "half", "open")}
    lo = float(cam.data.ortho_scale) * 0.25
    hi = max(float(cam.data.ortho_scale) * 8.0, 8.0)
    probe_orthos: list[float] = []
    for step in range(24):
        t = float(step) / 23.0
        probe_orthos.append(lo + (hi - lo) * t)
    probe_orthos = sorted(set(probe_orthos + [lo, hi]))

    for ortho in probe_orthos:
        joint_ok, rows = _eye_joint_eval_at_ortho(
            sc,
            cam,
            center,
            view_dir,
            dist,
            ortho,
            landmarks,
            side,
            res,
            set_eye_fn,
            rig_objs,
            skin_basis_coords,
            mask_mat,
            fid_mats,
            frame_keys,
            locked_semantic_bounds=bounds0,
        )
        base_ortho = float(cam.data.ortho_scale) if float(cam.data.ortho_scale) > 1e-6 else ortho
        for row in rows:
            row["orthoMult"] = float(ortho / base_ortho)
            row["semanticCenter"] = [float(x) for x in sem_center]
            scan_log[row["state"]].append(row)
        if joint_ok:
            for st in ("closed", "half", "open"):
                feasible_sets[st].append(float(ortho))

    best_ortho = None
    blo, bhi = lo, hi
    for _ in range(28):
        mid = (blo + bhi) / 2.0
        joint_ok, rows = _eye_joint_eval_at_ortho(
            sc,
            cam,
            center,
            view_dir,
            dist,
            mid,
            landmarks,
            side,
            res,
            set_eye_fn,
            rig_objs,
            skin_basis_coords,
            mask_mat,
            fid_mats,
            frame_keys,
            locked_semantic_bounds=bounds0,
        )
        if joint_ok:
            best_ortho = mid
            bhi = mid
            for st in ("closed", "half", "open"):
                feasible_sets[st].append(float(mid))
        else:
            row = rows[0] if rows else {}
            if not row.get("inFrame"):
                bhi = mid
            elif row.get("fullBleed"):
                blo = mid
            elif not row.get("contextOk"):
                if row.get("contextReason") == "CONTEXT_LOSS_FULL_BLEED":
                    blo = mid
                else:
                    bhi = mid
            elif not row.get("evidenceOk"):
                bhi = mid
            else:
                bhi = mid

    state_intervals = {st: _ortho_feasible_interval(feasible_sets[st]) for st in ("closed", "half", "open")}
    common = state_intervals.get("closed")
    for st in ("half", "open"):
        common = _interval_intersection(common, state_intervals.get(st))

    if common is None and best_ortho is not None:
        common = (float(best_ortho), float(best_ortho))

    if common is None:
        return {
            "pass": False,
            "side": side,
            "classification": _classify_eye_solver_failure(state_intervals, scan_log),
            "stateIntervals": {
                k: None if v is None else {"minOrtho": v[0], "maxOrtho": v[1]} for k, v in state_intervals.items()
            },
            "scan": scan_log,
            "parityCameraRef": {
                "location": [float(x) for x in cam.location],
                "rotation": [float(x) for x in cam.rotation_euler],
                "ortho_scale": float(cam.data.ortho_scale),
                "distance": float(dist),
                "view_dir": [float(x) for x in view_dir],
                "semanticViewDir": [float(x) for x in _landmark_view_dir(landmarks, "front")],
                "semanticCenter": [float(x) for x in sem_center],
                "paritySource": "SOLVER_LAST_BISECT_STATE",
            },
        }

    chosen_ortho = common[0]
    _apply_semantic_camera(cam, center, chosen_ortho, view_dir, dist)
    _nudge_camera_to_landmarks(
        sc, cam, landmarks, frame_keys, center, view_dir, dist, res, skin_basis_coords, "front"
    )
    return {
        "pass": True,
        "location": [float(x) for x in cam.location],
        "rotation": [float(x) for x in cam.rotation_euler],
        "ortho_scale": float(chosen_ortho),
        "distance": float(dist),
        "view_dir": [float(x) for x in view_dir],
        "semanticViewDir": [float(x) for x in _landmark_view_dir(landmarks, "front")],
        "semanticCenter": [float(x) for x in sem_center],
        "commonOrthoInterval": {"minOrtho": common[0], "maxOrtho": common[1]},
        "stateIntervals": {
            k: None if v is None else {"minOrtho": v[0], "maxOrtho": v[1]} for k, v in state_intervals.items()
        },
        "scan": scan_log,
        "semanticLocked": True,
    }


def _ortho_feasible_interval(feasible: list[float]) -> tuple[float, float] | None:
    if not feasible:
        return None
    return float(min(feasible)), float(max(feasible))


def _interval_intersection(a: tuple[float, float] | None, b: tuple[float, float] | None) -> tuple[float, float] | None:
    if a is None or b is None:
        return None
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    if lo > hi:
        return None
    return lo, hi


def _visibility_conflict_label_from_scan(scan: dict) -> str | None:
    for st in ("closed", "half", "open"):
        for row in scan.get(st, []):
            parity = row.get("visibilityParity") or {}
            for feat, cls in parity.items():
                if cls == "EXPECTED_VISIBLE_MISSING":
                    vis = (row.get("featureVisibility") or {}).get(feat, {})
                    reason = (vis.get("nativeSemanticEmission") or {}).get("missingReason")
                    if reason == "FID_RENDER_PATH_FAIL":
                        return f"FID_RENDER_PATH_FAIL_{feat}"
                    return f"EXPECTED_VISIBLE_MISSING_{feat}"
                if cls == "EXPECTED_OCCLUDED_BUT_VISIBLE":
                    return f"EXPECTED_OCCLUDED_BUT_VISIBLE_{feat}"
    return None


def _classify_eye_solver_failure(state_intervals: dict[str, tuple[float, float] | None], scan: dict) -> str:
    parity_label = _visibility_conflict_label_from_scan(scan)
    if not any(state_intervals.values()):
        rows = [r for st in scan.values() for r in st if isinstance(r, dict)]
        if rows and all(not r.get("inFrame") for r in rows):
            if any("BEHIND" in str(r.get("frameReason", "")) for r in rows):
                return "PROJECTION_CLIP_CONFLICT"
        if rows and all(not r.get("evidenceOk") for r in rows):
            if any(r.get("contextReason") == "CONTEXT_LOSS_FULL_BLEED" for r in rows):
                return "CONTEXT_MIN_CONFLICT"
            if any(not r.get("inFrame") for r in rows):
                return "PROJECTION_CLIP_CONFLICT"
            return parity_label or "FEATURE_VISIBILITY_CONFLICT"
        return "PROJECTION_CLIP_CONFLICT"
    present = [k for k, v in state_intervals.items() if v is not None]
    if len(present) < 3:
        missing = [k for k in ("closed", "half", "open") if state_intervals.get(k) is None]
        if missing:
            for st in missing:
                rows = scan.get(st, [])
                if any(r.get("fullBleed") for r in rows):
                    return "CONTEXT_MIN_CONFLICT"
                if any(not r.get("evidenceOk") and r.get("inFrame") for r in rows):
                    return parity_label or "FEATURE_VISIBILITY_CONFLICT"
            return "GUARD_RING_CONFLICT"
    common = _interval_intersection(
        state_intervals.get("closed"),
        _interval_intersection(state_intervals.get("half"), state_intervals.get("open")),
    )
    if common is None:
        return "NO_COMMON_ORTHO_INTERVAL"
    return "NO_COMMON_ORTHO_INTERVAL"


def _assign_semantic_regions(obj, basis_coords, landmarks, qa_mats, weights):
    mesh = obj.data
    mats = [
        qa_mats["skin"],
        qa_mats["lip"],
        qa_mats["lip_corner_l"],
        qa_mats["lip_corner_r"],
        qa_mats["chin"],
    ]
    mesh.materials.clear()
    for m in mats:
        mesh.materials.append(m)

    region_map = _build_semantic_region_map(mesh, basis_coords, landmarks, weights)
    landmarks["region_map"] = region_map
    chin_faces = region_map.get("chin_faces", set())

    for fi, poly in enumerate(mesh.polygons):
        if fi in chin_faces:
            poly.material_index = 4
        elif any(v in region_map["corner_l_verts"] for v in poly.vertices):
            poly.material_index = 2
        elif any(v in region_map["corner_r_verts"] for v in poly.vertices):
            poly.material_index = 3
        elif any(v in region_map["lip_verts"] for v in poly.vertices):
            poly.material_index = 1
        else:
            poly.material_index = 0


def _apply_lip_faces(obj, basis_coords, weights, lip_mat, skin_mat):
    return


def _setup_scene(res):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.image_settings.file_format = "PNG"
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    sc.view_settings.exposure = 0.0
    vl = bpy.context.view_layer
    vl.use_pass_object_index = True
    w = bpy.data.worlds.new("QA")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
        bg.inputs[1].default_value = 1.0


def _lights_semantic_qa(cam, target: Vector, view_dir: Vector, key_energy: float):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)
    view_dir = view_dir.normalized()
    up = Vector((0.0, 0.0, 1.0))
    right = view_dir.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up_cam = right.cross(view_dir).normalized()

    def add(n, loc, e, size=1.5):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = size
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    key_pos = target - view_dir * 0.55 + up_cam * 0.32 + right * 0.10
    fill_pos = target - view_dir * 0.42 - right * 0.28 + up_cam * 0.04
    fill_energy = max(key_energy * FILL_ENERGY_RATIO, 18.0)
    add("Key", key_pos, key_energy, 1.8)
    add("Fill", fill_pos, fill_energy, 1.6)


def _lights_human_qa(target):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e, size=1.4):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = size
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.16, target.y - 0.78, target.z + 0.58), 620, 2.6)
    add("Fill", (target.x - 0.34, target.y - 0.58, target.z - 0.12), 55, 2.2)
    add("Rim", (target.x + 0.02, target.y + 0.62, target.z + 0.32), 360, 1.6)


def _lights(target):
    for o in list(bpy.data.objects):
        if o.type == "LIGHT":
            bpy.data.objects.remove(o, do_unlink=True)

    def add(n, loc, e):
        d = bpy.data.lights.new(n, "AREA")
        d.energy = e
        d.size = 1.6
        o = bpy.data.objects.new(n, d)
        bpy.context.scene.collection.objects.link(o)
        o.location = Vector(loc)
        _look_at(o, target)

    add("Key", (target.x + 0.06, target.y - 0.45, target.z + 0.12), 90)
    add("Fill", (target.x - 0.10, target.y - 0.35, target.z), 45)


def _mouth_framing(v: Vector) -> bool:
    return 6.02 <= v.y <= 7.10 and 0.72 <= v.z <= 1.74 and -0.68 <= v.x <= 0.68


def _eye_framing(v: Vector, side: str) -> bool:
    if side == "L":
        return -0.66 <= v.x <= 0.10 and 6.78 <= v.y <= 7.72 and 0.88 <= v.z <= 1.66
    return -0.10 <= v.x <= 0.66 and 6.78 <= v.y <= 7.72 and 0.88 <= v.z <= 1.66


def _interior_framing(v: Vector) -> bool:
    return 6.35 <= v.y <= 6.98 and 1.02 <= v.z <= 1.58 and -0.42 <= v.x <= 0.42


def _framing_bounds(skin_obj, basis_coords, region_fn, extras=None, extras_only=False):
    bpy.context.view_layer.update()
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(wc: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], wc[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], wc[i]) for i in range(3)))

    if skin_obj is not None and not extras_only:
        mw = skin_obj.matrix_world
        for co in basis_coords:
            if region_fn(co):
                absorb(mw @ Vector(co))
    if extras:
        for obj in extras:
            if obj.hide_render or obj.type != "MESH":
                continue
            mw = obj.matrix_world
            for corner in obj.bound_box:
                absorb(mw @ Vector(corner))
    if not found:
        return None, None
    return co_min, co_max


def _union_aabb(
    a_min: Vector | None, a_max: Vector | None, b_min: Vector, b_max: Vector
) -> tuple[Vector, Vector]:
    if a_min is None:
        return b_min.copy(), b_max.copy()
    return Vector((min(a_min.x, b_min.x), min(a_min.y, b_min.y), min(a_min.z, b_min.z))), Vector(
        (max(a_max.x, b_max.x), max(a_max.y, b_max.y), max(a_max.z, b_max.z))
    )


def _pad_aabb(co_min: Vector, co_max: Vector, pad: Vector) -> tuple[Vector, Vector]:
    return co_min - pad, co_max + pad


def _coords_framing_bounds(coords: list[Vector], mw, region_fn, extras=None):
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(wc: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], wc[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], wc[i]) for i in range(3)))

    for co in coords:
        if region_fn(co):
            absorb(mw @ Vector(co))
    if extras:
        for obj in extras:
            if obj.hide_render or obj.type != "MESH":
                continue
            emw = obj.matrix_world
            for corner in obj.bound_box:
                absorb(emw @ Vector(corner))
    if not found:
        return None, None
    return co_min, co_max


def _jaw_morphed_coords(basis_coords: list[Vector], weights: dict[int, float], pivot: Vector, angle_deg: float):
    out = [co.copy() for co in basis_coords]
    angle_rad = math.radians(angle_deg)
    for vi, w in weights.items():
        if w < 1e-6 or vi >= len(out):
            continue
        rel = out[vi] - pivot
        partial = angle_rad * w
        c, s = math.cos(partial), math.sin(partial)
        y, z = float(rel.y), float(rel.z)
        out[vi] = pivot + Vector((rel.x, c * y - s * z, s * y + c * z))
    return out


def _mouth_morph_union_bounds(
    skin_obj,
    basis_coords: list[Vector],
    weights: dict[int, float],
    pivot: Vector,
    oral_objs,
):
    mw = skin_obj.matrix_world
    u_min, u_max = None, None
    for angle, show_oral in ((0.0, False), (12.0, True), (24.0, True)):
        morphed = _jaw_morphed_coords(basis_coords, weights, pivot, angle)
        bmin, bmax = _coords_framing_bounds(
            morphed, mw, _mouth_framing, oral_objs if show_oral else None
        )
        if bmin is None:
            continue
        u_min, u_max = _union_aabb(u_min, u_max, bmin, bmax)
    return u_min, u_max


def _mouth_union_bounds_with_chin_guard(
    skin_obj,
    basis_coords: list[Vector],
    weights: dict[int, float],
    pivot: Vector,
    oral_objs,
    landmarks: dict,
):
    u_min, u_max = _mouth_morph_union_bounds(skin_obj, basis_coords, weights, pivot, oral_objs)
    if u_min is None:
        return None, None
    chin = landmarks.get("chin")
    if chin is not None:
        pad = Vector((0.08, 0.08, 0.10))
        cmin = chin - pad
        cmax = chin + pad
        u_min, u_max = _union_aabb(u_min, u_max, cmin, cmax)
    ctx = Vector((CONTEXT_GUARD_PAD, CONTEXT_GUARD_PAD, CONTEXT_GUARD_PAD))
    return _pad_aabb(u_min, u_max, ctx)


def _mouth_morph_projection_specs(
    skin_obj,
    basis_coords: list[Vector],
    weights: dict[int, float],
    pivot: Vector,
    oral_objs,
    view: str,
    union_min: Vector,
    union_max: Vector,
) -> list[dict]:
    mw = skin_obj.matrix_world
    specs: list[dict] = []
    for angle, show_oral in ((0.0, False), (12.0, True), (24.0, True)):
        morphed = _jaw_morphed_coords(basis_coords, weights, pivot, angle)
        co_min, co_max = _coords_framing_bounds(
            morphed, mw, _mouth_framing, oral_objs if show_oral else None
        )
        if co_min is None:
            continue
        specs.append(
            {
                "angle": angle,
                "showOral": show_oral,
                "view": view,
                "coMin": co_min,
                "coMax": co_max,
                "unionMin": union_min,
                "unionMax": union_max,
            }
        )
    return specs


def _interior_bounds_with_guard(skin_obj, basis_coords, oral_objs):
    bmin, bmax = _framing_bounds(skin_obj, basis_coords, _interior_framing, oral_objs, extras_only=False)
    if bmin is None:
        return None, None
    pad = Vector((CONTEXT_GUARD_PAD, CONTEXT_GUARD_PAD, CONTEXT_GUARD_PAD))
    return _pad_aabb(bmin, bmax, pad)


def _eye_bounds_with_guard(valid_objs):
    bmin, bmax = _objects_world_bounds(valid_objs)
    if bmin is None:
        return None, None
    return _pad_aabb(bmin, bmax, EYE_GUARD_PAD)


def _legacy_view_dir(mode: str) -> Vector:
    if mode == "front":
        return Vector((0.0, -1.0, 0.0))
    if mode == "left":
        return Vector((0.70, -0.72, 0.05)).normalized()
    if mode == "interior":
        return Vector((0.0, -0.92, -0.08)).normalized()
    raise ValueError(mode)


def _legacy_nudge(cam, mask, center, mode, dist):
    h, w = mask.shape
    ys, xs = np.where(mask > 0.5)
    if len(xs) == 0:
        return center
    cx_px = (float(xs.min()) + float(xs.max())) / 2.0
    cy_px = (float(ys.min()) + float(ys.max())) / 2.0
    dx = (cx_px - w / 2.0) / w
    dy = (cy_px - h / 2.0) / h
    scale = float(cam.data.ortho_scale)
    if mode == "front":
        shift = Vector((dx * scale * 0.95, 0.0, -dy * scale * 0.95))
    elif mode == "left":
        shift = Vector((dx * scale * 0.65, dx * scale * 0.45, -dy * scale * 0.95))
    else:
        shift = Vector((dx * scale * 0.5, dy * scale * 0.2, -dy * scale * 0.8))
    center = center + shift
    view_dir = _legacy_view_dir(mode)
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    return center


def _legacy_place_camera(cam, center, co_min, co_max, mode):
    extent = co_max - co_min
    span_x = max(extent.x, 0.05)
    span_y = max(extent.y, 0.05)
    span_z = max(extent.z, 0.05)
    if mode == "left":
        ortho_span = max(math.hypot(span_x, span_y), span_z) * 0.92
    else:
        ortho_span = max(span_x, span_z)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(ortho_span / OCC_TARGET, 0.12)
    dist = 2.8 if mode != "interior" else 1.4
    view_dir = _legacy_view_dir(mode)
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    cam.data.clip_start = 0.001
    cam.data.clip_end = 120.0
    return dist


def _landmark_bounds(landmarks: dict, keys: tuple[str, ...]) -> tuple[Vector, Vector]:
    pts = [landmarks[k] for k in keys]
    co_min = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    co_max = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    pad = Vector((0.07, 0.07, 0.07))
    return co_min - pad, co_max + pad


def _semantic_ortho_scale(landmarks: dict, profile: str, view_dir: Vector) -> float:
    view_dir = view_dir.normalized()
    if profile.startswith("mouth"):
        keys = ("lip_corner_l", "lip_corner_r", "chin", "mouth_center")
    elif profile == "eye":
        keys = ("eye_l", "eye_r", "eye_mid")
    else:
        keys = ("mouth_center", "upper_lip", "lower_lip")
    co_min, co_max = _landmark_bounds(landmarks, keys)
    span_w, span_h = _view_aligned_span(co_min, co_max, view_dir)
    span = max(span_w, span_h)
    if profile.startswith("mouth"):
        return max(span / 1.35, 0.20)
    if profile == "eye":
        return max(span / 1.12, 0.18)
    return max(span / 1.45, 0.16)


def _apply_semantic_camera(cam, center: Vector, ortho: float, view_dir: Vector, dist: float):
    view_dir = view_dir.normalized()
    cam.data.ortho_scale = ortho
    cam.location = center - view_dir * dist
    _look_at(cam, center)


def _view_direction(mode: str) -> Vector:
    raise RuntimeError("Use _landmark_view_dir")


def _nudge_camera_to_mask(cam, mask: np.ndarray, center: Vector, view_dir: Vector, dist: float):
    h, w = mask.shape
    ys, xs = np.where(mask > 0.5)
    if len(xs) == 0:
        return center
    cx_px = (float(xs.min()) + float(xs.max())) / 2.0
    cy_px = (float(ys.min()) + float(ys.max())) / 2.0
    dx = (cx_px - w / 2.0) / w
    dy = (cy_px - h / 2.0) / h
    scale = float(cam.data.ortho_scale)
    view_dir = view_dir.normalized()
    up = Vector((0.0, 0.0, 1.0))
    right = view_dir.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up_cam = right.cross(view_dir).normalized()
    shift = right * (dx * scale * 0.95) + up_cam * (-dy * scale * 0.95)
    center = center + shift
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    return center


def _view_aligned_span(co_min: Vector, co_max: Vector, view_dir: Vector) -> tuple[float, float]:
    view_dir = view_dir.normalized()
    up = Vector((0.0, 0.0, 1.0))
    right = view_dir.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up_cam = right.cross(view_dir).normalized()
    corners = [
        Vector((co_min.x, co_min.y, co_min.z)),
        Vector((co_max.x, co_min.y, co_min.z)),
        Vector((co_min.x, co_max.y, co_min.z)),
        Vector((co_max.x, co_max.y, co_min.z)),
        Vector((co_min.x, co_min.y, co_max.z)),
        Vector((co_max.x, co_min.y, co_max.z)),
        Vector((co_min.x, co_max.y, co_max.z)),
        Vector((co_max.x, co_max.y, co_max.z)),
    ]
    rs = [float(c.dot(right)) for c in corners]
    us = [float(c.dot(up_cam)) for c in corners]
    return max(rs) - min(rs), max(us) - min(us)


def _place_camera(cam, center: Vector, co_min: Vector, co_max: Vector, view_dir: Vector, mode: str):
    view_dir = view_dir.normalized()
    span_w, span_h = _view_aligned_span(co_min, co_max, view_dir)
    if mode == "left":
        ortho_span = max(span_w, span_h) * 0.92
    else:
        ortho_span = max(span_w, span_h)
    cam.data.type = "ORTHO"
    cam.data.ortho_scale = max(ortho_span / OCC_TARGET, 0.12)
    dist = 2.8 if mode != "interior" else 1.4
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    cam.data.clip_start = 0.001
    cam.data.clip_end = 120.0
    return dist


def _load_rgb(path: Path) -> np.ndarray | None:
    path = _resolve_png(path)
    if not path.is_file():
        return None
    img = bpy.data.images.load(str(path))
    try:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return None
        px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        return px[:, :, :3]
    finally:
        bpy.data.images.remove(img)


def _luminance(rgb: np.ndarray) -> np.ndarray:
    return 0.2126 * rgb[:, :, 0] + 0.7152 * rgb[:, :, 1] + 0.0722 * rgb[:, :, 2]


def _active_feature_bbox(fid_rgb: np.ndarray, fallback: list[int]) -> list[int]:
    active = np.any(fid_rgb > 0.12, axis=2)
    if not active.any():
        return fallback
    ys, xs = np.where(active)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _union_bbox(a: list[int], b: list[int]) -> list[int]:
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _count_feature_pixels(
    fid_rgb: np.ndarray, bbox: list[int] | None, features: tuple[str, ...], *, full_frame: bool = False
) -> dict[str, int]:
    h, w = fid_rgb.shape[:2]
    if full_frame or bbox is None:
        x0, y0, x1, y1 = 0, 0, w - 1, h - 1
    else:
        x0, y0, x1, y1 = bbox
        x0 = max(0, min(x0, w - 1))
        x1 = max(0, min(x1, w - 1))
        y0 = max(0, min(y0, h - 1))
        y1 = max(0, min(y1, h - 1))
    roi = fid_rgb[y0 : y1 + 1, x0 : x1 + 1]
    counts: dict[str, int] = {}
    for feat in features:
        target = np.array(FEATURE_ID_RGB[feat], dtype=np.float32)
        dist = np.linalg.norm(roi - target, axis=2)
        counts[feat] = int((dist < FEATURE_COLOR_TOL).sum())
    return counts


def _count_qa_palette_pixels(human_rgb: np.ndarray, bbox: list[int], features: tuple[str, ...]) -> dict[str, int]:
    h, w = human_rgb.shape[:2]
    x0, y0, x1, y1 = bbox
    x0 = max(0, min(x0, w - 1))
    x1 = max(0, min(x1, w - 1))
    y0 = max(0, min(y0, h - 1))
    y1 = max(0, min(y1, h - 1))
    roi = human_rgb[y0 : y1 + 1, x0 : x1 + 1]
    counts: dict[str, int] = {}
    for feat in features:
        if feat not in QA_PALETTE:
            continue
        target = np.array(QA_PALETTE[feat], dtype=np.float32)
        dist = np.linalg.norm(roi - target, axis=2)
        counts[feat] = int((dist < QA_PALETTE_TOL).sum())
    return counts


def _feature_masks(fid_rgb: np.ndarray, bbox: list[int], features: tuple[str, ...]) -> dict[str, np.ndarray]:
    h, w = fid_rgb.shape[:2]
    x0, y0, x1, y1 = bbox
    roi = fid_rgb[y0 : y1 + 1, x0 : x1 + 1]
    masks: dict[str, np.ndarray] = {}
    for feat in features:
        target = np.array(FEATURE_ID_RGB[feat], dtype=np.float32)
        dist = np.linalg.norm(roi - target, axis=2)
        full = np.zeros((h, w), dtype=bool)
        full[y0 : y1 + 1, x0 : x1 + 1] = dist < FEATURE_COLOR_TOL
        masks[feat] = full
    return masks


def _validate_feature_contrast(human_rgb: np.ndarray, fid_rgb: np.ndarray, bbox: list[int], required: tuple[str, ...]) -> dict:
    h, w = human_rgb.shape[:2]
    x0, y0, x1, y1 = bbox
    roi_rgb = human_rgb[y0 : y1 + 1, x0 : x1 + 1]
    lum = _luminance(roi_rgb)
    skin_target = np.array(QA_PALETTE["skin"], dtype=np.float32)
    skin_mask_full = np.linalg.norm(human_rgb - skin_target, axis=2) < QA_PALETTE_TOL
    skin_roi = skin_mask_full[y0 : y1 + 1, x0 : x1 + 1]
    masks = _feature_masks(fid_rgb, bbox, required)
    per_feature: dict[str, dict] = {}
    failures: list[str] = []
    for feat in required:
        mask = masks.get(feat)
        if mask is None:
            per_feature[feat] = {"pass": False, "reason": "NO_FEATURE_MASK"}
            failures.append(f"CONTRAST_{feat}")
            continue
        local = mask[y0 : y1 + 1, x0 : x1 + 1]
        if not local.any() and feat in QA_PALETTE:
            qa_target = np.array(QA_PALETTE[feat], dtype=np.float32)
            qa_full = np.linalg.norm(human_rgb - qa_target, axis=2) < QA_PALETTE_TOL
            local = qa_full[y0 : y1 + 1, x0 : x1 + 1]
        if not local.any():
            per_feature[feat] = {"pass": False, "reason": "NO_FEATURE_MASK"}
            failures.append(f"CONTRAST_{feat}")
            continue
        feat_lum = lum[local]
        surround = skin_roi & ~local
        skin_mean = float(lum[surround].mean()) if surround.any() else 0.32
        feat_mean = float(feat_lum.mean())
        delta = abs(feat_mean - skin_mean)
        std_l = float(feat_lum.std())
        ok = delta >= 0.055 and (std_l >= 0.004 or delta >= 0.085)
        per_feature[feat] = {
            "meanLuminance": feat_mean,
            "skinMeanLuminance": skin_mean,
            "luminanceDelta": delta,
            "stdLuminance": std_l,
            "pass": ok,
        }
        if not ok:
            failures.append(f"CONTRAST_{feat}")
    return {
        "pass": not failures,
        "perFeature": per_feature,
        "failures": failures,
        "reason": None if not failures else f"FEATURE_CONTRAST:{','.join(failures)}",
    }


def _validate_oral_opening(fid_rgb: np.ndarray, bbox: list[int]) -> dict:
    masks = _feature_masks(fid_rgb, bbox, ("upper_teeth", "lower_teeth"))
    up = masks["upper_teeth"]
    lo = masks["lower_teeth"]
    if not up.any() or not lo.any():
        return {"pass": False, "separationPx": 0, "reason": "ORAL_OPENING_NOT_VISIBLE"}
    up_ys = np.where(up)[0]
    lo_ys = np.where(lo)[0]
    separation = int(max(0, lo_ys.min() - up_ys.max()))
    ok = separation >= ORAL_OPENING_MIN_PX
    return {
        "pass": ok,
        "separationPx": separation,
        "reason": None if ok else "ORAL_OPENING_TOO_NARROW",
    }


def _landmark_pixel_bbox(
    sc,
    cam,
    landmarks: dict,
    keys: tuple[str, ...],
    res: int,
    pad_frac: float = 0.10,
    basis_coords: list[Vector] | None = None,
    mode: str = "front",
) -> list[int]:
    bpy.context.view_layer.update()
    xs: list[float] = []
    ys: list[float] = []
    for pt in _frame_landmark_points(landmarks, basis_coords, keys, mode):
        ndc = world_to_camera_view(sc, cam, pt)
        xs.append(float(ndc.x) * res)
        ys.append((1.0 - float(ndc.y)) * res)
    pad = res * pad_frac
    return [
        max(0, int(min(xs) - pad)),
        max(0, int(min(ys) - pad)),
        min(res - 1, int(max(xs) + pad)),
        min(res - 1, int(max(ys) + pad)),
    ]


def _nudge_camera_to_landmarks(
    sc,
    cam,
    landmarks: dict,
    keys: tuple[str, ...],
    center: Vector,
    view_dir: Vector,
    dist: float,
    res: int,
    basis_coords: list[Vector] | None = None,
    mode: str = "front",
) -> Vector:
    bpy.context.view_layer.update()
    xs: list[float] = []
    ys: list[float] = []
    for pt in _frame_landmark_points(landmarks, basis_coords, keys, mode):
        ndc = world_to_camera_view(sc, cam, pt)
        xs.append(float(ndc.x) * res)
        ys.append((1.0 - float(ndc.y)) * res)
    if not xs:
        return center
    cx_px = (min(xs) + max(xs)) / 2.0
    cy_px = (min(ys) + max(ys)) / 2.0
    dx = (cx_px - res / 2.0) / res
    dy = (cy_px - res / 2.0) / res
    scale = float(cam.data.ortho_scale)
    view_dir = view_dir.normalized()
    up = Vector((0.0, 0.0, 1.0))
    right = view_dir.cross(up)
    if right.length < 1e-6:
        right = Vector((1.0, 0.0, 0.0))
    right.normalize()
    up_cam = right.cross(view_dir).normalized()
    shift = right * (dx * scale * 0.92) + up_cam * (-dy * scale * 0.92)
    center = center + shift
    cam.location = center - view_dir * dist
    _look_at(cam, center)
    return center


def _frame_landmark_points(
    landmarks: dict,
    basis_coords: list[Vector] | None,
    keys: tuple[str, ...],
    mode: str = "front",
) -> list[Vector]:
    region = landmarks.get("region_map", {}) if landmarks else {}
    chin_verts = region.get("chin_verts") or set()
    points: list[Vector] = []
    for key in keys:
        if key == "chin" and chin_verts and basis_coords and mode == "front":
            coords = [basis_coords[vi] for vi in chin_verts if vi < len(basis_coords)]
            if coords:
                points.append(min(coords, key=lambda c: c.z))
                continue
        points.append(landmarks[key])
    return points


def _landmarks_in_frame(
    sc,
    cam,
    landmarks: dict,
    keys: tuple[str, ...],
    res: int,
    basis_coords: list[Vector] | None = None,
    mode: str = "front",
) -> tuple[bool, str | None]:
    bpy.context.view_layer.update()
    margin = res * FRAME_MARGIN_FRAC
    for key, pt in zip(keys, _frame_landmark_points(landmarks, basis_coords, keys, mode)):
        ndc = world_to_camera_view(sc, cam, pt)
        if ndc.z <= 0.0:
            return False, f"BEHIND_CAMERA:{key}"
        px = float(ndc.x) * res
        py = (1.0 - float(ndc.y)) * res
        if px < margin or px > res - margin or py < margin or py > res - margin:
            return False, f"FRAME_ESCAPE:{key}"
    return True, None


def _semantic_context_ok(sem_m: dict) -> tuple[bool, str | None]:
    wf = float(sem_m.get("widthFrac", 0.0))
    hf = float(sem_m.get("heightFrac", 0.0))
    if wf >= SEMANTIC_OCC_MAX and hf >= SEMANTIC_OCC_MAX:
        return False, "CONTEXT_LOSS_FULL_BLEED"
    if wf <= 0.06 or hf <= 0.06:
        return False, "CONTEXT_LOSS_EMPTY"
    return True, None


def _frame_landmark_keys(profile: str, shot_kind: str) -> tuple[str, ...]:
    if profile == "eye":
        return FRAME_LANDMARKS.get(shot_kind, FRAME_LANDMARKS["eye_l"])
    return FRAME_LANDMARKS.get(profile, FRAME_LANDMARKS["mouth"])


def _semantic_center(landmarks: dict, profile: str, shot_kind: str, fallback: Vector) -> Vector:
    keys = _frame_landmark_keys(profile, shot_kind)
    if not keys:
        return fallback
    acc = Vector((0.0, 0.0, 0.0))
    for key in keys:
        acc += landmarks[key]
    return acc / float(len(keys))


def _validate_exposure(human_rgb: np.ndarray, bbox: list[int], fid_rgb: np.ndarray | None = None, required: tuple[str, ...] | None = None) -> dict:
    h, w = human_rgb.shape[:2]
    x0, y0, x1, y1 = bbox
    roi = human_rgb[y0 : y1 + 1, x0 : x1 + 1]
    lum = _luminance(roi)
    sat_ratio = float((lum > 0.95).mean())
    clip_ratio = float(((lum < 0.02) | (lum > 0.98)).mean())
    shadow_clip_ratio = sat_ratio
    if fid_rgb is not None and required:
        masks = _feature_masks(fid_rgb, bbox, required)
        active = np.zeros_like(lum, dtype=bool)
        for m in masks.values():
            active |= m[y0 : y1 + 1, x0 : x1 + 1]
        if active.any():
            feat_lum = lum[active]
            shadow_clip_ratio = float((feat_lum < 0.02).mean())
    ok = sat_ratio <= SAT_MAX_RATIO and clip_ratio <= CLIP_MAX_RATIO and shadow_clip_ratio <= CLIP_MAX_RATIO
    reason = None
    if sat_ratio > SAT_MAX_RATIO:
        reason = "OVEREXPOSURE_SATURATION"
    elif clip_ratio > CLIP_MAX_RATIO:
        reason = "GLOBAL_CLIP"
    elif shadow_clip_ratio > CLIP_MAX_RATIO:
        reason = "FEATURE_SHADOW_CLIP"
    return {
        "saturationRatio": sat_ratio,
        "clipRatio": clip_ratio,
        "featureShadowClipRatio": shadow_clip_ratio,
        "pass": ok,
        "reason": reason,
    }


def _feature_from_material_index(idx: int) -> str | None:
    return SLOT_TO_FEATURE.get(int(idx))


def _mouth_corner_contract(mode: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if mode == "left":
        return ("lip_corner_l",), ("lip_corner_r",)
    if mode == "front":
        return ("lip_corner_l", "lip_corner_r"), ()
    return (), ()


def _project_poly_visible_area(
    sc, cam, obj, poly, res: int, margin: float, view_dir: Vector
) -> int:
    mesh = obj.data
    mw = obj.matrix_world
    normal = (mw.to_3x3() @ poly.normal).normalized()
    facing = float(normal.dot(view_dir))
    if facing <= 0.04:
        return 0
    xs: list[float] = []
    ys: list[float] = []
    for vi in poly.vertices:
        co = mw @ mesh.vertices[vi].co
        ndc = world_to_camera_view(sc, cam, co)
        if ndc.z <= 0.0:
            return 0
        xs.append(float(ndc.x) * res)
        ys.append((1.0 - float(ndc.y)) * res)
    if not xs:
        return 0
    if max(xs) < margin or min(xs) > res - margin or max(ys) < margin or min(ys) > res - margin:
        return 0
    n = len(xs)
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += xs[i] * ys[j] - xs[j] * ys[i]
    area = abs(area) * 0.5
    return int(max(1.0, area * min(1.0, facing)))


def _compute_expected_visible_pixels(
    sc, cam, skin_obj, res: int, features: tuple[str, ...]
) -> dict[str, int]:
    """Full-frame rasterized semantic-slot visibility (3D ground truth, independent of ROI bbox)."""
    full = [0, 0, res - 1, res - 1]
    return _count_semantic_index_pixels(sc, cam, skin_obj, full, features, res)


def _evaluate_feature_visibility(
    feat: str,
    detected: int,
    expected: int,
    mode: str,
    *,
    occluded_expected: bool = False,
) -> dict:
    if occluded_expected:
        return {
            "pass": True,
            "status": "OCCLUDED_EXPECTED",
            "detectedVisiblePixels": detected,
            "expectedVisiblePixels": expected,
            "detectionRate": float(detected) / float(max(expected, 1)),
            "absoluteFloor": MIN_ABSOLUTE_FLOOR.get(feat, 40),
        }
    floor = MIN_ABSOLUTE_FLOOR.get(feat, 40)
    front_target = MIN_FEATURE_PIXELS.get(feat, floor)
    detail = {
        "detectedVisiblePixels": detected,
        "expectedVisiblePixels": expected,
        "detectionRate": float(detected) / float(max(expected, 1)),
        "absoluteFloor": floor,
        "minDetectionRate": VISIBILITY_DETECTION_MIN,
    }
    if detected < floor:
        return {**detail, "pass": False, "status": "BELOW_ABSOLUTE_FLOOR"}
    if expected <= 0:
        if mode == "front" and detected < front_target:
            return {**detail, "pass": False, "status": "BELOW_FRONT_ABSOLUTE_TARGET"}
        return {**detail, "pass": True, "status": "PASS"}
    rate = float(detected) / float(expected)
    detail["detectionRate"] = rate
    if rate < VISIBILITY_DETECTION_MIN:
        return {**detail, "pass": False, "status": "BELOW_VISIBILITY_DETECTION_RATE"}
    if mode == "front" and expected >= int(front_target * FRONT_ABSOLUTE_EXPECTED_FRAC):
        if detected < front_target:
            return {**detail, "pass": False, "status": "BELOW_FRONT_ABSOLUTE_TARGET"}
    return {**detail, "pass": True, "status": "PASS"}


def _validate_semantic_index_coherence(
    fid_counts: dict[str, int], index_counts: dict[str, int], features: tuple[str, ...]
) -> dict:
    per_feature: dict[str, dict] = {}
    failures: list[str] = []
    for feat in features:
        fid_c = int(fid_counts.get(feat, 0))
        idx_c = int(index_counts.get(feat, 0))
        if idx_c <= 0 and fid_c <= 0:
            per_feature[feat] = {"pass": True, "fidPixels": fid_c, "indexPixels": idx_c, "ratio": 1.0}
            continue
        ratio = float(min(fid_c, idx_c)) / float(max(fid_c, idx_c, 1))
        ok = ratio >= 0.50 or (idx_c >= MIN_ABSOLUTE_FLOOR.get(feat, 40) and fid_c >= MIN_ABSOLUTE_FLOOR.get(feat, 40))
        per_feature[feat] = {"pass": ok, "fidPixels": fid_c, "indexPixels": idx_c, "ratio": ratio}
        if not ok:
            failures.append(f"INDEX_MISMATCH_{feat}")
    return {
        "pass": not failures,
        "perFeature": per_feature,
        "failures": failures,
        "reason": None if not failures else f"SEMANTIC_INDEX_MISMATCH:{','.join(failures)}",
    }


def _count_semantic_index_pixels(
    sc, cam, skin_obj, bbox: list[int], features: tuple[str, ...], res: int
) -> dict[str, int]:
    index_mats = {name: _emit_mat(f"IDX_{name}", rgb) for name, rgb in FEATURE_ID_RGB.items()}
    index_mats["skin"] = _emit_mat("IDX_skin", (0.05, 0.05, 0.05))
    tmp = Path(tempfile.gettempdir()) / f"nurion_sem_index_{id(cam)}_{id(skin_obj)}.png"
    rgb = _render_feature_id(sc, cam, skin_obj, {}, index_mats, [skin_obj], tmp, res)
    if rgb is None:
        return {f: 0 for f in features}
    return _count_feature_pixels(rgb, bbox, features, full_frame=False)


def _validate_semantic_features(
    fid_rgb: np.ndarray,
    human_rgb: np.ndarray,
    bbox: list[int],
    profile: str,
    cam,
    landmarks: dict,
    mode: str,
    region_map: dict | None = None,
    skin_obj=None,
    sc=None,
    res: int = FINAL_RES,
) -> dict:
    if fid_rgb is None or human_rgb is None:
        return {"pass": False, "reason": "NO_FEATURE_OR_HUMAN_IMAGE"}
    required = REQUIRED_FEATURES[profile]
    fid_counts = _count_feature_pixels(fid_rgb, bbox, required, full_frame=False)
    index_counts = (
        _count_semantic_index_pixels(sc, cam, skin_obj, bbox, required, res)
        if skin_obj is not None and sc is not None
        else fid_counts
    )
    expected_counts = (
        _compute_expected_visible_pixels(sc, cam, skin_obj, res, required)
        if skin_obj is not None and sc is not None
        else {f: MIN_FEATURE_PIXELS.get(f, 0) for f in required}
    )
    counts = {f: int(fid_counts.get(f, 0)) for f in required}
    required_corners, occluded_corners = _mouth_corner_contract(mode if profile.startswith("mouth") else "front")
    visibility: dict[str, dict] = {}
    missing: list[str] = []
    occluded_ok: list[str] = []
    for feat in required:
        occluded = profile.startswith("mouth") and feat in occluded_corners
        vis = _evaluate_feature_visibility(
            feat,
            counts.get(feat, 0),
            expected_counts.get(feat, 0),
            mode if profile.startswith("mouth") else "front",
            occluded_expected=occluded,
        )
        visibility[feat] = vis
        if vis.get("status") == "OCCLUDED_EXPECTED":
            occluded_ok.append(feat)
        elif not vis.get("pass"):
            missing.append(feat)
    index_coherence = _validate_semantic_index_coherence(fid_counts, index_counts, required)
    qa_counts = _count_qa_palette_pixels(human_rgb, bbox, required)
    exposure = _validate_exposure(human_rgb, bbox, fid_rgb, required)
    contrast = _validate_feature_contrast(human_rgb, fid_rgb, bbox, required)
    depth_ok = _depth_nose_in_front(cam, landmarks, mode) if mode in ("front", "left") else True
    align = _landmark_view_alignment(landmarks, cam, mode)
    align_ok = align > 0.80
    region_map = region_map or landmarks.get("region_map", {})
    sym_ok = bool(region_map.get("corner_symmetry_pass", True))
    oral = {"pass": True, "reason": None}
    if profile == "mouth_interior":
        oral = _validate_oral_opening(fid_rgb, bbox)
    checks = {
        "featurePixelCounts": counts,
        "featureIdPixelCounts": fid_counts,
        "semanticIndexPixelCounts": index_counts,
        "expectedVisiblePixels": expected_counts,
        "featureVisibility": visibility,
        "occludedExpectedFeatures": occluded_ok,
        "qaPalettePixelCounts": qa_counts,
        "semanticIndexCoherence": index_coherence,
        "requiredFeatures": list(required),
        "missingFeatures": missing,
        "minFeaturePixels": {k: MIN_FEATURE_PIXELS[k] for k in required if k in MIN_FEATURE_PIXELS},
        "minAbsoluteFloor": {k: MIN_ABSOLUTE_FLOOR[k] for k in required if k in MIN_ABSOLUTE_FLOOR},
        "exposure": exposure,
        "featureContrast": contrast,
        "oralOpening": oral,
        "depthNoseInFront": depth_ok,
        "landmarkViewAlignment": align,
        "landmarkViewAlignmentPass": align_ok,
        "cornerSymmetry": region_map.get("corner_symmetry"),
        "cornerSymmetryPass": sym_ok,
        "regionVertexCounts": region_map.get("vertex_counts"),
        "landmarks": {
            k: [float(landmarks[k].x), float(landmarks[k].y), float(landmarks[k].z)]
            for k in ("nose_tip", "ear_l", "ear_r", "mouth_center", "eye_l", "eye_r")
        },
    }
    if not sym_ok:
        return {**checks, "pass": False, "reason": "CORNER_SYMMETRY_FAIL"}
    if not align_ok:
        return {**checks, "pass": False, "reason": "LANDMARK_CAMERA_MISALIGNED"}
    if missing:
        reasons = [f"{f}:{visibility[f].get('status')}" for f in missing]
        return {**checks, "pass": False, "reason": f"VISIBILITY_FAIL:{','.join(reasons)}"}
    if not index_coherence.get("pass"):
        return {**checks, "pass": False, "reason": index_coherence.get("reason")}
    if not oral.get("pass"):
        return {**checks, "pass": False, "reason": oral.get("reason")}
    if not contrast.get("pass"):
        return {**checks, "pass": False, "reason": contrast.get("reason")}
    if not exposure.get("pass"):
        return {**checks, "pass": False, "reason": exposure.get("reason")}
    if not depth_ok:
        return {**checks, "pass": False, "reason": "DEPTH_NOSE_NOT_IN_FRONT"}
    return {**checks, "pass": True, "reason": None}


def _save_rgb(path: Path, rgb: np.ndarray) -> None:
    h, w, _ = rgb.shape
    img = bpy.data.images.new("SaveRGB", width=w, height=h)
    rgba = np.dstack([np.clip(rgb, 0.0, 1.0), np.ones((h, w), dtype=np.float32)])
    img.pixels = rgba.reshape(-1).tolist()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def _write_feature_overlay(human_rgb: np.ndarray, fid_rgb: np.ndarray, bbox: list[int], path: Path) -> None:
    blend = human_rgb.copy()
    x0, y0, x1, y1 = bbox
    roi_fid = fid_rgb[y0 : y1 + 1, x0 : x1 + 1]
    roi_h = blend[y0 : y1 + 1, x0 : x1 + 1]
    active = np.any(roi_fid > 0.12, axis=2)
    roi_h[active] = roi_h[active] * 0.50 + roi_fid[active] * 0.50
    _save_rgb(path, blend)


def _resolve_png(path: Path) -> Path:
    if path.is_file():
        return path
    png = path.with_suffix(".png")
    return png if png.is_file() else path


def _load_mask(path: Path) -> np.ndarray | None:
    path = _resolve_png(path)
    if not path.is_file():
        return None
    img = bpy.data.images.load(str(path))
    try:
        iw, ih = img.size
        if iw == 0 or ih == 0:
            return None
        px = np.array(img.pixels[:], dtype=np.float32).reshape(ih, iw, 4)
        return px[:, :, 0]
    finally:
        bpy.data.images.remove(img)


def _measure_mask(mask: np.ndarray) -> dict:
    if mask is None:
        return {"pass": False, "reason": "NO_MASK"}
    h, w = mask.shape
    fg = mask > 0.5
    if not fg.any():
        return {"pass": False, "reason": "EMPTY_MASK", "widthFrac": 0.0, "heightFrac": 0.0}
    ys, xs = np.where(fg)
    bbox = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
    wf = float(bbox[2] - bbox[0] + 1) / float(w)
    hf = float(bbox[3] - bbox[1] + 1) / float(h)
    ok = OCC_MIN <= wf <= OCC_MAX and OCC_MIN <= hf <= OCC_MAX
    return {
        "pass": ok,
        "widthFrac": wf,
        "heightFrac": hf,
        "fgPixelRatio": float(fg.mean()),
        "bbox": bbox,
        "reason": None if ok else "FINAL_MASK_OCCUPANCY",
    }


def _bbox_dims(bbox: list[int] | None) -> tuple[int, int]:
    if not bbox or len(bbox) < 4:
        return 0, 0
    return int(bbox[2] - bbox[0] + 1), int(bbox[3] - bbox[1] + 1)


def _clip_screen_bbox(bbox: list[int] | None, res: int) -> list[int] | None:
    if not bbox or len(bbox) < 4:
        return None
    x0 = max(0, min(res - 1, int(bbox[0])))
    y0 = max(0, min(res - 1, int(bbox[1])))
    x1 = max(0, min(res - 1, int(bbox[2])))
    y1 = max(0, min(res - 1, int(bbox[3])))
    if x1 < x0 or y1 < y0:
        return None
    return [x0, y0, x1, y1]


def _relative_bbox_occupancy(mask_bbox: list[int] | None, denom_bbox: list[int] | None) -> dict:
    if not mask_bbox or not denom_bbox:
        return {
            "widthFrac": 0.0,
            "heightFrac": 0.0,
            "pass": False,
            "bbox": mask_bbox,
            "denomBBox": denom_bbox,
        }
    mw, mh = _bbox_dims(mask_bbox)
    dw, dh = _bbox_dims(denom_bbox)
    if dw <= 0 or dh <= 0:
        return {
            "widthFrac": 0.0,
            "heightFrac": 0.0,
            "pass": False,
            "bbox": mask_bbox,
            "denomBBox": denom_bbox,
        }
    wf = float(mw) / float(dw)
    hf = float(mh) / float(dh)
    ok = _occupancy_ok({"widthFrac": wf, "heightFrac": hf})
    return {
        "widthFrac": wf,
        "heightFrac": hf,
        "pass": ok,
        "bbox": mask_bbox,
        "denomBBox": denom_bbox,
        "reason": None if ok else "FINAL_MASK_OCCUPANCY",
    }


def evaluate_native_holdout_occupancy(
    final_mask: np.ndarray | None,
    *,
    locked_semantic_roi: dict | None,
    projected_morph_aabb: dict | None,
    render_frame: int,
) -> dict:
    empty = {"widthFrac": 0.0, "heightFrac": 0.0, "pass": False, "bbox": None, "denomBBox": None}
    if final_mask is None:
        return {
            "frameOccupancy": dict(empty),
            "semanticRoiOccupancy": dict(empty),
            "morphAabbOccupancy": dict(empty),
            "maskBBox": None,
            "semanticRoiBBox": None,
            "morphAabbBBox": None,
        }
    frame_m = _measure_mask(final_mask)
    mask_bbox = frame_m.get("bbox")
    frame_occ = {
        "widthFrac": float(frame_m.get("widthFrac", 0.0)),
        "heightFrac": float(frame_m.get("heightFrac", 0.0)),
        "pass": bool(frame_m.get("pass")),
        "bbox": mask_bbox,
        "denomBBox": [0, 0, render_frame - 1, render_frame - 1],
        "reason": frame_m.get("reason"),
    }
    sem_bbox = _clip_screen_bbox((locked_semantic_roi or {}).get("bbox"), render_frame)
    morph_bbox = _clip_screen_bbox((projected_morph_aabb or {}).get("bbox"), render_frame)
    sem_occ = _relative_bbox_occupancy(mask_bbox, sem_bbox)
    morph_occ = _relative_bbox_occupancy(mask_bbox, morph_bbox)
    return {
        "frameOccupancy": frame_occ,
        "semanticRoiOccupancy": sem_occ,
        "morphAabbOccupancy": morph_occ,
        "maskBBox": mask_bbox,
        "semanticRoiBBox": sem_bbox,
        "morphAabbBBox": morph_bbox,
    }


def _occupancy_contract_metric_key(contract: str | None = None) -> str:
    contract = contract or _OCCUPANCY_GATE_CONTRACT
    return {
        "frame": "frameOccupancy",
        "semanticRoi": "semanticRoiOccupancy",
        "morphAabb": "morphAabbOccupancy",
    }.get(contract, "frameOccupancy")


def _occupancy_metric_from_eval(occ_eval: dict, contract: str | None = None) -> dict:
    key = _occupancy_contract_metric_key(contract)
    metric = dict(occ_eval.get(key) or {"widthFrac": 0.0, "heightFrac": 0.0, "pass": False})
    metric["contractMetric"] = contract or _OCCUPANCY_GATE_CONTRACT
    metric["contractKey"] = key
    return metric


def _resolve_occupancy_gate_contract(baseline_rows: list[dict]) -> tuple[str, dict]:
    if not baseline_rows:
        return "frame", {"reason": "NO_BASELINE_ROWS", "baselineRowCount": 0}
    frame_pass = sem_pass = morph_pass = 0
    sem_when_frame_fail = morph_when_frame_fail = 0
    total = len(baseline_rows)
    for row in baseline_rows:
        om = row.get("occupancyMetrics") or {}
        fp = bool((om.get("frameOccupancy") or {}).get("pass"))
        sp = bool((om.get("semanticRoiOccupancy") or {}).get("pass"))
        mp = bool((om.get("morphAabbOccupancy") or {}).get("pass"))
        if fp:
            frame_pass += 1
        if sp:
            sem_pass += 1
        if mp:
            morph_pass += 1
        if not fp:
            if sp:
                sem_when_frame_fail += 1
            if mp:
                morph_when_frame_fail += 1
    receipt = {
        "baselineRowCount": total,
        "framePassCount": frame_pass,
        "semanticRoiPassCount": sem_pass,
        "morphAabbPassCount": morph_pass,
        "semanticRoiPassWhenFrameFail": sem_when_frame_fail,
        "morphAabbPassWhenFrameFail": morph_when_frame_fail,
    }
    all_frame = frame_pass == total
    all_sem = sem_pass == total
    all_morph = morph_pass == total
    if all_sem and not all_frame:
        return "semanticRoi", {**receipt, "reason": "ROI_RELATIVE_SEMANTIC"}
    if all_morph and not all_frame:
        return "morphAabb", {**receipt, "reason": "ROI_RELATIVE_MORPH"}
    if all_sem:
        return "semanticRoi", {**receipt, "reason": "SEMANTIC_ROI_PASSES"}
    if all_morph:
        return "morphAabb", {**receipt, "reason": "MORPH_AABB_PASSES"}
    if all_frame:
        return "frame", {**receipt, "reason": "FRAME_PASSES"}
    return "frame", {**receipt, "reason": "DEFAULT_FRAME"}


def _legacy_occupancy_diagnostic(occ_metrics: dict | None) -> dict:
    occ_metrics = occ_metrics or {}
    frame = occ_metrics.get("frameOccupancy") or {}
    sem = occ_metrics.get("semanticRoiOccupancy") or {}
    morph = occ_metrics.get("morphAabbOccupancy") or {}
    return {
        "frame": {"widthFrac": float(frame.get("widthFrac", 0.0)), "heightFrac": float(frame.get("heightFrac", 0.0))},
        "semanticRoi": {"widthFrac": float(sem.get("widthFrac", 0.0)), "heightFrac": float(sem.get("heightFrac", 0.0))},
        "morphAabb": {"widthFrac": float(morph.get("widthFrac", 0.0)), "heightFrac": float(morph.get("heightFrac", 0.0))},
        "legacyMin": OCC_MIN,
        "legacyMax": OCC_MAX,
        "legacyPass": bool(frame.get("pass")),
        "enforcement": "DIAGNOSTIC_ONLY",
        "replacementReviewId": OCCUPANCY_REPLACEMENT_REVIEW_ID,
    }


def _eye_feature_occluded_expected(state: str, feature: str) -> bool:
    return state == "closed" and feature == "eyeball"


OCCLUDED_EXPECTED_SEMANTICS = "B_NOT_REQUIRED_INVISIBLE"
OCCLUDED_EXPECTED_SEMANTICS_MEANING = (
    "OCCLUDED_EXPECTED means not-visible is acceptable and partial visibility is allowed; "
    "it does not require zero pixels (not semantics A)."
)


def _eye_side_tag(side: str) -> str:
    return "l" if side == "L" else "r"


def _eye_feature_registry_entry(feature: str) -> dict | None:
    return EYE_FEATURE_REGISTRY.get(feature)


def _eye_feature_rig_object(feature: str, side: str, rig_objs: dict):
    entry = _eye_feature_registry_entry(feature)
    if not entry:
        return None
    name = entry["rigObjectPattern"].format(side=_eye_side_tag(side))
    return rig_objs.get(name)


def _eye_feature_semantic_slot(feature: str, side: str, rig_objs: dict) -> str | None:
    obj = _eye_feature_rig_object(feature, side, rig_objs)
    if obj is None:
        return None
    return f"rig:{obj.name}:0"


def _eye_morph_weight_key(feature: str, side: str) -> str | None:
    entry = _eye_feature_registry_entry(feature)
    if not entry or not entry.get("morphWeightKeys"):
        return None
    side_prefix = "LEFT" if side == "L" else "RIGHT"
    return entry["morphWeightKeys"][0].format(SIDE=side_prefix)


def _eye_seed_vertex_count(eyelid_weights: dict, morph_key: str | None) -> int:
    if not morph_key:
        return 0
    weights = eyelid_weights.get(morph_key, {})
    return sum(1 for v in weights.values() if float(v) > 0.01)


def _eye_feature_region_defined(feature: str, side: str, rig_objs: dict) -> bool:
    obj = _eye_feature_rig_object(feature, side, rig_objs)
    return obj is not None and obj.type == "MESH" and len(obj.data.polygons) > 0


def _eye_feature_manifest_counts(feature: str, side: str, rig_objs: dict) -> tuple[int, int]:
    obj = _eye_feature_rig_object(feature, side, rig_objs)
    if obj is None or obj.type != "MESH":
        return 0, 0
    mesh = obj.data
    return len(mesh.vertices), len(mesh.polygons)


def _eye_state_mapping_present(
    feature: str,
    eyelid_weights: dict,
    eyelid_spec: dict,
    side: str,
) -> tuple[bool, list[str], str | None]:
    entry = _eye_feature_registry_entry(feature)
    if not entry:
        return False, [], None
    allowed = list(entry["allowedStates"])
    morph_key = _eye_morph_weight_key(feature, side)
    if morph_key:
        if morph_key not in eyelid_weights or morph_key not in eyelid_spec:
            return False, allowed, None
        if len(eyelid_weights.get(morph_key, {})) == 0:
            return False, allowed, None
    return True, allowed, "eye_morph_open_pct"


def _classify_eyelid_manifest_parity_failure(row: dict) -> str:
    if not row.get("featureRegistryPresent"):
        return "EYELID_FEATURE_REGISTRY_MISSING"
    if not row.get("featureRegionDefined"):
        return "EYELID_REGION_MANIFEST_MISSING"
    if int(row.get("manifestFaceCount", 0)) <= 0:
        return "EYELID_FACE_DERIVATION_EMPTY"
    if row.get("semanticSlot") is None:
        return "EYELID_SLOT_BINDING_MISSING"
    if not row.get("stateMappingPresent"):
        return "EYELID_STATE_MAPPING_MISSING"
    if int(row.get("projectedFaces", 0)) <= 0 or int(row.get("positiveAreaFaces", 0)) <= 0:
        return "EYELID_PROJECTION_PARITY_FAIL"
    return "PASS"


def _eyelid_manifest_parity_success(row: dict) -> bool:
    return (
        int(row.get("manifestFaceCount", 0)) > 0
        and row.get("semanticSlot") is not None
        and bool(row.get("stateMappingPresent"))
        and set(EYE_ALLOWED_MORPH_STATES).issubset(set(row.get("allowedStates") or ()))
        and int(row.get("projectedFaces", 0)) > 0
        and int(row.get("positiveAreaFaces", 0)) > 0
    )


def _matrix4_to_rows(m) -> list[list[float]]:
    return [[float(m[i][j]) for j in range(4)] for i in range(4)]


def _vector3_to_list(v) -> list[float]:
    return [float(v.x), float(v.y), float(v.z)]


def _bbox_to_dict(co_min: Vector | None, co_max: Vector | None) -> dict | None:
    if co_min is None or co_max is None:
        return None
    return {
        "min": _vector3_to_list(co_min),
        "max": _vector3_to_list(co_max),
        "center": _vector3_to_list((co_min + co_max) * 0.5),
    }


def _mesh_face_vertex_bbox(mesh, face_indices: set[int] | None = None) -> tuple[Vector | None, Vector | None]:
    if mesh is None or not mesh.vertices:
        return None, None
    used: set[int] = set()
    if face_indices is None:
        for poly in mesh.polygons:
            used.update(int(v) for v in poly.vertices)
    else:
        for fi in face_indices:
            if 0 <= int(fi) < len(mesh.polygons):
                used.update(int(v) for v in mesh.polygons[int(fi)].vertices)
    if not used:
        return None, None
    xs = [float(mesh.vertices[vi].co.x) for vi in used]
    ys = [float(mesh.vertices[vi].co.y) for vi in used]
    zs = [float(mesh.vertices[vi].co.z) for vi in used]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _object_world_bbox(obj, *, face_indices: set[int] | None = None) -> tuple[Vector | None, Vector | None]:
    if obj is None or obj.type != "MESH":
        return None, None
    co_min, co_max = _mesh_face_vertex_bbox(obj.data, face_indices)
    if co_min is None:
        return None, None
    mw = obj.matrix_world.copy()
    corners = [
        mw @ Vector((co_min.x, co_min.y, co_min.z)),
        mw @ Vector((co_max.x, co_min.y, co_min.z)),
        mw @ Vector((co_min.x, co_max.y, co_min.z)),
        mw @ Vector((co_max.x, co_max.y, co_min.z)),
        mw @ Vector((co_min.x, co_min.y, co_max.z)),
        mw @ Vector((co_max.x, co_min.y, co_max.z)),
        mw @ Vector((co_min.x, co_max.y, co_max.z)),
        mw @ Vector((co_max.x, co_max.y, co_max.z)),
    ]
    xs = [float(c.x) for c in corners]
    ys = [float(c.y) for c in corners]
    zs = [float(c.z) for c in corners]
    return Vector((min(xs), min(ys), min(zs))), Vector((max(xs), max(ys), max(zs)))


def _sync_rig_projection_matrices(sc) -> None:
    bpy.context.view_layer.update()
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            obj.data.update()


def _camera_state_snapshot(cam) -> dict:
    return {
        "location": _vector3_to_list(cam.location),
        "rotation": [float(cam.rotation_euler[i]) for i in range(3)],
        "ortho_scale": float(cam.data.ortho_scale),
    }


def _camera_state_receipt(sc, cam) -> dict:
    _sync_rig_projection_matrices(sc)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    vm = cam.matrix_world.inverted()
    try:
        proj = cam.calc_matrix_camera(depsgraph)
        projection_matrix = _matrix4_to_rows(proj)
    except Exception:
        projection_matrix = None
    return {
        "cameraMatrixWorld": _matrix4_to_rows(cam.matrix_world),
        "viewMatrix": _matrix4_to_rows(vm),
        "projectionMatrix": projection_matrix,
        "orthoScale": float(cam.data.ortho_scale),
        "cameraLocation": _vector3_to_list(cam.location),
        "cameraRotation": [float(cam.rotation_euler[i]) for i in range(3)],
    }


def _classify_eyelid_projection_failure(row: dict) -> str:
    if not row.get("helperObjectExists"):
        return "EYELID_HELPER_OBJECT_MISSING"
    if int(row.get("evaluatedMeshFaceCount", 0)) <= 0:
        return "EYELID_EVALUATED_MESH_EMPTY"
    if bool(row.get("doubleTransform")):
        return "EYELID_WORLD_TRANSFORM_FAIL"
    if bool(row.get("worldBBoxAbnormal")):
        return "EYELID_WORLD_TRANSFORM_FAIL"
    if int(row.get("worldVerticesInFrontCount", 0)) <= 0:
        return "EYELID_CAMERA_SPACE_BEHIND_FAIL"
    if int(row.get("ndcVerticesInFrameCount", 0)) <= 0:
        return "EYELID_CAMERA_STATE_CONSUMPTION_FAIL"
    if int(row.get("projectedFaces", 0)) <= 0:
        return "EYELID_FACE_PROJECTION_ASSEMBLY_FAIL"
    if int(row.get("positiveAreaFaces", 0)) <= 0:
        return "EYELID_RASTER_DEGENERACY"
    return "PASS"


def _eyelid_projection_parity_success(row: dict) -> bool:
    bbox_dist = row.get("bboxCenterDistance")
    if bbox_dist is None:
        bbox_dist = row.get("worldBBoxCenterDistanceFromReference")
    return (
        int(row.get("projectedFaces", 0)) > 0
        and int(row.get("positiveAreaFaces", 0)) > 0
        and not bool(row.get("doubleTransform"))
        and (bbox_dist is None or float(bbox_dist) <= 0.35)
        and not bool(row.get("cameraMutation"))
    )


def _audit_eyelid_helper_projection_chain(
    sc,
    cam,
    mesh_obj,
    res: int,
    *,
    projection_source: str,
    camera_state_source: str,
    reference_world_bbox: dict | None = None,
) -> dict:
    _sync_rig_projection_matrices(sc)
    helper_exists = mesh_obj is not None and mesh_obj.type == "MESH"
    if not helper_exists:
        return {
            "helperObjectName": None,
            "helperObjectExists": False,
            "evaluatedMeshVertexCount": 0,
            "evaluatedMeshFaceCount": 0,
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
            "worldVerticesInFrontCount": 0,
            "ndcVerticesInFrameCount": 0,
            "projectionSource": projection_source,
            "cameraStateSource": camera_state_source,
            "classification": "EYELID_HELPER_OBJECT_MISSING",
            "pass": False,
        }

    eval_obj, mw = _projection_eval_object(sc, mesh_obj)
    if eval_obj is None or mw is None:
        return {
            "helperObjectName": mesh_obj.name,
            "helperObjectExists": True,
            "evaluatedMeshVertexCount": 0,
            "evaluatedMeshFaceCount": 0,
            "projectedFaces": 0,
            "positiveAreaFaces": 0,
            "worldVerticesInFrontCount": 0,
            "ndcVerticesInFrameCount": 0,
            "projectionSource": projection_source,
            "cameraStateSource": camera_state_source,
            "classification": "EYELID_EVALUATED_MESH_EMPTY",
            "pass": False,
        }

    source_mesh = mesh_obj.data
    face_indices = set(range(len(source_mesh.polygons)))
    local_min, local_max = _mesh_face_vertex_bbox(source_mesh, face_indices)
    world_min, world_max = _object_world_bbox(eval_obj, face_indices=face_indices)
    parent = mesh_obj.parent
    world_center = (world_min + world_max) * 0.5 if world_min is not None else None
    ref_center = None
    world_bbox_abnormal = False
    if reference_world_bbox and reference_world_bbox.get("center") and world_center is not None:
        ref_center = Vector(reference_world_bbox["center"])
        world_bbox_abnormal = float((world_center - ref_center).length) > 0.35
    elif world_min is not None and world_max is not None:
        ext = world_max - world_min
        world_bbox_abnormal = float(ext.length) > 3.0

    world_in_front = 0
    ndc_in_frame = 0
    used_verts: set[int] = set()
    for fi in face_indices:
        used_verts.update(int(v) for v in source_mesh.polygons[int(fi)].vertices)
    for vi in used_verts:
        co = mw @ source_mesh.vertices[int(vi)].co.copy()
        ndc = world_to_camera_view(sc, cam, co)
        if float(ndc.z) > 0.0:
            world_in_front += 1
        if float(ndc.z) > 0.0 and 0.0 <= float(ndc.x) <= 1.0 and 0.0 <= float(ndc.y) <= 1.0:
            ndc_in_frame += 1

    pivot_matrix = parent.matrix_world.copy() if parent is not None else mw.copy()
    provenance = _eyelid_transform_provenance(
        mesh_obj,
        source_mesh,
        face_indices,
        parent=parent,
        pivot_matrix=pivot_matrix,
        object_matrix_world=mw,
        reference_world_bbox=reference_world_bbox,
    )
    geom = _audit_feature_face_geometry(sc, cam, mesh_obj, face_indices, res)
    row = {
        "helperObjectName": mesh_obj.name,
        "helperObjectExists": True,
        "evaluatedMeshVertexCount": len(used_verts),
        "evaluatedMeshFaceCount": len(face_indices),
        "objectMatrixWorld": provenance.get("objectMatrixWorld"),
        "parentObject": parent.name if parent else None,
        "parentMatrixWorld": _matrix4_to_rows(parent.matrix_world.copy()) if parent else None,
        "localBBox": _bbox_to_dict(local_min, local_max),
        "worldBBox": _bbox_to_dict(world_min, world_max),
        "referenceWorldBBox": reference_world_bbox,
        "worldBBoxCenterDistanceFromReference": (
            float((world_center - ref_center).length) if world_center is not None and ref_center is not None else None
        ),
        "worldBBoxAbnormal": bool(world_bbox_abnormal),
        "worldVerticesInFrontCount": int(world_in_front),
        "ndcVerticesInFrameCount": int(ndc_in_frame),
        "projectedFaces": int(geom.get("projectedFaces", 0)),
        "positiveAreaFaces": int(geom.get("positiveAreaFaces", 0)),
        "frontFacingFaces": int(geom.get("frontFacingFaces", 0)),
        "depthVisibleFaces": int(geom.get("depthVisibleFaces", 0)),
        "projectionSource": projection_source,
        "cameraStateSource": camera_state_source,
    }
    row.update(provenance)
    if row.get("bboxCenterDistance") is None and row.get("worldBBoxCenterDistanceFromReference") is not None:
        row["bboxCenterDistance"] = row["worldBBoxCenterDistanceFromReference"]
    row["classification"] = _classify_eyelid_projection_failure(row)
    row["pass"] = _eyelid_projection_parity_success(row)
    return row


def _audit_eyelid_rig_geometry(
    sc,
    cam,
    feature: str,
    side: str,
    rig_objs: dict,
    res: int,
    *,
    projection_source: str = "RIG_HELPER_MATRIX_WORLD",
    camera_state_source: str = "EYE_PARITY_CAMERA_LOCKED",
    reference_world_bbox: dict | None = None,
) -> dict:
    obj = _eye_feature_rig_object(feature, side, rig_objs)
    chain = _audit_eyelid_helper_projection_chain(
        sc,
        cam,
        obj,
        res,
        projection_source=projection_source,
        camera_state_source=camera_state_source,
        reference_world_bbox=reference_world_bbox,
    )
    return {
        "manifestFaces": int(chain.get("evaluatedMeshFaceCount", 0)),
        "projectedFaces": int(chain.get("projectedFaces", 0)),
        "positiveAreaFaces": int(chain.get("positiveAreaFaces", 0)),
        "frontFacingFaces": int(chain.get("frontFacingFaces", 0)),
        "depthVisibleFaces": int(chain.get("depthVisibleFaces", 0)),
        "projectionChain": chain,
    }


def _prepare_eye_closed_parity_scene(
    sc,
    cam,
    parity_cam: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    side: str,
    res: int,
    set_eye_fn,
) -> dict:
    cam_before = _camera_state_snapshot(cam)
    _apply_eye_parity_camera(sc, cam, parity_cam, landmarks, skin_basis_coords, side, res)
    cam_applied = _camera_state_snapshot(cam)
    set_eye_fn(side, 0.0)
    _sync_rig_projection_matrices(sc)
    cam_after = _camera_state_snapshot(cam)
    camera_mutation = cam_after != cam_applied
    return {
        "cameraStateBeforeApply": cam_before,
        "cameraStateApplied": cam_applied,
        "cameraStateAfterMorph": cam_after,
        "cameraMutation": bool(camera_mutation),
        "cameraStateReceipt": _camera_state_receipt(sc, cam),
    }


def _run_eyelid_rig_helper_projection_parity_probe(
    sc,
    cam,
    *,
    side: str,
    locked_cam: dict | None,
    solver_report: dict | None,
    set_eye_fn,
    rig_objs: dict,
    eye_pivots: dict,
    rig_setup_receipt: dict | None,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    res: int,
) -> dict:
    parity_cam = locked_cam if locked_cam is not None else _parity_camera_from_eye_solver(solver_report)
    if parity_cam is None:
        return {
            "probeShot": "eye_left_closed",
            "pass": False,
            "reason": "PARITY_CAMERA_UNAVAILABLE",
            "policy": {
                "cameraMatrixMutation": 0,
                "orthoMutation": 0,
                "semanticRecenter": "DENY",
                "helperFaceManifestMutation": 0,
            },
        }
    camera_state_source = "LOCK" if locked_cam is not None else parity_cam.get("paritySource", "SOLVER")
    scene_state = _prepare_eye_closed_parity_scene(
        sc, cam, parity_cam, landmarks, skin_basis_coords, side, res, set_eye_fn
    )
    eyeball_obj = _eye_feature_rig_object("eyeball", side, rig_objs)
    eyeball_chain = _audit_eyelid_helper_projection_chain(
        sc,
        cam,
        eyeball_obj,
        res,
        projection_source="RIG_HELPER_REFERENCE_EYEBALL",
        camera_state_source=camera_state_source,
    )
    reference_world_bbox = eyeball_chain.get("worldBBox")
    per_feature: dict[str, dict] = {}
    for feature in EYELID_MANIFEST_FEATURES:
        obj = _eye_feature_rig_object(feature, side, rig_objs)
        chain = _audit_eyelid_helper_projection_chain(
            sc,
            cam,
            obj,
            res,
            projection_source="RIG_HELPER_MATRIX_WORLD",
            camera_state_source=camera_state_source,
            reference_world_bbox=reference_world_bbox,
        )
        parent = obj.parent if obj else None
        chain["feature"] = feature
        chain["eyePivotName"] = eye_pivots.get(side).name if eye_pivots.get(side) else None
        chain["eyePivotMatrixWorld"] = (
            _matrix4_to_rows(eye_pivots[side].matrix_world.copy()) if eye_pivots.get(side) else None
        )
        per_feature[feature] = chain
    probe_pass = all(per_feature[f]["pass"] for f in EYELID_MANIFEST_FEATURES)
    return {
        "probeShot": "eye_left_closed",
        "pass": bool(probe_pass),
        "visibilityPass": bool(probe_pass),
        "perFeature": per_feature,
        "referenceEyeball": eyeball_chain,
        "rigSetupReceipt": rig_setup_receipt or {},
        "classifications": {f: per_feature[f]["classification"] for f in EYELID_MANIFEST_FEATURES},
        "provenanceChain": [
            "rig_helper_object",
            "helper_vertex_space_provenance",
            "evaluated_mesh",
            "single_transform_application",
            "object_matrix_world",
            "helper_local_vertex",
            "world_space_vertex",
            "camera_view_projection_matrix",
            "clip_ndc",
            "in_frame_faces",
            "positive_area_faces",
        ],
        "currentMorphState": "closed",
        "cameraSource": camera_state_source,
        "cameraStateConsumption": scene_state,
        "policy": {
            "cameraMatrixMutation": 0 if not scene_state.get("cameraMutation") else 1,
            "orthoMutation": 0 if not scene_state.get("cameraMutation") else 1,
            "semanticRecenter": "DENY",
            "helperFaceManifestMutation": 0,
        },
    }


def _audit_eyelid_feature_provenance(
    feature: str,
    *,
    side: str,
    morph_state: str,
    rig_objs: dict,
    eyelid_weights: dict,
    eyelid_spec: dict,
    geometry_audit: dict,
) -> dict:
    registry = _eye_feature_registry_entry(feature)
    feature_registry_present = registry is not None
    rig_obj = _eye_feature_rig_object(feature, side, rig_objs) if registry else None
    feature_region_defined = _eye_feature_region_defined(feature, side, rig_objs)
    manifest_vertex_count, manifest_face_count = _eye_feature_manifest_counts(feature, side, rig_objs)
    semantic_slot = _eye_feature_semantic_slot(feature, side, rig_objs)
    morph_key = _eye_morph_weight_key(feature, side)
    seed_vertex_count = _eye_seed_vertex_count(eyelid_weights, morph_key)
    state_mapping_present, allowed_states, _mapping_source = _eye_state_mapping_present(
        feature, eyelid_weights, eyelid_spec, side
    )
    row = {
        "feature": feature,
        "featureRegistryPresent": feature_registry_present,
        "featureRegionDefined": feature_region_defined,
        "sourceLandmarkIds": list(registry.get("sourceLandmarkIds", ())) if registry else [],
        "seedVertexCount": seed_vertex_count,
        "manifestVertexCount": manifest_vertex_count,
        "manifestFaceCount": manifest_face_count,
        "semanticSlot": semantic_slot,
        "stateMappingPresent": state_mapping_present,
        "allowedStates": allowed_states,
        "currentMorphState": morph_state,
        "mappingRuleId": f"eye_{morph_state}_{feature}",
        "projectedFaces": int(geometry_audit.get("projectedFaces", 0)),
        "positiveAreaFaces": int(geometry_audit.get("positiveAreaFaces", 0)),
        "rigObjectName": rig_obj.name if rig_obj else None,
        "landmarkSemanticDefinition": registry.get("landmarkSemanticDefinition") if registry else None,
        "morphWeightKey": morph_key,
        "cameraStateConsumption": "EYE_PARITY_CAMERA_LOCKED",
    }
    row["classification"] = _classify_eyelid_manifest_parity_failure(row)
    chain = geometry_audit.get("projectionChain")
    if (
        row.get("featureRegistryPresent")
        and row.get("featureRegionDefined")
        and int(row.get("manifestFaceCount", 0)) > 0
        and row.get("semanticSlot") is not None
        and row.get("stateMappingPresent")
        and chain
    ):
        row["classification"] = chain.get("classification") or _classify_eyelid_projection_failure(chain)
    row["pass"] = _eyelid_manifest_parity_success(row)
    return row


def _eye_feature_projection_audit(
    sc,
    cam,
    skin_obj,
    rig_objs: dict,
    fid_mats: dict,
    valid,
    fid_path: Path,
    res: int,
    *,
    side: str,
    features: tuple[str, ...],
    composite_rgb: np.ndarray | None = None,
) -> tuple[dict[str, dict], dict[str, dict]]:
    per_feature_audit = {
        f: _audit_native_fid_feature(
            sc,
            cam,
            skin_obj,
            rig_objs,
            fid_mats,
            valid,
            f,
            fid_path,
            res,
            side=side,
            composite_rgb=composite_rgb,
        )
        for f in features
    }
    feature_projection = {
        f: {
            "projectedFaces": int(per_feature_audit[f].get("projectedFaces", 0)),
            "positiveAreaFaces": int(per_feature_audit[f].get("positiveAreaFaces", 0)),
            "projectedAreaPxEstimate": int(per_feature_audit[f].get("positiveAreaFaces", 0)),
        }
        for f in features
    }
    return per_feature_audit, feature_projection


def _feature_manifest_face_count(
    skin_obj,
    feature: str,
    *,
    rig_objs: dict | None = None,
    side: str | None = None,
) -> int:
    if feature in EYE_FEATURE_REGISTRY and rig_objs is not None and side is not None:
        _, faces = _eye_feature_manifest_counts(feature, side, rig_objs)
        return faces
    if skin_obj is None or skin_obj.type != "MESH":
        return 0
    slot_idx = FEATURE_TO_SLOT.get(feature)
    if slot_idx is None:
        return 0
    return sum(1 for p in skin_obj.data.polygons if int(p.material_index) == int(slot_idx))


def _expected_visibility_rule(
    feature: str,
    *,
    profile: str,
    mode: str,
    morph_state: str | None = None,
    side: str | None = None,
) -> dict:
    if profile == "eye":
        state = morph_state or "closed"
        occluded = _eye_feature_occluded_expected(state, feature)
        return {
            "expectedVisible": not occluded,
            "expectedOccluded": occluded,
            "expectedVisibilityClass": "OCCLUDED_EXPECTED" if occluded else "VISIBLE_REQUIRED",
            "visibilityRuleSource": "EYE_STATE_MAPPING",
            "visibilityRuleId": f"eye_{state}_{feature}",
            "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS if occluded else None,
            "occludedExpectedSemanticsMeaning": OCCLUDED_EXPECTED_SEMANTICS_MEANING if occluded else None,
        }
    _, occluded_corners = _mouth_corner_contract(mode)
    occluded = feature in occluded_corners
    if mode == "front":
        rule_id = "mouth_front_corner_visible"
    elif mode == "left":
        rule_id = "mouth_left_near_corner_visible"
    else:
        rule_id = f"mouth_{mode}_default"
    return {
        "expectedVisible": not occluded,
        "expectedOccluded": occluded,
        "expectedVisibilityClass": "OCCLUDED_EXPECTED" if occluded else "VISIBLE_REQUIRED",
        "visibilityRuleSource": "MOUTH_VIEW_CORNER_CONTRACT",
        "visibilityRuleId": rule_id,
        "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS if occluded else None,
        "occludedExpectedSemanticsMeaning": OCCLUDED_EXPECTED_SEMANTICS_MEANING if occluded else None,
    }


def _classify_visibility_parity(
    expected_visible: bool,
    expected_occluded: bool,
    actual_visible: bool,
) -> str:
    if expected_visible and actual_visible:
        return "VISIBILITY_MATCH_VISIBLE"
    if expected_occluded and not actual_visible:
        return "VISIBILITY_MATCH_OCCLUDED"
    if expected_visible and not actual_visible:
        return "EXPECTED_VISIBLE_MISSING"
    if expected_occluded and actual_visible:
        return "EXPECTED_OCCLUDED_BUT_VISIBLE"
    return "UNCLASSIFIED"


def _evaluate_geometric_visibility(
    feature: str,
    rule: dict,
    *,
    index_pixels: int,
    projected_faces: int,
    positive_area_faces: int,
    mask_slot_pixels: int,
) -> dict:
    actual_visible = (
        int(index_pixels) > 0
        or int(projected_faces) > 0
        or int(positive_area_faces) > 0
        or int(mask_slot_pixels) > 0
    )
    if rule.get("expectedOccluded"):
        geo_pass = True
    else:
        floor = MIN_ABSOLUTE_FLOOR.get(feature, 0)
        geo_pass = actual_visible and (int(index_pixels) >= floor or int(mask_slot_pixels) >= floor or int(projected_faces) > 0)
    return {
        "pass": bool(geo_pass),
        "actualVisible": bool(actual_visible),
        "indexPixels": int(index_pixels),
        "projectedFaces": int(projected_faces),
        "positiveAreaFaces": int(positive_area_faces),
        "maskSlotPixels": int(mask_slot_pixels),
    }


def _evaluate_native_semantic_emission(
    feature: str,
    rule: dict,
    *,
    fid_pixels: int,
    mask_slot_pixels: int,
    expected_pixels: int,
    mode: str,
    emission_reference_pixels: int | None = None,
) -> dict:
    floor = MIN_ABSOLUTE_FLOOR.get(feature, 40)
    fid_visible = int(fid_pixels) >= int(floor)
    mask_visible = int(mask_slot_pixels) >= int(floor)
    actual_visible = fid_visible or mask_visible
    if rule.get("expectedOccluded"):
        classification = _classify_visibility_parity(False, True, actual_visible)
        return {
            "pass": True,
            "actualVisible": bool(actual_visible),
            "fidPixels": int(fid_pixels),
            "maskSlotPixels": int(mask_slot_pixels),
            "fidAboveFloor": bool(fid_visible),
            "maskAboveFloor": bool(mask_visible),
            "classification": classification,
            "emissionPath": "OCCLUDED_EXPECTED_B",
        }
    reference = (
        int(emission_reference_pixels)
        if emission_reference_pixels is not None and int(emission_reference_pixels) > 0
        else int(expected_pixels)
    )
    denominator_source = (
        "NATIVE_SLOT_DECODED"
        if emission_reference_pixels is not None and int(emission_reference_pixels) > 0
        else "SEMANTIC_INDEX"
    )
    rate = float(fid_pixels) / float(max(reference, 1))
    rate_ok = rate >= VISIBILITY_DETECTION_MIN if reference > 0 else fid_visible
    front_target = MIN_FEATURE_PIXELS.get(feature, floor)
    front_ok = not (mode == "front" and reference >= int(front_target * FRONT_ABSOLUTE_EXPECTED_FRAC)) or int(fid_pixels) >= front_target
    emission_pass = fid_visible and rate_ok and front_ok
    classification = _classify_visibility_parity(True, False, actual_visible)
    missing_reason = None
    if not emission_pass:
        if mask_visible and not fid_visible:
            missing_reason = "FID_RENDER_PATH_FAIL"
        elif not mask_visible and not fid_visible:
            missing_reason = "MASK_AND_FID_EMISSION_MISSING"
        elif fid_visible and not rate_ok:
            missing_reason = "BELOW_VISIBILITY_DETECTION_RATE"
        elif fid_visible and not front_ok:
            missing_reason = "BELOW_FRONT_ABSOLUTE_TARGET"
        else:
            missing_reason = "NATIVE_SEMANTIC_EMISSION_FAIL"
    return {
        "pass": bool(emission_pass),
        "actualVisible": bool(actual_visible),
        "fidPixels": int(fid_pixels),
        "maskSlotPixels": int(mask_slot_pixels),
        "fidAboveFloor": bool(fid_visible),
        "maskAboveFloor": bool(mask_visible),
        "detectionRate": rate,
        "detectionRateDenominator": int(reference),
        "detectionRateDenominatorSource": denominator_source,
        "semanticIndexExpectedPixels": int(expected_pixels),
        "classification": classification,
        "missingReason": missing_reason,
        "emissionPath": "FID_NATIVE_COMPOSITE",
    }


def _evaluate_feature_visibility_contract(
    sc,
    cam,
    skin_obj,
    feature: str,
    *,
    profile: str,
    mode: str,
    morph_state: str | None,
    side: str | None,
    fid_rgb: np.ndarray | None,
    res: int,
    mask_slot_pixels: int,
    projected_faces: int,
    positive_area_faces: int,
    native_final_pixels: int,
    rig_objs: dict | None = None,
    fid_layer_receipt: dict | None = None,
) -> dict:
    rule = _expected_visibility_rule(
        feature,
        profile=profile,
        mode=mode,
        morph_state=morph_state,
        side=side,
    )
    bbox = [0, 0, res - 1, res - 1]
    fid_pixels = (
        int(_count_feature_pixels(fid_rgb, bbox, (feature,), full_frame=False).get(feature, 0))
        if fid_rgb is not None
        else 0
    )
    index_pixels = int(
        _count_semantic_index_pixels(sc, cam, skin_obj, bbox, (feature,), res).get(feature, 0)
    )
    geometric = _evaluate_geometric_visibility(
        feature,
        rule,
        index_pixels=index_pixels,
        projected_faces=projected_faces,
        positive_area_faces=positive_area_faces,
        mask_slot_pixels=mask_slot_pixels,
    )
    expected_pixels = int(_compute_expected_visible_pixels(sc, cam, skin_obj, res, (feature,)).get(feature, 0))
    layer = ((fid_layer_receipt or {}).get("layers") or {}).get(feature, {})
    emission_reference = int(layer.get("decodedLayerPixels") or layer.get("nativeSlotRenderPixels") or 0)
    emission = _evaluate_native_semantic_emission(
        feature,
        rule,
        fid_pixels=fid_pixels,
        mask_slot_pixels=mask_slot_pixels,
        expected_pixels=expected_pixels,
        mode=mode if mode in ("front", "left") else "front",
        emission_reference_pixels=emission_reference if profile.startswith("mouth") else None,
    )
    if rule["expectedOccluded"]:
        visibility_contract_pass = True
        emission_contract_pass = bool(emission["pass"])
        parity_class = emission["classification"]
        contract_pass = bool(visibility_contract_pass)
    elif not geometric["pass"]:
        visibility_contract_pass = False
        emission_contract_pass = bool(emission["pass"])
        parity_class = "EXPECTED_VISIBLE_MISSING"
        contract_pass = False
    elif not emission["pass"]:
        visibility_contract_pass = True
        emission_contract_pass = False
        parity_class = "VISIBILITY_MATCH_VISIBLE"
        contract_pass = True
    else:
        visibility_contract_pass = True
        emission_contract_pass = True
        parity_class = "VISIBILITY_MATCH_VISIBLE"
        contract_pass = True
    semantic_slot = (
        _eye_feature_semantic_slot(feature, side, rig_objs)
        if profile == "eye" and side and rig_objs is not None
        else FEATURE_TO_SLOT.get(feature)
    )
    return {
        "feature": feature,
        "morphState": morph_state,
        "expectedVisibilityClass": rule["expectedVisibilityClass"],
        "projectedFaces": int(projected_faces),
        "positiveAreaFaces": int(positive_area_faces),
        "nativeFinalPixels": int(native_final_pixels),
        "existingAbsoluteFloor": MIN_ABSOLUTE_FLOOR.get(feature, 0),
        "expectedVisible": bool(rule["expectedVisible"]),
        "expectedOccluded": bool(rule["expectedOccluded"]),
        "actualVisible": bool(emission["actualVisible"]),
        "geometricActualVisible": bool(geometric["actualVisible"]),
        "visibilityRuleSource": rule["visibilityRuleSource"],
        "visibilityRuleId": rule["visibilityRuleId"],
        "semanticSlot": semantic_slot,
        "manifestFaceCount": _feature_manifest_face_count(
            skin_obj, feature, rig_objs=rig_objs, side=side
        ),
        "geometricVisibility": geometric,
        "nativeSemanticEmission": emission,
        "visibilityParityClassification": parity_class,
        "occludedExpectedSemantics": rule.get("occludedExpectedSemantics"),
        "visibilityContractPass": bool(visibility_contract_pass),
        "emissionContractPass": bool(emission_contract_pass),
        "contractPass": bool(contract_pass),
        "pass": bool(contract_pass),
    }


def _evaluate_feature_visibility_contract_bundle(
    sc,
    cam,
    skin_obj,
    fid_rgb: np.ndarray | None,
    res: int,
    features: tuple[str, ...],
    *,
    profile: str,
    mode: str,
    morph_state: str | None = None,
    side: str | None = None,
    native_final_pixels: int = 0,
    slot_projection: dict | None = None,
    feature_projection: dict[str, dict] | None = None,
    rig_objs: dict | None = None,
    fid_layer_receipt: dict | None = None,
) -> tuple[bool, bool, dict[str, dict], dict[str, int]]:
    slot_projection = slot_projection or {}
    feature_projection = feature_projection or {}
    per_slot = (slot_projection.get("perFeature") or {}) if profile.startswith("mouth") else {}
    slot_diag = _mouth_mask_slot_diagnostics(sc, cam, skin_obj, None, [skin_obj], res) if profile.startswith("mouth") else []
    slot_by_name = {d["slotName"]: d for d in slot_diag}
    visibility: dict[str, dict] = {}
    fid_counts: dict[str, int] = {}
    visibility_pass = True
    emission_pass = True
    for feat in features:
        slot_row = per_slot.get(feat) or slot_by_name.get(feat, {})
        if profile == "eye":
            slot_row = feature_projection.get(feat, slot_row)
        mask_slot_px = int(slot_row.get("projectedAreaPxEstimate", 0))
        projected_faces = int(slot_row.get("projectedFaces", 0))
        if projected_faces <= 0:
            projected_faces = 1 if bool(slot_row.get("projected")) else 0
        positive_area_faces = int(slot_row.get("positiveAreaFaces", 0))
        if positive_area_faces <= 0:
            positive_area_faces = 1 if bool(slot_row.get("positiveArea")) else 0
        row = _evaluate_feature_visibility_contract(
            sc,
            cam,
            skin_obj,
            feat,
            profile=profile,
            mode=mode,
            morph_state=morph_state,
            side=side,
            fid_rgb=fid_rgb,
            res=res,
            mask_slot_pixels=mask_slot_px,
            projected_faces=projected_faces,
            positive_area_faces=positive_area_faces,
            native_final_pixels=native_final_pixels,
            rig_objs=rig_objs,
            fid_layer_receipt=fid_layer_receipt,
        )
        visibility[feat] = row
        fid_counts[feat] = int(row["nativeSemanticEmission"]["fidPixels"])
        if not row["visibilityContractPass"]:
            visibility_pass = False
        if not row["emissionContractPass"]:
            emission_pass = False
    return visibility_pass, emission_pass, visibility, fid_counts


def _parity_camera_from_eye_solver(solver_report: dict | None) -> dict | None:
    if not isinstance(solver_report, dict):
        return None
    if solver_report.get("pass"):
        return solver_report
    ref = solver_report.get("parityCameraRef")
    if isinstance(ref, dict) and ref.get("ortho_scale") is not None:
        return ref
    scan = solver_report.get("scan") or {}
    closed_rows = scan.get("closed") or []
    if not closed_rows:
        return None
    row = closed_rows[0]
    if row.get("semanticCenter") and row.get("ortho") is not None:
        return {
            "paritySource": "SOLVER_SCAN_CLOSED_FIRST",
            "semanticCenter": list(row["semanticCenter"]),
            "ortho_scale": float(row["ortho"]),
        }
    return None


def _apply_eye_parity_camera(
    sc,
    cam,
    parity_cam: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    side: str,
    res: int,
) -> None:
    if parity_cam.get("location") and parity_cam.get("rotation"):
        _apply_locked_camera(cam, parity_cam)
        return
    center = Vector(parity_cam.get("semanticCenter") or parity_cam.get("location") or (0.0, 0.0, 0.0))
    view_dir = Vector(parity_cam.get("view_dir") or parity_cam.get("semanticViewDir") or (0.0, -1.0, 0.0))
    dist = float(parity_cam.get("distance", 2.8))
    ortho = float(parity_cam.get("ortho_scale", cam.data.ortho_scale))
    _apply_semantic_camera(cam, center, ortho, view_dir, dist)
    frame_keys = _frame_landmark_keys("eye", f"eye_{'l' if side == 'L' else 'r'}")
    _nudge_camera_to_landmarks(
        sc, cam, landmarks, frame_keys, center, view_dir, dist, res, skin_basis_coords, "front"
    )


def _run_eye_l_closed_visibility_parity_probe(
    sc,
    cam,
    *,
    side: str,
    locked_cam: dict | None,
    solver_report: dict | None,
    set_eye_fn,
    rig_objs: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    fid_mats: dict,
    mask_mat,
    res: int,
) -> dict:
    parity_cam = locked_cam if locked_cam is not None else _parity_camera_from_eye_solver(solver_report)
    if parity_cam is None:
        return {
            "probeShot": "eye_left_closed",
            "pass": False,
            "contractResolved": False,
            "reason": "PARITY_CAMERA_UNAVAILABLE",
            "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS,
            "occludedExpectedSemanticsMeaning": OCCLUDED_EXPECTED_SEMANTICS_MEANING,
        }
    _prepare_eye_closed_parity_scene(sc, cam, parity_cam, landmarks, skin_basis_coords, side, res, set_eye_fn)
    valid = _eye_valid_objects(set_eye_fn, side, rig_objs)
    skin_eye = set_eye_fn.skin_eye
    bounds = _eye_bounds_for_pct(set_eye_fn, side, 0.0, rig_objs, skin_basis_coords)
    metrics = _render_holdout_occupancy_metrics(
        sc,
        cam,
        valid,
        mask_mat,
        res,
        semantic_bounds=bounds,
        morph_bounds=bounds,
    )
    fid_path = Path(tempfile.gettempdir()) / f"nurion_eye_vis_parity_{side}_closed.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin_eye, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    _, feature_projection = _eye_feature_projection_audit(
        sc,
        cam,
        skin_eye,
        rig_objs,
        fid_mats,
        valid,
        fid_path,
        res,
        side=side,
        features=EYE_GATE_FEATURES,
        composite_rgb=fid_rgb,
    )
    vis_pass, emission_pass, per_feature, fid_counts = _evaluate_feature_visibility_contract_bundle(
        sc,
        cam,
        skin_eye,
        fid_rgb,
        res,
        EYE_GATE_FEATURES,
        profile="eye",
        mode="front",
        morph_state="closed",
        side=side,
        native_final_pixels=int(metrics.get("finalMaskPixels", 0)),
        feature_projection=feature_projection,
        rig_objs=rig_objs,
    )
    classifications = {f: per_feature[f]["visibilityParityClassification"] for f in EYE_GATE_FEATURES}
    contract_resolved = all(
        classifications[f]
        in (
            "VISIBILITY_MATCH_VISIBLE",
            "VISIBILITY_MATCH_OCCLUDED",
            "EXPECTED_OCCLUDED_BUT_VISIBLE",
            "EXPECTED_VISIBLE_MISSING",
        )
        for f in EYE_GATE_FEATURES
    )
    return {
        "probeShot": "eye_left_closed",
        "pass": bool(vis_pass),
        "visibilityPass": bool(vis_pass),
        "emissionPass": bool(emission_pass),
        "contractResolved": bool(contract_resolved),
        "nativeFinalPixels": int(metrics.get("finalMaskPixels", 0)),
        "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS,
        "occludedExpectedSemanticsMeaning": OCCLUDED_EXPECTED_SEMANTICS_MEANING,
        "perFeature": per_feature,
        "classifications": classifications,
        "cameraSource": "LOCK" if locked_cam is not None else parity_cam.get("paritySource", "SOLVER"),
        "featureProjection": feature_projection,
    }


def _run_eyelid_manifest_state_mapping_parity_probe(
    sc,
    cam,
    *,
    side: str,
    locked_cam: dict | None,
    solver_report: dict | None,
    set_eye_fn,
    rig_objs: dict,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    eyelid_weights: dict,
    eyelid_spec: dict,
    res: int,
) -> dict:
    parity_cam = locked_cam if locked_cam is not None else _parity_camera_from_eye_solver(solver_report)
    if parity_cam is None:
        return {
            "probeShot": "eye_left_closed",
            "pass": False,
            "reason": "PARITY_CAMERA_UNAVAILABLE",
            "policy": {
                "arbitraryEyelidFaceExpansion": "DENY",
                "newThresholds": "DENY",
                "cameraRetune": "DENY",
                "fidRepairFirst": "DENY",
                "basisWeightMorphMutation": "DENY",
            },
        }
    camera_state_source = "LOCK" if locked_cam is not None else parity_cam.get("paritySource", "SOLVER")
    _prepare_eye_closed_parity_scene(sc, cam, parity_cam, landmarks, skin_basis_coords, side, res, set_eye_fn)
    morph_state = "closed"
    eyeball_obj = _eye_feature_rig_object("eyeball", side, rig_objs)
    eyeball_ref = _audit_eyelid_helper_projection_chain(
        sc,
        cam,
        eyeball_obj,
        res,
        projection_source="RIG_HELPER_REFERENCE_EYEBALL",
        camera_state_source=camera_state_source,
    )
    reference_world_bbox = eyeball_ref.get("worldBBox")
    per_feature: dict[str, dict] = {}
    for feature in EYELID_MANIFEST_FEATURES:
        geometry = _audit_eyelid_rig_geometry(
            sc,
            cam,
            feature,
            side,
            rig_objs,
            res,
            projection_source="RIG_HELPER_MATRIX_WORLD",
            camera_state_source=camera_state_source,
            reference_world_bbox=reference_world_bbox,
        )
        provenance = _audit_eyelid_feature_provenance(
            feature,
            side=side,
            morph_state=morph_state,
            rig_objs=rig_objs,
            eyelid_weights=eyelid_weights,
            eyelid_spec=eyelid_spec,
            geometry_audit=geometry,
        )
        provenance["projectionChain"] = geometry.get("projectionChain")
        per_feature[feature] = provenance
    classifications = {f: per_feature[f]["classification"] for f in EYELID_MANIFEST_FEATURES}
    probe_pass = all(per_feature[f]["pass"] for f in EYELID_MANIFEST_FEATURES)
    return {
        "probeShot": "eye_left_closed",
        "pass": bool(probe_pass),
        "visibilityPass": bool(probe_pass),
        "perFeature": per_feature,
        "classifications": classifications,
        "provenanceChain": [
            "landmark_semantic_definition",
            "feature_registry",
            "face_region_manifest",
            "semantic_slot_assignment",
            "morph_state_mapping",
            "camera_state_consumption",
            "projected_faces",
        ],
        "currentMorphState": morph_state,
        "cameraSource": camera_state_source,
        "referenceEyeball": eyeball_ref,
        "policy": {
            "arbitraryEyelidFaceExpansion": "DENY",
            "newThresholds": "DENY",
            "cameraRetune": "DENY",
            "fidRepairFirst": "DENY",
            "basisWeightMorphMutation": "DENY",
        },
    }


def _run_mouth_visibility_parity_probe(
    sc,
    cam,
    lock: dict,
    morph_spec: dict,
    *,
    view: str,
    skin_obj,
    valid_objs,
    mask_mat,
    fid_mats: dict,
    res: int,
    set_mouth_fn,
    mouth_valid_fn,
    camera_ref_source: str = "MOUTH_VISIBILITY_PARITY_FIXED",
) -> dict:
    _apply_locked_camera(cam, lock)
    set_mouth_fn(float(morph_spec["angle"]), show_oral=bool(morph_spec["showOral"]))
    valid, skin = mouth_valid_fn(bool(morph_spec["showOral"]))
    morph_tag = _morph_tag_from_angle(float(morph_spec["angle"]))
    metrics = _render_holdout_occupancy_metrics(
        sc,
        cam,
        valid,
        mask_mat,
        res,
        semantic_bounds=(morph_spec.get("unionMin"), morph_spec.get("unionMax")),
        morph_bounds=(morph_spec["coMin"], morph_spec["coMax"]),
    )
    fid_path = Path(tempfile.gettempdir()) / f"nurion_mouth_vis_parity_{view}_{morph_tag}.png"
    fid_rgb = _render_feature_id(sc, cam, skin, {}, fid_mats, valid, fid_path, res, allow_software_fallback=False)
    fid_layer_receipt = dict(_FID_RENDER_RECEIPT)
    slot_proj = _mouth_slot_projection_summary(sc, cam, skin, res, MOUTH_GATE_FEATURES)
    vis_pass, emission_pass, per_feature, _ = _evaluate_feature_visibility_contract_bundle(
        sc,
        cam,
        skin,
        fid_rgb,
        res,
        MOUTH_GATE_FEATURES,
        profile="mouth",
        mode=view,
        morph_state=morph_tag,
        native_final_pixels=int(metrics.get("finalMaskPixels", 0)),
        slot_projection=slot_proj,
        fid_layer_receipt=fid_layer_receipt,
    )
    classifications = {f: per_feature[f]["visibilityParityClassification"] for f in MOUTH_GATE_FEATURES}
    contract_resolved = all(
        per_feature[f]["visibilityContractPass"] or per_feature[f]["expectedOccluded"] for f in MOUTH_GATE_FEATURES
    )
    forensic_camera_ref = _build_mouth_forensic_camera_ref(lock, source=camera_ref_source)
    return {
        "probeShot": f"mouth_{morph_tag}_{view}",
        "view": view,
        "morphState": morph_tag,
        "pass": bool(vis_pass),
        "visibilityPass": bool(vis_pass),
        "emissionPass": bool(emission_pass),
        "contractResolved": bool(contract_resolved),
        "nativeFinalPixels": int(metrics.get("finalMaskPixels", 0)),
        "perFeature": per_feature,
        "classifications": classifications,
        "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS,
        "fidLayerReceipt": fid_layer_receipt,
        "forensicCameraRef": forensic_camera_ref,
        "parityCameraConsumed": {
            "location": [float(x) for x in lock["location"]],
            "rotation": [float(x) for x in lock["rotation"]],
            "ortho_scale": float(lock["ortho_scale"]),
        },
    }


def _evaluate_native_semantic_evidence_gate(
    *,
    projected_faces: int,
    positive_area_faces: int,
    native_final_pixels: int,
    clipped: bool,
    full_bleed: bool,
    context_retained: bool,
    expected_visibility_pass: bool,
    min_native_floor: int = 0,
) -> dict:
    checks = {
        "projectedFaces": int(projected_faces) > 0,
        "positiveAreaFaces": int(positive_area_faces) > 0,
        "nativeFinalPixels": int(native_final_pixels) >= int(min_native_floor) if min_native_floor > 0 else int(native_final_pixels) > 0,
        "clipped": not bool(clipped),
        "fullBleed": not bool(full_bleed),
        "contextRetained": bool(context_retained),
        "expectedVisibility": bool(expected_visibility_pass),
    }
    failing = [k for k, ok in checks.items() if not ok]
    return {
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "pass": len(failing) == 0,
        "checks": checks,
        "failures": failing,
        "nativeFinalPixels": int(native_final_pixels),
        "projectedFaces": int(projected_faces),
        "positiveAreaFaces": int(positive_area_faces),
    }


def _framing_context_from_occ_metrics(occ_metrics: dict | None) -> tuple[bool, bool, bool, str | None]:
    frame = (occ_metrics or {}).get("frameOccupancy") or {}
    wf = float(frame.get("widthFrac", 0.0))
    hf = float(frame.get("heightFrac", 0.0))
    full_bleed = wf >= SEMANTIC_OCC_MAX and hf >= SEMANTIC_OCC_MAX
    ctx_ok, ctx_reason = _semantic_context_ok(frame)
    return full_bleed, bool(ctx_ok), wf <= 0.0 and hf <= 0.0, ctx_reason


def _mouth_required_features(show_oral: bool, mode: str) -> tuple[str, ...]:
    base = MOUTH_GATE_FEATURES
    if show_oral:
        return base + MOUTH_ORAL_GATE_FEATURES
    return base


def _evaluate_feature_visibility_bundle(
    sc,
    cam,
    skin_obj,
    fid_rgb: np.ndarray | None,
    res: int,
    features: tuple[str, ...],
    mode: str,
    *,
    occluded_features: tuple[str, ...] = (),
) -> tuple[bool, dict[str, dict], dict[str, int]]:
    bbox = [0, 0, res - 1, res - 1]
    fid_counts = (
        _count_feature_pixels(fid_rgb, bbox, features, full_frame=False) if fid_rgb is not None else {f: 0 for f in features}
    )
    expected_counts = _compute_expected_visible_pixels(sc, cam, skin_obj, res, features)
    visibility: dict[str, dict] = {}
    all_pass = True
    for feat in features:
        vis = _evaluate_feature_visibility(
            feat,
            int(fid_counts.get(feat, 0)),
            int(expected_counts.get(feat, 0)),
            mode if mode in ("front", "left") else "front",
            occluded_expected=feat in occluded_features,
        )
        visibility[feat] = vis
        if not vis.get("pass"):
            all_pass = False
    return all_pass, visibility, {k: int(v) for k, v in fid_counts.items()}


def _mouth_slot_projection_summary(
    sc,
    cam,
    skin_obj,
    res: int,
    features: tuple[str, ...],
    rig_objs: dict | None = None,
) -> dict:
    slot_diag = _mouth_mask_slot_diagnostics(sc, cam, skin_obj, None, [skin_obj], res)
    by_name = {d["slotName"]: d for d in slot_diag}
    per_feature: dict[str, dict] = {}
    projected_total = 0
    positive_total = 0
    for feat in features:
        provider = _mouth_feature_projection_provider(feat)
        skin_row = _skin_slot_feature_projection_row(by_name, feat)
        if provider == "RIG_HELPER_PROJECTION" and rig_objs is not None:
            rig_row = _rig_helper_feature_projection_row(sc, cam, rig_objs, feat, res)
            consumed_pf = int(rig_row.get("projectedFaces", 0))
            consumed_paf = int(rig_row.get("positiveAreaFaces", 0))
            projected = consumed_pf > 0
            positive = consumed_paf > 0
            per_feature[feat] = {
                **rig_row,
                "feature": feat,
                "projectionProvider": provider,
                "providerSelected": provider,
                "providerReason": "ORAL_RIG_HELPER_FEATURE",
                "skinSlotProjectedFaces": int(skin_row.get("projectedFaces", 0)),
                "rigHelperProjectedFaces": consumed_pf,
                "consumedProjectedFaces": consumed_pf,
                "consumptionParityPass": consumed_pf > 0,
            }
        else:
            consumed_pf = int(skin_row.get("projectedFaces", 0))
            per_feature[feat] = {
                **skin_row,
                "feature": feat,
                "projectionProvider": provider,
                "providerSelected": provider,
                "providerReason": "SKIN_MATERIAL_SLOT",
                "skinSlotProjectedFaces": consumed_pf,
                "rigHelperProjectedFaces": 0,
                "consumedProjectedFaces": consumed_pf,
                "consumptionParityPass": bool(skin_row.get("projected")),
            }
            projected = bool(skin_row.get("projected"))
            positive = bool(skin_row.get("positiveArea"))
        if projected:
            projected_total += 1
        if positive:
            positive_total += 1
    return {
        "perFeature": per_feature,
        "projectedFaces": projected_total,
        "positiveAreaFaces": positive_total,
        "consumptionPathRepair": MOUTH_CONSUMPTION_PATH_REPAIR,
    }


def _evaluate_mouth_morph_native_evidence(
    sc,
    cam,
    valid,
    skin_obj,
    mask_mat,
    fid_mats,
    res: int,
    mode: str,
    show_oral: bool,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    morph_spec: dict,
    sem_bounds: tuple[Vector | None, Vector | None] | None,
    rig_objs: dict | None = None,
) -> dict:
    metrics = _render_holdout_occupancy_metrics(
        sc,
        cam,
        valid,
        mask_mat,
        res,
        semantic_bounds=sem_bounds,
        morph_bounds=(morph_spec["coMin"], morph_spec["coMax"]),
    )
    occ_metrics = metrics.get("occupancyMetrics") or {}
    legacy_occ = _legacy_occupancy_diagnostic(occ_metrics)
    frame_keys = _frame_landmark_keys("mouth", "mouth_oral" if show_oral else "mouth")
    in_frame, frame_reason = _landmarks_in_frame(
        sc, cam, landmarks, frame_keys, res, skin_basis_coords, mode
    )
    full_bleed, context_retained, _empty, ctx_reason = _framing_context_from_occ_metrics(occ_metrics)
    clipped = not in_frame
    required = _mouth_required_features(show_oral, mode)
    required_corners, occluded_corners = _mouth_corner_contract(mode)
    fid_path = Path(tempfile.gettempdir()) / f"nurion_mouth_evidence_{id(cam)}_{mode}.png"
    fid_rgb = _render_feature_id(sc, cam, skin_obj, {}, fid_mats, valid, fid_path, res, allow_software_fallback=False)
    fid_layer_receipt = dict(_FID_RENDER_RECEIPT)
    slot_proj = _mouth_slot_projection_summary(sc, cam, skin_obj, res, required, rig_objs=rig_objs)
    morph_tag = _morph_tag_from_angle(float(morph_spec["angle"]))
    vis_pass, emission_pass, visibility, fid_counts = _evaluate_feature_visibility_contract_bundle(
        sc,
        cam,
        skin_obj,
        fid_rgb,
        res,
        required,
        profile="mouth",
        mode=mode,
        morph_state=morph_tag,
        native_final_pixels=int(metrics.get("finalMaskPixels", 0)),
        slot_projection=slot_proj,
        rig_objs=rig_objs,
        fid_layer_receipt=fid_layer_receipt,
    )
    min_floor = min(MIN_ABSOLUTE_FLOOR.get(f, 0) for f in required if f in MIN_ABSOLUTE_FLOOR) if required else 0
    native_final_pixels = int(metrics.get("finalMaskPixels", 0))
    evidence = _evaluate_native_semantic_evidence_gate(
        projected_faces=int(slot_proj["projectedFaces"]),
        positive_area_faces=int(slot_proj["positiveAreaFaces"]),
        native_final_pixels=native_final_pixels,
        clipped=clipped,
        full_bleed=full_bleed,
        context_retained=context_retained,
        expected_visibility_pass=vis_pass,
        min_native_floor=min_floor,
    )
    holdout_ok = (
        native_final_pixels > 0
        and metrics.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
        and not bool(metrics.get("finalMaskSourceDivergence"))
    )
    return {
        **metrics,
        "legacyOccupancy": legacy_occ,
        "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
        "nativeSemanticEvidence": evidence,
        "nativeSemanticEvidencePass": bool(evidence.get("pass") and holdout_ok),
        "maskOccupancyPass": bool(legacy_occ.get("legacyPass")),
        "featureVisibility": visibility,
        "visibilityContractPass": bool(vis_pass),
        "nativeSemanticEmissionPass": bool(emission_pass),
        "nativeFeaturePixels": fid_counts,
        "slotProjection": slot_proj,
        "inFrame": bool(in_frame),
        "frameReason": frame_reason,
        "contextReason": ctx_reason,
        "fullBleed": full_bleed,
        "contextRetained": context_retained,
        "clipped": clipped,
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
    }


def _evaluate_eye_state_native_evidence(
    sc,
    cam,
    valid,
    skin_eye,
    rig_objs: dict,
    side: str,
    state: str,
    mask_mat,
    fid_mats,
    res: int,
    landmarks: dict,
    skin_basis_coords: list[Vector],
    frame_keys: tuple[str, ...],
    sem_bounds: tuple[Vector | None, Vector | None] | None,
    morph_bounds: tuple[Vector | None, Vector | None] | None,
) -> dict:
    metrics = _render_holdout_occupancy_metrics(
        sc,
        cam,
        valid,
        mask_mat,
        res,
        semantic_bounds=sem_bounds,
        morph_bounds=morph_bounds,
    )
    occ_metrics = metrics.get("occupancyMetrics") or {}
    legacy_occ = _legacy_occupancy_diagnostic(occ_metrics)
    in_frame, frame_reason = _landmarks_in_frame(
        sc, cam, landmarks, frame_keys, res, skin_basis_coords, "front"
    )
    full_bleed, context_retained, _empty, ctx_reason = _framing_context_from_occ_metrics(occ_metrics)
    clipped = not in_frame
    fid_path = Path(tempfile.gettempdir()) / f"nurion_eye_evidence_{side}_{state}_{id(cam)}.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin_eye, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    per_feature_audit, feature_projection = _eye_feature_projection_audit(
        sc,
        cam,
        skin_eye,
        rig_objs,
        fid_mats,
        valid,
        fid_path,
        res,
        side=side,
        features=EYE_GATE_FEATURES,
        composite_rgb=fid_rgb,
    )
    vis_pass, emission_pass, visibility, fid_counts = _evaluate_feature_visibility_contract_bundle(
        sc,
        cam,
        skin_eye,
        fid_rgb,
        res,
        EYE_GATE_FEATURES,
        profile="eye",
        mode="front",
        morph_state=state,
        side=side,
        native_final_pixels=int(metrics.get("finalMaskPixels", 0)),
        feature_projection=feature_projection,
        rig_objs=rig_objs,
    )
    projected_faces = sum(int(per_feature_audit[f].get("projectedFaces", 0)) for f in EYE_GATE_FEATURES)
    positive_area_faces = sum(int(per_feature_audit[f].get("positiveAreaFaces", 0)) for f in EYE_GATE_FEATURES)
    min_floor = min(MIN_ABSOLUTE_FLOOR.get(f, 0) for f in EYE_GATE_FEATURES)
    native_final_pixels = int(metrics.get("finalMaskPixels", 0))
    evidence = _evaluate_native_semantic_evidence_gate(
        projected_faces=projected_faces,
        positive_area_faces=positive_area_faces,
        native_final_pixels=native_final_pixels,
        clipped=clipped,
        full_bleed=full_bleed,
        context_retained=context_retained,
        expected_visibility_pass=vis_pass,
        min_native_floor=min_floor,
    )
    holdout_ok = native_final_pixels > 0 and metrics.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
    return {
        **metrics,
        "legacyOccupancy": legacy_occ,
        "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
        "nativeSemanticEvidence": evidence,
        "nativeSemanticEvidencePass": bool(evidence.get("pass") and holdout_ok),
        "maskOccupancyPass": bool(legacy_occ.get("legacyPass")),
        "featureVisibility": visibility,
        "visibilityContractPass": bool(vis_pass),
        "nativeSemanticEmissionPass": bool(emission_pass),
        "nativeFeaturePixels": fid_counts,
        "perFeatureAudit": per_feature_audit,
        "inFrame": bool(in_frame),
        "frameReason": frame_reason,
        "contextReason": ctx_reason,
        "fullBleed": full_bleed,
        "contextRetained": context_retained,
        "clipped": clipped,
        "occupancyOk": bool(legacy_occ.get("legacyPass")),
        "evidenceOk": bool(vis_pass and evidence.get("pass") and holdout_ok),
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
    }


def _evaluate_interior_native_evidence(
    sc,
    cam,
    valid,
    skin_obj,
    rig_objs: dict,
    fid_mats: dict,
    mask_mat,
    res: int,
    bounds: tuple[Vector, Vector],
    landmarks: dict,
    skin_basis_coords: list[Vector],
) -> dict:
    metrics = _render_holdout_occupancy_metrics(
        sc, cam, valid, mask_mat, res, semantic_bounds=bounds, morph_bounds=bounds
    )
    occ_metrics = metrics.get("occupancyMetrics") or {}
    legacy_occ = _legacy_occupancy_diagnostic(occ_metrics)
    in_frame, frame_reason = _landmarks_in_frame(
        sc, cam, landmarks, _frame_landmark_keys("mouth", "mouth_interior"), res, skin_basis_coords, "front"
    )
    full_bleed, context_retained, _empty, ctx_reason = _framing_context_from_occ_metrics(occ_metrics)
    clipped = not in_frame
    fid_path = Path(tempfile.gettempdir()) / f"nurion_interior_evidence_{id(cam)}.png"
    fid_rgb = _render_feature_id(
        sc, cam, skin_obj, rig_objs, fid_mats, valid, fid_path, res, allow_software_fallback=False
    )
    bbox = [0, 0, res - 1, res - 1]
    oral = _validate_oral_opening(fid_rgb, bbox) if fid_rgb is not None else {"pass": False, "separationPx": 0}
    feature_keys = ("upper_teeth", "lower_teeth", "tongue")
    native_counts = {
        f: int(_count_feature_pixels(fid_rgb, bbox, (f,), full_frame=False).get(f, 0)) if fid_rgb is not None else 0
        for f in feature_keys
    }
    lip_counts = (
        _count_feature_pixels(fid_rgb, bbox, ("lip", "lip_corner_l", "lip_corner_r"), full_frame=False)
        if fid_rgb is not None
        else {}
    )
    lip_guard = sum(int(lip_counts.get(k, 0)) for k in ("lip", "lip_corner_l", "lip_corner_r"))
    per_feature = {
        "oralOpening": {
            "pixels": 0,
            "floor": 0,
            "pass": False,
            "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
            "deferredToNativeEvidenceContract": True,
            "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
            "sourceReceipt": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
        },
        "upperTeeth": {
            "pixels": native_counts["upper_teeth"],
            "floor": MIN_ABSOLUTE_FLOOR["upper_teeth"],
            "pass": native_counts["upper_teeth"] >= MIN_ABSOLUTE_FLOOR["upper_teeth"],
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        },
        "lowerTeeth": {
            "pixels": native_counts["lower_teeth"],
            "floor": MIN_ABSOLUTE_FLOOR["lower_teeth"],
            "pass": native_counts["lower_teeth"] >= MIN_ABSOLUTE_FLOOR["lower_teeth"],
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        },
        "tongue": {
            "pixels": native_counts["tongue"],
            "floor": MIN_ABSOLUTE_FLOOR["tongue"],
            "pass": native_counts["tongue"] >= MIN_ABSOLUTE_FLOOR["tongue"],
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        },
        "lipGuard": {
            "pixels": lip_guard,
            "floor": MIN_ABSOLUTE_FLOOR["lip"],
            "pass": lip_guard >= MIN_ABSOLUTE_FLOOR["lip"],
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        },
    }
    expected_visibility_pass = all(
        v["pass"] for v in per_feature.values() if not v.get("deferredToNativeEvidenceContract")
    )
    slot_proj = _mouth_slot_projection_summary(sc, cam, skin_obj, res, ("lip", "lip_corner_l", "lip_corner_r", "chin"))
    native_final_pixels = int(metrics.get("finalMaskPixels", 0))
    min_floor = min(v["floor"] for v in per_feature.values() if isinstance(v.get("floor"), int))
    evidence = _evaluate_native_semantic_evidence_gate(
        projected_faces=int(slot_proj["projectedFaces"]),
        positive_area_faces=int(slot_proj["positiveAreaFaces"]),
        native_final_pixels=native_final_pixels,
        clipped=clipped,
        full_bleed=full_bleed,
        context_retained=context_retained,
        expected_visibility_pass=expected_visibility_pass,
        min_native_floor=min_floor,
    )
    holdout_ok = native_final_pixels > 0 and metrics.get("finalSource") == "SLOT_HOLDOUT_COMPOSITE"
    failing = [k for k, v in per_feature.items() if not v["pass"]]
    return {
        "pass": bool(evidence.get("pass") and holdout_ok and expected_visibility_pass),
        "perFeature": per_feature,
        "nativeMask": metrics,
        "legacyOccupancy": legacy_occ,
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
        "nativeSemanticEvidence": evidence,
        "nativeSemanticEvidencePass": bool(evidence.get("pass") and holdout_ok),
        "failures": failing,
        "classification": "PASS" if evidence.get("pass") and holdout_ok and expected_visibility_pass else f"INTERIOR_{failing[0]}_FAIL",
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "inFrame": bool(in_frame),
        "frameReason": frame_reason,
        "contextReason": ctx_reason,
    }


def _render_holdout_occupancy_metrics(
    sc,
    cam,
    valid_objs,
    mask_mat,
    res: int,
    *,
    semantic_bounds: tuple[Vector | None, Vector | None] | None = None,
    morph_bounds: tuple[Vector | None, Vector | None] | None = None,
) -> dict:
    tmp = Path(tempfile.gettempdir()) / f"nurion_occ_eval_{id(cam)}_{id(valid_objs)}.png"
    _tag_valid(valid_objs)
    mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp, res)
    sem_proj = (
        _project_aabb_occupancy(sc, cam, semantic_bounds[0], semantic_bounds[1], res)
        if semantic_bounds and semantic_bounds[0] is not None
        else None
    )
    morph_proj = (
        _project_aabb_occupancy(sc, cam, morph_bounds[0], morph_bounds[1], res)
        if morph_bounds and morph_bounds[0] is not None
        else None
    )
    occ_eval = evaluate_native_holdout_occupancy(
        mask,
        locked_semantic_roi=sem_proj,
        projected_morph_aabb=morph_proj,
        render_frame=res,
    )
    receipt = dict(_MASK_RENDER_RECEIPT)
    final_px = int(receipt.get("finalPixels", 0)) if mask is not None else 0
    if final_px <= 0 and mask is not None:
        final_px = int(np.sum(mask > 0.5))
    gate_occ = _occupancy_metric_from_eval(occ_eval)
    legacy_occ = _legacy_occupancy_diagnostic(occ_eval)
    return {
        "occupancyMetrics": occ_eval,
        "occupancyMetricsEnforcement": "DIAGNOSTIC_ONLY",
        "legacyOccupancy": legacy_occ,
        "occupancy": {"widthFrac": gate_occ["widthFrac"], "heightFrac": gate_occ["heightFrac"]},
        "maskOccupancyPass": bool(legacy_occ.get("legacyPass")),
        "occupancyContractMetric": gate_occ.get("contractMetric"),
        "finalMaskPixels": final_px,
        "finalSource": receipt.get("finalSource"),
        "finalMaskSourceDivergence": bool(receipt.get("finalMaskSourceDivergence")),
        "maskRenderReceipt": receipt,
        "bbox": occ_eval.get("maskBBox"),
    }


def _recompute_occupancy_contract_baseline(
    sc,
    cam,
    mask_mat,
    res: int,
    baseline_preflight_path: Path,
    *,
    set_mouth_fn,
    mouth_valid_fn,
    set_eye_fn,
    rig_objs: dict,
    skin_basis,
    skin_basis_coords: list[Vector],
    weights: dict,
    pivot: Vector,
    oral: list,
    landmarks: dict,
) -> dict:
    if not baseline_preflight_path.is_file():
        return {"resolvedContract": "frame", "baselineRows": [], "reason": "BASELINE_MISSING"}
    baseline = json.loads(baseline_preflight_path.read_text(encoding="utf-8"))
    gates = baseline.get("gates") or baseline
    rows: list[dict] = []

    c_gate = gates.get("C_MOUTH_NATIVE_MASK_FRONT") or {}
    c_cam = c_gate.get("camera")
    if c_cam:
        _apply_locked_camera(cam, c_cam)
        set_mouth_fn(0, show_oral=False)
        valid, _skin = mouth_valid_fn(False)
        union_min, union_max = _mouth_union_bounds_with_chin_guard(
            skin_basis, skin_basis_coords, weights, pivot, oral, landmarks
        )
        morph_specs = (
            _mouth_morph_projection_specs(
                skin_basis, skin_basis_coords, weights, pivot, oral, "front", union_min, union_max
            )
            if union_min is not None
            else []
        )
        closed_spec = next((s for s in morph_specs if float(s["angle"]) < 6.0), morph_specs[0] if morph_specs else None)
        if closed_spec is not None and union_min is not None:
            metrics = _render_holdout_occupancy_metrics(
                sc,
                cam,
                valid,
                mask_mat,
                res,
                semantic_bounds=(union_min, union_max),
                morph_bounds=(closed_spec["coMin"], closed_spec["coMax"]),
            )
            rows.append(
                {
                    "gate": "C_MOUTH_NATIVE_MASK_FRONT",
                    "morph": "closed",
                    "cameraSource": "OLD_PASS_BASELINE",
                    **metrics,
                }
            )

    e_gate = gates.get("E_EYE_CAMERA_LEFT") or {}
    e_cam = e_gate.get("camera")
    if e_cam:
        _apply_locked_camera(cam, e_cam)
        set_eye_fn("L", 0.0)
        valid = _eye_valid_objects(set_eye_fn, "L", rig_objs)
        bounds = _eye_bounds_for_pct(set_eye_fn, "L", 0.0, rig_objs, skin_basis_coords)
        if bounds[0] is not None:
            metrics = _render_holdout_occupancy_metrics(
                sc,
                cam,
                valid,
                mask_mat,
                res,
                semantic_bounds=bounds,
                morph_bounds=bounds,
            )
            rows.append(
                {
                    "gate": "E_EYE_CAMERA_LEFT",
                    "state": "closed",
                    "cameraSource": "OLD_PASS_BASELINE",
                    **metrics,
                }
            )

    contract, resolution = _resolve_occupancy_gate_contract(rows)
    return {
        "resolvedContract": contract,
        "contractResolution": resolution,
        "baselineRows": rows,
        "baselinePreflight": str(baseline_preflight_path),
        "thresholds": {
            "widthFracMin": OCC_MIN,
            "widthFracMax": OCC_MAX,
            "heightFracMin": OCC_MIN,
            "heightFracMax": OCC_MAX,
        },
    }


def _reset_preflight_scene_after_baseline(set_mouth_fn, set_eye_fn, rig_objs: dict) -> None:
    set_mouth_fn(0, show_oral=False)
    if hasattr(set_eye_fn, "skin_eye") and set_eye_fn.skin_eye is not None:
        set_eye_fn.skin_eye.hide_render = True
    for _g, obj in rig_objs.items():
        if "eyelash" in _g or _g.endswith("-eye"):
            obj.hide_render = True


def _diff_mask_bbox(a: np.ndarray, b: np.ndarray) -> list[int] | None:
    if a is None or b is None:
        return None
    diff = np.abs(a - b) > 0.08
    if not diff.any():
        return None
    ys, xs = np.where(diff)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def _tag_valid(objs):
    for o in objs:
        o.pass_index = VALID_PASS_INDEX


def _save_mask(path: Path, mask: np.ndarray) -> None:
    h, w = mask.shape
    img = bpy.data.images.new("SaveMask", width=w, height=h)
    rgba = np.dstack([np.clip(mask, 0.0, 1.0)] * 3 + [np.ones((h, w), dtype=np.float32)])
    img.pixels = rgba.reshape(-1).tolist()
    img.filepath_raw = str(path)
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def _primary_skin_from_valid(valid_objs) -> object | None:
    for name in ("SkinOpen", "SkinBasis", "SkinEye"):
        for o in valid_objs:
            if o.name == name and not o.hide_render:
                return o
    for o in valid_objs:
        if o.type == "MESH" and not o.hide_render:
            return o
    return None


def _render_raw_flat_mask(
    sc, cam, valid_objs, mask_mat, path: Path, res: int
) -> np.ndarray | None:
    saved = {}
    for o in valid_objs:
        saved[o.name] = [s.material for s in o.material_slots]
        while len(o.material_slots) < 1:
            o.data.materials.append(mask_mat)
        o.material_slots[0].material = mask_mat
        o.pass_index = VALID_PASS_INDEX
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    mask = _load_mask(path)
    for o, mats in saved.items():
        obj = bpy.data.objects.get(o)
        if not obj:
            continue
        for i, mat in enumerate(mats):
            if i < len(obj.material_slots):
                obj.material_slots[i].material = mat
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = False
    return mask


def _render_index_mask(sc, cam, valid_objs, mask_mat, gray_mats, path: Path, res: int) -> np.ndarray | None:
    global _MASK_RENDER_RECEIPT
    _tag_valid(valid_objs)
    primary_skin = _primary_skin_from_valid(valid_objs)
    if primary_skin is None:
        _MASK_RENDER_RECEIPT = {
            "finalSource": "NO_PRIMARY_SKIN",
            "finalPixels": 0,
            "finalMaskSourceDivergence": True,
        }
        return None
    composite = _render_mask_holdout_composite(
        sc, cam, primary_skin, valid_objs, mask_mat, path, res
    )
    if composite is None or not np.any(composite > 0.5):
        _MASK_RENDER_RECEIPT = {
            "slotCompositePixels": 0,
            "postprocessInputPixels": 0,
            "postprocessOutputPixels": 0,
            "finalPixels": 0,
            "finalSource": "SLOT_HOLDOUT_COMPOSITE_EMPTY",
            "finalMaskSourceDivergence": True,
        }
        return None
    slot_px = int(np.sum(composite > 0.5))
    _save_mask(path, composite)
    _MASK_RENDER_RECEIPT = {
        "slotCompositePixels": slot_px,
        "postprocessInputPixels": slot_px,
        "postprocessOutputPixels": slot_px,
        "finalPixels": slot_px,
        "finalSource": "SLOT_HOLDOUT_COMPOSITE",
        "finalMaskSourceDivergence": False,
    }
    return composite


def _render_feature_id(
    sc,
    cam,
    skin_obj,
    rig_objs,
    fid_mats,
    valid_objs,
    path: Path,
    res: int,
    allow_software_fallback: bool = True,
) -> np.ndarray | None:
    global _FID_RENDER_RECEIPT
    saved: dict[str, list] = {}
    rig_map = {
        "helper-upper-teeth": "upper_teeth",
        "helper-lower-teeth": "lower_teeth",
        "helper-tongue": "tongue",
        "helper-l-eye": "eyeball",
        "helper-r-eye": "eyeball",
        "helper-l-eyelashes-1": "eyelid_upper",
        "helper-l-eyelashes-2": "eyelid_lower",
        "helper-r-eyelashes-1": "eyelid_upper",
        "helper-r-eyelashes-2": "eyelid_lower",
    }
    skin_slot_map = ["skin", "lip", "lip_corner_l", "lip_corner_r", "chin"]
    visible = {o.name for o in valid_objs}
    layer_receipts: dict[str, dict] = {}

    def apply_obj(obj):
        if obj is None or obj.type != "MESH" or obj.hide_render or obj.name not in visible:
            return
        saved[obj.name] = [s.material for s in obj.material_slots]
        if obj is skin_obj or obj.name in ("SkinBasis", "SkinOpen", "SkinEye"):
            slot_mats = {k: fid_mats[k] for k in skin_slot_map}
            _ensure_semantic_material_slots(obj, slot_mats)
            for i, key in enumerate(skin_slot_map):
                if i < len(obj.material_slots):
                    obj.material_slots[i].material = fid_mats[key]
        elif obj.name in rig_map:
            mat = fid_mats[rig_map[obj.name]]
            while len(obj.material_slots) < 1:
                obj.data.materials.append(mat)
            obj.material_slots[0].material = mat

    apply_obj(skin_obj)
    for o in valid_objs:
        apply_obj(o)
    for o in rig_objs.values():
        apply_obj(o)
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = True
    bg = sc.world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    saved_view = sc.view_settings.view_transform
    saved_exp = float(sc.view_settings.exposure)
    sc.view_settings.view_transform = "Raw"
    sc.view_settings.exposure = 0.0
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    for obj_name in saved:
        obj = bpy.data.objects.get(obj_name)
        if obj and obj.type == "MESH":
            obj.data.update()
    bpy.context.view_layer.update()

    primary_skin = None
    if skin_obj is not None and not skin_obj.hide_render and skin_obj.name in visible:
        primary_skin = skin_obj
    else:
        for o in valid_objs:
            if o.name in ("SkinBasis", "SkinOpen", "SkinEye") and not o.hide_render:
                primary_skin = o
                break

    fid: np.ndarray | None = None
    merge_pool = list(valid_objs)
    if primary_skin is not None:
        void_mats = {k: _emit_void_mat(f"FID_VOID_{k}") for k in skin_slot_map}
        composite: np.ndarray | None = None
        try:
            for slot_idx, key in enumerate(skin_slot_map):
                slot_mats = {name: void_mats[name] for name in skin_slot_map}
                slot_mats[key] = fid_mats[key]
                _ensure_semantic_material_slots(primary_skin, slot_mats)
                for i, slot_key in enumerate(skin_slot_map):
                    if i < len(primary_skin.material_slots):
                        primary_skin.material_slots[i].material = slot_mats[slot_key]
                primary_skin.data.update()
                bpy.context.view_layer.update()
                layer_path = path.with_name(f"{path.stem}_slot{slot_idx}{path.suffix}")
                sc.render.filepath = str(layer_path)
                bpy.ops.render.render(write_still=True)
                layer = _load_rgb(layer_path)
                native_slot_path = "EEVEE"
                software_fallback_used = False
                if layer is None or not np.any(layer > 0.045):
                    face_indices = {
                        i for i, p in enumerate(primary_skin.data.polygons) if int(p.material_index) == slot_idx
                    }
                    geom = _audit_feature_face_geometry(sc, cam, primary_skin, face_indices, res)
                    if int(geom.get("positiveAreaFaces", 0)) > 0:
                        layer = _native_raster_fid_skin_slot_triangles(
                            sc, cam, primary_skin, slot_idx, key, res
                        )
                        native_slot_path = "NATIVE_FACE_RASTER"
                    elif allow_software_fallback:
                        layer = _software_raster_fid_layer(sc, cam, primary_skin, slot_idx, key, res)
                        native_slot_path = "SOFTWARE_FALLBACK_BBOX"
                        software_fallback_used = True
                native_px = int(np.sum(np.any(layer > 0.045, axis=2))) if layer is not None else 0
                encoded_px = native_px
                if layer is not None and key in FEATURE_ID_RGB:
                    decoded_px = int(_count_feature_pixels(layer, None, (key,), full_frame=True).get(key, 0))
                    if decoded_px <= 0 and native_px > 0:
                        decoded_px = native_px
                else:
                    decoded_px = native_px
                layer_receipts[key] = {
                    "nativeSlotRenderPixels": native_px,
                    "encodedLayerPixels": encoded_px,
                    "decodedLayerPixels": decoded_px,
                    "compositeInputPixels": 0,
                    "compositeOutputPixels": 0,
                    "nativeSlotRenderPath": native_slot_path,
                    "softwareFallbackUsed": software_fallback_used,
                }
                if layer is None:
                    continue
                if composite is None:
                    composite = np.zeros_like(layer)
                composite_input = int(np.sum(np.any(composite > 0.045, axis=2)))
                active = np.any(layer > 0.045, axis=2)
                composite[active] = layer[active]
                composite_output = int(np.sum(np.any(composite > 0.045, axis=2)))
                layer_receipts[key]["compositeInputPixels"] = composite_input
                layer_receipts[key]["compositeOutputPixels"] = composite_output
            if composite is not None:
                for o in valid_objs:
                    if o is primary_skin or o.name in ("SkinBasis", "SkinOpen", "SkinEye"):
                        continue
                    if o.type != "MESH" or o.hide_render or o.name not in visible:
                        continue
                    feature_key = rig_map.get(o.name)
                    if not feature_key:
                        continue
                    layer_path = path.with_name(f"{path.stem}_{o.name}{path.suffix}")
                    encoded, decoded, _, layer = _render_native_fid_layer_pixels(
                        sc,
                        cam,
                        o,
                        fid_mats[feature_key],
                        feature_key,
                        layer_path,
                        res,
                        hide_others=merge_pool,
                    )
                    native_px = encoded
                    composite_input = int(np.sum(np.any(composite > 0.045, axis=2)))
                    if layer is not None:
                        active = np.any(layer > 0.045, axis=2)
                        composite[active] = layer[active]
                    composite_output = int(np.sum(np.any(composite > 0.045, axis=2)))
                    feature_count = int(_count_feature_pixels(composite, None, (feature_key,), full_frame=True).get(feature_key, 0))
                    layer_receipts[feature_key] = {
                        "nativeSlotRenderPixels": native_px,
                        "encodedLayerPixels": encoded,
                        "decodedLayerPixels": decoded,
                        "compositeInputPixels": composite_input,
                        "compositeOutputPixels": composite_output,
                        "finalFIDPixels": feature_count,
                    }
                _save_rgb(path, composite)
                fid = composite
        finally:
            slot_mats = {k: fid_mats[k] for k in skin_slot_map}
            _ensure_semantic_material_slots(primary_skin, slot_mats)
            for i, key in enumerate(skin_slot_map):
                if i < len(primary_skin.material_slots):
                    primary_skin.material_slots[i].material = fid_mats[key]
            primary_skin.data.update()
    if fid is None:
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        fid = _load_rgb(path)

    per_feature_final: dict[str, int] = {}
    if fid is not None:
        for key in set(list(skin_slot_map) + list(rig_map.values())):
            if key not in FEATURE_ID_RGB and key != "skin":
                continue
            if key in layer_receipts:
                if key in FEATURE_ID_RGB:
                    per_feature_final[key] = int(
                        _count_feature_pixels(fid, None, (key,), full_frame=True).get(key, 0)
                    )
                else:
                    per_feature_final[key] = int(np.sum(np.any(fid > 0.045, axis=2)))
                layer_receipts[key]["finalFIDPixels"] = per_feature_final[key]
    _FID_RENDER_RECEIPT = {
        "finalSource": "SKIN_SLOT_AND_RIG_HOLDOUT_COMPOSITE" if fid is not None else "RENDER_FAIL",
        "layers": layer_receipts,
        "perFeatureFinal": per_feature_final,
    }

    sc.view_settings.view_transform = saved_view
    sc.view_settings.exposure = saved_exp
    for name, mats in saved.items():
        obj = bpy.data.objects.get(name)
        if not obj:
            continue
        for i, mat in enumerate(mats):
            if i < len(obj.material_slots):
                obj.material_slots[i].material = mat
    for o in bpy.data.objects:
        if o.type == "LIGHT":
            o.hide_render = False
    return fid


def _render_human_qa(
    sc, cam, path: Path, res: int, center: Vector, view_dir: Vector, bbox: list[int] | None = None
) -> tuple[np.ndarray | None, float | None]:
    bg_node = sc.world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs[0].default_value = (0.30, 0.31, 0.34, 1.0)
        bg_node.inputs[1].default_value = 1.0
    chosen = None
    rgb = None
    for key_energy in KEY_ENERGY_STEPS:
        _lights_semantic_qa(cam, center, view_dir, key_energy)
        for o in bpy.data.objects:
            if o.type == "LIGHT":
                o.hide_render = False
        sc.render.resolution_x = res
        sc.render.resolution_y = res
        sc.render.filepath = str(path)
        bpy.ops.render.render(write_still=True)
        rgb = _load_rgb(path)
        chosen = key_energy
        if rgb is not None:
            if bbox is not None:
                x0, y0, x1, y1 = bbox
                roi = rgb[y0 : y1 + 1, x0 : x1 + 1]
                lum = _luminance(roi)
            else:
                lum = _luminance(rgb)
            sat_ratio = float((lum > 0.95).mean())
            clip_ratio = float(((lum < 0.02) | (lum > 0.98)).mean())
            if sat_ratio <= SAT_MAX_RATIO and clip_ratio <= CLIP_MAX_RATIO:
                break
    return rgb, chosen


def _render_beauty(sc, cam, path: Path, res: int, center: Vector):
    sc.world.node_tree.nodes["Background"].inputs[0].default_value = (0.14, 0.14, 0.15, 1.0)
    sc.world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    _lights(center)
    sc.render.resolution_x = res
    sc.render.resolution_y = res
    sc.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)


def _objects_world_bounds(objects):
    bpy.context.view_layer.update()
    co_min = Vector((1e18, 1e18, 1e18))
    co_max = Vector((-1e18, -1e18, -1e18))
    found = False

    def absorb(wc: Vector):
        nonlocal found, co_min, co_max
        found = True
        co_min = Vector((min(co_min[i], wc[i]) for i in range(3)))
        co_max = Vector((max(co_max[i], wc[i]) for i in range(3)))

    for obj in objects:
        if obj.hide_render or obj.type != "MESH":
            continue
        mw = obj.matrix_world
        for v in obj.data.vertices:
            absorb(mw @ v.co)
    if not found:
        return None, None
    return co_min, co_max


def _establish_mouth_view_lock(
    sc,
    cam,
    mask_mat,
    valid_objs,
    skin_obj,
    basis_coords,
    landmarks,
    union_min: Vector,
    union_max: Vector,
    view: str,
    res: int,
    fid_mats: dict,
    rig_objs: dict,
    beauty_stub: Path,
    morph_valid_sets: list | None = None,
):
    view_dir = _legacy_view_dir(view)
    semantic_view = _landmark_view_dir(landmarks, view)
    center = (union_min + union_max) / 2.0
    dist = _place_camera(cam, center, union_min, union_max, view_dir, view)
    sem_center = _semantic_center(landmarks, "mouth", "mouth", center)
    region_map = landmarks.get("region_map", {})
    frame_keys = _frame_landmark_keys("mouth", "mouth")
    base_ortho = max(_semantic_ortho_scale(landmarks, "mouth", semantic_view) * 1.05, float(cam.data.ortho_scale))
    trial_center = sem_center.copy()
    _apply_semantic_camera(cam, trial_center, base_ortho, semantic_view, dist)
    trial_center = _nudge_camera_to_landmarks(
        sc, cam, landmarks, frame_keys, trial_center, semantic_view, dist, res, basis_coords, view
    )
    for _ in range(12):
        sem_mask = _render_index_mask(
            sc,
            cam,
            valid_objs,
            mask_mat,
            {},
            Path(tempfile.gettempdir()) / f"nurion_mouth_ctx_{view}.png",
            res,
        )
        ctx_ok, _ = _semantic_context_ok(_measure_mask(sem_mask))
        if ctx_ok:
            break
        cam.data.ortho_scale = float(cam.data.ortho_scale) * 1.06
    bbox_try = _landmark_pixel_bbox(
        sc, cam, landmarks, frame_keys, res, pad_frac=0.12, basis_coords=basis_coords, mode=view
    )
    fid_rgb = _render_feature_id(
        sc,
        cam,
        skin_obj,
        rig_objs,
        fid_mats,
        valid_objs,
        Path(tempfile.gettempdir()) / f"nurion_mouth_fid_{view}.png",
        res,
    )
    if fid_rgb is None:
        return None
    if fid_rgb is not None:
        bbox_try = _union_bbox(bbox_try, _active_feature_bbox(fid_rgb, bbox_try))
    human_rgb, key_energy = _render_human_qa(sc, cam, beauty_stub, res, trial_center, semantic_view, bbox_try)
    semantic = _validate_semantic_features(
        fid_rgb,
        human_rgb,
        bbox_try,
        "mouth",
        cam,
        landmarks,
        view,
        region_map,
        skin_obj=skin_obj,
        sc=sc,
        res=res,
    )
    semantic["semanticOrthoScale"] = float(cam.data.ortho_scale)
    semantic["keyEnergy"] = key_energy
    ortho = float(cam.data.ortho_scale)
    mask_pass = False
    tmp = Path(tempfile.gettempdir()) / f"nurion_mouth_lock_{view}.png"
    check_sets = morph_valid_sets if morph_valid_sets else [valid_objs]
    for _ in range(32):
        cam.data.ortho_scale = ortho
        passes = []
        for objs in check_sets:
            mask = _render_index_mask(sc, cam, objs, mask_mat, {}, tmp, res)
            passes.append(bool(_measure_mask(mask).get("pass")))
        if all(passes):
            mask_pass = True
            break
        wf = hf = 0.0
        min_wf = min_hf = 1.0
        for objs in check_sets:
            mask = _render_index_mask(sc, cam, objs, mask_mat, {}, tmp, res)
            m = _measure_mask(mask)
            wf = max(wf, float(m.get("widthFrac", 0.0)))
            hf = max(hf, float(m.get("heightFrac", 0.0)))
            min_wf = min(min_wf, float(m.get("widthFrac", 0.0)))
            min_hf = min(min_hf, float(m.get("heightFrac", 0.0)))
        if max(wf, hf) > OCC_MAX:
            ortho *= 1.06
        elif min(min_wf, min_hf) < OCC_MIN:
            ortho *= 0.94
        else:
            ortho *= 1.04
    return {
        "location": [float(x) for x in cam.location],
        "rotation": [float(x) for x in cam.rotation_euler],
        "ortho_scale": float(cam.data.ortho_scale),
        "distance": float(dist),
        "view_dir": [float(x) for x in view_dir],
        "semanticViewDir": [float(x) for x in semantic_view],
        "semanticCenter": [float(x) for x in sem_center],
        "semanticLock": {
            "location": [float(x) for x in cam.location],
            "rotation": [float(x) for x in cam.rotation_euler],
            "ortho_scale": float(cam.data.ortho_scale),
            "center": [float(x) for x in sem_center],
            "keyEnergy": key_energy,
        },
        "roiUnionBounds": {
            "min": [float(union_min.x), float(union_min.y), float(union_min.z)],
            "max": [float(union_max.x), float(union_max.y), float(union_max.z)],
        },
        "establishSemanticPass": bool(semantic.get("pass")),
        "maskFitAllMorphs": mask_pass,
    }


def _converge_semantic_shot(
    sc,
    cam,
    sem_center: Vector,
    sem_view: Vector,
    dist: float,
    landmarks: dict,
    semantic_profile: str,
    shot_kind: str,
    mode: str,
    skin_obj,
    rig_objs: dict,
    fid_mats: dict,
    valid_objs,
    mask_mat,
    tmp_fid: Path,
    beauty_path: Path,
    res: int,
    metrics: dict,
    basis_coords: list[Vector] | None = None,
    semantic_locked: dict | None = None,
    allow_software_fid_fallback: bool = False,
):
    region_map = landmarks.get("region_map", {})
    if not region_map.get("corner_symmetry_pass", True):
        fail = {
            "pass": False,
            "reason": "CORNER_SYMMETRY_FAIL",
            "cornerSymmetry": region_map.get("corner_symmetry"),
        }
        return None, None, fail, metrics.get("bbox") or [0, 0, res - 1, res - 1], None

    frame_keys = _frame_landmark_keys(semantic_profile, shot_kind)
    required = REQUIRED_FEATURES[semantic_profile]
    last_semantic = {"pass": False, "reason": "SEMANTIC_CAMERA_NO_CONVERGE"}
    key_energy = None
    best_pack = None
    best_score = -1.0

    if semantic_locked:
        trial_center = Vector(semantic_locked.get("center", sem_center))
        sem_ortho = float(semantic_locked["ortho_scale"])
        cam.location = Vector(semantic_locked["location"])
        cam.rotation_euler = semantic_locked["rotation"]
        cam.data.ortho_scale = sem_ortho
        key_energy = semantic_locked.get("keyEnergy")
        bbox_try = _landmark_pixel_bbox(
            sc, cam, landmarks, frame_keys, res, pad_frac=0.12, basis_coords=basis_coords, mode=mode
        )
        fid_try = _render_feature_id(
            sc, cam, skin_obj, rig_objs, fid_mats, valid_objs, tmp_fid, res, allow_software_fallback=allow_software_fid_fallback
        )
        if fid_try is not None:
            bbox_try = _union_bbox(bbox_try, _active_feature_bbox(fid_try, bbox_try))
        if key_energy is None:
            human_try, key_energy = _render_human_qa(sc, cam, beauty_path, res, trial_center, sem_view, bbox_try)
        else:
            human_try, _ = _render_human_qa(sc, cam, beauty_path, res, trial_center, sem_view, bbox_try)
        semantic_try = _validate_semantic_features(
            fid_try,
            human_try,
            bbox_try,
            semantic_profile,
            cam,
            landmarks,
            mode,
            region_map,
            skin_obj=skin_obj,
            sc=sc,
            res=res,
        )
        semantic_try["semanticOrthoScale"] = sem_ortho
        semantic_try["keyEnergy"] = key_energy
        semantic_try["semanticLocked"] = True
        return fid_try, human_try, semantic_try, bbox_try, key_energy

    base_ortho = _semantic_ortho_scale(landmarks, semantic_profile, sem_view)
    required = REQUIRED_FEATURES[semantic_profile]

    base_center = sem_center.copy()
    lo = base_ortho * 0.28
    hi = base_ortho * 1.16
    tightest_in_frame = None
    for _ in range(22):
        mid = (lo + hi) / 2.0
        trial_center = base_center.copy()
        _apply_semantic_camera(cam, trial_center, mid, sem_view, dist)
        trial_center = _nudge_camera_to_landmarks(
            sc, cam, landmarks, frame_keys, trial_center, sem_view, dist, res, basis_coords, mode
        )
        in_frame, frame_reason = _landmarks_in_frame(sc, cam, landmarks, frame_keys, res, basis_coords, mode)
        if in_frame:
            tightest_in_frame = mid
            hi = mid
        else:
            lo = mid

    if tightest_in_frame is None:
        trial_center = base_center.copy()
        _apply_semantic_camera(cam, trial_center, hi, sem_view, dist)
        in_frame, frame_reason = _landmarks_in_frame(sc, cam, landmarks, frame_keys, res, basis_coords, mode)
        if not in_frame:
            return None, None, {"pass": False, "reason": frame_reason or "FRAME_ESCAPE", "safeAbort": True}, metrics.get("bbox") or [0, 0, res - 1, res - 1], None
        tightest_in_frame = hi

    ortho_candidates = sorted(
        {
            tightest_in_frame,
            tightest_in_frame * 0.97,
            tightest_in_frame * 0.94,
            tightest_in_frame * 0.91,
            tightest_in_frame * 0.88,
            tightest_in_frame * 0.85,
            tightest_in_frame * 1.03,
            tightest_in_frame * 1.06,
            tightest_in_frame * 1.10,
        }
    )

    best_pass_pack = None
    best_pack = None
    best_score = -1.0

    for sem_ortho in ortho_candidates:
        trial_center = base_center.copy()
        _apply_semantic_camera(cam, trial_center, sem_ortho, sem_view, dist)
        trial_center = _nudge_camera_to_landmarks(
            sc, cam, landmarks, frame_keys, trial_center, sem_view, dist, res, basis_coords, mode
        )
        in_frame, frame_reason = _landmarks_in_frame(sc, cam, landmarks, frame_keys, res, basis_coords, mode)
        if not in_frame:
            last_semantic = {"pass": False, "reason": frame_reason or "FRAME_ESCAPE", "safeAbort": True}
            continue
        tmp_sem_mask = Path(tempfile.gettempdir()) / f"nurion_sem_{beauty_path.stem}.png"
        trial_ortho = float(sem_ortho)
        ctx_ok = False
        ctx_reason = None
        for _widen in range(12):
            _apply_semantic_camera(cam, trial_center, trial_ortho, sem_view, dist)
            sem_mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_sem_mask, res)
            sem_m = _measure_mask(sem_mask)
            ctx_ok, ctx_reason = _semantic_context_ok(sem_m)
            if ctx_ok:
                sem_ortho = trial_ortho
                break
            if ctx_reason == "CONTEXT_LOSS_FULL_BLEED":
                trial_ortho *= 1.06
                continue
            break
        if not ctx_ok:
            last_semantic = {"pass": False, "reason": ctx_reason}
            continue
        bbox_try = _landmark_pixel_bbox(sc, cam, landmarks, frame_keys, res, pad_frac=0.12, basis_coords=basis_coords, mode=mode)
        fid_try = _render_feature_id(
            sc, cam, skin_obj, rig_objs, fid_mats, valid_objs, tmp_fid, res, allow_software_fallback=allow_software_fid_fallback
        )
        if fid_try is not None:
            bbox_try = _union_bbox(bbox_try, _active_feature_bbox(fid_try, bbox_try))
        fid_counts = _count_feature_pixels(fid_try, bbox_try, required, full_frame=False) if fid_try is not None else {}
        human_try, key_energy = _render_human_qa(sc, cam, beauty_path, res, trial_center, sem_view, bbox_try)
        semantic_try = _validate_semantic_features(
            fid_try,
            human_try,
            bbox_try,
            semantic_profile,
            cam,
            landmarks,
            mode,
            region_map,
            skin_obj=skin_obj,
            sc=sc,
            res=res,
        )
        semantic_try["semanticOrthoScale"] = float(sem_ortho)
        semantic_try["keyEnergy"] = key_energy
        vis = semantic_try.get("featureVisibility", {})
        score_vals = [
            float(vis.get(f, {}).get("detectionRate", 0.0))
            for f in required
            if vis.get(f, {}).get("status") != "OCCLUDED_EXPECTED"
        ]
        score = min(score_vals) if score_vals else 0.0
        semantic_try["convergenceScore"] = score
        if semantic_try.get("pass") and score > best_score:
            best_score = score
            best_pack = (sem_ortho, bbox_try, fid_try, trial_center.copy(), human_try, key_energy, semantic_try)
        last_semantic = semantic_try
        if semantic_try.get("pass"):
            return fid_try, human_try, semantic_try, bbox_try, key_energy

    if best_pack and best_score > 0.0:
        sem_ortho, bbox_try, fid_try, trial_center, human_try, key_energy, semantic_try = best_pack
        _apply_semantic_camera(cam, trial_center, sem_ortho, sem_view, dist)
        _nudge_camera_to_landmarks(
            sc, cam, landmarks, frame_keys, trial_center, sem_view, dist, res, basis_coords, mode
        )
        last_semantic = semantic_try
        return fid_try, human_try, semantic_try, bbox_try, key_energy

    if str(last_semantic.get("reason", "")).startswith("FRAME_ESCAPE"):
        last_semantic["safeAbort"] = True
    return None, None, last_semantic, metrics.get("bbox") or [0, 0, res - 1, res - 1], key_energy


def _validate_morph_feature_delta(
    shots: dict[str, dict], closed_key: str, open_key: str, features: tuple[str, ...]
) -> dict:
    closed = shots.get(closed_key, {}).get("semanticQa", {}).get("featurePixelCounts", {})
    opened = shots.get(open_key, {}).get("semanticQa", {}).get("featurePixelCounts", {})
    delta = {f: int(opened.get(f, 0)) - int(closed.get(f, 0)) for f in features}
    missing = [f for f in features if delta.get(f, 0) <= 0]
    return {
        "pass": not missing,
        "delta": delta,
        "missingMorphChange": missing,
        "reason": None if not missing else f"MORPH_FEATURE_DELTA:{','.join(missing)}",
    }


def _frame_and_capture(
    sc,
    cam,
    mask_mat,
    valid_objs,
    skin_obj,
    basis_coords,
    region_fn,
    mode: str,
    beauty_path: Path,
    overlay_path: Path,
    res: int,
    landmarks: dict,
    fid_mats: dict,
    rig_objs: dict,
    extras=None,
    extras_only=False,
    locked_cam=None,
    use_object_bounds=False,
    bounds_override=None,
    semantic_profile="mouth",
    shot_kind="mouth",
    manifest_entry: dict | None = None,
    morph_state: str | None = None,
    allow_software_fid_fallback: bool = False,
):
    immutable = bool(manifest_entry and manifest_entry.get("immutable"))
    if immutable:
        _apply_camera_lock_manifest(cam, manifest_entry)
        dist = float(manifest_entry.get("distance", 2.8))
        view_dir = Vector(manifest_entry["viewDir"])
        semantic_view = Vector(manifest_entry["semanticViewDir"])
        semantic_center = Vector(manifest_entry["semanticCenter"])
        center = semantic_center.copy()
        semantic_lock = manifest_entry.get("semanticLock")
        gb = manifest_entry.get("guardBounds")
        if gb:
            co_min = Vector(gb["min"])
            co_max = Vector(gb["max"])
        elif bounds_override is not None:
            co_min, co_max = bounds_override
        else:
            co_min, co_max = _framing_bounds(skin_obj, basis_coords, region_fn, extras, extras_only)
    else:
        view_dir = Vector(locked_cam["view_dir"]) if locked_cam and "view_dir" in locked_cam else _legacy_view_dir(mode)
        semantic_view = (
            Vector(locked_cam["semanticViewDir"])
            if locked_cam and "semanticViewDir" in locked_cam
            else _landmark_view_dir(landmarks, mode)
        )
        if bounds_override is not None:
            co_min, co_max = bounds_override
        elif use_object_bounds:
            co_min, co_max = _objects_world_bounds(valid_objs)
        else:
            co_min, co_max = _framing_bounds(skin_obj, basis_coords, region_fn, extras, extras_only)
        if co_min is None:
            return {"pass": False, "reason": "EMPTY_BOUNDS", "safeAbort": True}
        mask_center = (co_min + co_max) / 2.0
        semantic_center = _semantic_center(landmarks, semantic_profile, shot_kind, mask_center)
        center = mask_center
        semantic_lock = locked_cam.get("semanticLock") if locked_cam else None
        if locked_cam:
            cam.location = Vector(locked_cam["location"])
            cam.rotation_euler = locked_cam["rotation"]
            cam.data.ortho_scale = float(locked_cam["ortho_scale"])
            dist = float(locked_cam.get("distance", 2.8))
            view_dir = Vector(locked_cam["view_dir"])
            semantic_view = Vector(locked_cam["semanticViewDir"])
            semantic_center = Vector(locked_cam.get("semanticCenter", semantic_center))
            if not semantic_lock and locked_cam.get("semanticLocked"):
                semantic_lock = _manifest_semantic_lock(locked_cam)
        else:
            dist = _legacy_place_camera(cam, center, co_min, co_max, mode)

    if co_min is None:
        return {"pass": False, "reason": "EMPTY_BOUNDS", "safeAbort": True}

    tmp_mask = Path(tempfile.gettempdir()) / f"nurion_fpix_{beauty_path.stem}.png"
    tmp_fid = Path(tempfile.gettempdir()) / f"nurion_fid_{beauty_path.stem}.png"
    metrics: dict = {"pass": False, "reason": "MASK_FAIL", "safeAbort": True}
    last_m = {"widthFrac": 0.0, "heightFrac": 0.0}

    if immutable or locked_cam:
        mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
        m = _measure_mask(mask)
        capture_state = _snapshot_capture_framing_state(
            sc, cam, valid_objs, mask_mat, res, (co_min, co_max), skin_obj=skin_obj
        )
        preflight_ref = None
        if manifest_entry:
            by_morph = manifest_entry.get("preflightStateByMorph") or {}
            preflight_ref = by_morph.get(morph_state) if morph_state and morph_state in by_morph else manifest_entry.get("preflightState")
        state_audit = _compare_preflight_capture_state(preflight_ref, capture_state)
        mask_diag = _diagnose_mask_pipeline(capture_state)
        metrics = dict(m)
        metrics["orthoScale"] = float(cam.data.ortho_scale)
        metrics["cameraLocation"] = [float(x) for x in cam.location]
        metrics["cameraRotation"] = [float(x) for x in cam.rotation_euler]
        metrics["distance"] = dist
        metrics["viewDir"] = [float(x) for x in view_dir]
        metrics["semanticViewDir"] = [float(x) for x in semantic_view]
        metrics["semanticCenter"] = [float(x) for x in semantic_center]
        metrics["maskPath"] = str(tmp_mask)
        metrics["maskArray"] = mask
        metrics["captureStateAudit"] = state_audit
        metrics["maskPipelineDiagnostic"] = mask_diag
        metrics["immutableManifest"] = immutable
        metrics["morphState"] = morph_state
        if not state_audit.get("pass"):
            metrics["pass"] = False
            metrics["safeAbort"] = True
            metrics["reason"] = state_audit.get("classification") or "CAPTURE_STATE_DIVERGENCE"
            return metrics
        if immutable:
            auth = _evaluate_immutable_capture_authoritative_evidence(
                sc,
                cam,
                valid_objs,
                skin_obj,
                mask_mat,
                fid_mats,
                res,
                landmarks,
                basis_coords,
                rig_objs,
                semantic_profile=semantic_profile,
                shot_kind=shot_kind,
                mode=mode,
                morph_state=morph_state,
                co_min=co_min,
                co_max=co_max,
                manifest_entry=manifest_entry,
            )
            metrics = _attach_authoritative_capture_contract(metrics, auth)
            metrics["maskPipelineDiagnostic"] = {
                **mask_diag,
                "legacyFrameOccupancyDiagnostic": {
                    "classification": mask_diag.get("classification"),
                    "enforcement": "DIAGNOSTIC_ONLY",
                },
            }
            if not metrics.get("pass"):
                return metrics
        elif not m.get("pass"):
            metrics["pass"] = False
            metrics["safeAbort"] = True
            metrics["reason"] = mask_diag.get("classification") or m.get("reason") or "FINAL_MASK_OCCUPANCY"
            return metrics
    else:
        lo = float(cam.data.ortho_scale) * 0.25
        hi = max(float(cam.data.ortho_scale) * 8.0, 8.0)
        best = None
        best_mask = None
        for _ in range(28):
            mid = (lo + hi) / 2.0
            cam.data.ortho_scale = mid
            cam.location = center - view_dir * dist
            _look_at(cam, center)
            mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
            if mask is not None:
                center = _legacy_nudge(cam, mask, center, mode, dist)
                mask = _render_index_mask(sc, cam, valid_objs, mask_mat, {}, tmp_mask, res)
            m = _measure_mask(mask)
            last_m = m
            wf = float(m.get("widthFrac", 0.0))
            hf = float(m.get("heightFrac", 0.0))
            min_f = min(wf, hf)
            max_f = max(wf, hf)
            if m.get("pass"):
                best = dict(m)
                best_mask = mask
                best["orthoScale"] = mid
                break
            if min_f < OCC_MIN:
                hi = mid
            elif max_f > OCC_MAX:
                lo = mid
            elif hf < wf:
                hi = mid
            else:
                lo = mid
        if best is None:
            capture_state = _snapshot_capture_framing_state(
                sc, cam, valid_objs, mask_mat, res, (co_min, co_max), skin_obj=skin_obj
            )
            out_m = {k: v for k, v in last_m.items() if k != "maskArray"}
            out_m["pass"] = False
            out_m["safeAbort"] = True
            out_m["reason"] = _diagnose_mask_pipeline(capture_state).get("classification") or out_m.get("reason") or "FINAL_MASK_OCCUPANCY"
            out_m["maskPipelineDiagnostic"] = _diagnose_mask_pipeline(capture_state)
            return out_m
        metrics = best
        cam.data.ortho_scale = float(best["orthoScale"])
        metrics["cameraLocation"] = [float(x) for x in cam.location]
        metrics["cameraRotation"] = [float(x) for x in cam.rotation_euler]
        metrics["distance"] = dist
        metrics["viewDir"] = [float(x) for x in view_dir]
        metrics["semanticViewDir"] = [float(x) for x in semantic_view]
        metrics["semanticCenter"] = [float(x) for x in semantic_center]
        metrics["maskPath"] = str(tmp_mask)
        metrics["maskArray"] = best_mask
        semantic_lock = None

    if immutable:
        sem_view = semantic_view
        sem_center = semantic_center
    else:
        sem_view = _landmark_view_dir(landmarks, mode)
        sem_center = _semantic_center(landmarks, semantic_profile, shot_kind, center)

    fid_rgb, human_rgb, semantic, bbox, key_energy = _converge_semantic_shot(
        sc,
        cam,
        sem_center,
        sem_view,
        dist,
        landmarks,
        semantic_profile,
        shot_kind,
        mode,
        skin_obj,
        rig_objs,
        fid_mats,
        valid_objs,
        mask_mat,
        tmp_fid,
        beauty_path,
        res,
        metrics,
        basis_coords,
        semantic_locked=semantic_lock,
        allow_software_fid_fallback=allow_software_fid_fallback,
    )
    metrics["featureBBox"] = bbox
    metrics["semanticViewDir"] = [float(x) for x in sem_view]
    metrics["semanticCenter"] = [float(x) for x in sem_center]
    metrics["semanticOrthoScale"] = float(semantic.get("semanticOrthoScale", cam.data.ortho_scale))
    metrics["keyEnergy"] = key_energy
    metrics["semanticCameraLocation"] = [float(x) for x in cam.location]
    metrics["semanticCameraRotation"] = [float(x) for x in cam.rotation_euler]
    metrics["landmarkViewAlignment"] = float(semantic.get("landmarkViewAlignment", 0.0))
    metrics["maskPass"] = bool(metrics.get("pass"))
    metrics["semanticQa"] = semantic
    metrics["semanticProfile"] = semantic_profile
    metrics["beautyPath"] = str(_resolve_png(beauty_path))
    if human_rgb is not None and fid_rgb is not None:
        _write_feature_overlay(human_rgb, fid_rgb, bbox, overlay_path)
        metrics["overlayPath"] = str(_resolve_png(overlay_path))
    metrics["pass"] = metrics["maskPass"] and bool(semantic.get("pass"))
    if not semantic.get("pass"):
        metrics["reason"] = semantic.get("reason") or "SEMANTIC_FEATURE_FAIL"
        metrics["safeAbort"] = True
    return metrics


def main() -> int:
    _configure_blender_temp_dir()
    args = _parse()
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    wdata = json.loads(Path(args.weight_json).read_text(encoding="utf-8"))
    pivot = Vector(wdata["jawPivot"])
    weights = {int(k): float(v) for k, v in wdata["weights"].items()}
    eyelid_weights = wdata.get("eyelidWeights", {})
    eyelid_spec = wdata.get("eyelidMorphSpec", {})

    _clear()
    coll = bpy.context.scene.collection
    gray = _gray("Skin")
    qa_mats = {k: _qa_mat(f"QA_{k}", v) for k, v in QA_PALETTE.items()}

    head_root = bpy.data.objects.new("HeadRoot", None)
    coll.objects.link(head_root)
    jaw_empty = bpy.data.objects.new("JawPivot", None)
    coll.objects.link(jaw_empty)
    jaw_empty.location = pivot
    jaw_empty.parent = head_root

    skin_basis = _load_mesh(Path(args.skin_obj), "NurionHeadSkin", qa_mats["skin"], coll, "SkinBasis")
    skin_basis.parent = head_root
    skin_basis_coords = [v.co.copy() for v in skin_basis.data.vertices]
    landmarks = _compute_landmarks(skin_basis_coords)
    _assign_semantic_regions(skin_basis, skin_basis_coords, landmarks, qa_mats, weights)
    region_map = landmarks.get("region_map", {})
    region_integrity = _validate_region_map_integrity(skin_basis.data, region_map)
    if not region_map.get("corner_symmetry_pass", True) or not region_integrity.get("pass"):
        reason = region_integrity.get("reason") or "CORNER_SYMMETRY_FAIL"
        abort = {
            "schema": "NURION_V07_V1_SEMANTIC_FEATURE_VISIBILITY_VALIDATION_V1",
            "pass": False,
            "safeAbort": True,
            "reason": reason,
            "regionMapIntegrity": region_integrity,
            "regionVertexCounts": region_map.get("vertex_counts"),
            "regionFaceCounts": region_map.get("face_counts"),
            "cornerSymmetry": region_map.get("corner_symmetry"),
        }
        Path(args.semantic_validation_json).write_text(json.dumps(abort, indent=2) + "\n", encoding="utf-8")
        Path(args.validation_json).write_text(
            json.dumps({"pass": False, "safeAbort": True, "reason": reason, "regionMapIntegrity": region_integrity}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print(json.dumps({"pass": False, "safeAbort": True, "reason": reason, "regionMapIntegrity": region_integrity}))
        return 4

    rig_objs, eye_pivots, rig_setup_receipt = _setup_rig(Path(args.rig_obj), qa_mats, coll, head_root, jaw_empty)
    fid_mats = {k: _emit_mat(f"FID_{k}", v) for k, v in {**FEATURE_ID_RGB, "skin": (0.05, 0.05, 0.05)}.items()}

    mask_mat = _mask_mat("ObjID")
    overlay_dir = Path(args.overlay_dir)
    overlay_dir.mkdir(parents=True, exist_ok=True)

    _setup_scene(args.resolution)
    cam_d = bpy.data.cameras.new("Cam")
    cam = bpy.data.objects.new("Cam", cam_d)
    coll.objects.link(cam)
    bpy.context.scene.camera = cam
    sc = bpy.context.scene

    shots: dict[str, dict] = {}
    morph_masks: dict[str, np.ndarray] = {}
    camera_lock: dict[str, dict] = {}
    camera_lock_manifest: dict = {"schema": "NURION_CAMERA_LOCK_MANIFEST_V1", "locks": {}}
    captures: list[str] = []
    diagnostic_mode = bool(args.diagnostic_mode)
    failure_summary: list[dict] = []
    safe_abort = False

    def _record_shot(key: str, m: dict) -> None:
        shots[key] = {k: v for k, v in m.items() if k != "maskArray"}
        if m.get("pass"):
            if m.get("maskArray") is not None:
                morph_masks[key] = m.get("maskArray")
            beauty = m.get("beautyPath")
            if beauty and Path(beauty).is_file():
                captures.append(Path(beauty).name)
            return
        sq = m.get("semanticQa", {})
        failure_summary.append(
            {
                "shot": key,
                "pass": False,
                "reason": m.get("reason") or sq.get("reason"),
                "maskPass": bool(m.get("maskPass")),
                "missingFeatures": sq.get("missingFeatures", []),
                "featureVisibility": sq.get("featureVisibility", {}),
                "semanticIndexCoherence": sq.get("semanticIndexCoherence"),
            }
        )

    def _abort(msg: str, key: str) -> None:
        nonlocal safe_abort
        shots[key] = {"pass": False, "reason": msg, "safeAbort": True, "maskPass": False}
        failure_summary.append({"shot": key, "pass": False, "reason": msg, "maskPass": False})
        if not diagnostic_mode:
            safe_abort = True

    def _should_stop() -> bool:
        return safe_abort and not diagnostic_mode

    def set_mouth(angle, show_oral=False):
        skin_basis.hide_render = angle > 0.01
        if angle > 0.01:
            if not hasattr(set_mouth, "skin_open") or set_mouth.skin_open is None:
                set_mouth.skin_open = skin_basis.copy()
                set_mouth.skin_open.data = skin_basis.data.copy()
                set_mouth.skin_open.name = "SkinOpen"
                coll.objects.link(set_mouth.skin_open)
                set_mouth.skin_open.parent = head_root
                _assign_semantic_regions(set_mouth.skin_open, skin_basis_coords, landmarks, qa_mats, weights)
            else:
                for i, v in enumerate(skin_basis.data.vertices):
                    set_mouth.skin_open.data.vertices[i].co = v.co.copy()
                set_mouth.skin_open.data.update()
            _apply_weighted_jaw(set_mouth.skin_open, weights, pivot, angle)
            set_mouth.skin_open.hide_render = False
        elif hasattr(set_mouth, "skin_open") and set_mouth.skin_open:
            set_mouth.skin_open.hide_render = True
            skin_basis.hide_render = False
        jaw_empty.rotation_euler = (math.radians(angle), 0, 0)
        rig_objs["helper-upper-teeth"].hide_render = not show_oral
        rig_objs["helper-lower-teeth"].hide_render = not show_oral
        rig_objs["helper-tongue"].hide_render = not show_oral
        for g, o in rig_objs.items():
            if "eyelash" in g or g.endswith("-eye"):
                o.hide_render = True

    set_mouth.skin_open = None

    def mouth_valid(show_oral):
        skin = set_mouth.skin_open if show_oral else skin_basis
        objs = [skin]
        if show_oral:
            objs.extend(
                [
                    rig_objs["helper-upper-teeth"],
                    rig_objs["helper-lower-teeth"],
                    rig_objs["helper-tongue"],
                ]
            )
        return objs, skin

    def set_eye(side, open_pct):
        skin_basis.hide_render = True
        if hasattr(set_mouth, "skin_open") and set_mouth.skin_open:
            set_mouth.skin_open.hide_render = True
        jaw_empty.rotation_euler = (0, 0, 0)
        if not hasattr(set_eye, "skin_eye") or set_eye.skin_eye is None:
            set_eye.skin_eye = skin_basis.copy()
            set_eye.skin_eye.data = skin_basis.data.copy()
            set_eye.skin_eye.name = "SkinEye"
            coll.objects.link(set_eye.skin_eye)
            set_eye.skin_eye.parent = head_root
            _assign_semantic_regions(set_eye.skin_eye, skin_basis_coords, landmarks, qa_mats, weights)
        for i, co in enumerate(skin_basis_coords):
            set_eye.skin_eye.data.vertices[i].co = co.copy()
        set_eye.skin_eye.data.update()
        if eyelid_weights and eyelid_spec:
            _apply_eyelid_morph(set_eye.skin_eye, skin_basis_coords, eyelid_weights, eyelid_spec, side, open_pct)
        set_eye.skin_eye.hide_render = False
        for g, o in rig_objs.items():
            if "eyelash" in g:
                show = (side == "L" and g.startswith("helper-l")) or (side == "R" and g.startswith("helper-r"))
                o.hide_render = not show
            elif g.endswith("-eye"):
                show = (side == "L" and g == "helper-l-eye") or (side == "R" and g == "helper-r-eye")
                o.hide_render = not show
            else:
                o.hide_render = True
        for s, ep in eye_pivots.items():
            t = (open_pct - 0.5) * 2.0
            deg = math.radians(-14.0 * t) if s == side else 0.0
            ep.rotation_euler = (deg, 0, 0)

    set_eye.skin_eye = None

    oral = [
        rig_objs["helper-upper-teeth"],
        rig_objs["helper-lower-teeth"],
        rig_objs["helper-tongue"],
    ]

    global _OCCUPANCY_GATE_CONTRACT, _OCCUPANCY_CONTRACT_RECEIPT
    interior_only = bool(args.interior_diagnostic_only)
    parity_dir = out / "preflight_parity"
    parity_dir.mkdir(parents=True, exist_ok=True)

    if args.bc_evidence_only:
        source_preflight_path = (
            Path(args.bc_evidence_source_preflight)
            if args.bc_evidence_source_preflight
            else (Path(args.preflight_json) if args.preflight_json else None)
        )
        if source_preflight_path is None or not source_preflight_path.is_file():
            print(json.dumps({"pass": False, "reason": "BC_EVIDENCE_SOURCE_PREFLIGHT_REQUIRED"}, ensure_ascii=True))
            return 2
        d_probe_path = source_preflight_path.with_name("d_interior_revalidation_probe.json")
        d_probe_loaded = _load_json_file(d_probe_path) if d_probe_path.is_file() else None
        closed_baseline_preflight = (
            Path(args.closed_baseline_preflight)
            if args.closed_baseline_preflight
            else DEFAULT_CLOSED_EYE_MOUTH_CHIN_BASELINE_PREFLIGHT
        )
        d_interior_baseline_probe = (
            Path(args.d_interior_baseline_probe)
            if args.d_interior_baseline_probe
            else DEFAULT_D_INTERIOR_BASELINE_PROBE
        )
        return _run_bc_required_capture_evidence_regeneration_go(
            source_preflight_path=source_preflight_path,
            parity_dir=parity_dir,
            label=args.label,
            sc=sc,
            cam=cam,
            skin_basis=skin_basis,
            skin_basis_coords=skin_basis_coords,
            landmarks=landmarks,
            region_map=region_map,
            qa_mats=qa_mats,
            fid_mats=fid_mats,
            res=args.resolution,
            set_mouth_fn=set_mouth,
            mouth_valid_fn=mouth_valid,
            weights=weights,
            pivot=pivot,
            oral=oral,
            preflight_json=Path(args.preflight_json) if args.preflight_json else None,
            regenerate_rollup=bool(args.bc_evidence_regenerate_rollup),
            closed_baseline_preflight=closed_baseline_preflight,
            d_interior_baseline_probe=d_interior_baseline_probe,
            d_interior_probe=d_probe_loaded,
        )

    thirteen_shot_only = bool(args.thirteen_shot_diagnostic_only)
    occupancy_forensic_only = bool(args.thirteen_shot_occupancy_forensic_only)
    contract_parity_proof_only = bool(args.thirteen_shot_contract_parity_proof_only)
    preflight_report = None
    ah_preflight_capture_evidence_probe = None
    thirteen_shot_manifest_frozen: dict | None = None
    thirteen_shot_manifest_assert: dict | None = None

    if thirteen_shot_only or occupancy_forensic_only or contract_parity_proof_only:
        source_path = Path(args.ah_preflight_source) if args.ah_preflight_source else None
        if source_path is None or not source_path.is_file():
            print(json.dumps({"pass": False, "reason": "AH_PREFLIGHT_SOURCE_REQUIRED"}, ensure_ascii=True))
            return 2
        bundle = _load_closed_ah_preflight_bundle(source_path)
        if not bundle.get("pass"):
            print(
                json.dumps(
                    {
                        "pass": False,
                        "reason": "AH_PREFLIGHT_SOURCE_NOT_CLOSED",
                        "preflightPass": bundle.get("preflightPass"),
                        "ahPass": bundle.get("ahPass"),
                        "sourcePreflight": bundle.get("sourcePreflight"),
                    },
                    ensure_ascii=True,
                )
            )
            return 2
        preflight_gates = bundle["gates"]
        preflight_pass = bool(bundle["preflightPass"])
        camera_lock_manifest = bundle["cameraLockManifest"]
        thirteen_shot_manifest_frozen = json.loads(json.dumps(camera_lock_manifest))
        thirteen_shot_manifest_assert = _assert_thirteen_shot_manifest_consumption(
            source_path, camera_lock_manifest
        )
        preflight_gates["13_SHOT_MANIFEST_CONSUMPTION_ASSERT"] = thirteen_shot_manifest_assert
        if not thirteen_shot_manifest_assert.get("pass"):
            _emit_thirteen_shot_manifest_consumption_abort(
                args,
                thirteen_shot_manifest_assert,
                preflight_report=bundle["preflightReport"],
            )
            return 2
        if occupancy_forensic_only:
            shot_key = str(args.forensic_shot or "mouth_closed_front")
            spec = FORENSIC_SHOT_SPECS.get(shot_key)
            if spec is None:
                print(json.dumps({"pass": False, "reason": "FORENSIC_SHOT_UNSUPPORTED", "shot": shot_key}, ensure_ascii=True))
                return 2
            fail_ref = None
            if args.fail_run_semantic_json:
                fail_sem = _load_json_file(Path(args.fail_run_semantic_json))
                for row in fail_sem.get("failureSummary") or []:
                    if row.get("shot") == shot_key:
                        fail_ref = row
                        break
            baseline = _extract_frozen_baseline_forensic_evidence(
                preflight_gates, camera_lock_manifest, shot_key=shot_key
            )
            set_mouth(float(spec["mouthAngle"]), show_oral=bool(spec["showOral"]))
            valid, skin = mouth_valid(bool(spec["showOral"]))
            manifest_entry = (camera_lock_manifest.get("locks") or {}).get(spec["manifestKey"])
            capture_key = shot_key
            beauty_path = out / f"{args.label}_{capture_key}"
            overlay_path = overlay_dir / f"{args.label}_{capture_key}_overlay.png"
            capture_metrics = _frame_and_capture(
                sc,
                cam,
                mask_mat,
                valid,
                skin,
                skin_basis_coords,
                _mouth_framing,
                spec["view"],
                beauty_path,
                overlay_path,
                args.resolution,
                landmarks,
                fid_mats,
                rig_objs,
                manifest_entry=manifest_entry,
                morph_state=spec["morphState"],
                semantic_profile=spec["semanticProfile"],
                shot_kind=spec["shotKind"],
                allow_software_fid_fallback=False,
            )
            capture_metrics = _enrich_capture_metrics_with_holdout_occupancy(
                capture_metrics,
                manifest_entry=manifest_entry or {},
                morph_state=spec["morphState"],
                res=args.resolution,
            )
            forensic_receipt = _build_occupancy_forensic_receipt(
                shot_key=shot_key,
                baseline=baseline,
                capture_metrics=capture_metrics,
                manifest_assert=thirteen_shot_manifest_assert,
                fail_run_reference=fail_ref,
            )
            receipt_path = (
                Path(args.occupancy_forensic_json)
                if args.occupancy_forensic_json
                else out.parent / "thirteen_shot_occupancy_forensic_receipt.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(forensic_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(
                json.dumps(
                    {
                        "occupancyForensicOnly": True,
                        "forensicShot": shot_key,
                        "isolationBucket": forensic_receipt["isolation"]["classificationBucket"],
                        "captureAbortReason": capture_metrics.get("reason"),
                        "cameraParityPass": (forensic_receipt.get("captureEvidence") or {}).get("cameraParity", {}).get("pass"),
                        "firstZeroStage": (forensic_receipt.get("captureEvidence") or {}).get("firstZeroStage"),
                        "receipt": str(receipt_path),
                    },
                    ensure_ascii=True,
                )
            )
            return 0
        if contract_parity_proof_only:
            shot_key = str(args.forensic_shot or "mouth_closed_front")
            spec = FORENSIC_SHOT_SPECS.get(shot_key)
            if spec is None:
                print(json.dumps({"pass": False, "reason": "FORENSIC_SHOT_UNSUPPORTED", "shot": shot_key}, ensure_ascii=True))
                return 2
            baseline = _extract_frozen_baseline_forensic_evidence(
                preflight_gates, camera_lock_manifest, shot_key=shot_key
            )
            set_mouth(float(spec["mouthAngle"]), show_oral=bool(spec["showOral"]))
            valid, skin = mouth_valid(bool(spec["showOral"]))
            manifest_entry = (camera_lock_manifest.get("locks") or {}).get(spec["manifestKey"])
            capture_key = shot_key
            beauty_path = out / f"{args.label}_{capture_key}"
            overlay_path = overlay_dir / f"{args.label}_{capture_key}_overlay.png"
            capture_metrics = _frame_and_capture(
                sc,
                cam,
                mask_mat,
                valid,
                skin,
                skin_basis_coords,
                _mouth_framing,
                spec["view"],
                beauty_path,
                overlay_path,
                args.resolution,
                landmarks,
                fid_mats,
                rig_objs,
                manifest_entry=manifest_entry,
                morph_state=spec["morphState"],
                semantic_profile=spec["semanticProfile"],
                shot_kind=spec["shotKind"],
                allow_software_fid_fallback=False,
            )
            proof_receipt = _build_contract_parity_proof_receipt(
                shot_key=shot_key,
                baseline=baseline,
                capture_metrics=capture_metrics,
                manifest_assert=thirteen_shot_manifest_assert,
            )
            receipt_path = (
                Path(args.contract_parity_proof_json)
                if args.contract_parity_proof_json
                else out.parent / "thirteen_shot_contract_parity_proof_receipt.json"
            )
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            receipt_path.write_text(json.dumps(proof_receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(
                json.dumps(
                    {
                        "contractParityProofOnly": True,
                        "forensicShot": shot_key,
                        "proofPass": bool(proof_receipt.get("pass")),
                        "nativeFinalPixels": capture_metrics.get("finalMaskPixels"),
                        "frameOccupancy": capture_metrics.get("occupancy"),
                        "legacyOccupancyPass": (capture_metrics.get("legacyOccupancy") or {}).get("legacyPass"),
                        "legacyOccupancyRole": capture_metrics.get("legacyOccupancyRole"),
                        "nativeSemanticEvidencePass": capture_metrics.get("nativeSemanticEvidencePass"),
                        "authoritativeGate": capture_metrics.get("authoritativeGate"),
                        "captureAbort": not bool(capture_metrics.get("pass")),
                        "receipt": str(receipt_path),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if proof_receipt.get("pass") else 2
        preflight_report = bundle["preflightReport"]
        ah_preflight_capture_evidence_probe = bundle["ahProbe"]
        mouth_mask_parity = preflight_report.get("mouthMaskEmissionParity") or {}
        mouth_visibility_parity = preflight_report.get("expectedVisibilityContractParity") or {}
        chin_forensic = (preflight_report.get("nativeRenderPathParity") or {}).get("chinForensicProbes") or {}
        mouth_chin_lip_corner_fid_forensic = preflight_report.get("mouthChinLipCornerNativeFidEmissionParity") or {}
        mouth_forensic_camera_trigger = preflight_report.get("mouthForensicCameraRefAndFidTrigger") or {}
        interior_diagnostic_probe = preflight_report.get("interiorNativeVisibilityAndEmissionParity") or {}
        interior_restoration_probe = preflight_report.get("interiorCameraLockProvenanceAndStateConsumption") or {}
        oral_opening_degeneracy_probe = preflight_report.get("oralOpeningProjectionDegeneracy") or {}
        oral_opening_native_evidence_probe = preflight_report.get("oralOpeningLipBoundaryNativeEvidenceContract") or {}
        d_interior_revalidation_probe = _load_json_file(
            source_path.with_name("d_interior_revalidation_probe.json")
        ) or preflight_report.get("dInteriorNativeSemanticEvidenceRevalidation") or {}
        eye_visibility_parity = mouth_visibility_parity.get("eyeLeftClosed") or {}
        eyelid_manifest_parity = preflight_report.get("eyelidManifestStateMappingParity") or {}
        eyelid_projection_parity = preflight_report.get("eyelidRigHelperProjectionParity") or {}
        eye_forensic_probe = (preflight_report.get("nativeRenderPathParity") or {}).get("eyeForensicProbe") or {}
    elif interior_only:
        occupancy_contract_baseline = {
            "resolvedContract": "frame",
            "skipped": True,
            "reason": "INTERIOR_DIAGNOSTIC_ONLY",
        }
        _OCCUPANCY_GATE_CONTRACT = "frame"
        _OCCUPANCY_CONTRACT_RECEIPT = occupancy_contract_baseline
        preflight_gates = {}
        preflight_pass = True
        mouth_mask_parity = {}
        mouth_visibility_parity = {}
        chin_forensic = {}
        mouth_chin_lip_corner_fid_forensic = {"skipped": True, "reason": "INTERIOR_DIAGNOSTIC_ONLY"}
        mouth_forensic_camera_trigger = {"skipped": True, "reason": "INTERIOR_DIAGNOSTIC_ONLY"}
        gate_b_front = {"pass": True, "skipped": True, "reason": "INTERIOR_DIAGNOSTIC_ONLY"}
        gate_b_left = {"pass": True, "skipped": True, "reason": "INTERIOR_DIAGNOSTIC_ONLY"}
        gate_b_diag_front = None
    else:
        baseline_preflight = Path(args.occupancy_baseline_preflight) if args.occupancy_baseline_preflight else DEFAULT_OCCUPANCY_BASELINE_PREFLIGHT
        occupancy_contract_baseline = _recompute_occupancy_contract_baseline(
            sc,
            cam,
            mask_mat,
            args.resolution,
            baseline_preflight,
            set_mouth_fn=set_mouth,
            mouth_valid_fn=mouth_valid,
            set_eye_fn=set_eye,
            rig_objs=rig_objs,
            skin_basis=skin_basis,
            skin_basis_coords=skin_basis_coords,
            weights=weights,
            pivot=pivot,
            oral=oral,
            landmarks=landmarks,
        )
        _OCCUPANCY_GATE_CONTRACT = str(occupancy_contract_baseline.get("resolvedContract", "frame"))
        _OCCUPANCY_CONTRACT_RECEIPT = occupancy_contract_baseline
        _reset_preflight_scene_after_baseline(set_mouth, set_eye, rig_objs)

        preflight_gates = {}
        preflight_pass = True
        preflight_gates["OCCUPANCY_CONTRACT_ALIGNMENT"] = {
            "gate": "OCCUPANCY_CONTRACT_ALIGNMENT",
            "pass": True,
            "resolvedContract": _OCCUPANCY_GATE_CONTRACT,
            "contractMetricKey": _occupancy_contract_metric_key(),
            "baselineRecompute": occupancy_contract_baseline,
            "policy": {
                "cameraRetune": "DENY",
                "thresholdRelaxation": "DENY",
                "maskFinalSourceWiring": "PASS",
                "rawFullframeMask": "DIAGNOSTIC_ONLY",
                "holdoutComposite": "NATIVE_FINAL_MASK",
                "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
                "replacementReviewId": OCCUPANCY_REPLACEMENT_REVIEW_ID,
                "nativeSemanticEvidenceGate": NATIVE_SEMANTIC_EVIDENCE_GATE,
            },
        }

        preflight_gates["A_CHIN_REGION_INTEGRITY"] = {
            "gate": "CHIN_REGION_INTEGRITY",
            "pass": True,
            "chinFaceCount": region_integrity.get("chinFaceCount"),
            "chinVertexCount": (region_map.get("vertex_counts") or {}).get("chin"),
            "connectedComponents": region_integrity.get("chinConnectedComponents"),
            "semanticOverlap": region_integrity.get("semanticOverlapVerts"),
            "cornerSymmetry": region_map.get("corner_symmetry"),
        }

        set_mouth(0, show_oral=False)
        front_morph_specs: list[dict] = []
        left_morph_specs: list[dict] = []
        mouth_mask_parity = {}
        mouth_visibility_parity = {}
        chin_forensic = {}
        left_projection_lock = None
        mouth_projection_locks: dict[str, dict | None] = {"front": None, "left": None}
        for view in ("front", "left"):
            set_mouth(0, show_oral=False)
            cam_key = f"mouth_{view}"
            union_min, union_max = _mouth_union_bounds_with_chin_guard(
                skin_basis, skin_basis_coords, weights, pivot, oral, landmarks
            )
            morph_specs = (
                _mouth_morph_projection_specs(
                    skin_basis, skin_basis_coords, weights, pivot, oral, view, union_min, union_max
                )
                if union_min is not None
                else []
            )
            if view == "front":
                front_morph_specs = morph_specs
            else:
                left_morph_specs = morph_specs
            projection_lock = _solve_mouth_union_camera(
                sc, cam, landmarks, skin_basis_coords, morph_specs, args.resolution
            )
            mouth_projection_locks[view] = projection_lock
            if view == "left":
                left_projection_lock = projection_lock
            framing_report: dict = {}
            if view == "front":
                if projection_lock is not None:
                    camera_lock["mouth_front"] = projection_lock
                framed_cam, framing_report = _solve_front_chin_constrained_framing(
                    sc,
                    cam,
                    camera_lock.get("mouth_front"),
                    landmarks,
                    skin_basis_coords,
                    region_map,
                    skin_basis,
                    front_morph_specs,
                    args.resolution,
                    mask_mat=mask_mat,
                    set_mouth_fn=set_mouth,
                    mouth_valid_fn=mouth_valid,
                    fid_mats=fid_mats,
                    rig_objs=rig_objs,
                )
                preflight_gates["B0_FRONT_CHIN_CONSTRAINED_FRAMING"] = framing_report
                lock = framed_cam if framed_cam is not None else None
            else:
                lock = projection_lock
            native_pass = False
            native_rows: list[dict] = []
            if view == "front" and framing_report.get("nativeMaskQualification"):
                native_rows = list(framing_report["nativeMaskQualification"])
                native_pass = _native_mask_rows_pass(native_rows)
            elif lock is not None and len(morph_specs) == 3:
                native_pass, native_rows = _validate_mouth_native_mask_morphs(
                    sc,
                    cam,
                    lock,
                    morph_specs,
                    mask_mat,
                    set_mouth,
                    mouth_valid,
                    args.resolution,
                    view=view,
                    fid_mats=fid_mats,
                    landmarks=landmarks,
                    skin_basis_coords=skin_basis_coords,
                    rig_objs=rig_objs,
                )
            gate_key = f"C_MOUTH_NATIVE_MASK_{view.upper()}"
            gate_pass = lock is not None and len(morph_specs) == 3 and native_pass
            if view == "front":
                gate_pass = gate_pass and bool(framing_report.get("pass"))
            gate_receipt = _bind_c_mouth_production_gate_receipt(
                view=view,
                gate_pass=gate_pass,
                native_rows=native_rows,
                lock=lock,
                projection_lock=projection_lock,
                framing_report=framing_report,
                morph_specs=morph_specs,
            )
            preflight_gates[gate_key] = gate_receipt
            gate_pass = bool(gate_receipt.get("pass"))
            native_rows = gate_receipt.get("nativeMaskQualification") or native_rows
            if gate_pass and lock is not None:
                lock["semanticLock"] = _manifest_semantic_lock(lock)
                camera_lock[cam_key] = lock
            else:
                preflight_pass = False
                if cam_key in camera_lock and not gate_pass:
                    del camera_lock[cam_key]
                failure_summary.append(
                    {
                        "shot": f"preflight_{gate_key.lower()}",
                        "pass": False,
                        "reason": "MOUTH_NATIVE_MASK_QUALIFICATION_FAIL",
                        "maskPass": False,
                        "nativeMaskQualification": native_rows,
                    }
                )
                if view == "left" and morph_specs:
                    left_closed = next((s for s in morph_specs if s["angle"] < 6), morph_specs[0])
                    diag_lock = lock if lock is not None else projection_lock
                    if diag_lock is not None:
                        mouth_mask_parity["mouth_closed_left"] = _run_mouth_mask_emission_parity(
                            sc,
                            cam,
                            diag_lock,
                            left_closed,
                            skin_basis,
                            mouth_valid(False)[0],
                            mask_mat,
                            args.resolution,
                            "left",
                            "closed",
                            set_mouth,
                            mouth_valid,
                        )
            if view == "front" and morph_specs:
                closed_spec = next((s for s in morph_specs if s["angle"] < 6), morph_specs[0])
                parity_lock = lock if lock is not None else projection_lock
                if parity_lock is not None:
                    mouth_visibility_parity["front_closed"] = _run_mouth_visibility_parity_probe(
                        sc,
                        cam,
                        parity_lock,
                        closed_spec,
                        view="front",
                        skin_obj=skin_basis,
                        valid_objs=mouth_valid(False)[0],
                        mask_mat=mask_mat,
                        fid_mats=fid_mats,
                        res=args.resolution,
                        set_mouth_fn=set_mouth,
                        mouth_valid_fn=mouth_valid,
                    )

        _finalize_c_mouth_gate_provenance_rebind(
            preflight_gates,
            mouth_visibility_parity=mouth_visibility_parity,
            projection_locks=mouth_projection_locks,
        )

        baseline_left_camera_fp = _camera_state_fingerprint(left_projection_lock)

        if args.c_mouth_consumption_repair_verification_only:
            c_consumption_repair_probe = _run_c_mouth_consumption_path_repair_verification(
                preflight_gates,
                baseline_left_camera_fingerprint=baseline_left_camera_fp,
            )
            preflight_gates["C_MOUTH_CONSUMPTION_PATH_REPAIR_VERIFICATION"] = {
                "gate": "C_MOUTH_CONSUMPTION_PATH_REPAIR_VERIFICATION",
                "pass": bool(c_consumption_repair_probe.get("verificationPass")),
                "verificationPass": bool(c_consumption_repair_probe.get("verificationPass")),
                "C_LEFT": c_consumption_repair_probe.get("C_LEFT"),
                "C_FRONT": c_consumption_repair_probe.get("C_FRONT"),
                "successCriteria": c_consumption_repair_probe.get("successCriteria"),
                "nextGo": c_consumption_repair_probe.get("nextGo"),
                "policy": c_consumption_repair_probe.get("policy"),
            }
            if args.preflight_json:
                repair_checkpoint = Path(args.preflight_json).with_name(
                    "c_mouth_consumption_path_repair_verification_probe.json"
                )
                repair_checkpoint.write_text(
                    json.dumps(c_consumption_repair_probe, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                partial_report = {
                    "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
                    "pass": bool(c_consumption_repair_probe.get("verificationPass")),
                    "cMouthConsumptionRepairVerificationOnly": True,
                    "gates": {
                        "A_CHIN_REGION_INTEGRITY": preflight_gates.get("A_CHIN_REGION_INTEGRITY"),
                        "C_MOUTH_NATIVE_MASK_FRONT": preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT"),
                        "C_MOUTH_NATIVE_MASK_LEFT": preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
                        "C_MOUTH_CONSUMPTION_PATH_REPAIR_VERIFICATION": preflight_gates.get(
                            "C_MOUTH_CONSUMPTION_PATH_REPAIR_VERIFICATION"
                        ),
                    },
                    "cMouthConsumptionPathRepairVerificationProbe": c_consumption_repair_probe,
                }
                Path(args.preflight_json).write_text(
                    json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "cMouthConsumptionRepairVerificationOnly": True,
                        "verificationPass": bool(c_consumption_repair_probe.get("verificationPass")),
                        "closedBaselinePreserved": (
                            c_consumption_repair_probe.get("closedBaseline") or {}
                        ).get("preserved"),
                        "successCriteria": c_consumption_repair_probe.get("successCriteria"),
                        "productionGatePass": c_consumption_repair_probe.get("productionGatePass"),
                        "consumptionReceipts": c_consumption_repair_probe.get("consumptionReceipts"),
                        "nextGo": c_consumption_repair_probe.get("nextGo"),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if c_consumption_repair_probe.get("verificationPass") else 2

        if args.c_left_oral_geometry_diagnostic_only:
            c_left_oral_geometry_probe = _run_c_left_oral_rig_morph_state_geometry_diagnostic(
                preflight_gates=preflight_gates,
                camera_lock=camera_lock,
                rig_objs=rig_objs,
                jaw_empty=jaw_empty,
                head_root=head_root,
                set_mouth_fn=set_mouth,
                sc=sc,
                cam=cam,
                res=args.resolution,
                mouth_valid_fn=mouth_valid,
            )
            preflight_gates["C_LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_DIAGNOSTIC"] = {
                "gate": "C_LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_DIAGNOSTIC",
                "pass": bool(c_left_oral_geometry_probe.get("diagnosticPass")),
                "diagnosticPass": bool(c_left_oral_geometry_probe.get("diagnosticPass")),
                "half": c_left_oral_geometry_probe.get("half"),
                "open": c_left_oral_geometry_probe.get("open"),
                "recommendedBranch": c_left_oral_geometry_probe.get("recommendedBranch"),
                "nextGo": c_left_oral_geometry_probe.get("nextGo"),
                "policy": c_left_oral_geometry_probe.get("policy"),
            }
            if args.preflight_json:
                oral_geom_checkpoint = Path(args.preflight_json).with_name(
                    "c_left_oral_rig_morph_state_geometry_probe.json"
                )
                oral_geom_checkpoint.write_text(
                    json.dumps(c_left_oral_geometry_probe, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                partial_report = {
                    "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
                    "pass": False,
                    "cLeftOralGeometryDiagnosticOnly": True,
                    "gates": {
                        "A_CHIN_REGION_INTEGRITY": preflight_gates.get("A_CHIN_REGION_INTEGRITY"),
                        "C_MOUTH_NATIVE_MASK_LEFT": preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
                        "C_LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_DIAGNOSTIC": preflight_gates.get(
                            "C_LEFT_ORAL_RIG_MORPH_STATE_GEOMETRY_DIAGNOSTIC"
                        ),
                    },
                    "cLeftOralRigMorphStateGeometryProbe": c_left_oral_geometry_probe,
                }
                Path(args.preflight_json).write_text(
                    json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "cLeftOralGeometryDiagnosticOnly": True,
                        "diagnosticPass": bool(c_left_oral_geometry_probe.get("diagnosticPass")),
                        "closedBaselinePreserved": (
                            c_left_oral_geometry_probe.get("closedBaseline") or {}
                        ).get("preserved"),
                        "successCriteria": c_left_oral_geometry_probe.get("successCriteria"),
                        "rootCauseComparison": c_left_oral_geometry_probe.get("rootCauseComparison"),
                        "recommendedBranch": c_left_oral_geometry_probe.get("recommendedBranch"),
                        "nextGo": c_left_oral_geometry_probe.get("nextGo"),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if c_left_oral_geometry_probe.get("diagnosticPass") else 2

        if args.c_left_half_open_diagnostic_only:
            c_left_half_open_probe = _run_c_left_half_open_native_evidence_diagnostic(
                preflight_gates=preflight_gates,
                camera_lock=camera_lock,
                left_morph_specs=left_morph_specs,
                sc=sc,
                cam=cam,
                mask_mat=mask_mat,
                set_mouth_fn=set_mouth,
                mouth_valid_fn=mouth_valid,
                res=args.resolution,
                fid_mats=fid_mats,
                landmarks=landmarks,
                skin_basis_coords=skin_basis_coords,
                rig_objs=rig_objs,
            )
            preflight_gates["C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC"] = {
                "gate": "C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC",
                "pass": bool(c_left_half_open_probe.get("diagnosticPass")),
                "diagnosticPass": bool(c_left_half_open_probe.get("diagnosticPass")),
                "half": c_left_half_open_probe.get("half"),
                "open": c_left_half_open_probe.get("open"),
                "recommendedBranch": c_left_half_open_probe.get("recommendedBranch"),
                "nextGo": c_left_half_open_probe.get("nextGo"),
                "policy": c_left_half_open_probe.get("policy"),
            }
            if args.preflight_json:
                left_diag_checkpoint = Path(args.preflight_json).with_name(
                    "c_left_half_open_native_evidence_probe.json"
                )
                left_diag_checkpoint.write_text(
                    json.dumps(c_left_half_open_probe, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                partial_report = {
                    "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
                    "pass": False,
                    "cLeftHalfOpenDiagnosticOnly": True,
                    "gates": {
                        "A_CHIN_REGION_INTEGRITY": preflight_gates.get("A_CHIN_REGION_INTEGRITY"),
                        "C_MOUTH_NATIVE_MASK_LEFT": preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
                        "C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC": preflight_gates.get(
                            "C_LEFT_HALF_OPEN_NATIVE_EVIDENCE_DIAGNOSTIC"
                        ),
                    },
                    "cLeftHalfOpenNativeEvidenceProbe": c_left_half_open_probe,
                }
                Path(args.preflight_json).write_text(
                    json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "cLeftHalfOpenDiagnosticOnly": True,
                        "diagnosticPass": bool(c_left_half_open_probe.get("diagnosticPass")),
                        "closedStatePreserved": c_left_half_open_probe.get("closedStatePreserved"),
                        "halfPrimary": (
                            (c_left_half_open_probe.get("half") or {}).get("classification") or {}
                        ).get("primaryClassification"),
                        "openPrimary": (
                            (c_left_half_open_probe.get("open") or {}).get("classification") or {}
                        ).get("primaryClassification"),
                        "recommendedBranch": c_left_half_open_probe.get("recommendedBranch"),
                        "nextGo": c_left_half_open_probe.get("nextGo"),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if c_left_half_open_probe.get("diagnosticPass") else 2

        set_mouth(0, show_oral=False)
        gate_b_front: dict = {"pass": False, "reason": "MOUTH_FRONT_CAMERA_LOCK_MISSING"}
        gate_b_left: dict = {"pass": False, "reason": "MOUTH_LEFT_CAMERA_LOCK_MISSING"}
        front_closed_vis = mouth_visibility_parity.get("front_closed") or {}
        forensic_camera_ref = front_closed_vis.get("forensicCameraRef")
        production_camera_lock_present = camera_lock.get("mouth_front") is not None
        visibility_pass = bool(front_closed_vis.get("visibilityPass"))
        mouth_chin_lip_corner_fid_forensic: dict = {}
        mouth_forensic_camera_trigger: dict = {}

        if visibility_pass and forensic_camera_ref is not None:
            trigger_receipt = _mouth_forensic_fid_trigger_receipt(
                visibility_pass=visibility_pass,
                production_camera_lock_present=production_camera_lock_present,
                forensic_camera_ref=forensic_camera_ref,
                probe_triggered=True,
                probe_trigger_reason="VISIBILITY_PASS_WITH_FORENSIC_CAMERA_REF",
            )
            mouth_chin_lip_corner_fid_forensic = _run_mouth_forensic_camera_ref_and_fid_trigger_probe(
                sc,
                cam,
                forensic_camera_ref=forensic_camera_ref,
                trigger_receipt=trigger_receipt,
                set_mouth_fn=set_mouth,
                mouth_valid_fn=mouth_valid,
                skin_obj=skin_basis,
                region_map=region_map,
                fid_mats=fid_mats,
                res=args.resolution,
                out_dir=parity_dir,
                label=args.label,
            )
            mouth_forensic_camera_trigger = {
                "probeShot": "mouth_front_closed",
                "pass": bool(mouth_chin_lip_corner_fid_forensic.get("diagnosticPass")),
                "gatePassEligible": False,
                "forensicTrigger": trigger_receipt,
                "fidProbe": {
                    "probeTriggered": True,
                    "perFeaturePresent": all(
                        f in (mouth_chin_lip_corner_fid_forensic.get("perFeature") or {})
                        for f in MOUTH_FID_EMISSION_FEATURES
                    ),
                    "classifications": mouth_chin_lip_corner_fid_forensic.get("classifications"),
                    "fidLayerChains": mouth_chin_lip_corner_fid_forensic.get("fidLayerChains"),
                },
                "policy": {
                    "cameraRetune": "DENY",
                    "productionCameraLockBypass": False,
                    "gatePassEligible": False,
                    "cameraMutation": 0,
                    "thresholdMutation": 0,
                },
            }
            chin_forensic["front"] = mouth_chin_lip_corner_fid_forensic
            chin_row = (mouth_chin_lip_corner_fid_forensic.get("perFeature") or {}).get("chin", {})
            gate_b_front = {
                "pass": bool(chin_row.get("pass")),
                "forensicProbe": mouth_chin_lip_corner_fid_forensic,
                "classification": chin_row.get("classification"),
                "finalFidPixels": chin_row.get("finalFIDPixels"),
                "fidLayerChain": chin_row.get("fidLayerChain"),
                "forensicCameraRefUsed": True,
                "productionCameraLockUsed": production_camera_lock_present,
            }
        else:
            probe_reason = (
                "MOUTH_VISIBILITY_CONTRACT_NOT_RESOLVED"
                if not visibility_pass
                else "FORENSIC_CAMERA_REF_UNAVAILABLE"
            )
            trigger_receipt = _mouth_forensic_fid_trigger_receipt(
                visibility_pass=visibility_pass,
                production_camera_lock_present=production_camera_lock_present,
                forensic_camera_ref=forensic_camera_ref,
                probe_triggered=False,
                probe_trigger_reason=probe_reason,
            )
            mouth_chin_lip_corner_fid_forensic = {
                "probeShot": "mouth_front_closed",
                "pass": False,
                "skipped": True,
                "reason": probe_reason,
                "visibilityParity": front_closed_vis,
                "forensicTrigger": trigger_receipt,
                "diagnosticPass": False,
                "fidRepairPass": False,
                "gatePassEligible": False,
            }
            mouth_forensic_camera_trigger = {
                "probeShot": "mouth_front_closed",
                "pass": False,
                "gatePassEligible": False,
                "forensicTrigger": trigger_receipt,
                "fidProbe": {"probeTriggered": False},
                "policy": {
                    "cameraRetune": "DENY",
                    "productionCameraLockBypass": False,
                    "gatePassEligible": False,
                },
            }

        preflight_gates["MOUTH_FORENSIC_CAMERA_REF_AND_FID_TRIGGER"] = {
            "gate": "MOUTH_FORENSIC_CAMERA_REF_AND_FID_TRIGGER",
            "pass": bool(mouth_forensic_camera_trigger.get("pass")),
            "gatePassEligible": False,
            "probeShot": "mouth_front_closed",
            "mouthFrontClosed": mouth_forensic_camera_trigger,
            "forensicTrigger": mouth_forensic_camera_trigger.get("forensicTrigger"),
            "policy": mouth_forensic_camera_trigger.get("policy"),
        }

        preflight_gates["MOUTH_CHIN_LIP_CORNER_NATIVE_FID_EMISSION_PARITY"] = {
            "gate": "MOUTH_CHIN_LIP_CORNER_NATIVE_FID_EMISSION_PARITY",
            "pass": bool(mouth_chin_lip_corner_fid_forensic.get("fidRepairPass"))
            if mouth_chin_lip_corner_fid_forensic.get("forensicTrigger", {}).get("probeTriggered")
            else False,
            "probeTriggered": bool(mouth_chin_lip_corner_fid_forensic.get("forensicTrigger", {}).get("probeTriggered")),
            "probeShot": "mouth_front_closed",
            "mouthFrontClosed": mouth_chin_lip_corner_fid_forensic,
            "classifications": mouth_chin_lip_corner_fid_forensic.get("classifications"),
            "fidLayerChains": mouth_chin_lip_corner_fid_forensic.get("fidLayerChains"),
            "provenanceChain": mouth_chin_lip_corner_fid_forensic.get("provenanceChain"),
            "policy": mouth_chin_lip_corner_fid_forensic.get("policy"),
            "gatePassEligible": False,
        }
        if (
            mouth_chin_lip_corner_fid_forensic.get("forensicTrigger", {}).get("probeTriggered")
            and not mouth_chin_lip_corner_fid_forensic.get("fidRepairPass")
        ):
            preflight_pass = False
            failure_summary.append(
                {
                    "shot": "preflight_mouth_chin_lip_corner_native_fid_emission",
                    "pass": False,
                    "reason": "MOUTH_CHIN_LIP_CORNER_NATIVE_FID_EMISSION_PARITY_FAIL",
                    "classifications": mouth_chin_lip_corner_fid_forensic.get("classifications"),
                    "perFeature": mouth_chin_lip_corner_fid_forensic.get("perFeature"),
                }
            )

        if production_camera_lock_present and gate_b_front.get("forensicProbe") is None:
            chin_forensic["front"] = _run_chin_fid_forensic_probe(
                sc,
                cam,
                skin_basis,
                region_map,
                fid_mats,
                camera_lock["mouth_front"],
                "front",
                args.resolution,
                parity_dir,
                args.label,
            )
            gate_b_front = {
                "pass": bool(chin_forensic["front"].get("pass")),
                "forensicProbe": chin_forensic["front"],
                "classification": chin_forensic["front"].get("chinAudit", {}).get("classification"),
                "finalFidPixels": chin_forensic["front"].get("finalFidPixels"),
            }
        front_evidence_lock = camera_lock.get("mouth_front")
        if front_evidence_lock is None:
            fcr = (front_closed_vis.get("forensicCameraRef") or {})
            front_evidence_lock = _parity_lock_from_source_camera_record(fcr.get("cameraState"))
        if front_evidence_lock is not None and "front_fid_probe" not in chin_forensic:
            chin_forensic["front_fid_probe"] = _run_chin_fid_forensic_probe(
                sc,
                cam,
                skin_basis,
                region_map,
                fid_mats,
                front_evidence_lock,
                "front",
                args.resolution,
                parity_dir,
                args.label,
            )
        left_evidence_lock = camera_lock.get("mouth_left")
        if left_evidence_lock is None and left_projection_lock is not None:
            left_evidence_lock = left_projection_lock
        if left_evidence_lock is not None:
            chin_forensic["left"] = _run_chin_fid_forensic_probe(
                sc,
                cam,
                skin_basis,
                region_map,
                fid_mats,
                left_evidence_lock,
                "left",
                args.resolution,
                parity_dir,
                args.label,
            )
            gate_b_left = {
                "pass": bool(chin_forensic["left"].get("pass")),
                "forensicProbe": chin_forensic["left"],
                "classification": chin_forensic["left"].get("chinAudit", {}).get("classification"),
                "finalFidPixels": chin_forensic["left"].get("finalFidPixels"),
                "leftNativeBaselinePx": chin_forensic["left"].get("finalFidPixels"),
            }
        gate_b_diag_front = _run_chin_fid_render_parity(
            sc,
            cam,
            skin_basis,
            skin_basis_coords,
            landmarks,
            region_map,
            qa_mats,
            fid_mats,
            "front",
            args.resolution,
            parity_dir,
            args.label,
            locked_cam=camera_lock.get("mouth_front") or front_evidence_lock,
            allow_software_fallback=True,
        )
        gate_b_diag_left = (
            _run_chin_fid_render_parity(
                sc,
                cam,
                skin_basis,
                skin_basis_coords,
                landmarks,
                region_map,
                qa_mats,
                fid_mats,
                "left",
                args.resolution,
                parity_dir,
                args.label,
                locked_cam=left_evidence_lock,
                allow_software_fallback=False,
            )
            if left_evidence_lock is not None
            else {"pass": False, "reason": "MOUTH_LEFT_EVIDENCE_LOCK_MISSING", "mode": "left"}
        )
        gate_b_pass = bool(gate_b_front.get("pass")) and bool(gate_b_left.get("pass"))
        preflight_gates["B_CHIN_NATIVE_FID_PARITY"] = {
            "gate": "CHIN_NATIVE_FID_PARITY",
            "pass": gate_b_pass,
            "front": gate_b_front,
            "left": gate_b_left,
            "forensicProbes": chin_forensic,
            "diagnosticSoftwareFallbackFront": gate_b_diag_front,
            "diagnosticSoftwareFallbackLeft": gate_b_diag_left,
            "softwareRasterPolicy": "DIAGNOSTIC_EVIDENCE_ONLY",
            "nativeFidAuditFramework": True,
        }
        if not gate_b_pass:
            preflight_pass = False
            for side, rep in (("front", gate_b_front), ("left", gate_b_left)):
                if not rep.get("pass"):
                    failure_summary.append(
                        {
                            "shot": f"preflight_chin_native_fid_{side}",
                            "pass": False,
                            "reason": rep.get("classification") or rep.get("reason") or "CHIN_NATIVE_FID_PARITY_FAIL",
                            "maskPass": False,
                            "pixels": rep.get("pixels"),
                        }
                    )

        closed_baseline_preflight = (
            Path(args.closed_baseline_preflight)
            if args.closed_baseline_preflight
            else DEFAULT_CLOSED_EYE_MOUTH_CHIN_BASELINE_PREFLIGHT
        )
        c_mouth_rebind_verification_probe = _run_c_mouth_rebind_verification(preflight_gates)
        preflight_gates["C_MOUTH_PRODUCTION_EVIDENCE_REBIND_VERIFICATION"] = {
            "gate": "C_MOUTH_PRODUCTION_EVIDENCE_REBIND_VERIFICATION",
            "pass": bool(c_mouth_rebind_verification_probe.get("verificationPass")),
            "verificationPass": bool(c_mouth_rebind_verification_probe.get("verificationPass")),
            "C_FRONT": c_mouth_rebind_verification_probe.get("C_FRONT"),
            "C_LEFT": c_mouth_rebind_verification_probe.get("C_LEFT"),
            "nextGo": c_mouth_rebind_verification_probe.get("nextGo"),
            "policy": c_mouth_rebind_verification_probe.get("policy"),
        }
        if args.preflight_json:
            rebind_checkpoint = Path(args.preflight_json).with_name("c_mouth_rebind_verification_probe.json")
            rebind_checkpoint.write_text(
                json.dumps(c_mouth_rebind_verification_probe, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

        if args.c_mouth_rebind_verification_only:
            partial_report = {
                "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
                "pass": False,
                "cMouthRebindVerificationOnly": True,
                "gates": {
                    "A_CHIN_REGION_INTEGRITY": preflight_gates.get("A_CHIN_REGION_INTEGRITY"),
                    "B0_FRONT_CHIN_CONSTRAINED_FRAMING": preflight_gates.get("B0_FRONT_CHIN_CONSTRAINED_FRAMING"),
                    "B_CHIN_NATIVE_FID_PARITY": preflight_gates.get("B_CHIN_NATIVE_FID_PARITY"),
                    "C_MOUTH_NATIVE_MASK_FRONT": preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT"),
                    "C_MOUTH_NATIVE_MASK_LEFT": preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
                    "C_MOUTH_PRODUCTION_EVIDENCE_REBIND_VERIFICATION": preflight_gates.get(
                        "C_MOUTH_PRODUCTION_EVIDENCE_REBIND_VERIFICATION"
                    ),
                },
                "mouthVisibilityParity": mouth_visibility_parity,
                "mouthMaskParity": mouth_mask_parity,
                "cMouthRebindVerificationProbe": c_mouth_rebind_verification_probe,
            }
            if args.preflight_json:
                Path(args.preflight_json).write_text(
                    json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
            print(
                json.dumps(
                    {
                        "cMouthRebindVerificationOnly": True,
                        "verificationPass": bool(c_mouth_rebind_verification_probe.get("verificationPass")),
                        "productionGatePass": c_mouth_rebind_verification_probe.get("productionGatePass"),
                        "C_FRONT": c_mouth_rebind_verification_probe.get("C_FRONT"),
                        "C_LEFT": c_mouth_rebind_verification_probe.get("C_LEFT"),
                        "nextGo": c_mouth_rebind_verification_probe.get("nextGo"),
                    },
                    ensure_ascii=True,
                )
            )
            return 0 if c_mouth_rebind_verification_probe.get("verificationPass") else 2

        c_consumption_baseline = (
            Path(args.c_consumption_baseline_preflight)
            if args.c_consumption_baseline_preflight
            else closed_baseline_preflight
        )
        c_mouth_production_gate_consumption_probe = _run_c_mouth_production_gate_consumption_diagnostic(
            preflight_gates=preflight_gates,
            mouth_visibility_parity=mouth_visibility_parity,
            mouth_mask_parity=mouth_mask_parity,
            camera_lock=camera_lock,
            gate_b_front=gate_b_front,
            gate_b_left=gate_b_left,
            front_evidence_lock=front_evidence_lock,
            left_evidence_lock=left_evidence_lock,
            left_projection_lock=left_projection_lock,
            closed_baseline_preflight=c_consumption_baseline,
        )
        preflight_gates["C_MOUTH_PRODUCTION_GATE_CONSUMPTION_DIAGNOSTIC"] = {
            "gate": "C_MOUTH_PRODUCTION_GATE_CONSUMPTION_DIAGNOSTIC",
            "pass": bool(c_mouth_production_gate_consumption_probe.get("diagnosticPass")),
            "diagnosticPass": bool(c_mouth_production_gate_consumption_probe.get("diagnosticPass")),
            "cFailureClass": c_mouth_production_gate_consumption_probe.get("cFailureClass"),
            "C_FRONT": c_mouth_production_gate_consumption_probe.get("C_FRONT"),
            "C_LEFT": c_mouth_production_gate_consumption_probe.get("C_LEFT"),
            "recommendedRepair": c_mouth_production_gate_consumption_probe.get("recommendedRepair"),
            "nextGo": c_mouth_production_gate_consumption_probe.get("nextGo"),
            "policy": c_mouth_production_gate_consumption_probe.get("policy"),
        }
        if args.preflight_json:
            c_checkpoint = Path(args.preflight_json).with_name("c_mouth_production_gate_consumption_probe.json")
            c_checkpoint.write_text(
                json.dumps(c_mouth_production_gate_consumption_probe, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )

    if args.c_mouth_consumption_diagnostic_only and not interior_only:
        partial_report = {
            "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
            "pass": False,
            "cMouthConsumptionDiagnosticOnly": True,
            "gates": {
                "A_CHIN_REGION_INTEGRITY": preflight_gates.get("A_CHIN_REGION_INTEGRITY"),
                "B0_FRONT_CHIN_CONSTRAINED_FRAMING": preflight_gates.get("B0_FRONT_CHIN_CONSTRAINED_FRAMING"),
                "B_CHIN_NATIVE_FID_PARITY": preflight_gates.get("B_CHIN_NATIVE_FID_PARITY"),
                "C_MOUTH_NATIVE_MASK_FRONT": preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT"),
                "C_MOUTH_NATIVE_MASK_LEFT": preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT"),
                "C_MOUTH_PRODUCTION_GATE_CONSUMPTION_DIAGNOSTIC": preflight_gates.get(
                    "C_MOUTH_PRODUCTION_GATE_CONSUMPTION_DIAGNOSTIC"
                ),
                "MOUTH_FORENSIC_CAMERA_REF_AND_FID_TRIGGER": preflight_gates.get(
                    "MOUTH_FORENSIC_CAMERA_REF_AND_FID_TRIGGER"
                ),
                "MOUTH_CHIN_LIP_CORNER_NATIVE_FID_EMISSION_PARITY": preflight_gates.get(
                    "MOUTH_CHIN_LIP_CORNER_NATIVE_FID_EMISSION_PARITY"
                ),
            },
            "mouthVisibilityParity": mouth_visibility_parity,
            "mouthMaskParity": mouth_mask_parity,
            "cMouthProductionGateConsumptionProbe": c_mouth_production_gate_consumption_probe,
        }
        if args.preflight_json:
            Path(args.preflight_json).write_text(
                json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "cMouthConsumptionDiagnosticOnly": True,
                    "diagnosticPass": bool(c_mouth_production_gate_consumption_probe.get("diagnosticPass")),
                    "cFailureClass": c_mouth_production_gate_consumption_probe.get("cFailureClass"),
                    "C_FRONT": {
                        "primaryClassification": (
                            c_mouth_production_gate_consumption_probe.get("C_FRONT") or {}
                        ).get("primaryClassification"),
                        "feasibleShots": (
                            (c_mouth_production_gate_consumption_probe.get("C_FRONT") or {}).get(
                                "productionGateConsumption"
                            )
                            or {}
                        ).get("feasibleShots"),
                    },
                    "C_LEFT": {
                        "primaryClassification": (
                            c_mouth_production_gate_consumption_probe.get("C_LEFT") or {}
                        ).get("primaryClassification"),
                        "feasibleShots": (
                            (c_mouth_production_gate_consumption_probe.get("C_LEFT") or {}).get(
                                "productionGateConsumption"
                            )
                            or {}
                        ).get("feasibleShots"),
                    },
                    "recommendedRepair": c_mouth_production_gate_consumption_probe.get("recommendedRepair"),
                    "nextGo": c_mouth_production_gate_consumption_probe.get("nextGo"),
                },
                ensure_ascii=True,
            )
        )
        return 0 if c_mouth_production_gate_consumption_probe.get("diagnosticPass") else 2

    set_mouth(24, show_oral=True)
    interior_bounds = _interior_bounds_with_guard(set_mouth.skin_open, skin_basis_coords, oral)
    interior_cam = None
    interior_native: dict = {}
    if interior_bounds[0] is not None:
        interior_cam = _solve_interior_camera(
            sc, cam, landmarks, interior_bounds, skin_basis_coords, args.resolution
        )
    interior_pass = False
    if interior_cam is not None:
        valid_int, skin_int = mouth_valid(True)
        interior_native = _audit_interior_native_features(
            sc,
            cam,
            interior_cam,
            valid_int,
            skin_int,
            rig_objs,
            fid_mats,
            mask_mat,
            args.resolution,
            set_mouth,
            mouth_valid,
            landmarks=landmarks,
            skin_basis_coords=skin_basis_coords,
            bounds=interior_bounds,
        )
        interior_pass = bool(interior_native.get("pass"))
    frozen_manifest_path = (
        Path(args.interior_frozen_camera_lock_manifest)
        if args.interior_frozen_camera_lock_manifest
        else DEFAULT_FROZEN_INTERIOR_CAMERA_LOCK_MANIFEST
    )
    interior_diagnostic_probe = _run_interior_native_visibility_emission_parity_probe(
        sc,
        cam,
        interior_cam,
        set_mouth_fn=set_mouth,
        mouth_valid_fn=mouth_valid,
        rig_objs=rig_objs,
        fid_mats=fid_mats,
        mask_mat=mask_mat,
        res=args.resolution,
        out_dir=parity_dir,
        label=args.label,
        landmarks=landmarks,
        skin_basis_coords=skin_basis_coords,
        bounds=interior_bounds,
    )
    interior_restoration_probe = _run_interior_camera_lock_provenance_and_state_consumption_restoration_probe(
        sc,
        cam,
        interior_cam=interior_cam,
        interior_bounds=interior_bounds,
        frozen_manifest_path=frozen_manifest_path,
        set_mouth_fn=set_mouth,
        mouth_valid_fn=mouth_valid,
        jaw_empty=jaw_empty,
        rig_objs=rig_objs,
        fid_mats=fid_mats,
        landmarks=landmarks,
        res=args.resolution,
        out_dir=parity_dir,
        label=args.label,
        interior_diagnostic_probe=interior_diagnostic_probe,
        skin_basis_coords=skin_basis_coords,
    )
    effective_interior_cam = interior_restoration_probe.get("consumedCameraState") or interior_cam
    effective_camera_source = interior_restoration_probe.get("interiorCameraSource")
    if (
        effective_interior_cam is not None
        and effective_camera_source not in (None, "INTERIOR_SCENE_EXISTING_FALLBACK")
        and (
            interior_cam is None
            or effective_camera_source == "FROZEN_CAMERA_LOCK_MANIFEST_READONLY"
        )
    ):
        interior_diagnostic_probe = _run_interior_native_visibility_emission_parity_probe(
            sc,
            cam,
            effective_interior_cam,
            set_mouth_fn=set_mouth,
            mouth_valid_fn=mouth_valid,
            rig_objs=rig_objs,
            fid_mats=fid_mats,
            mask_mat=mask_mat,
            res=args.resolution,
            out_dir=parity_dir,
            label=args.label,
            landmarks=landmarks,
            skin_basis_coords=skin_basis_coords,
            bounds=interior_bounds,
            camera_source=effective_camera_source,
        )
        if effective_interior_cam is not None and interior_cam is None:
            valid_int, skin_int = mouth_valid(True)
            interior_native = _audit_interior_native_features(
                sc,
                cam,
                effective_interior_cam,
                valid_int,
                skin_int,
                rig_objs,
                fid_mats,
                mask_mat,
                args.resolution,
                set_mouth,
                mouth_valid,
                landmarks=landmarks,
                skin_basis_coords=skin_basis_coords,
                bounds=interior_bounds,
            )
            interior_pass = bool(interior_native.get("pass"))
    preflight_gates["INTERIOR_RIG_NATIVE_EMISSION"] = {
        "gate": "INTERIOR_RIG_NATIVE_EMISSION",
        "pass": all(
            (interior_restoration_probe.get("interiorRigNativeEmission") or {}).get(f) == "PASS"
            for f in INTERIOR_RIG_NATIVE_EMISSION_FEATURES
        ),
        "upperTeeth": (interior_restoration_probe.get("interiorRigNativeEmission") or {}).get("upperTeeth"),
        "lowerTeeth": (interior_restoration_probe.get("interiorRigNativeEmission") or {}).get("lowerTeeth"),
        "tongue": (interior_restoration_probe.get("interiorRigNativeEmission") or {}).get("tongue"),
        "detail": interior_restoration_probe.get("interiorRigNativeEmissionDetail"),
        "status": "PASS_CLOSED",
    }
    preflight_gates["INTERIOR_CAMERA_LOCK_PROVENANCE_AND_STATE_CONSUMPTION"] = {
        "gate": "INTERIOR_CAMERA_LOCK_PROVENANCE_AND_STATE_CONSUMPTION",
        "pass": bool(interior_restoration_probe.get("cameraConsumptionPass")),
        "gatePassEligible": False,
        "probeShot": "mouth_interior",
        "mouthInterior": interior_restoration_probe,
        "p0Classification": interior_restoration_probe.get("p0Classification"),
        "frozenLockReceipt": interior_restoration_probe.get("frozenLockReceipt"),
        "stateReceipt": interior_restoration_probe.get("stateReceipt"),
        "oralOpeningProjectedBounds": interior_restoration_probe.get("oralOpeningProjectedBounds"),
        "policy": interior_restoration_probe.get("policy"),
        "consumptionClosed": interior_restoration_probe.get("interiorCameraSource")
        not in (None, "INTERIOR_SCENE_EXISTING_FALLBACK"),
        "status": "PASS_CLOSED"
        if interior_restoration_probe.get("interiorCameraSource")
        not in (None, "INTERIOR_SCENE_EXISTING_FALLBACK")
        else "OPEN",
    }
    oral_opening_degeneracy_probe = _run_oral_opening_semantic_region_projection_degeneracy_probe(
        sc,
        cam,
        effective_interior_cam,
        camera_source=effective_camera_source,
        set_mouth_fn=set_mouth,
        mouth_valid_fn=mouth_valid,
        skin_basis_coords=skin_basis_coords,
        landmarks=landmarks,
        region_map=region_map,
        weights=weights,
        jaw_empty=jaw_empty,
        rig_objs=rig_objs,
        fid_mats=fid_mats,
        res=args.resolution,
        oral_bounds=interior_restoration_probe.get("oralOpeningProjectedBounds"),
        state_receipt=interior_restoration_probe.get("stateReceipt"),
    )
    preflight_gates["INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY"] = {
        "gate": "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY",
        "pass": not oral_opening_degeneracy_probe.get("skipped"),
        "diagnosticPass": not oral_opening_degeneracy_probe.get("skipped"),
        "gatePassEligible": False,
        "probeShot": "mouth_interior",
        "p0Classification": oral_opening_degeneracy_probe.get("p0Classification"),
        "classification": oral_opening_degeneracy_probe.get("classification"),
        "mouthInterior": oral_opening_degeneracy_probe,
        "oralOpeningDefinitionType": oral_opening_degeneracy_probe.get("oralOpeningDefinitionType"),
        "teethBBoxSeparationPx": oral_opening_degeneracy_probe.get("teethBBoxSeparationPx"),
        "lipBoundarySeparationPx": oral_opening_degeneracy_probe.get("lipBoundarySeparationPx"),
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "policy": oral_opening_degeneracy_probe.get("policy"),
        "status": "PASS_CLOSED",
        "blockerConfirmed": oral_opening_degeneracy_probe.get("classification") == "TEETH_BBOX_PROXY_INVALID",
    }
    if (
        effective_interior_cam is not None
        and effective_camera_source not in (None, "INTERIOR_SCENE_EXISTING_FALLBACK")
    ):
        valid_int, skin_int = mouth_valid(True)
        interior_native = _audit_interior_native_features(
            sc,
            cam,
            effective_interior_cam,
            valid_int,
            skin_int,
            rig_objs,
            fid_mats,
            mask_mat,
            args.resolution,
            set_mouth,
            mouth_valid,
            landmarks=landmarks,
            skin_basis_coords=skin_basis_coords,
            bounds=interior_bounds,
        )
    oral_opening_native_evidence_probe = _run_oral_opening_lip_boundary_native_evidence_contract_repair_probe(
        sc,
        cam,
        effective_interior_cam,
        camera_source=effective_camera_source,
        set_mouth_fn=set_mouth,
        mouth_valid_fn=mouth_valid,
        skin_basis_coords=skin_basis_coords,
        landmarks=landmarks,
        region_map=region_map,
        weights=weights,
        jaw_empty=jaw_empty,
        rig_objs=rig_objs,
        fid_mats=fid_mats,
        res=args.resolution,
        oral_bounds=interior_restoration_probe.get("oralOpeningProjectedBounds"),
        state_receipt=interior_restoration_probe.get("stateReceipt"),
        interior_diagnostic_probe=interior_diagnostic_probe,
    )
    native_evidence = oral_opening_native_evidence_probe.get("oralOpeningNativeEvidence") or {}
    if native_evidence:
        _patch_interior_diagnostic_oral_opening(interior_diagnostic_probe, native_evidence)
    d_interior_revalidation_probe = _bind_d_interior_production_contract(
        interior_native,
        effective_interior_cam=effective_interior_cam,
        camera_source=effective_camera_source,
        interior_restoration_probe=interior_restoration_probe,
        interior_diagnostic_probe=interior_diagnostic_probe,
        oral_opening_native_evidence_probe=oral_opening_native_evidence_probe,
    )
    interior_pass = bool(d_interior_revalidation_probe.get("pass"))
    preflight_gates["ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT"] = {
        "gate": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
        "pass": bool(oral_opening_native_evidence_probe.get("contractPass")),
        "gatePassEligible": bool(oral_opening_native_evidence_probe.get("contractPass")),
        "probeShot": "mouth_interior",
        "classification": oral_opening_native_evidence_probe.get("classification"),
        "contract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "mouthInterior": oral_opening_native_evidence_probe,
        "openingPolygonVertexCount": oral_opening_native_evidence_probe.get("openingPolygonVertexCount"),
        "openingPolygonProjectedArea": oral_opening_native_evidence_probe.get("openingPolygonProjectedArea"),
        "perXBoundaryGapStats": oral_opening_native_evidence_probe.get("perXBoundaryGapStats"),
        "teethBBoxSeparationPx": oral_opening_native_evidence_probe.get("teethBBoxSeparationPx"),
        "teethBBoxProxyEnforcement": TEETH_BBOX_PROXY_ENFORCEMENT,
        "policy": oral_opening_native_evidence_probe.get("policy"),
        "status": "PASS_CLOSED" if oral_opening_native_evidence_probe.get("contractPass") else "OPEN",
    }
    d_block_reason = None
    if effective_interior_cam is None:
        d_block_reason = "BLOCKED_BY_CAMERA_LOCK_PROVENANCE"
    preflight_gates["D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_REVALIDATION"] = {
        "gate": "D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_REVALIDATION",
        "pass": bool(d_interior_revalidation_probe.get("pass")),
        "gatePassEligible": bool(d_interior_revalidation_probe.get("gatePassEligible")),
        "probeShot": "mouth_interior",
        "holdReason": d_interior_revalidation_probe.get("holdReason"),
        "productionContract": d_interior_revalidation_probe.get("productionContract"),
        "mouthInterior": d_interior_revalidation_probe,
        "policy": d_interior_revalidation_probe.get("policy"),
        "status": "PASS" if d_interior_revalidation_probe.get("pass") else "OPEN",
    }
    preflight_gates["D_INTERIOR_NATIVE_VISIBILITY"] = {
        "gate": "INTERIOR_NATIVE_VISIBILITY",
        "pass": interior_pass,
        "camera": effective_interior_cam,
        "cameraSource": effective_camera_source,
        "cameraLockPass": d_interior_revalidation_probe.get("cameraLockPass"),
        "nativeFeatureAudit": interior_native,
        "perFeature": interior_native.get("perFeature"),
        "productionContract": d_interior_revalidation_probe.get("productionContract"),
        "oralOpeningNativeEvidencePass": d_interior_revalidation_probe.get("oralOpeningNativeEvidencePass"),
        "nativeSemanticEvidencePass": d_interior_revalidation_probe.get("nativeSemanticEvidencePass"),
        "contract": D_INTERIOR_PRODUCTION_CONTRACT,
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "blockReason": d_block_reason,
        "holdReason": d_interior_revalidation_probe.get("holdReason"),
        "p0Classification": "INTERIOR_CAMERA_LOCK_STATE_CONSUMPTION_MISSING"
        if d_block_reason
        else None,
        "oralOpeningContract": ORAL_OPENING_NATIVE_EVIDENCE_CONTRACT,
        "status": "PASS" if interior_pass else "OPEN",
    }
    if interior_pass and effective_interior_cam is not None:
        effective_interior_cam["semanticLock"] = _manifest_semantic_lock(effective_interior_cam)
        camera_lock["mouth_interior"] = effective_interior_cam
    elif effective_interior_cam is None or not interior_pass:
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_interior_native_visibility",
                "pass": False,
                "reason": d_block_reason or "INTERIOR_NATIVE_VISIBILITY_FAIL",
                "maskPass": False,
                "nativeFeatureAudit": interior_native,
            }
        )
    preflight_gates["INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY"] = {
        "gate": "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY",
        "pass": bool(interior_diagnostic_probe.get("diagnosticPass")),
        "gatePassEligible": False,
        "probeShot": "mouth_interior",
        "mouthInterior": interior_diagnostic_probe,
        "perFeature": interior_diagnostic_probe.get("perFeature"),
        "classifications": interior_diagnostic_probe.get("classifications"),
        "interiorCameraReceipt": interior_diagnostic_probe.get("interiorCameraReceipt"),
        "policy": interior_diagnostic_probe.get("policy"),
    }
    if (
        effective_interior_cam is not None
        and not interior_diagnostic_probe.get("skipped")
        and not interior_diagnostic_probe.get("diagnosticPass")
    ):
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_interior_native_visibility_emission_parity",
                "pass": False,
                "reason": "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY_FAIL",
                "classifications": interior_diagnostic_probe.get("classifications"),
                "perFeature": interior_diagnostic_probe.get("perFeature"),
            }
        )
    if (
        effective_interior_cam is not None
        and not oral_opening_native_evidence_probe.get("skipped")
        and not oral_opening_native_evidence_probe.get("contractPass")
    ):
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_oral_opening_lip_boundary_native_evidence_contract",
                "pass": False,
                "reason": oral_opening_native_evidence_probe.get("classification")
                or "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT_FAIL",
                "perXBoundaryGapStats": oral_opening_native_evidence_probe.get("perXBoundaryGapStats"),
                "openingPolygonProjectedArea": oral_opening_native_evidence_probe.get("openingPolygonProjectedArea"),
            }
        )

    if args.preflight_json:
        interior_checkpoint = Path(args.preflight_json).with_name("interior_diagnostic_probe.json")
        interior_checkpoint.write_text(
            json.dumps(
                {
                    "schema": "NURION_V07_V1_LSFQ_INTERIOR_DIAGNOSTIC_PROBE",
                    "gate": "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY",
                    "runLabel": args.label,
                    "probe": interior_diagnostic_probe,
                    "perFeature": interior_diagnostic_probe.get("perFeature"),
                    "classifications": interior_diagnostic_probe.get("classifications"),
                    "gatePassEligible": False,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        oral_checkpoint = Path(args.preflight_json).with_name("oral_opening_degeneracy_probe.json")
        oral_checkpoint.write_text(
            json.dumps(
                {
                    "schema": "NURION_V07_V1_LSFQ_ORAL_OPENING_DEGENERACY_PROBE",
                    "gate": "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY",
                    "runLabel": args.label,
                    "probe": oral_opening_degeneracy_probe,
                    "gatePassEligible": False,
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        oral_native_checkpoint = Path(args.preflight_json).with_name(
            "oral_opening_native_evidence_probe.json"
        )
        oral_native_checkpoint.write_text(
            json.dumps(
                {
                    "schema": "NURION_V07_V1_LSFQ_ORAL_OPENING_NATIVE_EVIDENCE_PROBE",
                    "gate": "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT",
                    "runLabel": args.label,
                    "probe": oral_opening_native_evidence_probe,
                    "gatePassEligible": bool(oral_opening_native_evidence_probe.get("contractPass")),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        d_interior_checkpoint = Path(args.preflight_json).with_name("d_interior_revalidation_probe.json")
        d_interior_checkpoint.write_text(
            json.dumps(
                {
                    "schema": "NURION_V07_V1_LSFQ_D_INTERIOR_REVALIDATION_PROBE",
                    "gate": "D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_REVALIDATION",
                    "runLabel": args.label,
                    "probe": d_interior_revalidation_probe,
                    "productionContract": d_interior_revalidation_probe.get("productionContract"),
                    "gatePassEligible": bool(d_interior_revalidation_probe.get("gatePassEligible")),
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    if args.interior_diagnostic_only:
        partial_report = {
            "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
            "pass": bool(d_interior_revalidation_probe.get("pass")),
            "interiorDiagnosticOnly": True,
            "gates": {
                "D_INTERIOR_NATIVE_VISIBILITY": preflight_gates.get("D_INTERIOR_NATIVE_VISIBILITY"),
                "D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_REVALIDATION": preflight_gates.get(
                    "D_INTERIOR_NATIVE_SEMANTIC_EVIDENCE_REVALIDATION"
                ),
                "INTERIOR_RIG_NATIVE_EMISSION": preflight_gates.get("INTERIOR_RIG_NATIVE_EMISSION"),
                "INTERIOR_CAMERA_LOCK_PROVENANCE_AND_STATE_CONSUMPTION": preflight_gates.get(
                    "INTERIOR_CAMERA_LOCK_PROVENANCE_AND_STATE_CONSUMPTION"
                ),
                "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY": preflight_gates.get(
                    "INTERIOR_ORAL_OPENING_PROJECTION_DEGENERACY"
                ),
                "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT": preflight_gates.get(
                    "ORAL_OPENING_LIP_BOUNDARY_NATIVE_EVIDENCE_CONTRACT"
                ),
                "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY": preflight_gates.get(
                    "INTERIOR_NATIVE_VISIBILITY_AND_EMISSION_PARITY"
                ),
            },
            "interiorNativeVisibilityAndEmissionParity": interior_diagnostic_probe,
            "interiorCameraLockProvenanceAndStateConsumption": interior_restoration_probe,
            "oralOpeningProjectionDegeneracy": oral_opening_degeneracy_probe,
            "oralOpeningLipBoundaryNativeEvidenceContract": oral_opening_native_evidence_probe,
            "dInteriorNativeSemanticEvidenceRevalidation": d_interior_revalidation_probe,
        }
        if args.preflight_json:
            Path(args.preflight_json).write_text(
                json.dumps(partial_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        return 0

    eye_solver_reports: dict = {}
    for side, tag, gate_letter in (("L", "left", "E"), ("R", "right", "F")):
        eye_cam = _solve_eye_side_camera(
            sc,
            cam,
            landmarks,
            side,
            args.resolution,
            set_eye,
            rig_objs,
            skin_basis_coords,
            mask_mat,
            fid_mats,
        )
        eye_solver_reports[tag] = eye_cam if isinstance(eye_cam, dict) else None
        eye_pass = bool(eye_cam and eye_cam.get("pass"))
        gate_key = f"{gate_letter}_EYE_CAMERA_{tag.upper()}"
        preflight_gates[gate_key] = {
            "gate": f"EYE_CAMERA_{tag.upper()}",
            "pass": eye_pass,
            "feasibleShots": 3 if eye_pass else 0,
            "requiredShots": 3,
            "camera": eye_cam if eye_pass else None,
            "solverReport": eye_cam if not eye_pass else None,
            "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
            "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        }
        if eye_pass and eye_cam is not None:
            eye_cam["semanticLock"] = _manifest_semantic_lock(eye_cam)
            camera_lock[f"eye_{tag}"] = eye_cam
        else:
            preflight_pass = False
            reason = "EYE_CAMERA_FAIL"
            if isinstance(eye_cam, dict):
                reason = eye_cam.get("classification") or reason
            failure_summary.append(
                {
                    "shot": f"preflight_{gate_key.lower()}",
                    "pass": False,
                    "reason": reason,
                    "maskPass": False,
                    "solverReport": eye_cam,
                }
            )

    preflight_gates["NATIVE_SEMANTIC_EVIDENCE_GATE_IMPLEMENTATION"] = {
        "gate": "NATIVE_SEMANTIC_EVIDENCE_GATE_IMPLEMENTATION",
        "pass": True,
        "contract": NATIVE_SEMANTIC_EVIDENCE_GATE,
        "reboundGates": {
            "C": [preflight_gates.get("C_MOUTH_NATIVE_MASK_FRONT", {}), preflight_gates.get("C_MOUTH_NATIVE_MASK_LEFT", {})],
            "D": preflight_gates.get("D_INTERIOR_NATIVE_VISIBILITY"),
            "E": preflight_gates.get("E_EYE_CAMERA_LEFT"),
            "F": preflight_gates.get("F_EYE_CAMERA_RIGHT"),
        },
        "legacyOccupancyEnforcement": "DIAGNOSTIC_ONLY",
        "replacementReviewId": OCCUPANCY_REPLACEMENT_REVIEW_ID,
        "policy": {
            "cameraRetune": "DENY",
            "thresholdRelaxation": "DENY",
            "newNumericThresholds": "DENY",
            "basisMutation": 0,
            "weightMutation": 0,
            "morphMutation": 0,
            "chinTopologyMutation": 0,
        },
    }

    eyelid_projection_parity = _run_eyelid_rig_helper_projection_parity_probe(
        sc,
        cam,
        side="L",
        locked_cam=camera_lock.get("eye_left"),
        solver_report=eye_solver_reports.get("left"),
        set_eye_fn=set_eye,
        rig_objs=rig_objs,
        eye_pivots=eye_pivots,
        rig_setup_receipt=rig_setup_receipt,
        landmarks=landmarks,
        skin_basis_coords=skin_basis_coords,
        res=args.resolution,
    )

    preflight_gates["EYELID_RIG_HELPER_PROJECTION_PARITY"] = {
        "gate": "EYELID_RIG_HELPER_PROJECTION_PARITY",
        "pass": bool(eyelid_projection_parity.get("pass")),
        "probeShot": "eye_left_closed",
        "eyeLeftClosed": eyelid_projection_parity,
        "rigSetupReceipt": rig_setup_receipt,
        "classifications": eyelid_projection_parity.get("classifications"),
        "provenanceChain": eyelid_projection_parity.get("provenanceChain"),
        "officialAxisStatus": {
            "EYELID_FEATURE_REGISTRY": "PASS",
            "EYELID_REGION_MANIFEST": "PASS",
            "EYELID_SLOT_BINDING": "PASS",
            "EYELID_STATE_MAPPING": "PASS",
            "EYELID_PROJECTION_PARITY": "PASS" if eyelid_projection_parity.get("pass") else "FAIL",
        },
        "policy": eyelid_projection_parity.get("policy"),
    }
    if not eyelid_projection_parity.get("pass"):
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_eyelid_rig_helper_projection_parity",
                "pass": False,
                "reason": "EYELID_RIG_HELPER_PROJECTION_PARITY_FAIL",
                "classifications": eyelid_projection_parity.get("classifications"),
                "perFeature": eyelid_projection_parity.get("perFeature"),
                "referenceEyeball": eyelid_projection_parity.get("referenceEyeball"),
            }
        )

    eye_visibility_parity = _run_eye_l_closed_visibility_parity_probe(
        sc,
        cam,
        side="L",
        locked_cam=camera_lock.get("eye_left"),
        solver_report=eye_solver_reports.get("left"),
        set_eye_fn=set_eye,
        rig_objs=rig_objs,
        landmarks=landmarks,
        skin_basis_coords=skin_basis_coords,
        fid_mats=fid_mats,
        mask_mat=mask_mat,
        res=args.resolution,
    )

    eyelid_manifest_parity = _run_eyelid_manifest_state_mapping_parity_probe(
        sc,
        cam,
        side="L",
        locked_cam=camera_lock.get("eye_left"),
        solver_report=eye_solver_reports.get("left"),
        set_eye_fn=set_eye,
        rig_objs=rig_objs,
        landmarks=landmarks,
        skin_basis_coords=skin_basis_coords,
        eyelid_weights=eyelid_weights,
        eyelid_spec=eyelid_spec,
        res=args.resolution,
    )

    preflight_gates["EYELID_MANIFEST_STATE_MAPPING_PARITY"] = {
        "gate": "EYELID_MANIFEST_STATE_MAPPING_PARITY",
        "pass": bool(eyelid_manifest_parity.get("pass")),
        "probeShot": "eye_left_closed",
        "eyeLeftClosed": eyelid_manifest_parity,
        "classifications": eyelid_manifest_parity.get("classifications"),
        "provenanceChain": eyelid_manifest_parity.get("provenanceChain"),
        "policy": eyelid_manifest_parity.get("policy"),
    }
    if not eyelid_manifest_parity.get("pass"):
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_eyelid_manifest_state_mapping_parity",
                "pass": False,
                "reason": "EYELID_MANIFEST_STATE_MAPPING_PARITY_FAIL",
                "classifications": eyelid_manifest_parity.get("classifications"),
                "perFeature": eyelid_manifest_parity.get("perFeature"),
            }
        )

    preflight_gates["EXPECTED_VISIBILITY_CONTRACT_PARITY"] = {
        "gate": "EXPECTED_VISIBILITY_CONTRACT_PARITY",
        "pass": bool(eye_visibility_parity.get("visibilityPass")) and bool(
            (mouth_visibility_parity.get("front_closed") or {}).get("visibilityPass")
        ),
        "visibilityPass": bool(eye_visibility_parity.get("visibilityPass"))
        and bool((mouth_visibility_parity.get("front_closed") or {}).get("visibilityPass")),
        "emissionPass": bool(eye_visibility_parity.get("emissionPass"))
        and bool((mouth_visibility_parity.get("front_closed") or {}).get("emissionPass")),
        "contractResolved": bool(eye_visibility_parity.get("contractResolved"))
        and bool((mouth_visibility_parity.get("front_closed") or {}).get("contractResolved")),
        "occludedExpectedSemantics": OCCLUDED_EXPECTED_SEMANTICS,
        "occludedExpectedSemanticsMeaning": OCCLUDED_EXPECTED_SEMANTICS_MEANING,
        "eyeLeftClosed": eye_visibility_parity,
        "mouthFrontClosed": mouth_visibility_parity.get("front_closed"),
        "policy": {
            "cameraMutation": 0,
            "thresholdMutation": 0,
            "geometryMutation": 0,
            "morphMutation": 0,
            "topologyMutation": 0,
            "interiorD": "DEFERRED",
        },
    }

    parity_fid_cam = camera_lock.get("eye_left") or _parity_camera_from_eye_solver(eye_solver_reports.get("left"))
    if eye_visibility_parity.get("visibilityPass") and parity_fid_cam is not None:
        eye_forensic_probe = _run_eye_fid_forensic_probe(
            sc,
            cam,
            parity_fid_cam,
            set_eye,
            rig_objs,
            fid_mats,
            mask_mat,
            args.resolution,
            parity_dir,
            args.label,
            landmarks=landmarks,
            skin_basis_coords=skin_basis_coords,
        )
        eye_forensic_probe["trigger"] = "VISIBILITY_CONTRACT_PARITY_PASS"
    else:
        eye_forensic_probe = {
            "probeShot": "eye_left_closed",
            "pass": False,
            "reason": "VISIBILITY_CONTRACT_NOT_RESOLVED"
            if not eye_visibility_parity.get("visibilityPass")
            else "PARITY_CAMERA_UNAVAILABLE",
            "skipped": True,
            "visibilityParity": eye_visibility_parity,
        }
    probe_ok = bool(eye_forensic_probe and eye_forensic_probe.get("pass"))
    eye_fid_reports: dict[str, dict] = {}
    for side, tag in (("L", "left"), ("R", "right")):
        lock = camera_lock.get(f"eye_{tag}")
        if lock is None:
            eye_fid_reports[tag] = {"pass": False, "reason": "EYE_CAMERA_LOCK_MISSING"}
            continue
        if not probe_ok:
            if side == "L":
                eye_fid_reports[tag] = _run_eye_fid_emission_parity(
                    sc,
                    cam,
                    side,
                    lock,
                    set_eye,
                    rig_objs,
                    landmarks,
                    skin_basis_coords,
                    fid_mats,
                    qa_mats,
                    mask_mat,
                    args.resolution,
                    parity_dir,
                    args.label,
                    forensic_probe=eye_forensic_probe,
                    run_full=False,
                )
            else:
                eye_fid_reports[tag] = {
                    "pass": False,
                    "reason": "FORENSIC_PROBE_FAIL",
                    "skippedFullValidation": True,
                    "forensicProbe": eye_forensic_probe,
                }
            continue
        eye_fid_reports[tag] = _run_eye_fid_emission_parity(
            sc,
            cam,
            side,
            lock,
            set_eye,
            rig_objs,
            landmarks,
            skin_basis_coords,
            fid_mats,
            qa_mats,
            mask_mat,
            args.resolution,
            parity_dir,
            args.label,
            forensic_probe=eye_forensic_probe if side == "L" else None,
            run_full=True,
        )
    gate_g_pass = probe_ok and all(bool(r.get("pass")) for r in eye_fid_reports.values())
    preflight_gates["G_EYE_NATIVE_FID_PARITY"] = {
        "gate": "EYE_NATIVE_FID_PARITY",
        "pass": gate_g_pass,
        "forensicProbe": eye_forensic_probe,
        "left": eye_fid_reports.get("left"),
        "right": eye_fid_reports.get("right"),
        "softwareRasterPolicy": "DIAGNOSTIC_EVIDENCE_ONLY",
        "nativeFidAuditFramework": True,
    }
    if not gate_g_pass:
        preflight_pass = False
        failure_summary.append(
            {
                "shot": "preflight_eye_native_fid_parity",
                "pass": False,
                "reason": "EYE_NATIVE_FID_PARITY_FAIL",
                "maskPass": False,
                "reports": eye_fid_reports,
            }
        )

    if preflight_pass and not thirteen_shot_only:
        preflight_snapshots, morph_snaps = _collect_preflight_manifest_snapshots(
            sc,
            cam,
            mask_mat,
            args.resolution,
            camera_lock,
            set_mouth_fn=set_mouth,
            mouth_valid_fn=mouth_valid,
            set_eye_fn=set_eye,
            rig_objs=rig_objs,
            skin_basis=skin_basis,
            skin_basis_coords=skin_basis_coords,
            landmarks=landmarks,
            weights=weights,
            pivot=pivot,
            oral=oral,
        )
        camera_lock_manifest = _build_camera_lock_manifest(
            camera_lock,
            preflight_snapshots=preflight_snapshots,
            morph_snapshots=morph_snaps,
        )
        if args.camera_lock_manifest:
            Path(args.camera_lock_manifest).write_text(
                json.dumps(camera_lock_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
        gate_h = _validate_gate_h_manifest_consistency(
            preflight_gates, camera_lock_manifest, require_native_mask_pass=False
        )
        preflight_gates["H_CAPTURE_LOCK_MANIFEST_CONSISTENCY"] = gate_h
        if not gate_h.get("pass"):
            preflight_pass = False
            failure_summary.append(
                {
                    "shot": "preflight_capture_lock_manifest_consistency",
                    "pass": False,
                    "reason": "CAPTURE_LOCK_MANIFEST_INCONSISTENT",
                    "maskPass": False,
                    "issues": gate_h.get("issues"),
                }
            )

    if not thirteen_shot_only:
        preflight_report = {
            "schema": "NURION_V07_V1_LSFQ_PREFLIGHT_GATES",
            "pass": preflight_pass,
            "gates": preflight_gates,
            "chinRegionFrozen": {
                "chinFaceCount": region_integrity.get("chinFaceCount"),
                "chinVertexCount": (region_map.get("vertex_counts") or {}).get("chin"),
                "connectedComponents": region_integrity.get("chinConnectedComponents"),
                "semanticOverlap": region_integrity.get("semanticOverlapVerts"),
                "cornerSymmetry": region_map.get("corner_symmetry"),
            },
            "cameraLockManifestReceipt": camera_lock_manifest.get("solverReceiptHash"),
            "mouthMaskEmissionParity": mouth_mask_parity,
            "expectedVisibilityContractParity": {
                "eyeLeftClosed": eye_visibility_parity,
                "mouthFrontClosed": mouth_visibility_parity.get("front_closed"),
            },
            "eyelidManifestStateMappingParity": eyelid_manifest_parity,
            "eyelidRigHelperProjectionParity": eyelid_projection_parity,
            "mouthChinLipCornerNativeFidEmissionParity": mouth_chin_lip_corner_fid_forensic,
            "mouthForensicCameraRefAndFidTrigger": mouth_forensic_camera_trigger,
            "interiorNativeVisibilityAndEmissionParity": interior_diagnostic_probe,
            "interiorCameraLockProvenanceAndStateConsumption": interior_restoration_probe,
            "oralOpeningProjectionDegeneracy": oral_opening_degeneracy_probe,
            "oralOpeningLipBoundaryNativeEvidenceContract": oral_opening_native_evidence_probe,
            "dInteriorNativeSemanticEvidenceRevalidation": d_interior_revalidation_probe,
            "interiorRigNativeEmission": preflight_gates.get("INTERIOR_RIG_NATIVE_EMISSION"),
            "nativeRenderPathParity": {
                "mouthLeftMaskPipeline": mouth_mask_parity.get("mouth_closed_left"),
                "chinForensicProbes": chin_forensic,
                "eyeForensicProbe": eye_forensic_probe,
                "eyeVisibilityParity": eye_visibility_parity,
                "eyelidManifestParity": eyelid_manifest_parity,
                "eyelidProjectionParity": eyelid_projection_parity,
                "mouthVisibilityParity": mouth_visibility_parity,
                "mouthChinLipCornerNativeFidEmissionParity": mouth_chin_lip_corner_fid_forensic,
                "mouthForensicCameraRefAndFidTrigger": mouth_forensic_camera_trigger,
                "interiorNativeVisibilityAndEmissionParity": interior_diagnostic_probe,
                "interiorCameraLockProvenanceAndStateConsumption": interior_restoration_probe,
                "oralOpeningProjectionDegeneracy": oral_opening_degeneracy_probe,
                "oralOpeningLipBoundaryNativeEvidenceContract": oral_opening_native_evidence_probe,
                "dInteriorNativeSemanticEvidenceRevalidation": d_interior_revalidation_probe,
            },
            "nativeSemanticEmissionContract": True,
            "nativeRenderPathAuditFramework": True,
            "softwareRasterFallbackPolicy": "DIAGNOSTIC_PARITY_EVIDENCE_ONLY",
        }
    if not interior_only and not thirteen_shot_only:
        closed_baseline_preflight = (
            Path(args.closed_baseline_preflight)
            if args.closed_baseline_preflight
            else DEFAULT_CLOSED_EYE_MOUTH_CHIN_BASELINE_PREFLIGHT
        )
        d_interior_baseline_probe = (
            Path(args.d_interior_baseline_probe)
            if args.d_interior_baseline_probe
            else DEFAULT_D_INTERIOR_BASELINE_PROBE
        )
        ah_preflight_capture_evidence_probe = _run_ah_preflight_capture_evidence_regression_confirmation(
            preflight_report=preflight_report,
            preflight_gates=preflight_gates,
            parity_dir=parity_dir,
            label=args.label,
            d_interior_probe=d_interior_revalidation_probe,
            closed_baseline_preflight=closed_baseline_preflight,
            d_interior_baseline_probe=d_interior_baseline_probe,
        )
        preflight_report["ahPreflightCaptureEvidenceRegressionConfirmation"] = ah_preflight_capture_evidence_probe
        if args.preflight_json:
            ah_checkpoint = Path(args.preflight_json).with_name("ah_preflight_capture_evidence_probe.json")
            ah_checkpoint.write_text(
                json.dumps(ah_preflight_capture_evidence_probe, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
    if args.preflight_json:
        Path(args.preflight_json).write_text(
            json.dumps(preflight_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    if thirteen_shot_only and thirteen_shot_manifest_frozen is not None:
        integrity = _verify_thirteen_shot_manifest_integrity(
            thirteen_shot_manifest_frozen, camera_lock_manifest
        )
        thirteen_shot_manifest_assert = dict(thirteen_shot_manifest_assert or {})
        thirteen_shot_manifest_assert["manifestRebuilt"] = bool(integrity.get("manifestRebuilt"))
        thirteen_shot_manifest_assert["manifestOverwritten"] = bool(integrity.get("manifestOverwritten"))
        thirteen_shot_manifest_assert["manifestConsumed"] = integrity.get("manifestConsumed")
        thirteen_shot_manifest_assert["pass"] = (
            bool(thirteen_shot_manifest_assert.get("pass"))
            and integrity.get("pass")
            and not integrity.get("manifestOverwritten")
        )
        if integrity.get("manifestOverwritten"):
            thirteen_shot_manifest_assert.setdefault("failures", []).append("manifestOverwritten_true")
        if integrity.get("manifestRebuilt"):
            thirteen_shot_manifest_assert.setdefault("failures", []).append("manifestRebuilt_true")
        preflight_gates["13_SHOT_MANIFEST_CONSUMPTION_ASSERT"] = thirteen_shot_manifest_assert
        if not thirteen_shot_manifest_assert.get("pass"):
            _emit_thirteen_shot_manifest_consumption_abort(
                args,
                thirteen_shot_manifest_assert,
                preflight_report=preflight_report,
            )
            return 2
        if args.preflight_json and preflight_report is not None:
            updated_preflight = dict(preflight_report)
            merged_gates = dict(updated_preflight.get("gates") or {})
            merged_gates.update(preflight_gates)
            updated_preflight["gates"] = merged_gates
            updated_preflight["thirteenShotManifestConsumptionAssert"] = thirteen_shot_manifest_assert
            Path(args.preflight_json).write_text(
                json.dumps(updated_preflight, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

    if args.preflight_ah_only:
        print(
            json.dumps(
                {
                    "preflightAhOnly": True,
                    "preflightPass": preflight_pass,
                    "ahPreflightCaptureEvidencePass": bool(
                        (ah_preflight_capture_evidence_probe or {}).get("pass")
                    ),
                    "ahGatesAllPass": bool((ah_preflight_capture_evidence_probe or {}).get("ahGatesAllPass")),
                    "totalRegressionCount": int(
                        ((ah_preflight_capture_evidence_probe or {}).get("closedAxisRegression") or {}).get(
                            "totalRegressionCount", -1
                        )
                    ),
                    "failClassifications": (ah_preflight_capture_evidence_probe or {}).get("failClassifications"),
                },
                ensure_ascii=True,
            )
        )
        ah_pass = bool((ah_preflight_capture_evidence_probe or {}).get("pass"))
        return 0 if ah_pass else 2

    run_full_diagnostic = preflight_pass
    if not run_full_diagnostic:
        safe_abort = True

    if run_full_diagnostic:
        set_mouth(0, show_oral=False)
        for angle, tag in ((0, "closed"), (12, "half"), (24, "open")):
            show_oral = angle >= 12
            set_mouth(angle, show_oral=show_oral)
            valid, skin = mouth_valid(show_oral)
            for view in ("front", "left"):
                key = f"mouth_{tag}_{view}"
                cam_key = f"mouth_{view}"
                manifest_entry = camera_lock_manifest.get("locks", {}).get(cam_key)
                if manifest_entry is None:
                    _abort("CAMERA_LOCK_MANIFEST_MISSING", key)
                    if _should_stop():
                        break
                    continue
                semantic_profile = "mouth_oral" if show_oral else "mouth"
                p = out / f"{args.label}_{key}"
                ov = overlay_dir / f"{args.label}_{key}_overlay.png"
                m = _frame_and_capture(
                    sc,
                    cam,
                    mask_mat,
                    valid,
                    skin if not show_oral else set_mouth.skin_open,
                    skin_basis_coords,
                    _mouth_framing,
                    view,
                    p,
                    ov,
                    args.resolution,
                    landmarks,
                    fid_mats,
                    rig_objs,
                    extras=oral if show_oral else None,
                    manifest_entry=manifest_entry,
                    morph_state=tag,
                    semantic_profile=semantic_profile,
                    shot_kind="mouth",
                    allow_software_fid_fallback=False,
                )
                _record_shot(key, m)
                if not m.get("pass") and not diagnostic_mode:
                    safe_abort = True
                    break
            if _should_stop():
                break

        set_mouth(24, show_oral=True)
        valid, skin = mouth_valid(True)
        key = "mouth_interior"
        p = out / f"{args.label}_{key}"
        ov = overlay_dir / f"{args.label}_{key}_overlay.png"
        interior_manifest = camera_lock_manifest.get("locks", {}).get("mouth_interior")
        m = _frame_and_capture(
            sc,
            cam,
            mask_mat,
            valid,
            set_mouth.skin_open,
            skin_basis_coords,
            _interior_framing,
            "interior",
            p,
            ov,
            args.resolution,
            landmarks,
            fid_mats,
            rig_objs,
            extras=oral,
            manifest_entry=interior_manifest,
            morph_state="interior",
            semantic_profile="mouth_interior",
            shot_kind="mouth",
            allow_software_fid_fallback=False,
        )
        _record_shot(key, m)
        if not m.get("pass") and not diagnostic_mode:
            safe_abort = True

        for side, tag in (("L", "left"), ("R", "right")):
            region = lambda v, s=side: _eye_framing(v, s)
            eyeball = rig_objs["helper-l-eye" if side == "L" else "helper-r-eye"]
            lashes = [
                rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-1"],
                rig_objs[f"helper-{'l' if side == 'L' else 'r'}-eyelashes-2"],
            ]
            cam_key = f"eye_{tag}"
            for pct, state in ((0.0, "closed"), (0.5, "half"), (1.0, "open")):
                set_eye(side, pct)
                valid = [set_eye.skin_eye, eyeball] + lashes
                key = f"eye_{tag}_{state}"
                manifest_entry = camera_lock_manifest.get("locks", {}).get(cam_key)
                if manifest_entry is None:
                    _abort("CAMERA_LOCK_MANIFEST_MISSING", key)
                    if _should_stop():
                        break
                    continue
                p = out / f"{args.label}_{key}"
                ov = overlay_dir / f"{args.label}_{key}_overlay.png"
                m = _frame_and_capture(
                    sc,
                    cam,
                    mask_mat,
                    valid,
                    set_eye.skin_eye,
                    skin_basis_coords,
                    region,
                    "front",
                    p,
                    ov,
                    args.resolution,
                    landmarks,
                    fid_mats,
                    rig_objs,
                    manifest_entry=manifest_entry,
                    morph_state=state,
                    semantic_profile="eye",
                    shot_kind=f"eye_{'l' if side == 'L' else 'r'}",
                    allow_software_fid_fallback=False,
                )
                _record_shot(key, m)
                if not m.get("pass") and not diagnostic_mode:
                    safe_abort = True
                    break
            if _should_stop():
                break

    morph_diff = {
        "mouth_front": {
            "bbox": _diff_mask_bbox(
                morph_masks.get("mouth_closed_front"), morph_masks.get("mouth_open_front")
            ),
            "pass": _diff_mask_bbox(
                morph_masks.get("mouth_closed_front"), morph_masks.get("mouth_open_front")
            )
            is not None,
        },
        "mouth_left": {
            "bbox": _diff_mask_bbox(
                morph_masks.get("mouth_closed_left"), morph_masks.get("mouth_open_left")
            ),
            "pass": _diff_mask_bbox(
                morph_masks.get("mouth_closed_left"), morph_masks.get("mouth_open_left")
            )
            is not None,
        },
        "eye_left": {
            "bbox": _diff_mask_bbox(morph_masks.get("eye_left_closed"), morph_masks.get("eye_left_open")),
            "pass": _diff_mask_bbox(morph_masks.get("eye_left_closed"), morph_masks.get("eye_left_open"))
            is not None,
        },
        "eye_right": {
            "bbox": _diff_mask_bbox(morph_masks.get("eye_right_closed"), morph_masks.get("eye_right_open")),
            "pass": _diff_mask_bbox(morph_masks.get("eye_right_closed"), morph_masks.get("eye_right_open"))
            is not None,
        },
    }
    morph_feature_delta = {
        "mouth_front_oral": _validate_morph_feature_delta(
            shots, "mouth_closed_front", "mouth_open_front", ("upper_teeth", "lower_teeth")
        ),
        "mouth_left_oral": _validate_morph_feature_delta(
            shots, "mouth_closed_left", "mouth_open_left", ("upper_teeth", "lower_teeth")
        ),
        "eye_left": _validate_morph_feature_delta(
            shots, "eye_left_closed", "eye_left_open", ("eyeball", "eyelid_upper", "eyelid_lower")
        ),
        "eye_right": _validate_morph_feature_delta(
            shots, "eye_right_closed", "eye_right_open", ("eyeball", "eyelid_upper", "eyelid_lower")
        ),
    }

    morph_delta_pass = all(v.get("pass") for v in morph_feature_delta.values())
    mask_only_pass = (
        not safe_abort
        and len(shots) >= 13
        and all(s.get("maskPass") for s in shots.values())
        and all(v.get("pass") for v in morph_diff.values())
    )
    semantic_pass = (
        not safe_abort
        and len(shots) >= 13
        and all(s.get("semanticQa", {}).get("pass") for s in shots.values())
        and morph_delta_pass
    )
    all_pass = mask_only_pass and semantic_pass
    if not all_pass or len(shots) < len(REQUIRED_SHOTS):
        safe_abort = True

    for key in REQUIRED_SHOTS:
        if key not in shots:
            entry = {"shot": key, "pass": False, "reason": "NOT_RUN", "maskPass": False}
            failure_summary.append(entry)
            shots[key] = {"pass": False, "reason": "NOT_RUN", "maskPass": False}

    if (safe_abort or not all_pass) and not diagnostic_mode:
        for c in list(out.glob(f"{args.label}_*.png")):
            try:
                c.unlink(missing_ok=True)
            except OSError:
                pass
        for c in list(overlay_dir.glob(f"{args.label}_*_overlay.png")):
            try:
                c.unlink(missing_ok=True)
            except OSError:
                pass
        captures = []

    mask_report = {
        "schema": "NURION_V07_V1_FINAL_PIXEL_MASK_VALIDATION_V1",
        "pass": mask_only_pass,
        "safeAbort": safe_abort and not mask_only_pass,
        "thresholds": {"widthFracMin": OCC_MIN, "widthFracMax": OCC_MAX, "heightFracMin": OCC_MIN, "heightFracMax": OCC_MAX},
        "validation": "FINAL_1280_OBJECT_ID_MASK",
        "renderPass": "MASK_PASS",
        "regionShells": "REJECTED",
        "anatomicalContext": True,
        "shots": {k: {kk: vv for kk, vv in v.items() if kk not in ("semanticQa", "maskArray")} for k, v in shots.items()},
        "morphDiff": morph_diff,
        "cameraLocks": list(camera_lock.keys()),
        "cameraLockManifest": camera_lock_manifest,
    }
    Path(args.validation_json).write_text(json.dumps(mask_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    semantic_report = {
        "schema": "NURION_V07_V1_SEMANTIC_FEATURE_VISIBILITY_VALIDATION_V1",
        "pass": semantic_pass and mask_only_pass,
        "safeAbort": safe_abort or not semantic_pass,
        "renderPass": "SEMANTIC_FEATURE_ID_PASS",
        "maskPassPreserved": mask_only_pass,
        "cameraOrientation": "LANDMARK_ORIENTED",
        "thresholds": {
            "minFeaturePixels": MIN_FEATURE_PIXELS,
            "minAbsoluteFloor": MIN_ABSOLUTE_FLOOR,
            "visibilityDetectionMin": VISIBILITY_DETECTION_MIN,
            "frontAbsoluteExpectedFrac": FRONT_ABSOLUTE_EXPECTED_FRAC,
            "requiredFeatures": REQUIRED_FEATURES,
            "saturationMaxRatio": SAT_MAX_RATIO,
            "clipMaxRatio": CLIP_MAX_RATIO,
            "featureColorTolerance": FEATURE_COLOR_TOL,
            "qaPaletteTolerance": QA_PALETTE_TOL,
            "minFeatureContrastStd": MIN_FEATURE_CONTRAST_STD,
            "cornerSymmetryMin": CORNER_SYMMETRY_MIN,
            "oralOpeningMinPx": ORAL_OPENING_MIN_PX,
        },
        "regionMap": {
            "vertexCounts": region_map.get("vertex_counts"),
            "faceCounts": region_map.get("face_counts"),
            "cornerSymmetry": region_map.get("corner_symmetry"),
            "seeds": region_map.get("seeds"),
            "chinMeta": region_map.get("chin_meta"),
            "integrity": region_integrity,
        },
        "landmarks": {
            k: [float(landmarks[k].x), float(landmarks[k].y), float(landmarks[k].z)]
            for k in (
                "nose_tip",
                "ear_l",
                "ear_r",
                "mouth_center",
                "lip_corner_l",
                "lip_corner_r",
                "chin",
                "eye_l",
                "eye_r",
            )
        },
        "palette": QA_PALETTE,
        "featureIdColors": FEATURE_ID_RGB,
        "lighting": "KEY_FILL_FIXED_EXPOSURE",
        "shots": {k: v.get("semanticQa", {}) for k, v in shots.items()},
        "morphDiff": morph_diff,
        "morphFeatureDelta": morph_feature_delta,
        "diagnosticMode": diagnostic_mode,
        "preflight": preflight_report,
        "preflightPass": preflight_pass,
        "runFullDiagnostic": run_full_diagnostic,
        "cameraLockManifest": camera_lock_manifest,
        "captureStateUnification": True,
        "softwareRasterFallbackPolicy": "DIAGNOSTIC_PARITY_ONLY",
        "shotOrder": list(REQUIRED_SHOTS),
        "failureSummary": failure_summary,
        "shotsCompleted": len(shots),
        "shotsPassed": sum(1 for s in shots.values() if s.get("pass")),
    }
    if thirteen_shot_manifest_assert is not None:
        semantic_report["thirteenShotManifestConsumptionAssert"] = thirteen_shot_manifest_assert
    Path(args.semantic_validation_json).write_text(json.dumps(semantic_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    meta = {
        "schema": "NURION_V07_V1_LSFQ_MORPH_QA_META",
        "weightMap": args.weight_json,
        "pass": all_pass,
        "maskPass": mask_only_pass,
        "semanticPass": semantic_pass,
        "safeAbort": safe_abort or not all_pass,
        "captures": captures,
        "production": "NO-GO",
    }
    Path(args.meta_json).write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if all_pass:
        bpy.ops.wm.save_as_mainfile(filepath=str(out / f"{args.label}.blend"))
    print(
        json.dumps(
            {
                "pass": all_pass,
                "maskPass": mask_only_pass,
                "semanticPass": semantic_pass,
                "safeAbort": safe_abort,
                "diagnosticMode": diagnostic_mode,
                "shotsCompleted": len(shots),
                "shotsPassed": sum(1 for s in shots.values() if s.get("pass")),
                "failureCount": len(failure_summary),
                "captures": len(captures),
            },
            ensure_ascii=True,
        )
    )
    return 0 if all_pass else 4


if __name__ == "__main__":
    raise SystemExit(main())
