import unittest

from transaction_authorization import (
    AuthorizationError,
    authorize_action,
    redact_audit_payload,
)


class TransactionAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.owner = {
            "authenticated": True,
            "actor_id": "owner-001",
            "role": "owner",
        }
        self.viewer = {
            "authenticated": True,
            "actor_id": "viewer-001",
            "role": "viewer",
        }

    def test_owner_can_view_and_record_manual_decision(self):
        self.assertEqual(authorize_action(self.owner, "VIEW_PROPOSALS"), "owner-001")
        self.assertEqual(authorize_action(self.owner, "APPROVE_PROPOSAL"), "owner-001")
        self.assertEqual(authorize_action(self.owner, "REJECT_PROPOSAL"), "owner-001")

    def test_viewer_is_read_only(self):
        self.assertEqual(authorize_action(self.viewer, "VIEW_AUDIT"), "viewer-001")
        with self.assertRaisesRegex(AuthorizationError, "OWNER_APPROVAL_REQUIRED"):
            authorize_action(self.viewer, "APPROVE_PROPOSAL")
        with self.assertRaisesRegex(AuthorizationError, "OWNER_APPROVAL_REQUIRED"):
            authorize_action(self.viewer, "REJECT_PROPOSAL")

    def test_missing_or_untrusted_principal_fails_closed(self):
        for principal in (None, {}, {"authenticated": False, "actor_id": "x", "role": "owner"}):
            with self.subTest(principal=principal):
                with self.assertRaises(AuthorizationError):
                    authorize_action(principal, "VIEW_DASHBOARD")

    def test_invalid_identity_or_role_fails_closed(self):
        cases = [
            {"authenticated": True, "actor_id": "", "role": "owner"},
            {"authenticated": True, "actor_id": "owner", "role": "admin"},
            {"authenticated": True, "actor_id": 123, "role": "owner"},
        ]
        for principal in cases:
            with self.subTest(principal=principal):
                with self.assertRaises(AuthorizationError):
                    authorize_action(principal, "VIEW_DASHBOARD")

    def test_unknown_or_execution_action_is_never_authorized(self):
        for action in ("EXECUTE_ORDER", "ENABLE_AUTOMATIC_EXECUTION", "UNKNOWN"):
            with self.subTest(action=action):
                with self.assertRaisesRegex(AuthorizationError, "ACTION_NOT_ALLOWED"):
                    authorize_action(self.owner, action)

    def test_sensitive_fields_are_redacted_recursively(self):
        payload = {
            "event": "LOGIN",
            "password": "do-not-store",
            "nested": {
                "api_key": "secret-key",
                "Authorization": "Bearer secret",
                "safe": "XAUUSD",
            },
            "items": [{"session_token": "secret-session"}],
        }
        cleaned = redact_audit_payload(payload)
        self.assertEqual(cleaned["password"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["Authorization"], "[REDACTED]")
        self.assertEqual(cleaned["nested"]["safe"], "XAUUSD")
        self.assertEqual(cleaned["items"][0]["session_token"], "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
