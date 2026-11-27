"""Fail-closed authorization policy primitives for V9.

This module is NOT an authentication system. A trusted server-side identity
provider must establish the principal before these checks are called. Never
trust a role, user ID, or authenticated flag supplied by a browser request.
No broker or order-execution capability exists here.
"""
from __future__ import annotations

from typing import Any, Mapping


class AuthorizationError(PermissionError):
    """Raised when a requested action is not explicitly authorized."""


READ_ACTIONS = frozenset({"VIEW_DASHBOARD", "VIEW_PROPOSALS", "VIEW_AUDIT"})
DECISION_ACTIONS = frozenset({"APPROVE_PROPOSAL", "REJECT_PROPOSAL"})
ALLOWED_ACTIONS = READ_ACTIONS | DECISION_ACTIONS


def authorize_action(principal: Mapping[str, Any] | None, action: str) -> str:
    """Return the authenticated actor ID or fail closed.

    Only the owner role may record manual approval/rejection decisions.
    Viewer access is read-only. Unknown actions and malformed identities deny.
    """
    if not isinstance(principal, Mapping):
        raise AuthorizationError("AUTHENTICATION_REQUIRED")
    if principal.get("authenticated") is not True:
        raise AuthorizationError("AUTHENTICATION_REQUIRED")

    actor_id = principal.get("actor_id")
    role = principal.get("role")
    if not isinstance(actor_id, str) or not actor_id.strip():
        raise AuthorizationError("INVALID_PRINCIPAL")
    if role not in {"owner", "viewer"}:
        raise AuthorizationError("INVALID_ROLE")
    if action not in ALLOWED_ACTIONS:
        raise AuthorizationError("ACTION_NOT_ALLOWED")

    if action in DECISION_ACTIONS and role != "owner":
        raise AuthorizationError("OWNER_APPROVAL_REQUIRED")
    return actor_id.strip()


_SENSITIVE_KEY_PARTS = (
    "password", "passwd", "secret", "token", "api_key", "apikey",
    "authorization", "cookie", "session", "credential", "private_key",
)


def redact_audit_payload(value: Any) -> Any:
    """Recursively redact values stored under credential-like mapping keys.

    This is a defense-in-depth filter, not a substitute for data minimization.
    Never pass raw credentials or broker account secrets into audit events.
    """
    if isinstance(value, Mapping):
        cleaned = {}
        for key, item in value.items():
            key_text = str(key)
            normalized = key_text.lower().replace("-", "_").replace(" ", "_")
            if any(part in normalized for part in _SENSITIVE_KEY_PARTS):
                cleaned[key_text] = "[REDACTED]"
            else:
                cleaned[key_text] = redact_audit_payload(item)
        return cleaned
    if isinstance(value, list):
        return [redact_audit_payload(item) for item in value]
    if isinstance(value, tuple):
        return [redact_audit_payload(item) for item in value]
    return value
