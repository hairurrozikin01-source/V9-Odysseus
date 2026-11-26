import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from transaction_audit import AuditJournal
from transaction_service import TransactionReviewService


class TransactionReviewServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.journal = AuditJournal(Path(self.temp.name) / "audit.jsonl")
        self.service = TransactionReviewService(self.journal)
        self.now = datetime(2026, 11, 26, 14, 0, tzinfo=timezone.utc)
        self.details = {"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15"}

    def tearDown(self):
        self.temp.cleanup()

    def create(self, **overrides):
        args = {
            "proposal_id": "proposal-001",
            "details": self.details,
            "data_ok": True,
            "risk_ok": True,
            "audit_ok": True,
            "now": self.now,
        }
        args.update(overrides)
        return self.service.create(**args)

    def test_creation_and_approval_are_both_audited(self):
        proposal = self.create()
        approved = self.service.decide(
            proposal,
            action="APPROVE",
            expected_hash=proposal["proposal_hash"],
            actor="human-reviewer",
            now=self.now + timedelta(seconds=2),
        )
        verified = self.journal.verify()
        self.assertEqual(verified["count"], 2)
        self.assertEqual(approved["status"], "APPROVED")
        self.assertFalse(approved["orders_enabled"])
        self.assertFalse(approved["execution_enabled"])

    def test_rejected_proposal_is_audited(self):
        proposal = self.create()
        rejected = self.service.decide(
            proposal,
            action="REJECT",
            expected_hash=proposal["proposal_hash"],
            actor="human-reviewer",
            now=self.now + timedelta(seconds=2),
        )
        self.assertEqual(rejected["status"], "REJECTED")
        self.assertEqual(self.journal.verify()["count"], 2)

    def test_blocked_creation_is_audited(self):
        proposal = self.create(risk_ok=False)
        self.assertEqual(proposal["status"], "BLOCKED")
        self.assertEqual(self.journal.verify()["count"], 1)

    def test_expiry_is_audited_once(self):
        proposal = self.create(ttl_seconds=5)
        expired = self.service.expire(proposal, now=self.now + timedelta(seconds=5))
        self.assertEqual(expired["status"], "EXPIRED")
        self.assertEqual(self.journal.verify()["count"], 2)
        self.service.expire(expired, now=self.now + timedelta(seconds=6))
        self.assertEqual(self.journal.verify()["count"], 2)

    def test_changed_proposal_block_is_audited(self):
        proposal = self.create()
        changed = dict(proposal)
        changed["details"] = dict(proposal["details"], side="SELL")
        result = self.service.decide(
            changed,
            action="APPROVE",
            expected_hash=proposal["proposal_hash"],
            actor="human-reviewer",
            now=self.now + timedelta(seconds=2),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(self.journal.verify()["count"], 2)


if __name__ == "__main__":
    unittest.main()
