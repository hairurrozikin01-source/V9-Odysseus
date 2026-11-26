import unittest
from datetime import datetime, timedelta, timezone

from transaction_control import (
    ProposalError,
    create_proposal,
    decide_proposal,
    expire_proposal,
)


class TransactionControlTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 26, 12, 0, tzinfo=timezone.utc)
        self.details = {"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15"}

    def proposal(self, **overrides):
        args = {
            "proposal_id": "v9-test-001",
            "details": self.details,
            "data_ok": True,
            "risk_ok": True,
            "audit_ok": True,
            "now": self.now,
        }
        args.update(overrides)
        return create_proposal(**args)

    def test_all_gates_pass_creates_pending_proposal(self):
        proposal = self.proposal()
        self.assertEqual(proposal["status"], "PROPOSAL_PENDING")
        self.assertFalse(proposal["orders_enabled"])
        self.assertFalse(proposal["execution_enabled"])

    def test_any_failed_gate_blocks_proposal(self):
        proposal = self.proposal(risk_ok=False)
        self.assertEqual(proposal["status"], "BLOCKED")
        with self.assertRaises(ProposalError):
            decide_proposal(
                proposal, action="APPROVE", expected_hash=proposal["proposal_hash"],
                actor="owner", now=self.now,
            )

    def test_approval_is_bound_to_exact_hash_and_never_enables_orders(self):
        proposal = self.proposal()
        result = decide_proposal(
            proposal, action="APPROVE", expected_hash=proposal["proposal_hash"],
            actor="owner", now=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result["status"], "APPROVED")
        self.assertFalse(result["orders_enabled"])
        self.assertFalse(result["execution_enabled"])

    def test_rejection_is_recorded(self):
        proposal = self.proposal()
        result = decide_proposal(
            proposal, action="REJECT", expected_hash=proposal["proposal_hash"],
            actor="owner", now=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result["status"], "REJECTED")

    def test_changed_proposal_is_blocked(self):
        proposal = self.proposal()
        proposal["details"]["side"] = "SELL"
        result = decide_proposal(
            proposal, action="APPROVE", expected_hash=proposal["proposal_hash"],
            actor="owner", now=self.now + timedelta(seconds=1),
        )
        self.assertEqual(result["status"], "BLOCKED")
        self.assertEqual(result["decision"]["reason"], "PROPOSAL_CHANGED")

    def test_expired_proposal_cannot_be_approved(self):
        proposal = self.proposal(ttl_seconds=10)
        result = decide_proposal(
            proposal, action="APPROVE", expected_hash=proposal["proposal_hash"],
            actor="owner", now=self.now + timedelta(seconds=10),
        )
        self.assertEqual(result["status"], "EXPIRED")

    def test_expire_helper_only_expires_pending(self):
        proposal = self.proposal()
        expired = expire_proposal(proposal, now=self.now + timedelta(minutes=6))
        self.assertEqual(expired["status"], "EXPIRED")
        approved = dict(proposal, status="APPROVED")
        self.assertEqual(expire_proposal(approved, now=self.now + timedelta(minutes=6))["status"], "APPROVED")

    def test_naive_datetime_is_rejected(self):
        with self.assertRaises(ProposalError):
            self.proposal(now=datetime(2026, 11, 26, 12, 0))

    def test_invalid_action_is_rejected(self):
        proposal = self.proposal()
        with self.assertRaises(ProposalError):
            decide_proposal(
                proposal, action="EXECUTE", expected_hash=proposal["proposal_hash"],
                actor="owner", now=self.now,
            )


if __name__ == "__main__":
    unittest.main()
