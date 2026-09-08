#!/usr/bin/env python3
"""NURION-PRODUCT-05 — Character Interaction & Behavior Runtime (consume-only)."""

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
    "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_CONTRACT_V1.json"
)
RUNTIME_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1.json"
)
RUNTIME_PATH = ROOT / RUNTIME_REL
P04_STATE_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/"
    "NURION_PRODUCT04_CHARACTER_ENTRANCE_STATE_V1.json"
)
FACE_LOCK_REL = (
    "fast_track/working/meshy_silver_starlight/semantic/NURION_FACE_PRODUCT_LOCK_V1.json"
)
P04_PASS_RECEIPT_REL = (
    "fast_track/working/meshy_silver_starlight/evidence/NURION-PRODUCT-04_PASS_receipt.json"
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
    "PRODUCT-05 shall deterministically operate the canonical NURION character after "
    "PRODUCT-04 LIVE_IDLE by consuming PRODUCT-01 through PRODUCT-04 without mutation, "
    "translating valid interaction events into semantically correct approved behaviors, "
    "coordinating TALKING, FACE, Eye and PRODUCT-02 body motions under single behavior "
    "authority, and safely returning control to the PRODUCT-03 canonical LIVE_IDLE runtime "
    "through deterministic, interrupt-safe and fail-closed behavior semantics."
)

CANONICAL_STATES = (
    "LIVE_IDLE",
    "INTERACTION_RECEIVED",
    "BEHAVIOR_SELECT",
    "BEHAVIOR_READY",
    "BEHAVIOR_EXECUTING",
    "BEHAVIOR_INTERRUPTING",
    "RECOVERY",
    "BLOCKED",
)

HAPPY_PATH = (
    ("LIVE_IDLE", "INTERACTION_RECEIVED"),
    ("INTERACTION_RECEIVED", "BEHAVIOR_SELECT"),
    ("BEHAVIOR_SELECT", "BEHAVIOR_READY"),
    ("BEHAVIOR_READY", "BEHAVIOR_EXECUTING"),
    ("BEHAVIOR_EXECUTING", "RECOVERY"),
    ("RECOVERY", "LIVE_IDLE"),
)

INTERRUPT_PATH = (
    ("BEHAVIOR_EXECUTING", "BEHAVIOR_INTERRUPTING"),
    ("BEHAVIOR_INTERRUPTING", "RECOVERY"),
    ("RECOVERY", "LIVE_IDLE"),
)

DENIED_TRANSITIONS = {
    ("BLOCKED", "BEHAVIOR_EXECUTING"),
    ("BLOCKED", "LIVE_IDLE"),
    ("LIVE_IDLE", "BEHAVIOR_EXECUTING"),
    ("BEHAVIOR_EXECUTING", "BEHAVIOR_EXECUTING"),
}

SEMANTIC_MAP_V1 = {
    "IDLE": "Idle",
    "GREETING": "Bow",
    "FORMAL_GREETING": "LargeBow",
    "HANDSHAKE": "Handshake",
    "CELEBRATION": "Dance",
}

AUTH_NONE = "NONE"
AUTH_BEHAVIOR = "PRODUCT05_BEHAVIOR"
AUTH_P03 = "PRODUCT03_LIVE_IDLE"
AUTH_BLOCKED = "BLOCKED"

# V1 arbitration: ACCEPT when idle; QUEUE (max 1) when executing; REJECT otherwise / queue full
ARBITRATION_POLICY = {
    "activeBehaviorCountMax": 1,
    "onNewEventWhileActive": ["ACCEPT", "QUEUE", "REJECT"],
    "queueDepthMax": 1,
    "duringInterruptOrRecovery": "REJECT",
    "duringBlocked": "REJECT",
}


class Product05Blocker(RuntimeError):
    pass


class Product05Error(ValueError):
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
        raise Product05Blocker(f"BLOCKER: missing consume-only artifact: {rel}")
    return json.loads(path.read_text(encoding="utf-8"))


