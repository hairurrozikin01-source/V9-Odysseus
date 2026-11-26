"""SQLite-backed persistent transaction review repository.

Proposal state and audit events are committed in the same SQLite transaction.
This repository is for local development/testing; production deployment still
requires authenticated API access, backups, filesystem controls, and review.
It never connects to a broker or submits orders.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

from transaction_control import create_proposal, decide_proposal, expire_proposal

GENESIS_HASH = "0" * 64


class RepositoryError(RuntimeError):
    """Raised when persistence or audit integrity checks fail."""


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _hash(previous_hash: str, record: Mapping[str, Any]) -> str:
    return hashlib.sha256(previous_hash.encode("ascii") + b"\n" + _json(record).encode("utf-8")).hexdigest()


class PersistentTransactionRepository:
    """Persist proposals and audit events with atomic SQLite transactions."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS proposals (
                    proposal_id TEXT PRIMARY KEY,
                    proposal_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    proposal_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS audit_events (
                    sequence INTEGER PRIMARY KEY,
                    recorded_at TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL UNIQUE
                );
                """
            )

    def _append_event(self, db: sqlite3.Connection, event: Mapping[str, Any], at: datetime) -> None:
        previous = db.execute(
            "SELECT sequence, event_hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        sequence = (previous["sequence"] + 1) if previous else 1
        previous_hash = previous["event_hash"] if previous else GENESIS_HASH
        record = {
            "sequence": sequence,
            "recorded_at": at.astimezone(timezone.utc).isoformat(),
            "previous_hash": previous_hash,
            "event": dict(event),
        }
        digest = _hash(previous_hash, record)
        db.execute(
            "INSERT INTO audit_events(sequence, recorded_at, previous_hash, event_json, event_hash) VALUES (?, ?, ?, ?, ?)",
            (sequence, record["recorded_at"], previous_hash, _json(record["event"]), digest),
        )

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
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "INSERT INTO proposals(proposal_id, proposal_hash, status, proposal_json, updated_at) VALUES (?, ?, ?, ?, ?)",
                (proposal_id, proposal["proposal_hash"], proposal["status"], _json(proposal), now.astimezone(timezone.utc).isoformat()),
            )
            self._append_event(db, {
                "event_type": "PROPOSAL_CREATED",
                "proposal_id": proposal_id,
                "proposal_hash": proposal["proposal_hash"],
                "status": proposal["status"],
                "gates": proposal["gates"],
            }, now)
            db.commit()
            return proposal
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, proposal_id: str) -> dict[str, Any] | None:
        with self._connect() as db:
            row = db.execute("SELECT proposal_json FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
        return json.loads(row["proposal_json"]) if row else None

    def decide(
        self,
        proposal_id: str,
        *,
        action: str,
        expected_hash: str,
        actor: str,
        now: datetime,
    ) -> dict[str, Any]:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT proposal_json FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
            if row is None:
                raise RepositoryError("Proposal tidak ditemukan.")
            current = json.loads(row["proposal_json"])
            updated = decide_proposal(
                current, action=action, expected_hash=expected_hash, actor=actor, now=now
            )
            db.execute(
                "UPDATE proposals SET proposal_hash = ?, status = ?, proposal_json = ?, updated_at = ? WHERE proposal_id = ?",
                (updated["proposal_hash"], updated["status"], _json(updated), now.astimezone(timezone.utc).isoformat(), proposal_id),
            )
            decision = updated.get("decision") or {}
            self._append_event(db, {
                "event_type": "PROPOSAL_DECISION",
                "proposal_id": proposal_id,
                "proposal_hash": updated["proposal_hash"],
                "status": updated["status"],
                "action": decision.get("action"),
                "actor": actor,
                "reason": decision.get("reason"),
            }, now)
            db.commit()
            return updated
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def expire(self, proposal_id: str, *, now: datetime) -> dict[str, Any]:
        db = self._connect()
        try:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT proposal_json FROM proposals WHERE proposal_id = ?", (proposal_id,)).fetchone()
            if row is None:
                raise RepositoryError("Proposal tidak ditemukan.")
            current = json.loads(row["proposal_json"])
            updated = expire_proposal(current, now=now)
            if updated != current:
                db.execute(
                    "UPDATE proposals SET status = ?, proposal_json = ?, updated_at = ? WHERE proposal_id = ?",
                    (updated["status"], _json(updated), now.astimezone(timezone.utc).isoformat(), proposal_id),
                )
                self._append_event(db, {
                    "event_type": "PROPOSAL_EXPIRED",
                    "proposal_id": proposal_id,
                    "proposal_hash": updated["proposal_hash"],
                    "status": updated["status"],
                    "reason": (updated.get("decision") or {}).get("reason"),
                }, now)
            db.commit()
            return updated
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def list_audit_events(self) -> list[dict[str, Any]]:
        with self._connect() as db:
            rows = db.execute(
                "SELECT sequence, recorded_at, previous_hash, event_json, event_hash FROM audit_events ORDER BY sequence"
            ).fetchall()
        return [{
            "sequence": row["sequence"],
            "recorded_at": row["recorded_at"],
            "previous_hash": row["previous_hash"],
            "event": json.loads(row["event_json"]),
            "event_hash": row["event_hash"],
        } for row in rows]

    def verify_audit(self) -> dict[str, Any]:
        events = self.list_audit_events()
        previous = GENESIS_HASH
        for expected_sequence, item in enumerate(events, start=1):
            record = {
                "sequence": item["sequence"],
                "recorded_at": item["recorded_at"],
                "previous_hash": item["previous_hash"],
                "event": item["event"],
            }
            if item["sequence"] != expected_sequence or item["previous_hash"] != previous:
                return {"valid": False, "count": expected_sequence - 1, "last_hash": previous}
            calculated = _hash(previous, record)
            if calculated != item["event_hash"]:
                return {"valid": False, "count": expected_sequence - 1, "last_hash": previous}
            previous = calculated
        return {"valid": True, "count": len(events), "last_hash": previous}
