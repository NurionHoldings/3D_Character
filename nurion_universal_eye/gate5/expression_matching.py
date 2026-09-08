"""Gate 5 — match gaze / lids / blink to external expression state."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mathutils import Vector

from ..gate4a.gaze_motion import _apply_eye
from ..gate4a.safe_ellipse import build_safe_ellipse
from ..gate4b.blink_motion import run_blink_motion
from ..gate4b.lid_proxy import create_or_update_lid, lid_edges
from .expression_recipes import EyeReactionTarget, blend_reactions, resolve_reaction
from .lock_guard import assert_gate1234ab_locked
from .parameters import GATE5_PARAMETERS, parameter_hash


def _v3(v: Vector) -> List[float]:
    return [round(float(v.x), 6), round(float(v.y), 6), round(float(v.z), 6)]


def _obj_snapshot(name: str) -> Optional[Dict]:
    import bpy

    obj = bpy.data.objects.get(name)
    if obj is None:
        return None
    m = obj.matrix_world.copy()
    return {
        "location": _v3(m.translation),
        "rotation": [round(float(x), 8) for x in m.to_quaternion()],
    }


def _smoothstep(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


@dataclass
class ExpressionFrame:
    name: str
    state: str
    intensity: float
    speech_active: bool
    sentence_boundary: bool
    phase: str
    reaction: Dict
    eyes: Dict[str, Dict] = field(default_factory=dict)
    lids: Dict[str, Dict] = field(default_factory=dict)
    gaze_escape_eu: float = 0.0
    lid_range_escape: float = 0.0
    conflict: bool = False


@dataclass
class ExpressionMatchResult:
    blink: object
    ellipses: Dict
    apertures: Dict
    bulges: Dict
    face_bvh: object
    dome_before: Dict
    dome_after: Dict
    frames: List[ExpressionFrame]
    max_transition_pop_gaze_eu: float
    max_transition_pop_lid_eu: float
    neutral_return_error_eu: float
    lr_desync_eu: float
    parameter_hash: str
    lock_info: Dict
    texture_note: str = (
        "Static face texture differences are input-asset characteristics; "
        "eye-reaction parameters are not character-retargeted."
    )

    def to_profile(self) -> dict:
        return {
            "schema": "NURION_GATE5_EXPRESSION_MATCH_PROFILE",
            "version": GATE5_PARAMETERS["version"],
            "parameterHash": self.parameter_hash,
            "gate4aParameterHash": GATE5_PARAMETERS["requiredGate4aParameterHash"],
            "gate4bParameterHash": GATE5_PARAMETERS["requiredGate4bParameterHash"],
            "frames": [
                {
                    "name": f.name,
                    "state": f.state,
                    "intensity": f.intensity,
                    "speechActive": f.speech_active,
                    "sentenceBoundary": f.sentence_boundary,
                    "phase": f.phase,
                    "reaction": f.reaction,
                    "eyes": f.eyes,
                    "lids": f.lids,
                    "gazeEscapeEU": round(float(f.gaze_escape_eu), 6),
                    "lidRangeEscape": round(float(f.lid_range_escape), 6),
                    "conflict": bool(f.conflict),
                }
                for f in self.frames
            ],
            "maxTransitionPopGazeEU": round(float(self.max_transition_pop_gaze_eu), 6),
            "maxTransitionPopLidEU": round(float(self.max_transition_pop_lid_eu), 6),
            "neutralReturnErrorEU": round(float(self.neutral_return_error_eu), 6),
            "lrDesyncEU": round(float(self.lr_desync_eu), 6),
            "domeBefore": self.dome_before,
            "domeAfter": self.dome_after,
            "textureNote": self.texture_note,
            "faceBoneGeneration": "HOLD",
            "eyebrowRig": "HOLD",
            "lipSync": "HOLD",
            "headBodyMotion": "HOLD",
            "beautyMaterial": "HOLD",
            "outputs": ["NURION_ExpressionControl"],
        }


def _user_target(axes, planes, eu: float) -> Vector:
    mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
    dist = eu * float(GATE5_PARAMETERS["gaze"]["userTargetEyeUnits"])
    return mid + axes.forward.normalized() * dist


def _target_from_yaw_pitch(axes, planes, eu: float, yaw_n: float, pitch_n: float) -> Vector:
    """Build shared 3D attention target from normalized yaw/pitch in [-1,1]."""
    import math

    from ..gate4a.parameters import GATE4A_PARAMETERS

    g = GATE4A_PARAMETERS["gaze"]
    yaw = math.radians(float(g["yawCardinalDeg"])) * float(yaw_n)
    pitch = math.radians(float(g["pitchCardinalDeg"])) * float(pitch_n)
    mid = 0.5 * (planes["L"].origin_world + planes["R"].origin_world)
    fwd = axes.forward.normalized()
    right = axes.right.normalized()
    up = axes.up.normalized()
    dist = eu * float(GATE5_PARAMETERS["gaze"]["userTargetEyeUnits"])
    d = (
        fwd * math.cos(yaw) * math.cos(pitch)
        + right * math.sin(yaw) * math.cos(pitch)
        + up * math.sin(pitch)
    )
    return mid + d.normalized() * dist


def _apply_lids_expression(
    *,
    planes,
    apertures,
    bulges,
    blink_amount: float,
    lower_raise: float,
    face_bvh,
) -> Tuple[Dict[str, Dict], float]:
    """Apply Gate4B lids with optional lower-lid raise inside validated range."""
    metrics = {}
    escape = 0.0
    for side, plane in planes.items():
        ap = apertures[side]
        eu = float(plane.eye_unit)
        amt = max(0.0, min(1.0, float(blink_amount)))
        upper_y, lower_y = lid_edges(ap, amt)
        if amt >= 0.999:
            ov = eu * 0.015
            upper_y = ap.meet_y - 0.5 * ov
            lower_y = ap.meet_y + 0.5 * ov
        # Lower lid raise: move lower edge toward meet without passing upper
        raise_span = max(0.0, ap.meet_y - ap.open_lower_y)
        raise_share = min(
            float(lower_raise), float(GATE5_PARAMETERS["lid"]["maxLowerRaiseShare"])
        )
        lower_y = lower_y + raise_span * raise_share
        # Keep within validated open..meet band (allow closed overlap)
        lo_bound = min(ap.open_lower_y, ap.meet_y) - eu * 0.02
        hi_bound = max(ap.open_upper_y, ap.meet_y) + eu * 0.02
        if lower_y < lo_bound - 1e-9 or lower_y > hi_bound + 1e-9:
            escape = max(escape, abs(lower_y - max(lo_bound, min(hi_bound, lower_y))) / max(eu, 1e-9))
        if upper_y < lo_bound - 1e-9 or upper_y > hi_bound + 1e-9:
            escape = max(escape, abs(upper_y - max(lo_bound, min(hi_bound, upper_y))) / max(eu, 1e-9))
        lower_y = max(lo_bound, min(hi_bound, lower_y))
        upper_y = max(lo_bound, min(hi_bound, upper_y))
        # Prevent inversion except sealed overlap
        if lower_y > upper_y and amt < 0.999:
            lower_y = upper_y
        top = ap.open_upper_y + ap.ry * 0.08
        bot = ap.open_lower_y - ap.ry * 0.08
        rgba_u = (0.55, 0.35, 0.28, 1.0) if side == "L" else (0.60, 0.38, 0.30, 1.0)
        rgba_l = (0.45, 0.28, 0.24, 1.0) if side == "L" else (0.50, 0.30, 0.26, 1.0)
        create_or_update_lid(
            name=f"NURION_UpperLidProxy.{side}",
            plane=plane,
            bulge=bulges[side],
            ap=ap,
            y0=upper_y,
            y1=top,
            which="upper",
            rgba=rgba_u,
            face_bvh=face_bvh,
        )
        create_or_update_lid(
            name=f"NURION_LowerLidProxy.{side}",
            plane=plane,
            bulge=bulges[side],
            ap=ap,
            y0=bot,
            y1=lower_y,
            which="lower",
            rgba=rgba_l,
            face_bvh=face_bvh,
        )
        metrics[side] = {
            "upperY": round(float(upper_y), 6),
            "lowerY": round(float(lower_y), 6),
            "blinkAmount": round(float(amt), 4),
            "lowerRaise": round(float(lower_raise), 4),
        }
    return metrics, float(escape)


def apply_expression_pose(
    *,
    planes,
    axes,
    ellipses,
    apertures,
    bulges,
    reaction: EyeReactionTarget,
    attention_world: Optional[Vector] = None,
    face_bvh=None,
) -> ExpressionFrame:
    import bpy

    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)
    if attention_world is not None:
        # Blend recipe gaze toward explicit attention by rebuilding target
        target = attention_world
        # Still apply small recipe offset around attention via yaw/pitch on top of user dir
        # Convert attention to base; then offset
        base = attention_world
        offset_tgt = _target_from_yaw_pitch(axes, planes, eu, reaction.gaze_yaw, reaction.gaze_pitch)
        # Mix: primarily attention, recipe offsets relative — use offset_tgt when no custom,
        # when attention provided, rotate offset around attention direction lightly
        target = offset_tgt if reaction.gaze_yaw or reaction.gaze_pitch else base
        if attention_world is not None and (abs(reaction.gaze_yaw) + abs(reaction.gaze_pitch)) > 1e-6:
            # average attention with recipe target for soft offset
            target = attention_world.lerp(offset_tgt, 0.35)
        elif attention_world is not None:
            target = attention_world
    else:
        target = _target_from_yaw_pitch(axes, planes, eu, reaction.gaze_yaw, reaction.gaze_pitch)

    ctrl = bpy.data.objects.get("NURION_ExpressionControl")
    if ctrl is not None:
        ctrl["expressionState"] = reaction.state
        ctrl["expressionIntensity"] = float(reaction.intensity)
        ctrl["speechActive"] = 1 if reaction.speech_active else 0
        ctrl["attentionTarget"] = _v3(target)
        ctrl.location = target

    gctrl = bpy.data.objects.get("NURION_GazeControl")
    if gctrl is not None:
        gctrl.location = target

    eyes = {}
    max_escape = 0.0
    for side, plane in planes.items():
        iris = bpy.data.objects.get(f"NURION_DiagnosticIris.{side}")
        pupil = bpy.data.objects.get(f"NURION_DiagnosticPupil.{side}")
        anchor = bpy.data.objects.get(f"NURION_GazeAnchor.{side}")
        st = _apply_eye(
            plane=plane,
            ellipse=ellipses[side],
            bulge=bulges[side],
            target=target,
            iris_obj=iris,
            pupil_obj=pupil,
            anchor_obj=anchor,
            axes=axes,
        )
        esc = float(st.iris_escape_eu)
        if not st.inside:
            esc = max(esc, 0.05)
        max_escape = max(max_escape, esc)
        eyes[side] = {
            "localXY": _v3(st.local_xy),
            "world": _v3(st.world),
            "escapeEU": round(esc, 6),
            "inside": bool(st.inside),
        }

    lids, lid_esc = _apply_lids_expression(
        planes=planes,
        apertures=apertures,
        bulges=bulges,
        blink_amount=reaction.blink_amount,
        lower_raise=reaction.lower_lid_raise,
        face_bvh=face_bvh,
    )

    # Conflict: wide-open hold states must not also command a heavy blink (boundary blink OK)
    conflict = bool(
        reaction.state in ("SURPRISE", "FOCUS", "NEUTRAL")
        and reaction.phase == "HOLD"
        and reaction.blink_amount > 0.5
        and not reaction.sentence_boundary
    )

    bctrl = bpy.data.objects.get("NURION_BlinkControl")
    if bctrl is not None:
        bctrl["nurion_blink_L"] = float(reaction.blink_amount)
        bctrl["nurion_blink_R"] = float(reaction.blink_amount)

    return ExpressionFrame(
        name="",
        state=reaction.state,
        intensity=reaction.intensity,
        speech_active=reaction.speech_active,
        sentence_boundary=reaction.sentence_boundary,
        phase=reaction.phase,
        reaction={
            "gazeYaw": round(reaction.gaze_yaw, 4),
            "gazePitch": round(reaction.gaze_pitch, 4),
            "blinkAmount": round(reaction.blink_amount, 4),
            "lowerLidRaise": round(reaction.lower_lid_raise, 4),
            "openness": round(reaction.openness, 4),
            "blinkSuppress": round(reaction.blink_suppress, 4),
        },
        eyes=eyes,
        lids=lids,
        gaze_escape_eu=float(max_escape),
        lid_range_escape=float(lid_esc),
        conflict=conflict,
    )


def _ensure_expression_control(planes, axes, eu: float):
    import bpy

    name = "NURION_ExpressionControl"
    obj = bpy.data.objects.get(name)
    if obj is None:
        obj = bpy.data.objects.new(name, None)
        obj.empty_display_type = "SPHERE"
        obj.empty_display_size = 0.025
        bpy.context.collection.objects.link(obj)
    obj["nurion_gate"] = "5"
    obj["expressionState"] = "NEUTRAL"
    obj["expressionIntensity"] = 0.0
    obj["speechActive"] = 0
    obj["attentionTarget"] = _v3(_user_target(axes, planes, eu))
    obj.location = _user_target(axes, planes, eu)
    return obj


def run_expression_matching(
    *,
    mesh_name: str = "",
    root: Optional[Path] = None,
    create_meshes: bool = True,
) -> ExpressionMatchResult:
    root = Path(root) if root else Path(__file__).resolve().parents[2]
    lock_info = assert_gate1234ab_locked(root)

    # Build locked Gate4B scene (includes Gate4A CENTER gaze + lid proxies)
    blink = run_blink_motion(mesh_name=mesh_name, root=root, create_meshes=True)
    planes = blink.gaze.convex.flat.planes
    axes = blink.gaze.convex.flat.basis.axes
    apertures = blink.apertures
    bulges = blink.bulges
    eu = sum(float(p.eye_unit) for p in planes.values()) / max(len(planes), 1)
    ellipses = {side: build_safe_ellipse(planes[side], bulge_m=bulges[side]) for side in planes}

    import bpy
    from ..gate2.multiview_depth import build_world_bvh

    face_obj = bpy.data.objects.get(blink.gaze.convex.flat.basis.mesh_name)
    face_bvh = build_world_bvh(face_obj) if face_obj is not None else None

    _ensure_expression_control(planes, axes, eu)
    user = _user_target(axes, planes, eu)

    dome_names = ["NURION_EyeDome.L", "NURION_EyeDome.R"]
    dome_before = {n: _obj_snapshot(n) for n in dome_names}

    frames: List[ExpressionFrame] = []
    n_blend = int(GATE5_PARAMETERS["blend"]["transitionSamples"])

    def emit(name: str, reaction: EyeReactionTarget, attention: Optional[Vector] = None):
        fr = apply_expression_pose(
            planes=planes,
            axes=axes,
            ellipses=ellipses,
            apertures=apertures,
            bulges=bulges,
            reaction=reaction,
            attention_world=attention if attention is not None else user,
            face_bvh=face_bvh,
        )
        fr.name = name
        frames.append(fr)
        return fr

    def transition(name_prefix: str, a: EyeReactionTarget, b: EyeReactionTarget, attention=None):
        for i in range(1, n_blend + 1):
            t = _smoothstep(i / float(n_blend))
            mid = blend_reactions(a, b, t)
            emit(f"{name_prefix}_T{i}", mid, attention)

    # --- Validation sequence ---
    neutral0 = resolve_reaction(state="NEUTRAL", intensity=0.0)
    emit("NEUTRAL_SOLO", neutral0, user)
    neutral_ref_eyes = {s: frames[-1].eyes[s]["localXY"][:] for s in ("L", "R")}
    neutral_ref_lids = {s: frames[-1].lids[s].copy() for s in ("L", "R")}

    states = [s for s in GATE5_PARAMETERS["states"] if s != "NEUTRAL"]
    prev = neutral0
    for st in states:
        # enter
        tgt = resolve_reaction(state=st, intensity=0.55, speech_active=(st == "SPEAKING"))
        transition(f"ENTER_{st}", prev, tgt, user)
        emit(f"HOLD_{st}_MID", tgt, user)
        # max intensity
        tmax = resolve_reaction(state=st, intensity=1.0, speech_active=(st == "SPEAKING"))
        transition(f"MAX_{st}", tgt, tmax, user)
        emit(f"HOLD_{st}_MAX", tmax, user)
        # aux phases
        if st == "EXPLAINING":
            aux = resolve_reaction(state=st, intensity=1.0, phase="AUX")
            transition(f"AUX_{st}", tmax, aux, user)
            emit(f"HOLD_{st}_AUX", aux, user)
            ret = resolve_reaction(state=st, intensity=1.0, phase="RETURN")
            transition(f"RETURN_{st}", aux, ret, user)
            emit(f"HOLD_{st}_RETURN", ret, user)
            tmax = ret
        if st == "THINKING":
            think = resolve_reaction(state=st, intensity=1.0, phase="HOLD")
            emit(f"HOLD_{st}_UP", think, user)
            ret = resolve_reaction(state=st, intensity=1.0, phase="RETURN")
            transition(f"RETURN_{st}", think, ret, user)
            emit(f"HOLD_{st}_RETURN", ret, user)
            tmax = ret
        # return neutral
        n1 = resolve_reaction(state="NEUTRAL", intensity=0.0)
        transition(f"TO_NEUTRAL_FROM_{st}", tmax, n1, user)
        emit(f"NEUTRAL_AFTER_{st}", n1, user)
        prev = n1

    # Direct expression-to-expression
    smile = resolve_reaction(state="FRIENDLY_SMILE", intensity=1.0)
    focus = resolve_reaction(state="FOCUS", intensity=1.0)
    transition("DIRECT_SMILE_TO_FOCUS", smile if prev.state == "NEUTRAL" else prev, smile, user)
    emit("HOLD_SMILE", smile, user)
    transition("DIRECT_SMILE_TO_FOCUS2", smile, focus, user)
    emit("HOLD_FOCUS_AFTER_SMILE", focus, user)

    # Gaze move during expression change
    left_attn = _target_from_yaw_pitch(axes, planes, eu, -0.7, 0.0)
    empathy = resolve_reaction(state="EMPATHY", intensity=0.8)
    transition("GAZE_MOVE_WHILE_EXPR", focus, empathy, left_attn)
    emit("HOLD_EMPATHY_GAZE", empathy, left_attn)

    # Blink during expression change
    blinking = resolve_reaction(state="EMPATHY", intensity=1.0)
    blinking = EyeReactionTarget(
        state=blinking.state,
        intensity=blinking.intensity,
        speech_active=False,
        sentence_boundary=False,
        phase="HOLD",
        gaze_yaw=blinking.gaze_yaw,
        gaze_pitch=blinking.gaze_pitch,
        blink_amount=0.75,
        lower_lid_raise=blinking.lower_lid_raise,
        blink_suppress=blinking.blink_suppress,
        openness=blinking.openness,
    )
    transition("ENTER_BLINK_OVERLAY", empathy, blinking, left_attn)
    emit("HOLD_BLINK_OVERLAY", blinking, left_attn)
    surprise = resolve_reaction(state="SURPRISE", intensity=1.0)
    transition("BLINK_WHILE_EXPR", blinking, surprise, user)
    emit("HOLD_SURPRISE_AFTER_BLINK", surprise, user)

    # Speaking on/off + sentence boundary
    speak_on = resolve_reaction(state="SPEAKING", intensity=1.0, speech_active=True, sentence_boundary=False)
    transition("SPEAK_ON", surprise, speak_on, user)
    emit("HOLD_SPEAKING", speak_on, user)
    speak_bound = resolve_reaction(state="SPEAKING", intensity=1.0, speech_active=True, sentence_boundary=True)
    transition("SPEAK_BOUNDARY", speak_on, speak_bound, user)
    emit("SPEAK_BOUNDARY_BLINK", speak_bound, user)
    speak_off = resolve_reaction(state="SPEAKING", intensity=0.0, speech_active=False)
    transition("SPEAK_OFF", speak_bound, speak_off, user)
    n_final = resolve_reaction(state="NEUTRAL", intensity=0.0)
    transition("TO_NEUTRAL_FINAL", speak_off, n_final, user)
    emit("NEUTRAL_FINAL", n_final, user)

    # Rapid state switching
    rapid_states = ["SURPRISE", "THINKING", "FRIENDLY_SMILE", "FOCUS", "NEUTRAL"]
    cur = n_final
    for i, st in enumerate(rapid_states):
        nxt = resolve_reaction(state=st, intensity=1.0 if st != "NEUTRAL" else 0.0)
        # fewer blend samples already encoded; still blend
        transition(f"RAPID_{i}_{st}", cur, nxt, user)
        emit(f"RAPID_HOLD_{st}", nxt, user)
        cur = nxt

    # Full sequence repeat marker (second neutral solo)
    emit("NEUTRAL_REPEAT", resolve_reaction(state="NEUTRAL", intensity=0.0), user)

    dome_after = {n: _obj_snapshot(n) for n in dome_names}

    # Metrics: transition pops = discontinuous jumps between non-blend frames.
    # Smoothstep samples (_T#) are expected motion; flag only sudden HOLD→HOLD leaps.
    max_pop_g = 0.0
    max_pop_l = 0.0
    for i in range(1, len(frames)):
        a, b = frames[i - 1], frames[i]
        blended = ("_T" in a.name) or ("_T" in b.name)
        if blended:
            continue
        for side in ("L", "R"):
            ax, ay = a.eyes[side]["localXY"][0], a.eyes[side]["localXY"][1]
            bx, by = b.eyes[side]["localXY"][0], b.eyes[side]["localXY"][1]
            dg = math.sqrt((bx - ax) ** 2 + (by - ay) ** 2) / max(eu, 1e-9)
            du = abs(b.lids[side]["upperY"] - a.lids[side]["upperY"]) / max(eu, 1e-9)
            dl = abs(b.lids[side]["lowerY"] - a.lids[side]["lowerY"]) / max(eu, 1e-9)
            max_pop_g = max(max_pop_g, dg)
            max_pop_l = max(max_pop_l, du, dl)

    # Neutral return error
    last_n = next(f for f in reversed(frames) if f.name.startswith("NEUTRAL"))
    nret = 0.0
    for side in ("L", "R"):
        ax, ay = neutral_ref_eyes[side][0], neutral_ref_eyes[side][1]
        bx, by = last_n.eyes[side]["localXY"][0], last_n.eyes[side]["localXY"][1]
        nret = max(nret, math.sqrt((bx - ax) ** 2 + (by - ay) ** 2) / max(eu, 1e-9))
        nret = max(
            nret,
            abs(last_n.lids[side]["upperY"] - neutral_ref_lids[side]["upperY"]) / max(eu, 1e-9),
            abs(last_n.lids[side]["lowerY"] - neutral_ref_lids[side]["lowerY"]) / max(eu, 1e-9),
        )

    # L/R desync on hold frames
    desync = 0.0
    for fr in frames:
        if not fr.name.startswith("HOLD_") and fr.name not in ("NEUTRAL_SOLO", "NEUTRAL_FINAL"):
            continue
        lxy = fr.eyes["L"]["localXY"]
        rxy = fr.eyes["R"]["localXY"]
        # relative to ellipse centers
        el, er = ellipses["L"], ellipses["R"]
        du = (lxy[0] - float(el.center_local.x)) / max(el.usable_rx, 1e-9) - (
            rxy[0] - float(er.center_local.x)
        ) / max(er.usable_rx, 1e-9)
        dv = (lxy[1] - float(el.center_local.y)) / max(el.usable_ry, 1e-9) - (
            rxy[1] - float(er.center_local.y)
        ) / max(er.usable_ry, 1e-9)
        # For mirrored convergence on center targets, du should be near 0 for same command;
        # use blink lid amount desync instead for L/R
        desync = max(desync, abs(fr.lids["L"]["blinkAmount"] - fr.lids["R"]["blinkAmount"]))
        desync = max(desync, abs(du) * 0.01, abs(dv) * 0.01)  # tiny gaze uv desync in EU-ish

    return ExpressionMatchResult(
        blink=blink,
        ellipses=ellipses,
        apertures=apertures,
        bulges=bulges,
        face_bvh=face_bvh,
        dome_before=dome_before,
        dome_after=dome_after,
        frames=frames,
        max_transition_pop_gaze_eu=float(max_pop_g),
        max_transition_pop_lid_eu=float(max_pop_l),
        neutral_return_error_eu=float(nret),
        lr_desync_eu=float(desync),
        parameter_hash=parameter_hash(),
        lock_info=lock_info,
    )
