"""NURION_CHANGE_CONTROL_GATE_V1 — Human Spec Gate enforcement.

Agent implementation is denied unless:
  1) humanSpecGate.status == APPROVED
  2) approvedSpecDigest == SHA256(current SPEC bytes)
  3) track.status == OPEN_PROTOTYPE
  4) implementationAuthority == GRANTED

Spec PASS ≠ technical PASS ≠ Engine V2 OPEN.
Human Final Gate is a separate authority (not granted here).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Union

SCHEMA_ID = "NURION_CHANGE_CONTROL_GATE_V1"

OPEN_PROTOTYPE_STATUSES = frozenset({"OPEN_PROTOTYPE", "OPEN / PROTOTYPE"})
APPROVED = "APPROVED"
GRANTED = "GRANTED"

PathLike = Union[str, Path]


class ChangeControlGateError(PermissionError):
    """Raised when Human Spec Gate blocks implementation."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: PathLike) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def load_json(path: PathLike) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _gate(track: Mapping[str, Any]) -> Mapping[str, Any]:
    gate = track.get("humanSpecGate")
    if not isinstance(gate, Mapping):
        raise ChangeControlGateError(
            "implementation denied: humanSpecGate missing from track"
        )
    return gate


def require_human_spec_gate(
    track: Mapping[str, Any],
    *,
    expected_change_request: str,
    spec_path: PathLike | None = None,
    spec_bytes: bytes | None = None,
) -> str:
    """Enforce Human Spec Gate before any CR implementation work.

    Returns the approved SPEC SHA256 on success.
    """
    cr = track.get("changeRequest") or track.get("changeRequestId")
    if cr != expected_change_request:
        raise ChangeControlGateError(
            f"implementation denied: changeRequest mismatch "
            f"(expected {expected_change_request!r}, got {cr!r})"
        )

    if track.get("implementationAuthority") != GRANTED:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            "implementationAuthority is not GRANTED"
        )

    status = str(track.get("status") or "")
    if status not in OPEN_PROTOTYPE_STATUSES:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: CR not OPEN "
            f"(status={status!r})"
        )

    gate = _gate(track)
    if gate.get("required") is not True:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            "humanSpecGate.required must be true"
        )
    if gate.get("status") != APPROVED:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            "Human Spec Gate not approved"
        )

    approved = gate.get("approvedSpecDigest")
    if not isinstance(approved, str) or not approved:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            "approvedSpecDigest missing"
        )

    if spec_bytes is None:
        if spec_path is None:
            raise ChangeControlGateError(
                f"{expected_change_request} implementation denied: "
                "spec_path or spec_bytes required"
            )
        spec_bytes = Path(spec_path).read_bytes()

    digest = sha256_bytes(spec_bytes)
    if digest != approved:
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            f"SPEC_DIGEST_MISMATCH → IMPLEMENTATION DENIED "
            f"(got={digest}, approved={approved})"
        )

    if track.get("engineV2") not in (None, "NOT_OPEN", "NOT OPEN"):
        # Soft check: engine must remain closed during CR prototype work.
        # Explicit NOT_OPEN expected; other values are rejected.
        raise ChangeControlGateError(
            f"{expected_change_request} implementation denied: "
            "engineV2 must remain NOT_OPEN during CR prototype"
        )

    return digest


def require_no_upstream_mutation(track: Mapping[str, Any]) -> None:
    upstream = track.get("upstream")
    if not isinstance(upstream, Mapping):
        return
    reopen = str(upstream.get("REOPEN", "DENY")).upper()
    if reopen not in ("DENY", "REOPEN DENY", "REOPEN=DENY"):
        raise ChangeControlGateError(
            f"implementation denied: upstream REOPEN must be DENY (got {upstream.get('REOPEN')!r})"
        )
    for key, value in upstream.items():
        if key.upper() == "REOPEN":
            continue
        text = str(value).upper()
        if "CONSUME" not in text:
            raise ChangeControlGateError(
                f"implementation denied: upstream {key} must be CONSUME_ONLY "
                f"(got {value!r})"
            )
