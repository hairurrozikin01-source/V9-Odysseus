"""Append-only, hash-chained audit journal for transaction review events.

This local journal records proposal decisions only. It has no broker or
execution integration and must be stored outside the public repository when
used with real account-related information.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

GENESIS_HASH = "0" * 64


class AuditJournalError(ValueError):
    """Raised when an audit event is invalid or the journal is inconsistent."""


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _event_hash(previous_hash: str, event: Mapping[str, Any]) -> str:
    return hashlib.sha256(previous_hash.encode("ascii") + b"\n" + _canonical(event)).hexdigest()


class AuditJournal:
    """Append review events and verify the journal's hash chain."""

    def __init__(self, path: str | os.PathLike[str]):
        self.path = Path(path)

    def append(self, event: Mapping[str, Any], *, recorded_at: datetime | None = None) -> dict[str, Any]:
        if not isinstance(event, Mapping) or not event:
            raise AuditJournalError("Event audit wajib berupa mapping yang tidak kosong.")
        if any(key in event for key in ("password", "otp", "api_secret", "broker_secret")):
            raise AuditJournalError("Event mengandung field rahasia yang dilarang.")

        timestamp = recorded_at or datetime.now(timezone.utc)
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise AuditJournalError("Waktu audit harus memiliki zona waktu.")

        self.path.parent.mkdir(parents=True, exist_ok=True)
        verified = self.verify()
        if not verified["valid"]:
            raise AuditJournalError("Jurnal audit tidak valid; append dihentikan.")

        envelope = {
            "sequence": verified["count"] + 1,
            "recorded_at": timestamp.astimezone(timezone.utc).isoformat(),
            "previous_hash": verified["last_hash"],
            "event": dict(event),
        }
        envelope["event_hash"] = _event_hash(envelope["previous_hash"], envelope)
        line = _canonical(envelope) + b"\n"

        with self.path.open("ab") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
        return envelope

    def verify(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"valid": True, "count": 0, "last_hash": GENESIS_HASH}
        previous = GENESIS_HASH
        count = 0
        try:
            with self.path.open("rb") as handle:
                for raw_line in handle:
                    if not raw_line.strip():
                        continue
                    item = json.loads(raw_line.decode("utf-8"))
                    supplied_hash = item.pop("event_hash")
                    if item.get("sequence") != count + 1:
                        raise AuditJournalError("Urutan event tidak konsisten.")
                    if item.get("previous_hash") != previous:
                        raise AuditJournalError("Rantai hash terputus.")
                    calculated = _event_hash(previous, item)
                    if supplied_hash != calculated:
                        raise AuditJournalError("Hash event tidak cocok.")
                    previous = supplied_hash
                    count += 1
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise AuditJournalError("Format jurnal audit rusak atau tidak valid.") from exc
        return {"valid": True, "count": count, "last_hash": previous}