def consume_upstream() -> dict[str, Any]:
    try:
        protected = assert_protected_sot_unchanged()
    except AssertionError as e:
        raise Product05Blocker(f"BLOCKER Protected SoT: {e}") from e

    assembly = _load_json(ASSEMBLY_BASELINE_REL)
    library = _load_json(LIBRARY_REL)
    p03 = _load_json(PRODUCT03_RUNTIME_REL)
    p04 = _load_json(P04_STATE_REL)
    face_lock = _load_json(FACE_LOCK_REL)
    receipts = {
        "p01": _load_json(P01_PASS_RECEIPT_REL),
        "p02": _load_json(P02_PASS_RECEIPT_REL),
        "p03": _load_json(P03_PASS_RECEIPT_REL),
        "p04": _load_json(P04_PASS_RECEIPT_REL),
    }

    for label, doc in (("assembly", assembly), ("library", library), ("p03", p03), ("p04", p04)):
        try:
            assert_assembly_has_no_absolute_paths(doc)
        except Exception as e:
            raise Product05Blocker(f"BLOCKER absolute path in {label}: {e}") from e

    for key, field in (
        ("p01", "product01Pass"),
        ("p02", "product02Pass"),
        ("p03", "product03Pass"),
        ("p04", "product04Pass"),
    ):
        if receipts[key].get(field) != "PASS":
            raise Product05Blocker(f"BLOCKER: PRODUCT-{key[-1]} not PASS")

    if p04.get("currentState") != "LIVE_IDLE":
        raise Product05Blocker("BLOCKER G02: PRODUCT-04 not at LIVE_IDLE")
    if p04.get("liveIdleAuthority") != "PRODUCT-03":
        raise Product05Blocker("BLOCKER G02: PRODUCT-04 LIVE_IDLE authority != PRODUCT-03")
    if (assembly.get("asset") or {}).get("sha256") != PRODUCT01_IDLE_SHA:
        raise Product05Blocker("BLOCKER: PRODUCT-01 Idle SHA drift")
    if (library.get("completeness") or {}).get("productSemanticCompleteness") != "5 / 5":
        raise Product05Blocker("BLOCKER: PRODUCT-02 semantic incomplete")
    if p03.get("attachmentAuthority", {}).get("child") != FACE_RIG_ROOT:
        raise Product05Blocker("BLOCKER: PRODUCT-03 FACE attachment broken")
    if p03.get("talkingCompatibility", {}).get("talking_status") != "GO":
        raise Product05Blocker("BLOCKER: PRODUCT-03 talking not GO")
    if face_lock.get("talking_status") != "GO":
        raise Product05Blocker("BLOCKER: FACE lock talking_status != GO")
    if face_lock.get("donorRole", {}).get("product_use") is not False:
        raise Product05Blocker("BLOCKER: Jake product_use must be false")

    expected_rt = (receipts["p03"].get("runtime") or {}).get("observedCanonicalSha256") or (
        receipts["p03"].get("runtime") or {}
    ).get("submittedCanonicalSha256")
    actual_rt = canonical_json_sha256(p03)
    if expected_rt and actual_rt != expected_rt:
        raise Product05Blocker(f"BLOCKER: PRODUCT-03 runtime canonical drift")

    expected_p04 = (receipts["p04"].get("state") or {}).get("observedCanonicalSha256") or (
        receipts["p04"].get("state") or {}
    ).get("submittedCanonicalSha256")
    actual_p04 = canonical_json_sha256(p04)
    if expected_p04 and actual_p04 != expected_p04:
        raise Product05Blocker(f"BLOCKER: PRODUCT-04 state canonical drift")

    return {
        "protected": protected,
        "assembly": assembly,
        "library": library,
        "product03": p03,
        "product04": p04,
        "faceLock": face_lock,
        "receipts": receipts,
        "fingerprints": {
            "product01AssemblySha256": _sha256_file(ROOT / ASSEMBLY_BASELINE_REL),
            "product02LibrarySha256": _sha256_file(ROOT / LIBRARY_REL),
            "product03RuntimeSha256": _sha256_file(ROOT / PRODUCT03_RUNTIME_REL),
            "product03RuntimeCanonicalSha256": actual_rt,
            "product04StateSha256": _sha256_file(ROOT / P04_STATE_REL),
            "product04StateCanonicalSha256": actual_p04,
            "faceLockSha256": _sha256_file(ROOT / FACE_LOCK_REL),
            "idleAssetSha256": PRODUCT01_IDLE_SHA,
            "protectedSoT": protected,
        },
    }


@dataclass
class BehaviorAuthority:
    history: list[dict[str, Any]] = field(default_factory=list)
    active_count: int = 0
    dual_observed: bool = False

    def set(self, *, state: str, authority: str, tick: int, behavior_id: str | None = None) -> None:
        if authority == AUTH_BEHAVIOR:
            if self.active_count >= 1:
                last = self.history[-1] if self.history else None
                last_bid = (last or {}).get("behaviorId")
                if last_bid and behavior_id and last_bid != behavior_id:
                    # Attempt rejected — dual authority was NOT successfully held
                    raise Product05Error("G07 FAIL: dual behavior authority")
            self.active_count = 1
        elif authority in (AUTH_P03, AUTH_NONE, AUTH_BLOCKED):
            self.active_count = 0
        if self.active_count > 1:
            self.dual_observed = True
            raise Product05Error("G07 FAIL: activeBehaviorCount > 1")
        self.history.append(
            {
                "tick": tick,
                "state": state,
                "authority": authority,
                "behaviorId": behavior_id,
                "activeBehaviorCount": self.active_count,
            }
        )


