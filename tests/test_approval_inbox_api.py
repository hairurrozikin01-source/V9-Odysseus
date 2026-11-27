import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from approval_inbox_api import ApprovalInboxWSGI
from persistent_transaction_service import PersistentTransactionReviewService
from transaction_repository import PersistentTransactionRepository


class ApprovalInboxAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        repository = PersistentTransactionRepository(Path(self.temp.name) / "api.sqlite3")
        self.service = PersistentTransactionReviewService(repository)
        self.app = ApprovalInboxWSGI(self.service)
        self.now = datetime.now(timezone.utc)
        self.proposal = self.service.create(
            proposal_id="api-proposal-1",
            details={"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15",
                     "account_number": "must-not-leak"},
            data_ok=True, risk_ok=True, audit_ok=True, now=self.now,
        )

    def tearDown(self):
        self.temp.cleanup()

    def request(self, path, *, user="owner", role="owner", authenticated=True,
                method="GET", query="", payload=None, csrf=True):
        body = b"" if payload is None else json.dumps(payload).encode("utf-8")
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "REMOTE_USER": user,
            "v9.authenticated": authenticated,
            "v9.role": role,
            "v9.csrf_valid": csrf,
            "CONTENT_LENGTH": str(len(body)) if method == "POST" else "",
            "CONTENT_TYPE": "application/json",
            "wsgi.input": io.BytesIO(body),
        }
        captured = {}
        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)
        body_out = b"".join(self.app(environ, start_response))
        return captured, json.loads(body_out.decode("utf-8"))

    def test_requires_authenticated_upstream_identity(self):
        response, payload = self.request("/api/v1/proposals", user=None, authenticated=False)
        self.assertTrue(response["status"].startswith("401"))
        self.assertEqual(payload["error"], "AUTHENTICATION_REQUIRED")

    def test_viewer_can_read_but_cannot_decide(self):
        response, _ = self.request("/api/v1/proposals", role="viewer")
        self.assertTrue(response["status"].startswith("200"))
        response, payload = self.request(
            "/api/v1/proposals/api-proposal-1/decision", method="POST",
            role="viewer", payload={"action": "APPROVE", "proposal_hash": self.proposal["proposal_hash"]},
        )
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(payload["error"], "OWNER_APPROVAL_REQUIRED")

    def test_status_always_reports_execution_blocks(self):
        response, payload = self.request("/api/v1/transaction-control/status")
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(payload["mode"], "MANUAL_APPROVAL")
        self.assertFalse(payload["execution_available"])
        self.assertFalse(payload["orders_enabled"])
        self.assertIn("EXECUTION_NOT_IMPLEMENTED", payload["hard_blocks"])
        self.assertIn("LIVE_TRADING_DISABLED", payload["hard_blocks"])

    def test_proposal_list_hides_account_identifiers(self):
        response, payload = self.request("/api/v1/proposals")
        self.assertTrue(response["status"].startswith("200"))
        details = payload["items"][0]["details"]
        self.assertEqual(details["symbol"], "XAUUSD")
        self.assertNotIn("account_number", details)

    def test_proposal_detail_returns_exact_snapshot_hash(self):
        response, payload = self.request("/api/v1/proposals/api-proposal-1")
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(payload["proposal_id"], "api-proposal-1")
        self.assertEqual(payload["proposal_hash"], self.proposal["proposal_hash"])

    def test_owner_can_record_exact_proposal_decision_only(self):
        response, payload = self.request(
            "/api/v1/proposals/api-proposal-1/decision", method="POST",
            payload={"action": "APPROVE", "proposal_hash": self.proposal["proposal_hash"]},
        )
        self.assertTrue(response["status"].startswith("200"))
        self.assertTrue(payload["decision_recorded"])
        self.assertEqual(payload["proposal"]["status"], "APPROVED")
        self.assertFalse(payload["orders_enabled"])
        self.assertFalse(payload["execution_enabled"])

    def test_decision_requires_csrf_validation(self):
        response, payload = self.request(
            "/api/v1/proposals/api-proposal-1/decision", method="POST", csrf=False,
            payload={"action": "APPROVE", "proposal_hash": self.proposal["proposal_hash"]},
        )
        self.assertTrue(response["status"].startswith("403"))
        self.assertEqual(payload["error"], "CSRF_VALIDATION_REQUIRED")

    def test_stale_hash_is_blocked(self):
        response, payload = self.request(
            "/api/v1/proposals/api-proposal-1/decision", method="POST",
            payload={"action": "APPROVE", "proposal_hash": "0" * 64},
        )
        self.assertTrue(response["status"].startswith("422"))
        self.assertEqual(payload["error"], "PROPOSAL_CHANGED")
        self.assertEqual(payload["proposal"]["status"], "BLOCKED")

    def test_unknown_route_and_unsupported_method_are_rejected(self):
        response, _ = self.request("/api/v1/orders")
        self.assertTrue(response["status"].startswith("404"))
        response, payload = self.request("/api/v1/proposals", method="DELETE")
        self.assertTrue(response["status"].startswith("405"))
        self.assertEqual(payload["error"], "METHOD_NOT_ALLOWED")

    def test_invalid_status_filter_is_rejected(self):
        response, payload = self.request("/api/v1/proposals", query="status=ANY")
        self.assertTrue(response["status"].startswith("400"))


if __name__ == "__main__":
    unittest.main()
