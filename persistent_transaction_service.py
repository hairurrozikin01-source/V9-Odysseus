"""Persistent approval-inbox service facade for V9.

This service delegates proposal lifecycle operations to the SQLite repository.
It is a local application-layer component only: no HTTP server, authentication,
broker connection, order submission, or automatic execution is provided.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from transaction_repository import PersistentTransactionRepository


class PersistentTransactionReviewService:
    """Application facade backed by durable proposal and audit storage."""

    def __init__(self, repository: PersistentTransactionRepository):
        self.repository = repository

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
        return self.repository.create(
            proposal_id=proposal_id,
            details=details,
            data_ok=data_ok,
            risk_ok=risk_ok,
            audit_ok=audit_ok,
            now=now,
            ttl_seconds=ttl_seconds,
        )

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        return self.repository.get(proposal_id)

    def decide(
        self,
        proposal_id: str,
        *,
        action: str,
        expected_hash: str,
        actor: str,
        now: datetime,
    ) -> dict[str, Any]:
        return self.repository.decide(
            proposal_id,
            action=action,
            expected_hash=expected_hash,
            actor=actor,
            now=now,
        )

    def expire(self, proposal_id: str, *, now: datetime) -> dict[str, Any]:
        return self.repository.expire(proposal_id, now=now)

    def list_audit_events(self) -> list[dict[str, Any]]:
        return self.repository.list_audit_events()

    def verify_audit(self) -> dict[str, Any]:
        return self.repository.verify_audit()