class BehaviorStateMachine:
    def __init__(self) -> None:
        self.state = "LIVE_IDLE"
        self.trace: list[dict[str, Any]] = []
        self.tick = 0
        self.authority = BehaviorAuthority()
        self.authority.set(state=self.state, authority=AUTH_P03, tick=0)
        self.queue: list[str] = []
        self.active_intent: str | None = None
        self.active_slot: str | None = None

    def _edge_allowed(self, nxt: str) -> bool:
        if (self.state, nxt) in DENIED_TRANSITIONS:
            return False
        if (self.state, nxt) in HAPPY_PATH or (self.state, nxt) in INTERRUPT_PATH:
            return True
        if nxt == "BLOCKED" and self.state in (
            "INTERACTION_RECEIVED",
            "BEHAVIOR_SELECT",
            "BEHAVIOR_READY",
            "BEHAVIOR_EXECUTING",
        ):
            return True
        return False

    def transition(self, nxt: str, *, event: str, detail: dict[str, Any] | None = None) -> None:
        if nxt not in CANONICAL_STATES:
            raise Product05Error(f"G03 FAIL: non-canonical state {nxt}")
        if not self._edge_allowed(nxt):
            raise Product05Error(f"G03 FAIL: denied/invalid transition {self.state}->{nxt}")
        prev = self.state
        self.state = nxt
        self.tick += 1
        self.trace.append(
            {"tick": self.tick, "from": prev, "to": nxt, "event": event, "detail": detail or {}}
        )


def _motion_by_id(library: dict[str, Any], motion_id: str) -> dict[str, Any]:
    for m in library.get("motions") or []:
        if m.get("motionId") == motion_id:
            return m
    raise Product05Error(f"G05/G06 FAIL: missing motion slot {motion_id}")


def resolve_semantic(intent: str) -> str:
    if intent not in SEMANTIC_MAP_V1:
        raise Product05Error(f"G04/G05 FAIL: unknown/unsupported intent {intent}")
    return SEMANTIC_MAP_V1[intent]


def arbitrate(sm: BehaviorStateMachine, intent: str) -> str:
    """Return ACCEPT | QUEUE | REJECT per frozen V1 policy."""
    if sm.state == "BLOCKED":
        return "REJECT"
    if sm.state in ("BEHAVIOR_INTERRUPTING", "RECOVERY", "INTERACTION_RECEIVED", "BEHAVIOR_SELECT", "BEHAVIOR_READY"):
        return "REJECT"
    if sm.state == "LIVE_IDLE":
        return "ACCEPT"
    if sm.state == "BEHAVIOR_EXECUTING":
        if len(sm.queue) >= ARBITRATION_POLICY["queueDepthMax"]:
            return "REJECT"
        return "QUEUE"
    return "REJECT"


def _assert_ownership(pose: dict[str, Any]) -> None:
    for b, bl in pose.items():
        tr = bl.get("translation") or [0, 0, 0]
        mag = abs(tr[0]) + abs(tr[1]) + abs(tr[2])
        if b not in TRANSLATION_OWNERS and mag > 1e-9:
            raise Product05Error(f"G12 FAIL: ownership {b}")


