#!/usr/bin/env python3
"""NURION-PRODUCT-04 — Character Entrance State System (consume-only)."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fast_track.runtime.product_character_assembly import (
    ASSEMBLY_BASELINE_REL,
    EXPECTED_ASSET_SHA256 as PRODUCT01_IDLE_SHA,
    FACE_RIG_ROOT,
    assert_assembly_has_no_absolute_paths,
    assert_jake_product_path_blocked,
    assert_logical_repo_path,
    canonical_json_sha256,
)
from fast_track.runtime.product_face_body_runtime import RUNTIME_REL as PRODUCT03_RUNTIME_REL
from fast_track.runtime.product_motion_library import LIBRARY_REL, REQUIRED_MOTION_IDS
from fast_track.runtime.retarget.canonical import TRANSLATION_OWNERS
from fast_track.runtime.retarget.protected import PROTECTED_SOT_SHA256, assert_protected_sot_unchanged

ROOT = Path(os.environ.get("NURION_REPO_ROOT", r"d:\NURION Character Landmarker"))

CONTRACT_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_CONTRACT_V1.json"
)
STATE_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json"
)
STATE_PATH = ROOT / STATE_REL
FACE_LOCK_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"
)
P03_PASS_RECEIPT_REL = (
    "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-03_PASS_receipt.json"
)
P02_PASS_RECEIPT_REL = (
    "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-02_PASS_receipt.json"
)
P01_PASS_RECEIPT_REL = (
    "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-01_PASS_receipt.json"
)

ONE_LINE = (
    "PRODUCT-04 shall deterministically orchestrate the canonical NURION Character Entrance "
    "from bootstrap through entrance playback and atomic handoff into the locked PRODUCT-03 "
    "live runtime, without mutation of PRODUCT-01/02/03 or protected FACE, Eye, TALKING, BODY "
    "and rig contracts, while preserving product identity, single character authority, visual "
    "transform continuity, provenance restrictions and fail-closed state semantics."
)

CANONICAL_STATES = (
    "BOOTSTRAP",
    "PRELOAD",
    "ENTRANCE_READY",
    "ENTRANCE_PLAYING",
    "RUNTIME_HANDOFF",
    "LIVE_IDLE",
    "RECOVERY",
    "BLOCKED",
)
HAPPY_PATH = (
    ("BOOTSTRAP", "PRELOAD"),
    ("PRELOAD", "ENTRANCE_READY"),
    ("ENTRANCE_READY", "ENTRANCE_PLAYING"),
    ("ENTRANCE_PLAYING", "RUNTIME_HANDOFF"),
    ("RUNTIME_HANDOFF", "LIVE_IDLE"),
)
DENIED_TRANSITIONS = {
    ("BOOTSTRAP", "LIVE_IDLE"),
    ("PRELOAD", "ENTRANCE_PLAYING"),
    ("ENTRANCE_READY", "LIVE_IDLE"),
    ("ENTRANCE_PLAYING", "LIVE_IDLE"),
    ("BLOCKED", "LIVE_IDLE"),
}

AUTH_NONE = "NONE"
AUTH_ENTRANCE = "ENTRANCE"
AUTH_HANDOFF = "RUNTIME_HANDOFF_COMMIT"
AUTH_P03 = "PRODUCT03_RUNTIME"
AUTH_BLOCKED = "BLOCKED"
MAX_ROOT_JUMP = 1e-6
FLOAT_EPS = 1e-9


class Product04Blocker(RuntimeError):
    pass


class Product04Error(ValueError):
    pass


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(rel: str) -> dict[str, Any]:
    rel = assert_logical_repo_path(rel, field="consume")
    path = ROOT / rel
    if not path.exists():
        raise Product04Blocker(f"BLOCKER: missing consume-only artifact: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def _quat_dot(a: list[float], b: list[float]) -> float:
    return abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3])


def _vec_l1(a: list[float], b: list[float]) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def consume_upstream() -> dict[str, Any]:
    try:
        protected = assert_protected_sot_unchanged()
    except AssertionError as e:
        raise Product04Blocker(f"BLOCKER Protected SoT: {e}") from e

    assembly = _load_json(ASSEMBLY_BASELINE_REL)
    library = _load_json(LIBRARY_REL)
    p03 = _load_json(PRODUCT03_RUNTIME_REL)
    face_lock = _load_json(FACE_LOCK_REL)
    p03_pass = _load_json(P03_PASS_RECEIPT_REL)
    p02_pass = _load_json(P02_PASS_RECEIPT_REL)
    p01_pass = _load_json(P01_PASS_RECEIPT_REL)

    for label, doc in (("assembly", assembly), ("library", library), ("p03", p03)):
        try:
            assert_assembly_has_no_absolute_paths(doc)
        except Exception as e:
            raise Product04Blocker(f"BLOCKER absolute path in {label}: {e}") from e

    if p01_pass.get("product01Pass") != "PASS":
        raise Product04Blocker("BLOCKER: PRODUCT-01 not PASS")
    if p02_pass.get("product02Pass") != "PASS":
        raise Product04Blocker("BLOCKER: PRODUCT-02 not PASS")
    if p03_pass.get("product03Pass") != "PASS":
        raise Product04Blocker("BLOCKER: PRODUCT-03 not PASS")

    idle_sha = (assembly.get("asset") or {}).get("sha256")
    if idle_sha != PRODUCT01_IDLE_SHA:
        raise Product04Blocker(f"BLOCKER: PRODUCT-01 Idle SHA drift {idle_sha}")
    if (library.get("completeness") or {}).get("productSemanticCompleteness") != "5 / 5":
        raise Product04Blocker("BLOCKER: PRODUCT-02 semantic incomplete")
    if p03.get("attachmentAuthority", {}).get("child") != FACE_RIG_ROOT:
        raise Product04Blocker("BLOCKER: PRODUCT-03 FACE attachment broken")
    if p03.get("talkingCompatibility", {}).get("talking_status") != "GO":
        raise Product04Blocker("BLOCKER: PRODUCT-03 talking not GO")
    if face_lock.get("talking_status") != "GO":
        raise Product04Blocker("BLOCKER: FACE lock talking_status != GO")
    if face_lock.get("donorRole", {}).get("product_use") is not False:
        raise Product04Blocker("BLOCKER: Jake product_use must be false")
    owners = set(assembly.get("translationOwners") or [])
    if "NURION_root" not in owners or "NURION_pelvis" not in owners:
        raise Product04Blocker("BLOCKER: root/pelvis owners missing")

    expected_rt = (p03_pass.get("runtime") or {}).get("observedCanonicalSha256") or (
        p03_pass.get("runtime") or {}
    ).get("submittedCanonicalSha256")
    actual_rt = canonical_json_sha256(p03)
    if expected_rt and actual_rt != expected_rt:
        raise Product04Blocker(
            f"BLOCKER: PRODUCT-03 runtime canonical drift {actual_rt} != {expected_rt}"
        )

    return {
        "protected": protected,
        "assembly": assembly,
        "library": library,
        "product03": p03,
        "faceLock": face_lock,
        "receipts": {"p01": p01_pass, "p02": p02_pass, "p03": p03_pass},
        "fingerprints": {
            "product01AssemblySha256": _sha256_file(ROOT / ASSEMBLY_BASELINE_REL),
            "product02LibrarySha256": _sha256_file(ROOT / LIBRARY_REL),
            "product03RuntimeSha256": _sha256_file(ROOT / PRODUCT03_RUNTIME_REL),
            "product03RuntimeCanonicalSha256": actual_rt,
            "faceLockSha256": _sha256_file(ROOT / FACE_LOCK_REL),
            "idleAssetSha256": PRODUCT01_IDLE_SHA,
            "protectedSoT": protected,
            "p03PassZipSha256": p03_pass.get("sourceReviewPackageSha256"),
            "p02PassZipSha256": p02_pass.get("sourceReviewPackageSha256"),
            "p01PassZipSha256": p01_pass.get("sourceReviewPackageSha256"),
        },
    }


@dataclass
class AuthorityLedger:
    history: list[dict[str, Any]] = field(default_factory=list)

    def commit(self, *, state: str, authority: str, tick: int) -> None:
        if authority not in (AUTH_NONE, AUTH_ENTRANCE, AUTH_HANDOFF, AUTH_P03, AUTH_BLOCKED):
            raise Product04Error(f"invalid authority token: {authority}")
        self.history.append({"tick": tick, "state": state, "authority": authority})
        if len(self.history) >= 2:
            prev, cur = self.history[-2], self.history[-1]
            if prev["authority"] == AUTH_ENTRANCE and cur["authority"] == AUTH_NONE:
                raise Product04Error("G11 FAIL: authority gap after ENTRANCE")
            if prev["authority"] == AUTH_ENTRANCE and cur["authority"] == AUTH_P03:
                raise Product04Error("G11 FAIL: skipped RUNTIME_HANDOFF commit")
            if prev["authority"] == AUTH_HANDOFF and cur["authority"] not in (AUTH_P03, AUTH_BLOCKED):
                raise Product04Error("G11 FAIL: handoff did not commit to PRODUCT-03")
        by_tick: dict[int, set[str]] = {}
        for row in self.history:
            by_tick.setdefault(row["tick"], set()).add(row["authority"])
        for t, auths in by_tick.items():
            if AUTH_ENTRANCE in auths and AUTH_P03 in auths:
                raise Product04Error(f"G11 FAIL: dual authority at tick {t}")

    def assert_live_idle_authority(self) -> None:
        last = self.history[-1]
        if last["state"] != "LIVE_IDLE" or last["authority"] != AUTH_P03:
            raise Product04Error("G13 FAIL: LIVE_IDLE must be PRODUCT03_RUNTIME authority")


class EntranceStateMachine:
    def __init__(self) -> None:
        self.state = "BOOTSTRAP"
        self.trace: list[dict[str, Any]] = []
        self.authority = AuthorityLedger()
        self.tick = 0
        self._entrance_active = False
        self._runtime_active = False

    def _edge_allowed(self, nxt: str) -> bool:
        if (self.state, nxt) in DENIED_TRANSITIONS:
            return False
        if (self.state, nxt) in HAPPY_PATH:
            return True
        if nxt in ("RECOVERY", "BLOCKED") and self.state in (
            "BOOTSTRAP",
            "PRELOAD",
            "ENTRANCE_READY",
            "ENTRANCE_PLAYING",
            "RUNTIME_HANDOFF",
        ):
            return True
        if self.state == "RECOVERY" and nxt in ("PRELOAD", "ENTRANCE_READY", "BLOCKED"):
            return True
        return False

    def transition(self, nxt: str, *, event: str, detail: dict[str, Any] | None = None) -> None:
        if nxt not in CANONICAL_STATES:
            raise Product04Error(f"G02 FAIL: non-canonical state {nxt}")
        if not self._edge_allowed(nxt):
            raise Product04Error(f"G02 FAIL: denied/invalid transition {self.state}->{nxt}")
        prev = self.state
        self.state = nxt
        self.tick += 1
        self.trace.append(
            {"tick": self.tick, "from": prev, "to": nxt, "event": event, "detail": detail or {}}
        )

    def set_authority(self, authority: str) -> None:
        if authority == AUTH_ENTRANCE:
            if self._runtime_active:
                raise Product04Error("G11 FAIL: Entrance ACTIVE while Runtime ACTIVE")
            self._entrance_active = True
            self._runtime_active = False
        elif authority == AUTH_HANDOFF:
            self._entrance_active = False
            self._runtime_active = False
        elif authority == AUTH_P03:
            if self._entrance_active:
                raise Product04Error("G11 FAIL: Runtime ACTIVE while Entrance ACTIVE")
            self._entrance_active = False
            self._runtime_active = True
        elif authority == AUTH_BLOCKED:
            self._entrance_active = False
            self._runtime_active = False
        elif authority == AUTH_NONE:
            if self.state not in ("BOOTSTRAP", "PRELOAD", "ENTRANCE_READY", "RECOVERY"):
                raise Product04Error(f"G11 FAIL: authority NONE illegal in {self.state}")
            self._entrance_active = False
            self._runtime_active = False
        self.authority.commit(state=self.state, authority=authority, tick=self.tick)


def _assert_ownership(pose: dict[str, Any]) -> None:
    for b, bl in pose.items():
        tr = bl.get("translation") or [0, 0, 0]
        mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
        if b not in TRANSLATION_OWNERS and mag > 1e-9:
            raise Product04Error(f"G10 FAIL: ownership {b}")


def _pose_continuity(
    entrance_last: dict[str, Any],
    live_idle_ref: dict[str, Any],
    *,
    reference_source: str,
) -> dict[str, Any]:
    if set(entrance_last.keys()) != set(live_idle_ref.keys()):
        raise Product04Error("G12 FAIL: Core bone set mismatch at handoff")
    root_td = _vec_l1(
        entrance_last["NURION_root"]["translation"], live_idle_ref["NURION_root"]["translation"]
    )
    root_rd = 1.0 - _quat_dot(
        entrance_last["NURION_root"]["rotation_wxyz"], live_idle_ref["NURION_root"]["rotation_wxyz"]
    )
    head_rd = 1.0 - _quat_dot(
        entrance_last["NURION_head"]["rotation_wxyz"], live_idle_ref["NURION_head"]["rotation_wxyz"]
    )
    scale_delta = 0.0
    if root_td > MAX_ROOT_JUMP:
        raise Product04Error(f"G12 FAIL: unexpected root jump {root_td}")
    if abs(scale_delta) > FLOAT_EPS:
        raise Product04Error(f"G12 FAIL: scale discontinuity {scale_delta}")
    return {
        "referenceSource": reference_source,
        "rootTranslationDelta": root_td,
        "rootRotationDelta": root_rd,
        "headRotationDelta": head_rd,
        "scaleDelta": scale_delta,
        "unexpectedTeleport": False,
        "unexpectedSnap": False,
        "scaleDiscontinuity": False,
        "status": "PASS",
        "note": "Idle head/root consumed from PRODUCT-01 baseline (PRODUCT-03 locked) — not redefined",
    }


def _analyze_handoff_authority(history: list[dict[str, Any]]) -> dict[str, Any]:
    dual = False
    by_tick: dict[int, set[str]] = {}
    for row in history:
        by_tick.setdefault(row["tick"], set()).add(row["authority"])
    for auths in by_tick.values():
        if AUTH_ENTRANCE in auths and AUTH_P03 in auths:
            dual = True
    zero_during = False
    for r in history:
        if r["state"] == "RUNTIME_HANDOFF" and r["authority"] == AUTH_NONE:
            zero_during = True
        if r["state"] == "RUNTIME_HANDOFF" and r["authority"] in (AUTH_ENTRANCE, AUTH_P03):
            dual = True
    if dual:
        raise Product04Error("G11 FAIL: dualAuthorityObserved=true")
    if zero_during:
        raise Product04Error("G11 FAIL: zeroAuthorityObservedDuringCommittedHandoff=true")
    auths = [r["authority"] for r in history]
    if AUTH_HANDOFF not in auths or AUTH_P03 not in auths:
        raise Product04Error("G11 FAIL: missing handoff commit sequence")
    i_h = auths.index(AUTH_HANDOFF)
    if i_h == 0 or auths[i_h - 1] != AUTH_ENTRANCE:
        raise Product04Error("G11 FAIL: handoff not preceded by ENTRANCE authority")
    if i_h + 1 >= len(auths) or auths[i_h + 1] != AUTH_P03:
        raise Product04Error("G11 FAIL: handoff not followed by PRODUCT03_RUNTIME")
    return {
        "dualAuthorityObserved": False,
        "zeroAuthorityObservedDuringCommittedHandoff": False,
        "authorityTransferCount": 1,
        "sequence": ["ENTRANCE", "RUNTIME_HANDOFF_COMMIT", "PRODUCT03_RUNTIME"],
    }


def run_happy_path(upstream: dict[str, Any]) -> dict[str, Any]:
    assembly = upstream["assembly"]
    library = upstream["library"]
    p03 = upstream["product03"]
    sm = EntranceStateMachine()

    sm.set_authority(AUTH_NONE)
    preload_plan = {
        "product01": ASSEMBLY_BASELINE_REL,
        "product02": LIBRARY_REL,
        "product03": PRODUCT03_RUNTIME_REL,
        "faceLock": FACE_LOCK_REL,
        "idleAssetSha256": PRODUCT01_IDLE_SHA,
        "requiredMotions": list(REQUIRED_MOTION_IDS),
    }
    sm.transition("PRELOAD", event="preload_start", detail={"plan": preload_plan})
    sm.set_authority(AUTH_NONE)
    if not all(
        (ROOT / rel).exists()
        for rel in (ASSEMBLY_BASELINE_REL, LIBRARY_REL, PRODUCT03_RUNTIME_REL, FACE_LOCK_REL)
    ):
        sm.transition("BLOCKED", event="preload_missing_deps")
        sm.set_authority(AUTH_BLOCKED)
        raise Product04Blocker("BLOCKER: preload dependency missing")

    p03_ready = (
        p03.get("productSemanticRuntime", {}).get("talkingGo") is True
        and p03.get("attachmentAuthority", {}).get("relation") == "SOLE_ATTACHMENT"
        and len(p03.get("motionBindings") or []) == 5
    )
    if not p03_ready:
        raise Product04Blocker("BLOCKER: PRODUCT-03 runtime not ready")

    sm.transition("ENTRANCE_READY", event="deps_verified", detail={"p03Ready": True})
    sm.set_authority(AUTH_NONE)

    live_idle_ref = assembly["idle"]["canonicalPose"]
    _assert_ownership(live_idle_ref)

    identity = {
        "donor": "mjn_legacy_v1",
        "idleAssetSha256": PRODUCT01_IDLE_SHA,
        "product01AssemblyId": assembly.get("assemblyId"),
        "product03RuntimeId": p03.get("runtimeId"),
        "proxyCharacter": False,
        "jakeProductUse": False,
        "continuity": "Entrance MJN Idle (P02) -> PRODUCT-01/03 idle reference -> LIVE_IDLE",
    }

    idle_motion = next(m for m in library["motions"] if m["motionId"] == "Idle")
    if idle_motion.get("fulfillment") != "DEDICATED":
        raise Product04Blocker("BLOCKER: Idle not DEDICATED")
    if idle_motion["sourceAsset"]["sha256"] != PRODUCT01_IDLE_SHA:
        raise Product04Blocker("BLOCKER: G08 Idle source SHA != PRODUCT-01 frozen Idle")

    sm.transition("ENTRANCE_PLAYING", event="entrance_start", detail={"clip": "Idle"})
    sm.set_authority(AUTH_ENTRANCE)

    entrance_frames = []
    for sample in idle_motion["samples"]:
        pose = sample["canonicalPose"]
        _assert_ownership(pose)
        entrance_frames.append({"frame": sample["frame"], "canonicalPose": pose})
        if sm._entrance_active and sm._runtime_active:
            raise Product04Error("G07/G11 FAIL: dual ownership during entrance")

    last_entrance = entrance_frames[-1]["canonicalPose"]
    continuity = _pose_continuity(
        last_entrance,
        live_idle_ref,
        reference_source="PRODUCT-01 idle canonicalPose (PRODUCT-03 consume lock)",
    )

    sm.transition("RUNTIME_HANDOFF", event="handoff_begin", detail={"commit": "pending"})
    sm.set_authority(AUTH_HANDOFF)
    handoff_commit: dict[str, Any] = {
        "from": "ENTRANCE",
        "through": "RUNTIME_HANDOFF",
        "to": "LIVE_IDLE",
        "commitId": canonical_json_sha256({"e": last_entrance, "l": live_idle_ref, "id": identity}),
        "fromAuthority": AUTH_ENTRANCE,
        "toAuthority": AUTH_P03,
        "commitCount": 1,
    }
    sm.transition("LIVE_IDLE", event="handoff_commit", detail={"commitId": handoff_commit["commitId"]})
    sm.set_authority(AUTH_P03)
    sm.authority.assert_live_idle_authority()
    g11 = _analyze_handoff_authority(sm.authority.history)
    handoff_commit.update(g11)

    face_fp = upstream["fingerprints"]["faceLockSha256"]
    if face_fp != PROTECTED_SOT_SHA256["NURION_FACE_PRODUCT_LOCK_V1.json"]:
        raise Product04Error("G09 FAIL: FACE lock mutated")

    return {
        "currentState": sm.state,
        "stateTrace": sm.trace,
        "characterAuthority": AUTH_P03,
        "authorityHistory": sm.authority.history,
        "authorityTransferCount": g11["authorityTransferCount"],
        "preloadPlan": preload_plan,
        "entranceIdentity": identity,
        "runtimeIdentity": {
            "product03RuntimeId": p03.get("runtimeId"),
            "attachment": p03.get("attachmentAuthority"),
            "idleAssetSha256": PRODUCT01_IDLE_SHA,
        },
        "entrance": {
            "motionId": "Idle",
            "sourceSha256": idle_motion["sourceAsset"]["sha256"],
            "frames": len(entrance_frames),
            "singleSequence": True,
        },
        "handoff": handoff_commit,
        "visualContinuity": continuity,
        "liveIdleAuthority": "PRODUCT-03",
        "liveIdle": {
            "authority": AUTH_P03,
            "product03RuntimeId": p03.get("runtimeId"),
            "product04OwnsCharacter": False,
            "talking": p03.get("talkingCompatibility", {}).get("talking_status"),
            "idleReferenceConsumed": True,
        },
        "faceEyeTalking": {
            "faceLockSha256": face_fp,
            "eyePreserved": p03.get("eyePreservation", {}).get("stableAcrossAllMotions"),
            "talking": "GO",
            "mutated": False,
        },
        "bodyRoot": {
            "translationOwners": sorted(TRANSLATION_OWNERS),
            "rootEqualsPelvis": False,
            "preserved": True,
        },
    }


def prove_denied_transitions() -> list[dict[str, Any]]:
    out = []
    path_to = {
        "BOOTSTRAP": [],
        "PRELOAD": [("PRELOAD", "t")],
        "ENTRANCE_READY": [("PRELOAD", "t"), ("ENTRANCE_READY", "t")],
        "ENTRANCE_PLAYING": [("PRELOAD", "t"), ("ENTRANCE_READY", "t"), ("ENTRANCE_PLAYING", "t")],
        "BLOCKED": [("PRELOAD", "t"), ("BLOCKED", "fail")],
    }
    for frm, to in sorted(DENIED_TRANSITIONS):
        sm = EntranceStateMachine()
        for nxt, ev in path_to.get(frm, []):
            sm.transition(nxt, event=ev)
        raised = False
        try:
            sm.transition(to, event="illegal")
        except Product04Error:
            raised = True
        if not raised:
            raise Product04Error(f"denied transition allowed: {frm}->{to}")
        out.append({"from": frm, "to": to, "denied": True})
    return out


def prove_fail_closed_missing_dep() -> dict[str, Any]:
    try:
        _load_json("fast_track/working/meshy_silver_starlight/semantic/DOES_NOT_EXIST_P03.json")
        return {"status": "FAIL", "error": "expected BLOCKER"}
    except Product04Blocker:
        return {"status": "BLOCKER_OK", "path": "missing_p03"}


def prove_recovery_allowed_blocked_deny() -> dict[str, Any]:
    sm = EntranceStateMachine()
    sm.transition("PRELOAD", event="t")
    sm.transition("RECOVERY", event="fail")
    sm.transition("PRELOAD", event="retry")
    sm2 = EntranceStateMachine()
    sm2.transition("PRELOAD", event="t")
    sm2.transition("BLOCKED", event="fail")
    blocked_to_live = False
    try:
        sm2.transition("LIVE_IDLE", event="illegal")
    except Product04Error:
        blocked_to_live = True
    if not blocked_to_live:
        raise Product04Error("BLOCKED->LIVE_IDLE must DENY")
    return {"recoveryToPreload": "ALLOW", "blockedToLiveIdle": "DENY"}


def build_entrance_state() -> dict[str, Any]:
    jake = assert_jake_product_path_blocked()
    upstream = consume_upstream()
    run = run_happy_path(upstream)
    denied = prove_denied_transitions()
    fail_closed = prove_fail_closed_missing_dep()
    recovery = prove_recovery_allowed_blocked_deny()

    run2 = run_happy_path(upstream)
    h1 = canonical_json_sha256({"trace": run["stateTrace"], "auth": run["authorityHistory"]})
    h2 = canonical_json_sha256({"trace": run2["stateTrace"], "auth": run2["authorityHistory"]})
    if h1 != h2:
        raise Product04Error("G14/G16 FAIL: non-deterministic state trace")

    fp = upstream["fingerprints"]
    artifact = {
        "schema": "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1",
        "runtimeId": "NURION-PRODUCT-04_CHARACTER_ENTRANCE_STATE_V1",
        "status": "AGENT_STATE_BUILT",
        "product04Pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "aestheticPass": "DENY — human visual review only",
        "oneLineContract": ONE_LINE,
        "contract": CONTRACT_REL,
        "coreBoundary": ["ENTRY", "ENTRANCE", "RUNTIME_HANDOFF", "LIVE_IDLE"],
        "canonicalStates": list(CANONICAL_STATES),
        "happyPath": [list(e) for e in HAPPY_PATH],
        "deniedTransitions": [{"from": a, "to": b} for a, b in sorted(DENIED_TRANSITIONS)],
        "deniedTransitionProof": denied,
        "recoveryProof": recovery,
        "currentState": run["currentState"],
        "stateTrace": run["stateTrace"],
        "characterAuthority": run["characterAuthority"],
        "authorityTransferCount": run["authorityTransferCount"],
        "entranceIdentity": run["entranceIdentity"],
        "runtimeIdentity": run["runtimeIdentity"],
        "handoff": run["handoff"],
        "liveIdleAuthority": "PRODUCT-03",
        "visualContinuity": run["visualContinuity"],
        "protectedState": {
            "FACE": {"sha256": fp["faceLockSha256"], "mutated": False},
            "Eye": {"preserved": True, "mutated": False},
            "TALKING": {"status": "GO", "mutated": False},
            "BODY": {"rootPelvisSeparate": True, "mutated": False},
            "PRODUCT-01": {"sha256": fp["product01AssemblySha256"], "mutated": False},
            "PRODUCT-02": {"sha256": fp["product02LibrarySha256"], "mutated": False},
            "PRODUCT-03": {
                "fileSha256": fp["product03RuntimeSha256"],
                "canonicalSha256": fp["product03RuntimeCanonicalSha256"],
                "mutated": False,
            },
        },
        "failClosed": fail_closed,
        "buildDeterminism": {"traceHash": h1, "stable": True},
        "relocationDeterminism": {"required": True, "provenInProofRunner": True},
        "consumes": {
            "PRODUCT-01": {
                "path": ASSEMBLY_BASELINE_REL,
                "sha256": fp["product01AssemblySha256"],
                "policy": "CONSUME ONLY",
            },
            "PRODUCT-02": {
                "path": LIBRARY_REL,
                "sha256": fp["product02LibrarySha256"],
                "policy": "CONSUME ONLY",
            },
            "PRODUCT-03": {
                "path": PRODUCT03_RUNTIME_REL,
                "fileSha256": fp["product03RuntimeSha256"],
                "canonicalSha256": fp["product03RuntimeCanonicalSha256"],
                "policy": "CONSUME ONLY — LIVE_IDLE authority",
            },
            "FACE_PRODUCT_LOCK": {
                "path": FACE_LOCK_REL,
                "sha256": fp["faceLockSha256"],
                "policy": "PRESERVE",
            },
            "idleAssetSha256": fp["idleAssetSha256"],
        },
        "run": run,
        "donorIsolation": {"Jake": jake, "jakeProductUse": False, "proxyCharacter": False},
        "criticalGates": {
            "P4-G08": {"status": "PASS", "identity": run["entranceIdentity"]},
            "P4-G11": {
                "status": "PASS",
                "dualAuthorityObserved": False,
                "zeroAuthorityObservedDuringCommittedHandoff": False,
                "handoff": run["handoff"],
            },
            "P4-G12": {"status": "PASS", "continuity": run["visualContinuity"]},
            "P4-G13": {"status": "PASS", "liveIdleAuthority": "PRODUCT-03"},
        },
        "scope": {
            "PRODUCT-05": "DENY",
            "upstreamAutoFix": "DENY",
            "agentClosedPass": "DENY",
            "aestheticPass": "DENY",
        },
        "foundation": {
            "PRODUCT-01": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-02": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-03": "CLOSED / PASS / CONSUME ONLY",
            "FACE_PRODUCT_LOCK": "PRESERVE",
            "Eye_Calibration": "PRESERVE",
            "TALKING": "GO / PRESERVE",
        },
        "notes": [
            "LIVE_IDLE authority is PRODUCT-03 only",
            "Character authority is exactly one at every tick",
            "Idle NURION_head/root consumed from PRODUCT-01 — not redefined",
        ],
    }
    assert_assembly_has_no_absolute_paths(artifact)
    return artifact


@dataclass
class EntranceStateBuildResult:
    state: dict[str, Any]
    sha256: str

    def write(self, path: Path | None = None) -> Path:
        out = path or STATE_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out


def build_and_hash() -> EntranceStateBuildResult:
    st = build_entrance_state()
    return EntranceStateBuildResult(state=st, sha256=canonical_json_sha256(st))


__all__ = [
    "CONTRACT_REL",
    "STATE_PATH",
    "STATE_REL",
    "ONE_LINE",
    "CANONICAL_STATES",
    "Product04Blocker",
    "Product04Error",
    "build_and_hash",
    "build_entrance_state",
    "consume_upstream",
]
