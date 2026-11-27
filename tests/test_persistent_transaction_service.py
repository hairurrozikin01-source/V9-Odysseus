import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from persistent_transaction_service import PersistentTransactionReviewService
from transaction_repository import PersistentTransactionRepository, RepositoryError


class PersistentTransactionReviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.database = Path(self.temp.name) / "v9.sqlite3"
        self.repository = PersistentTransactionRepository(self.database)
        self.service = PersistentTransactionReviewService(self.repository)
        self.now = datetime(2026, 11, 26, 16, 0, tzinfo=timezone.utc)
        self.details = {"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15"}

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        args = {
            "proposal_id": "inbox-001",
            "details": self.details,
            "data_ok": True,
            "risk_ok": True,
            "audit_ok": True,
            "now": self.now,
        }
        args.update(overrides)
        return self.service.create(**args)

    def test_service_persists_proposal_across_restart(self):
        proposal = self.create()
        restarted = PersistentTransactionReviewService(
            PersistentTransactionRepository(self.database)
        )
        self.assertEqual(
            restarted.get("inbox-001")["proposal_hash"], proposal["proposal_hash"]
        )
        self.assertEqual(restarted.verify_audit()["count"], 1)

    def test_service_decision_is_durable_and_audited(self):
        proposal = self.create()
        approved = self.service.decide(
            "inbox-001",
            action="APPROVE",
            expected_hash=proposal["proposal_hash"],
            actor="owner-session",
            now=self.now + timedelta(seconds=1),
        )
        restarted = PersistentTransactionReviewService(
            PersistentTransactionRepository(self.database)
        )
        saved = restarted.get("inbox-001")
        self.assertEqual(approved["status"], "APPROVED")
        self.assertEqual(saved["status"], "APPROVED")
        self.assertFalse(saved["orders_enabled"])
        self.assertFalse(saved["execution_enabled"])
        self.assertEqual(restarted.verify_audit()["count"], 2)

    def test_service_rejects_unknown_proposal(self):
        with self.assertRaises(RepositoryError):
            self.service.decide(
                "unknown",
                action="APPROVE",
                expected_hash="not-a-hash",
                actor="owner-session",
                now=self.now,
            )

    def test_service_expiry_is_persisted_once(self):
        self.create(ttl_seconds=5)
        first = self.service.expire("inbox-001", now=self.now + timedelta(seconds=5))
        second = self.service.expire("inbox-001", now=self.now + timedelta(seconds=6))
        self.assertEqual(first["status"], "EXPIRED")
        self.assertEqual(second["status"], "EXPIRED")
        self.assertEqual(self.service.verify_audit()["count"], 2)

    def test_service_exposes_audit_events(self):
        self.create()
        events = self.service.list_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["event"]["event_type"], "PROPOSAL_CREATED")
        self.assertTrue(self.service.verify_audit()["valid"])


if __name__ == "__main__":
    unittest.main()