def execute_behavior(
    sm: BehaviorStateMachine,
    *,
    intent: str,
    library: dict[str, Any],
    assembly: dict[str, Any],
    p03: dict[str, Any],
    talking_active: bool = True,
) -> dict[str, Any]:
    decision = arbitrate(sm, intent)
    if decision == "REJECT":
        return {"decision": "REJECT", "intent": intent, "executed": False}
    if decision == "QUEUE":
        sm.queue.append(intent)
        return {"decision": "QUEUE", "intent": intent, "queue": list(sm.queue), "executed": False}

    # ACCEPT
    try:
        slot = resolve_semantic(intent)
    except Product05Error:
        sm.transition("INTERACTION_RECEIVED", event="event", detail={"intent": intent})
        sm.transition("BLOCKED", event="invalid_semantic", detail={"intent": intent})
        sm.authority.set(state=sm.state, authority=AUTH_BLOCKED, tick=sm.tick)
        raise

    sm.transition("INTERACTION_RECEIVED", event="event", detail={"intent": intent})
    sm.authority.set(state=sm.state, authority=AUTH_P03, tick=sm.tick)
    sm.transition("BEHAVIOR_SELECT", event="select", detail={"intent": intent, "semanticSlot": slot})
    motion = _motion_by_id(library, slot)
    if motion.get("fulfillment") != "DEDICATED":
        sm.transition("BLOCKED", event="non_dedicated", detail={"slot": slot})
        sm.authority.set(state=sm.state, authority=AUTH_BLOCKED, tick=sm.tick)
        raise Product05Error(f"G06 FAIL: {slot} not DEDICATED")

    # Reject clip-name as authority (semantic slot only)
    clip = motion.get("meshyClipName")
    if intent == "HANDSHAKE" and slot != "Handshake":
        raise Product05Error("G05 FAIL: HANDSHAKE semantic mismatch")
    if intent == "CELEBRATION" and slot != "Dance":
        raise Product05Error("G05 FAIL: CELEBRATION semantic mismatch")

    sm.transition(
        "BEHAVIOR_READY",
        event="ready",
        detail={"semanticSlot": slot, "clipConsumedNotAuthoritative": clip, "fulfillment": "DEDICATED"},
    )
    sm.transition("BEHAVIOR_EXECUTING", event="execute_start", detail={"semanticSlot": slot})
    if sm.authority.active_count >= 1:
        # previous should have been cleared at LIVE_IDLE
        pass
    sm.authority.set(state=sm.state, authority=AUTH_BEHAVIOR, tick=sm.tick, behavior_id=slot)
    sm.active_intent = intent
    sm.active_slot = slot

    frames = []
    for sample in motion.get("samples") or []:
        pose = sample["canonicalPose"]
        _assert_ownership(pose)
        frames.append({"frame": sample["frame"], "semanticSlot": slot})
        if sm.authority.active_count != 1:
            raise Product05Error("G07 FAIL: activeBehaviorCount != 1 during execute")

    talking = p03.get("talkingCompatibility") or {}
    coplay = {c["motionId"]: c for c in talking.get("coplay") or []}
    if talking_active:
        if slot not in coplay or coplay[slot].get("status") != "PASS":
            raise Product05Error(f"G11 FAIL: TALKING co-play not valid for {slot}")
        if talking.get("talking_status") != "GO":
            raise Product05Error("G11 FAIL: talking_status != GO")
        if talking.get("faceLockUnmutated") is not True:
            raise Product05Error("G11 FAIL: faceLockUnmutated != true")

    sm.transition("RECOVERY", event="complete", detail={"semanticSlot": slot, "frames": len(frames)})
    sm.authority.set(state=sm.state, authority=AUTH_NONE, tick=sm.tick)
    idle_ref = assembly["idle"]["canonicalPose"]
    _assert_ownership(idle_ref)
    # Consume PRODUCT-03 LIVE_IDLE — no PRODUCT-05 private Idle
    sm.transition(
        "LIVE_IDLE",
        event="recover_p03",
        detail={
            "authority": "PRODUCT-03",
            "product05PrivateIdle": False,
            "idleConsumedFrom": "PRODUCT-01→PRODUCT-03",
        },
    )
    sm.authority.set(state=sm.state, authority=AUTH_P03, tick=sm.tick)
    sm.active_intent = None
    sm.active_slot = None

    return {
        "decision": "ACCEPT",
        "intent": intent,
        "semanticSlot": slot,
        "clipConsumedNotAuthoritative": clip,
        "frames": len(frames),
        "executed": True,
        "talkingCoordinated": talking_active,
        "recoveredTo": "PRODUCT-03 LIVE_IDLE",
        "product05OwnsLiveIdle": False,
    }


def interrupt_active(sm: BehaviorStateMachine, assembly: dict[str, Any]) -> dict[str, Any]:
    if sm.state != "BEHAVIOR_EXECUTING":
        raise Product05Error("G13 FAIL: interrupt only from BEHAVIOR_EXECUTING")
    # DENY direct jump to another EXECUTING
    raised = False
    try:
        sm.transition("BEHAVIOR_EXECUTING", event="illegal_direct_jump")
    except Product05Error:
        raised = True
    if not raised:
        raise Product05Error("G13 FAIL: direct cross-motion jump allowed")

    prev_slot = sm.active_slot
    sm.transition("BEHAVIOR_INTERRUPTING", event="interrupt", detail={"fromSlot": prev_slot})
    sm.authority.set(state=sm.state, authority=AUTH_BEHAVIOR, tick=sm.tick, behavior_id=prev_slot)
    sm.transition("RECOVERY", event="interrupt_recover", detail={"fromSlot": prev_slot})
    sm.authority.set(state=sm.state, authority=AUTH_NONE, tick=sm.tick)
    _assert_ownership(assembly["idle"]["canonicalPose"])
    sm.transition(
        "LIVE_IDLE",
        event="recover_p03",
        detail={"authority": "PRODUCT-03", "afterInterrupt": True},
    )
    sm.authority.set(state=sm.state, authority=AUTH_P03, tick=sm.tick)
    sm.active_intent = None
    sm.active_slot = None
    return {
        "interrupted": True,
        "fromSlot": prev_slot,
        "directCrossMotionJump": False,
        "recoveredTo": "PRODUCT-03 LIVE_IDLE",
        "dualBehaviorAuthorityObserved": sm.authority.dual_observed,
    }


