import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from transaction_repository import PersistentTransactionRepository, RepositoryError


class PersistentTransactionRepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp.name) / "state" / "v9.sqlite3"
        self.repo = PersistentTransactionRepository(self.db_path)
        self.now = datetime(2026, 11, 26, 15, 0, tzinfo=timezone.utc)
        self.details = {"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15"}

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        args = {
            "proposal_id": "persistent-proposal-01",
            "details": self.details,
            "data_ok": True,
            "risk_ok": True,
            "audit_ok": True,
            "now": self.now,
        }
        args.update(overrides)
        return self.repo.create(**args)

    def test_proposal_survives_repository_restart(self):
        proposal = self.create()
        reopened = PersistentTransactionRepository(self.db_path)
        loaded = reopened.get(proposal["proposal_id"])
        self.assertEqual(loaded["proposal_hash"], proposal["proposal_hash"])
        self.assertEqual(loaded["status"], "PROPOSAL_PENDING")

    def test_creation_and_approval_are_atomic_audited_transitions(self):
        proposal = self.create()
        result = self.repo.decide(
            proposal["proposal_id"],
            action="APPROVE",
            expected_hash=proposal["proposal_hash"],
            actor="owner-session",
            now=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["execution_enabled"])
        self.assertEqual(self.repo.verify_audit()["count"], 2)

    def test_rejection_is_persisted(self):
        proposal = self.create()
        result = self.repo.decide(
            proposal["proposal_id"],
            action="REJECT",
            expected_hash=proposal["proposal_hash"],
            actor="owner-session",
            now=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(self.repo.get(proposal["proposal_id"])["status"], "REJECTED")

    def test_blocked_creation_is_persisted_and_audited(self):
        proposal = self.create(risk_ok=False)
        self.assertEqual(proposal["status"], "BLOCKED")
        self.assertEqual(self.repo.verify_audit()["count"], 1)

    def test_expiry_is_persisted_and_audited_once(self):
        proposal = self.create(ttl_seconds=5)
        expired = self.repo.expire(
            proposal["proposal_id"], now=self.now + timedelta(seconds=5)
        )
        self.assertEqual(expired["status"], "EXPIRED")
        self.repo.expire(proposal["proposal_id"], now=self.now + timedelta(seconds=6))
        self.assertEqual(self.repo.verify_audit()["count"], 2)

    def test_unknown_proposal_is_rejected(self):
        with self.assertRaises(RepositoryError):
            self.repo.decide(
                "missing",
                action="APPROVE",
                expected_hash="x",
                actor="owner-session",
                now=self.now,
            )

    def test_audit_hash_chain_verifies(self):
        self.create()
        self.assertTrue(self.repo.verify_audit()["valid"])
        events = self.repo.list_audit_events()
        self.assertEqual(events[0]["sequence"], 1)
        self.assertEqual(events[0]["previous_hash"], "0" * 64)

    def test_duplicate_proposal_id_does_not_overwrite_existing(self):
        first = self.create()
        with self.assertRaises(Exception):
            self.create(details={"symbol": "EURUSD", "side": "SELL"})
        saved = self.repo.get(first["proposal_id"])
        self.assertEqual(saved["proposal_hash"], first["proposal_hash"])
        self.assertEqual(self.repo.verify_audit()["count"], 1)


if __name__ == "__main__":
    unittest.main()
