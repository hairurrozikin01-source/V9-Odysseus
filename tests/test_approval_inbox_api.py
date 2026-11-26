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
        self.now = datetime(2026, 11, 26, 17, 0, tzinfo=timezone.utc)
        self.service.create(
            proposal_id="api-proposal-1",
            details={"symbol": "XAUUSD", "side": "BUY", "timeframe": "M15",
                     "account_number": "must-not-leak"},
            data_ok=True, risk_ok=True, audit_ok=True, now=self.now,
        )

    def tearDown(self):
        self.temp.cleanup()

    def request(self, path, *, user="owner", method="GET", query=""):
        environ = {
            "REQUEST_METHOD": method,
            "PATH_INFO": path,
            "QUERY_STRING": query,
            "REMOTE_USER": user,
        }
        captured = {}
        def start_response(status, headers):
            captured["status"] = status
            captured["headers"] = dict(headers)
        body = b"".join(self.app(environ, start_response))
        return captured, json.loads(body.decode("utf-8"))

    def test_requires_authenticated_upstream_identity(self):
        response, payload = self.request("/api/v1/proposals", user=None)
        self.assertTrue(response["status"].startswith("401"))
        self.assertEqual(payload["error"], "UNAUTHENTICATED")

    def test_status_is_manual_and_never_enables_execution(self):
        response, payload = self.request("/api/v1/transaction-control/status")
        self.assertTrue(response["status"].startswith("200"))
        self.assertEqual(payload["mode"], "MANUAL_APPROVAL")
        self.assertFalse(payload["execution_available"])
        self.assertFalse(payload["orders_enabled"])

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
        self.assertEqual(len(payload["proposal_hash"]), 64)

    def test_unknown_route_and_write_method_are_rejected(self):
        response, payload = self.request("/api/v1/orders")
        self.assertTrue(response["status"].startswith("404"))
        response, payload = self.request("/api/v1/proposals", method="POST")
        self.assertTrue(response["status"].startswith("405"))

    def test_invalid_status_filter_is_rejected(self):
        response, payload = self.request("/api/v1/proposals", query="status=ANY")
        self.assertTrue(response["status"].startswith("400"))


if __name__ == "__main__":
    unittest.main()