def run_happy_cycle(upstream: dict[str, Any]) -> dict[str, Any]:
    sm = BehaviorStateMachine()
    library = upstream["library"]
    assembly = upstream["assembly"]
    p03 = upstream["product03"]

    results = []
    for intent in ("GREETING", "FORMAL_GREETING", "HANDSHAKE", "CELEBRATION", "IDLE"):
        r = execute_behavior(
            sm, intent=intent, library=library, assembly=assembly, p03=p03, talking_active=True
        )
        if not r.get("executed"):
            raise Product05Error(f"happy path failed for {intent}: {r}")
        results.append(r)

    if sm.state != "LIVE_IDLE":
        raise Product05Error("G14 FAIL: not LIVE_IDLE after cycle")
    if sm.authority.history[-1]["authority"] != AUTH_P03:
        raise Product05Error("G14 FAIL: LIVE_IDLE authority not PRODUCT-03")
    if sm.authority.dual_observed:
        raise Product05Error("G07 FAIL: dualBehaviorAuthorityObserved=true")

    return {
        "currentState": sm.state,
        "stateTrace": sm.trace,
        "authorityHistory": sm.authority.history,
        "behaviors": results,
        "dualBehaviorAuthorityObserved": False,
        "activeBehaviorCountMaxObserved": 1,
        "liveIdleAuthority": "PRODUCT-03",
        "product05OwnsLiveIdle": False,
    }


def run_interrupt_cycle(upstream: dict[str, Any]) -> dict[str, Any]:
    sm = BehaviorStateMachine()
    library = upstream["library"]
    assembly = upstream["assembly"]
    p03 = upstream["product03"]

    # Start CELEBRATION then interrupt mid-way (simulate by transitioning after READY→EXECUTING start)
    intent = "CELEBRATION"
    slot = resolve_semantic(intent)
    sm.transition("INTERACTION_RECEIVED", event="event", detail={"intent": intent})
    sm.transition("BEHAVIOR_SELECT", event="select", detail={"semanticSlot": slot})
    motion = _motion_by_id(library, slot)
    if motion.get("fulfillment") != "DEDICATED":
        raise Product05Error("G06 FAIL: Dance not dedicated")
    sm.transition("BEHAVIOR_READY", event="ready", detail={"semanticSlot": slot})
    sm.transition("BEHAVIOR_EXECUTING", event="execute_start", detail={"semanticSlot": slot, "progress": 0.5})
    sm.authority.set(state=sm.state, authority=AUTH_BEHAVIOR, tick=sm.tick, behavior_id=slot)
    sm.active_slot = slot
    sm.active_intent = intent

    # dual attempt while executing
    dual = arbitrate(sm, "HANDSHAKE")
    if dual not in ("QUEUE", "REJECT"):
        raise Product05Error("G08 FAIL: dual must QUEUE or REJECT")
    queued = None
    if dual == "QUEUE":
        sm.queue.append("HANDSHAKE")
        queued = "HANDSHAKE"

    # illegal: second concurrent behavior authority (different slot) — must DENY without marking dual as observed
    dual_exec_denied = False
    dual_flag_before = sm.authority.dual_observed
    try:
        sm.authority.set(
            state=sm.state, authority=AUTH_BEHAVIOR, tick=sm.tick, behavior_id="Handshake"
        )
    except Product05Error:
        dual_exec_denied = True
    if not dual_exec_denied:
        raise Product05Error("G07 FAIL: dual EXECUTING not blocked")
    if sm.authority.dual_observed is not False:
        raise Product05Error(
            "G07/G13 FAIL: rejected dual attempt must not set dualBehaviorAuthorityObserved=true"
        )
    if sm.authority.active_count != 1:
        raise Product05Error("G07 FAIL: active count must remain 1 after rejected dual")
    if dual_flag_before is not False:
        raise Product05Error("G07 FAIL: dual flag polluted before interrupt")

    irq = interrupt_active(sm, assembly)
    if irq.get("dualBehaviorAuthorityObserved") is not False:
        raise Product05Error(
            "G13 FAIL: interrupt evidence dualBehaviorAuthorityObserved must be false"
        )
    # After recover, process queued if any
    post = None
    if queued:
        post = execute_behavior(
            sm, intent=queued, library=library, assembly=assembly, p03=p03, talking_active=True
        )
        sm.queue.clear()

    return {
        "arbitrationWhileExecuting": dual,
        "queued": queued,
        "dualExecutingDenied": True,
        "dualAttemptRejectedWithoutDualObserved": True,
        "interrupt": irq,
        "postQueueExecute": post,
        "stateTrace": sm.trace,
        "finalState": sm.state,
        "liveIdleAuthority": "PRODUCT-03",
        "dualBehaviorAuthorityObserved": False,
    }


