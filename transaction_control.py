"""Fail-closed transaction proposal lifecycle for V9.

This module records review decisions only. It deliberately contains no broker
client, order-submission function, or automatic-execution capability.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Mapping


class ProposalError(ValueError):
    """Raised when a proposal transition is invalid."""


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ProposalError("Waktu harus memiliki zona waktu.")
    return value.astimezone(timezone.utc)


def _canonical_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def create_proposal(
    *,
    proposal_id: str,
    details: Mapping[str, Any],
    data_ok: bool,
    risk_ok: bool,
    audit_ok: bool,
    now: datetime,
    ttl_seconds: int = 300,
) -> dict[str, Any]:
    """Create a reviewable proposal; any failed gate creates BLOCKED state."""
    if not proposal_id.strip():
        raise ProposalError("proposal_id wajib diisi.")
    if not isinstance(details, Mapping) or not details:
        raise ProposalError("Detail proposal wajib berupa mapping yang tidak kosong.")
    if ttl_seconds <= 0:
        raise ProposalError("ttl_seconds harus lebih besar dari nol.")

    created = _utc(now)
    snapshot = dict(details)
    digest = _canonical_hash(snapshot)
    gates = {"data_ok": data_ok is True, "risk_ok": risk_ok is True, "audit_ok": audit_ok is True}
    passed = all(gates.values())

    return {
        "proposal_id": proposal_id,
        "proposal_version": 1,
        "proposal_hash": digest,
        "details": snapshot,
        "gates": gates,
        "status": "PROPOSAL_PENDING" if passed else "BLOCKED",
        "created_at": created.isoformat(),
        "expires_at": (created + timedelta(seconds=ttl_seconds)).isoformat(),
        "decision": None,
        "orders_enabled": False,
        "execution_enabled": False,
    }


def decide_proposal(
    proposal: Mapping[str, Any],
    *,
    action: str,
    expected_hash: str,
    actor: str,
    now: datetime,
) -> dict[str, Any]:
    """Approve/reject only the exact unchanged proposal before expiry."""
    result = dict(proposal)
    if result.get("status") != "PROPOSAL_PENDING":
        raise ProposalError("Hanya proposal berstatus PROPOSAL_PENDING yang dapat diputuskan.")
    if not actor.strip():
        raise ProposalError("Identitas pengambil keputusan wajib diisi.")
    if action not in {"APPROVE", "REJECT"}:
        raise ProposalError("Aksi harus APPROVE atau REJECT.")

    current_hash = _canonical_hash(result.get("details", {}))
    if current_hash != result.get("proposal_hash") or expected_hash != current_hash:
        result["status"] = "BLOCKED"
        result["decision"] = {"actor": actor, "action": "BLOCK", "reason": "PROPOSAL_CHANGED"}
        return result

    moment = _utc(now)
    expiry = datetime.fromisoformat(result["expires_at"])
    if moment >= _utc(expiry):
        result["status"] = "EXPIRED"
        result["decision"] = {"actor": actor, "action": "EXPIRE", "reason": "APPROVAL_WINDOW_ELAPSED"}
        return result

    result["status"] = "APPROVED" if action == "APPROVE" else "REJECTED"
    result["decision"] = {
        "actor": actor,
        "action": action,
        "decided_at": moment.isoformat(),
        "proposal_hash": current_hash,
    }
    # Approval is a review record only; it never authorizes order submission.
    result["orders_enabled"] = False
    result["execution_enabled"] = False
    return result


def expire_proposal(proposal: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    """Expire a pending proposal once its review window has elapsed."""
    result = dict(proposal)
    if result.get("status") != "PROPOSAL_PENDING":
        return result
    if _utc(now) >= _utc(datetime.fromisoformat(result["expires_at"])):
        result["status"] = "EXPIRED"
        result["decision"] = {"action": "EXPIRE", "reason": "APPROVAL_WINDOW_ELAPSED"}
    return result
