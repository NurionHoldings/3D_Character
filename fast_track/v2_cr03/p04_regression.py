"""CR03-P04 — Idle + TALKING coexistence / BODY+morph regression."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fast_track.adaptation.glb_io import load_gltf_document
from fast_track.change_control import require_human_spec_gate, require_no_upstream_mutation
from fast_track.v2_cr03.glb_measure import (
    base_skin_digests,
    canonical_sha256,
    morph_position_digests,
    sha256_file,
)
from fast_track.v2_cr03.pins import (
    APPROVED_SPEC_DIGEST,
    CR,
    CR02_R2_DERIVED_SHA,
    TALKING_ANIMATION_NAME,
)

REPORT_SCHEMA = "NURION_V2_CR03_P04_IDLE_TALKING_REGRESSION_V1"


def run_idle_talking_regression(
    *,
    input_glb: Path,
    derived_glb: Path,
    track: dict[str, Any],
    spec_path: Path,
) -> dict[str, Any]:
    require_no_upstream_mutation(track)
    gate_digest = require_human_spec_gate(
        track, expected_change_request=CR, spec_path=spec_path
    )
    if gate_digest != APPROVED_SPEC_DIGEST:
        raise PermissionError("SPEC_DIGEST_MISMATCH → IMPLEMENTATION DENIED")

    input_glb = Path(input_glb)
    derived_glb = Path(derived_glb)
    blockers: list[dict[str, Any]] = []

    if sha256_file(input_glb) != CR02_R2_DERIVED_SHA:
        blockers.append({"code": "INPUT_SHA_MISMATCH"})

    g_in, b_in, _ = load_gltf_document(input_glb)
    g_out, b_out, _ = load_gltf_document(derived_glb)
    assert b_in is not None and b_out is not None

    skin_in = base_skin_digests(b_in, g_in)
    skin_out = base_skin_digests(b_out, g_out)
    morph_in = morph_position_digests(b_in, g_in)
    morph_out = morph_position_digests(b_out, g_out)

    if skin_in != skin_out:
        blockers.append({"code": "BODY_SKIN_REGRESSION", "in": skin_in, "out": skin_out})
    if morph_in != morph_out:
        blockers.append({"code": "CR02_MORPH_POSITION_REGRESSION", "in": morph_in, "out": morph_out})

    # Skeleton hierarchy: node names + children topology digest
    def hierarchy_digest(g: dict) -> str:
        rows = []
        for i, n in enumerate(g.get("nodes") or []):
            rows.append(
                {
                    "i": i,
                    "name": n.get("name"),
                    "children": list(n.get("children") or []),
                    "mesh": n.get("mesh"),
                    "skin": n.get("skin"),
                }
            )
        # Ignore trailing FACE aux already present on input; compare shared prefix length of input
        return canonical_sha256(rows)

    # Compare hierarchy for nodes that existed in input (derived may only append animation, not nodes)
    hin = hierarchy_digest(g_in)
    # Rebuild input-equivalent node list from output (same length)
    n_in = len(g_in.get("nodes") or [])
    g_trim = dict(g_out)
    g_trim["nodes"] = list(g_out.get("nodes") or [])[:n_in]
    hout = hierarchy_digest(g_trim)
    if hin != hout:
        blockers.append({"code": "SKELETON_HIERARCHY_MUTATION"})

    anims = g_out.get("animations") or []
    names = [a.get("name") for a in anims]
    idle_present = any(n and "Idle" in n for n in names)
    talking_present = TALKING_ANIMATION_NAME in names
    if not idle_present:
        blockers.append({"code": "IDLE_CLIP_MISSING", "names": names})
    if not talking_present:
        blockers.append({"code": "TALKING_CLIP_MISSING", "names": names})

    # FACE_Rig_Root preserved
    face_ok = any(
        (n.get("extras") or {}).get("nurionSemantic") == "FACE_Rig_Root"
        for n in (g_out.get("nodes") or [])
    )
    if not face_ok:
        blockers.append({"code": "FACE_RIG_ROOT_MISSING"})

    # Idle channels still body-targeted; talking is weights on mesh node
    idle_anim = next((a for a in anims if a.get("name") and "Idle" in a.get("name")), None)
    talking_anim = next((a for a in anims if a.get("name") == TALKING_ANIMATION_NAME), None)
    idle_channels = len((idle_anim or {}).get("channels") or [])
    talk_weights = 0
    if talking_anim:
        talk_weights = sum(
            1
            for c in talking_anim.get("channels") or []
            if (c.get("target") or {}).get("path") == "weights"
        )
    if idle_channels < 1:
        blockers.append({"code": "IDLE_CHANNELS_EMPTY"})
    if talk_weights < 1:
        blockers.append({"code": "TALKING_WEIGHTS_CHANNEL_MISSING"})

    regression_digest = canonical_sha256(
        {
            "skin": skin_out,
            "morph": morph_out,
            "idlePresent": idle_present,
            "talkingPresent": talking_present,
            "idleChannels": idle_channels,
            "talkWeightsChannels": talk_weights,
        }
    )

    status = "PASS" if not blockers else "BLOCKED"
    return {
        "schema": REPORT_SCHEMA,
        "changeRequestId": CR,
        "stage": "CR03-P04",
        "status": status,
        "gate": {"approvedSpecDigest": gate_digest},
        "coexistence": {
            "Idle": idle_present,
            "TALKING": talking_present,
            "idleChannelCount": idle_channels,
            "talkingWeightsChannels": talk_weights,
            "executable": idle_present and talking_present and idle_channels > 0 and talk_weights > 0,
        },
        "preservation": {
            "basePOSITION": skin_out.get("POSITION"),
            "JOINTS_WEIGHTS": {k: skin_out[k] for k in skin_out if k != "POSITION"},
            "CR02_facial_morph_POSITION": morph_out,
            "FACE_Rig_Root": face_ok,
        },
        "profileSimulationExpansion": "DENY",
        "regressionDigest": regression_digest,
        "blockers": blockers,
        "next": "CR03-P05 Real Asset Proof Packaging"
        if status == "PASS"
        else "STOP — fail-closed",
    }