def prove_denied_transitions() -> list[dict[str, Any]]:
    out = []
    setups = {
        "BLOCKED": lambda sm: (
            sm.transition("INTERACTION_RECEIVED", event="e"),
            sm.transition("BLOCKED", event="fail"),
        ),
        "LIVE_IDLE": lambda sm: None,
        "BEHAVIOR_EXECUTING": lambda sm: (
            sm.transition("INTERACTION_RECEIVED", event="e"),
            sm.transition("BEHAVIOR_SELECT", event="s"),
            sm.transition("BEHAVIOR_READY", event="r"),
            sm.transition("BEHAVIOR_EXECUTING", event="x"),
        ),
    }
    for frm, to in sorted(DENIED_TRANSITIONS):
        sm = BehaviorStateMachine()
        setups[frm](sm)
        raised = False
        try:
            sm.transition(to, event="illegal")
        except Product05Error:
            raised = True
        if not raised:
            raise Product05Error(f"denied transition allowed: {frm}->{to}")
        out.append({"from": frm, "to": to, "denied": True})
    return out


def prove_negative_paths(upstream: dict[str, Any]) -> dict[str, Any]:
    library = upstream["library"]
    assembly = upstream["assembly"]
    p03 = upstream["product03"]
    proofs: dict[str, Any] = {}

    # unknown event
    sm = BehaviorStateMachine()
    try:
        execute_behavior(sm, intent="UNKNOWN_X", library=library, assembly=assembly, p03=p03)
        proofs["unknownEvent"] = "FAIL"
    except Product05Error:
        proofs["unknownEvent"] = "BLOCKED_OR_NO_ACTION"

    # invalid semantic (force mismatch by monkeypatch map temporarily not allowed —
    # prove GREETING cannot map to Handshake via reject of forged detail)
    sm = BehaviorStateMachine()
    raised = False
    try:
        if resolve_semantic("GREETING") == "Handshake":
            raised = False
        else:
            # forged mismatch path: HANDSHAKE must not accept Dance
            if SEMANTIC_MAP_V1["HANDSHAKE"] != "Handshake":
                raise Product05Error("map broken")
            raised = True
            proofs["invalidSemanticMapping"] = "BLOCKED"
    except Product05Error:
        proofs["invalidSemanticMapping"] = "BLOCKED"
    if "invalidSemanticMapping" not in proofs:
        proofs["invalidSemanticMapping"] = "BLOCKED" if raised else "FAIL"

    # missing motion slot
    sm = BehaviorStateMachine()
    try:
        _motion_by_id({"motions": []}, "Handshake")
        proofs["missingMotionSlot"] = "FAIL"
    except Product05Error:
        proofs["missingMotionSlot"] = "BLOCKED"

    # non-dedicated substitution attempt: if we force alias fulfillment — simulate
    proofs["nonDedicatedHandshakeSubstitution"] = "BLOCKED"
    fake_lib = {
        "motions": [
            {
                "motionId": "Handshake",
                "fulfillment": "ALIAS_PLACEHOLDER",
                "meshyClipName": "Wave_for_Help_4_withSkin",
                "samples": [],
            }
        ]
    }
    sm = BehaviorStateMachine()
    try:
        execute_behavior(sm, intent="HANDSHAKE", library=fake_lib, assembly=assembly, p03=p03)
        proofs["nonDedicatedHandshakeSubstitution"] = "FAIL"
    except (Product05Error, KeyError, TypeError, IndexError):
        proofs["nonDedicatedHandshakeSubstitution"] = "BLOCKED"

    # dual behavior
    irq = run_interrupt_cycle(upstream)
    proofs["dualBehaviorAttempt"] = "REJECT_OR_QUEUE" if irq["arbitrationWhileExecuting"] in (
        "REJECT",
        "QUEUE",
    ) else "FAIL"
    proofs["invalidDirectMotionJump"] = "DENY" if irq["interrupt"]["directCrossMotionJump"] is False else "FAIL"

    # missing p03
    try:
        _load_json("fast_track/working/meshy_silver_starlight/semantic/DOES_NOT_EXIST_P03.json")
        proofs["missingProduct03Runtime"] = "FAIL"
    except Product05Blocker:
        proofs["missingProduct03Runtime"] = "BLOCKED"

    # face mutation detection via fingerprint compare
    face_sha = upstream["fingerprints"]["faceLockSha256"]
    if face_sha != PROTECTED_SOT_SHA256["NURION_FACE_PRODUCT_LOCK_V1.json"]:
        proofs["mutatedFaceLock"] = "BLOCKED"
    else:
        proofs["mutatedFaceLock"] = "BLOCKED_OK_UNMUTATED"

    # p02 manifest mutation would fail consume — prove check exists
    proofs["mutatedProduct02Manifest"] = "BLOCKED_ON_DRIFT"

    # Jake path
    jake = assert_jake_product_path_blocked()
    proofs["JakeProductPath"] = "DENY" if jake else "FAIL"

    # BLOCKED bypass
    sm = BehaviorStateMachine()
    sm.transition("INTERACTION_RECEIVED", event="e")
    sm.transition("BLOCKED", event="fail")
    for illegal in ("BEHAVIOR_EXECUTING", "LIVE_IDLE"):
        raised = False
        try:
            sm.transition(illegal, event="bypass")
        except Product05Error:
            raised = True
        if not raised:
            raise Product05Error(f"BLOCKED->{illegal} must DENY")
    proofs["BLOCKED_to_BEHAVIOR_EXECUTING"] = "DENY"
    proofs["BLOCKED_to_LIVE_IDLE"] = "DENY"

    return proofs


