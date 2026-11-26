"""Orchestrate V9 proposal decisions and their audit records.

This is a local, synchronous review service only. It does not persist proposal
state, expose an HTTP API, connect to a broker, or submit orders.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from transaction_audit import AuditJournal
from transaction_control import create_proposal, decide_proposal, expire_proposal


class TransactionReviewService:
    """Coordinate proposal lifecycle with mandatory audit-journal writes."""

    def __init__(self, journal: AuditJournal):
        self.journal = journal

    def create(
        self,
        *,
        proposal_id: str,
        details: Mapping[str, Any],
        data_ok: bool,
        risk_ok: bool,
        audit_ok: bool,
        now: datetime,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        proposal = create_proposal(
            proposal_id=proposal_id,
            details=details,
            data_ok=data_ok,
            risk_ok=risk_ok,
            audit_ok=audit_ok,
            now=now,
            ttl_seconds=ttl_seconds,
        )
        self.journal.append(
            {
                "event_type": "PROPOSAL_CREATED",
                "proposal_id": proposal["proposal_id"],
                "proposal_hash": proposal["proposal_hash"],
                "status": proposal["status"],
                "gates": proposal["gates"],
            },
            recorded_at=now,
        )
        return proposal

    def decide(
        self,
        proposal: Mapping[str, Any],
        *,
        action: str,
        expected_hash: str,
        actor: str,
        now: datetime,
    ) -> dict[str, Any]:
        result = decide_proposal(
            proposal,
            action=action,
            expected_hash=expected_hash,
            actor=actor,
            now=now,
        )
        decision = result.get("decision") or {}
        self.journal.append(
            {
                "event_type": "PROPOSAL_DECISION",
                "proposal_id": result.get("proposal_id"),
                "proposal_hash": result.get("proposal_hash"),
                "status": result.get("status"),
                "action": decision.get("action"),
                "actor": actor,
                "reason": decision.get("reason"),
            },
            recorded_at=now,
        )
        return result

    def expire(self, proposal: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
        result = expire_proposal(proposal, now=now)
        if result.get("status") == "EXPIRED" and proposal.get("status") == "PROPOSAL_PENDING":
            self.journal.append(
                {
                    "event_type": "PROPOSAL_EXPIRED",
                    "proposal_id": result.get("proposal_id"),
                    "proposal_hash": result.get("proposal_hash"),
                    "status": result.get("status"),
                    "reason": (result.get("decision") or {}).get("reason"),
                },
                recorded_at=now,
            )
        return result