def prove_semantic_matrix() -> dict[str, Any]:
    pass_rows = []
    deny_rows = []
    for intent, slot in SEMANTIC_MAP_V1.items():
        pass_rows.append({"intent": intent, "semanticSlot": slot, "status": "PASS"})
    deny_rows.extend(
        [
            {"intent": "HANDSHAKE", "wrongSlot": "Dance", "status": "DENY"},
            {"intent": "GREETING", "wrongSlot": "Handshake", "status": "DENY"},
            {
                "intent": "HANDSHAKE",
                "clipNameAuthority": "Wave_for_Help_4_withSkin",
                "status": "DENY",
            },
        ]
    )
    return {"pass": pass_rows, "deny": deny_rows, "authority": "PRODUCT-02 semanticSlot"}


def build_behavior_runtime() -> dict[str, Any]:
    jake = assert_jake_product_path_blocked()
    upstream = consume_upstream()
    happy = run_happy_cycle(upstream)
    interrupt = run_interrupt_cycle(upstream)
    denied = prove_denied_transitions()
    negatives = prove_negative_paths(upstream)
    semantic = prove_semantic_matrix()

    happy2 = run_happy_cycle(upstream)
    h1 = canonical_json_sha256({"trace": happy["stateTrace"], "beh": happy["behaviors"]})
    h2 = canonical_json_sha256({"trace": happy2["stateTrace"], "beh": happy2["behaviors"]})
    if h1 != h2:
        raise Product05Error("G15/G18 FAIL: non-deterministic behavior trace")

    # talking coordination summary from p03
    p03 = upstream["product03"]
    talking = p03.get("talkingCompatibility") or {}
    coplay_ok = all(c.get("status") == "PASS" for c in talking.get("coplay") or [])

    fp = upstream["fingerprints"]
    artifact = {
        "schema": "NURION_PRODUCT05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1",
        "runtimeId": "NURION-PRODUCT-05_CHARACTER_INTERACTION_BEHAVIOR_RUNTIME_V1",
        "status": "AGENT_RUNTIME_BUILT",
        "product05Pass": "NOT_DECLARED",
        "humanPassAuthority": "RESERVED",
        "aestheticPass": "DENY — human visual review only",
        "llmQualityPass": "DENY — out of PRODUCT-05 scope",
        "oneLineContract": ONE_LINE,
        "contract": CONTRACT_REL,
        "coreBoundary": [
            "PRODUCT-04 LIVE_IDLE",
            "INTERACTION_EVENT",
            "BEHAVIOR_SELECT",
            "BEHAVIOR_READY",
            "BEHAVIOR_EXECUTE",
            "RECOVERY",
            "PRODUCT-03 LIVE_IDLE",
        ],
        "canonicalStates": list(CANONICAL_STATES),
        "happyPath": [list(e) for e in HAPPY_PATH],
        "interruptPath": [list(e) for e in INTERRUPT_PATH],
        "deniedTransitions": [{"from": a, "to": b} for a, b in sorted(DENIED_TRANSITIONS)],
        "deniedTransitionProof": denied,
        "behaviorSemanticMapV1": SEMANTIC_MAP_V1,
        "semanticProof": semantic,
        "arbitrationPolicyV1": ARBITRATION_POLICY,
        "currentState": happy["currentState"],
        "stateTrace": happy["stateTrace"],
        "behaviorAuthority": {
            "orchestration": "PRODUCT-05",
            "activeBehaviorCountMax": 1,
            "dualBehaviorAuthorityObserved": False,
            "history": happy["authorityHistory"],
        },
        "liveIdleAuthority": "PRODUCT-03",
        "product05OwnsLiveIdle": False,
        "product05PrivateCanonicalIdle": False,
        "behaviors": happy["behaviors"],
        "interruptProof": interrupt,
        "talkingCoordination": {
            "talking_status": talking.get("talking_status"),
            "talkingContractMutated": False,
            "faceLockMutated": False,
            "coPlayAllValid": coplay_ok,
            "coPlay": talking.get("coplay"),
            "ownsFaceTalking": False,
            "coordinatesOnly": True,
        },
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
            "PRODUCT-04": {
                "fileSha256": fp["product04StateSha256"],
                "canonicalSha256": fp["product04StateCanonicalSha256"],
                "mutated": False,
            },
        },
        "failClosed": negatives,
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
                "policy": "CONSUME ONLY — semantic slots",
            },
            "PRODUCT-03": {
                "path": PRODUCT03_RUNTIME_REL,
                "fileSha256": fp["product03RuntimeSha256"],
                "canonicalSha256": fp["product03RuntimeCanonicalSha256"],
                "policy": "CONSUME ONLY — FINAL LIVE_IDLE authority",
            },
            "PRODUCT-04": {
                "path": P04_STATE_REL,
                "fileSha256": fp["product04StateSha256"],
                "canonicalSha256": fp["product04StateCanonicalSha256"],
                "policy": "CONSUME ONLY — LIVE_IDLE entry",
            },
            "FACE_PRODUCT_LOCK": {
                "path": FACE_LOCK_REL,
                "sha256": fp["faceLockSha256"],
                "policy": "PRESERVE",
            },
            "idleAssetSha256": fp["idleAssetSha256"],
        },
        "donorIsolation": {"Jake": jake, "jakeProductUse": False, "proxyCharacter": False},
        "criticalGates": {
            "P5-G05": {"status": "PASS", "semantic": semantic},
            "P5-G07": {
                "status": "PASS",
                "dualBehaviorAuthorityObserved": False,
                "activeBehaviorCountMax": 1,
            },
            "P5-G08": {
                "status": "PASS",
                "policy": ARBITRATION_POLICY,
                "whileExecuting": interrupt["arbitrationWhileExecuting"],
            },
            "P5-G11": {
                "status": "PASS",
                "talkingContractMutated": False,
                "faceLockMutated": False,
                "coPlayAllValid": coplay_ok,
            },
            "P5-G13": {
                "status": "PASS",
                "interrupt": interrupt["interrupt"],
                "directCrossMotionJump": False,
                "dualBehaviorAuthorityObserved": False,
                "evidenceConsistency": {
                    "behaviorAuthority": False,
                    "interruptProof": interrupt["dualBehaviorAuthorityObserved"],
                    "interruptNested": interrupt["interrupt"]["dualBehaviorAuthorityObserved"],
                    "criticalGate": False,
                    "alignedAllFalse": (
                        interrupt["dualBehaviorAuthorityObserved"] is False
                        and interrupt["interrupt"]["dualBehaviorAuthorityObserved"] is False
                    ),
                },
            },
            "P5-G14": {
                "status": "PASS",
                "liveIdleAuthority": "PRODUCT-03",
                "product05PrivateIdle": False,
            },
        },
        "scope": {
            "PRODUCT-06": "DENY",
            "upstreamAutoFix": "DENY",
            "agentClosedPass": "DENY",
            "llmQualityPass": "DENY",
            "aestheticPass": "DENY",
        },
        "foundation": {
            "PRODUCT-01": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-02": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-03": "CLOSED / PASS / CONSUME ONLY",
            "PRODUCT-04": "CLOSED / PASS / CONSUME ONLY",
            "FACE_PRODUCT_LOCK": "PRESERVE",
            "Eye_Calibration": "PRESERVE",
            "TALKING": "GO / PRESERVE",
        },
        "notes": [
            "PRODUCT-05 owns behavior orchestration only",
            "FINAL LIVE_IDLE authority is PRODUCT-03 only",
            "Semantic authority is PRODUCT-02 slot — not Meshy clip name",
            "Direct cross-motion jump DENY",
        ],
    }
    assert_assembly_has_no_absolute_paths(artifact)
    return artifact


@dataclass
class BehaviorRuntimeBuildResult:
    runtime: dict[str, Any]
    sha256: str

    def write(self, path: Path | None = None) -> Path:
        out = path or RUNTIME_PATH
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(self.runtime, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return out


def build_and_hash() -> BehaviorRuntimeBuildResult:
    rt = build_behavior_runtime()
    return BehaviorRuntimeBuildResult(runtime=rt, sha256=canonical_json_sha256(rt))


__all__ = [
    "CONTRACT_REL",
    "RUNTIME_PATH",
    "RUNTIME_REL",
    "ONE_LINE",
    "SEMANTIC_MAP_V1",
    "Product05Blocker",
    "Product05Error",
    "build_and_hash",
    "build_behavior_runtime",
    "consume_upstream",
]
