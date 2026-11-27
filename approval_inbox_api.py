"""Authenticated Approval Inbox WSGI API for V9.

A trusted authentication middleware MUST set REMOTE_USER, v9.authenticated,
and v9.role. For POST decisions, a trusted CSRF middleware must additionally
set v9.csrf_valid=True after validating the request token. These WSGI keys
must never be copied from untrusted client headers or request JSON.

This API records human review decisions only. It has no broker or order route.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Callable
from urllib.parse import parse_qs

from persistent_transaction_service import PersistentTransactionReviewService
from transaction_authorization import AuthorizationError, authorize_action
from transaction_control import ProposalError
from transaction_repository import RepositoryError

_SAFE_DETAIL_KEYS = {"symbol", "side", "timeframe", "entry", "stop_loss", "take_profit",
                     "risk_percent", "risk_amount", "spread", "atr", "strategy", "reason"}
_MAX_BODY_BYTES = 4096


def _public_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    details = proposal.get("details") or {}
    safe_details = {k: v for k, v in details.items() if k in _SAFE_DETAIL_KEYS}
    return {
        "proposal_id": proposal["proposal_id"],
        "proposal_version": proposal["proposal_version"],
        "proposal_hash": proposal["proposal_hash"],
        "details": safe_details,
        "gates": proposal["gates"],
        "status": proposal["status"],
        "created_at": proposal["created_at"],
        "expires_at": proposal["expires_at"],
        "decision": proposal.get("decision"),
        "orders_enabled": False,
        "execution_enabled": False,
    }


class ApprovalInboxWSGI:
    """Authenticated JSON API with owner-only review decisions."""

    def __init__(self, service: PersistentTransactionReviewService):
        self.service = service

    @staticmethod
    def _response(start_response: Callable, status: str, payload: dict[str, Any]):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        start_response(status, [
            ("Content-Type", "application/json; charset=utf-8"),
            ("Content-Length", str(len(body))),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ])
        return [body]

    @staticmethod
    def _principal(environ: dict[str, Any]) -> dict[str, Any]:
        # These values are trusted ONLY when inserted by server-side middleware.
        return {
            "authenticated": environ.get("v9.authenticated") is True,
            "actor_id": environ.get("REMOTE_USER"),
            "role": environ.get("v9.role"),
        }

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "")
        principal = self._principal(environ)
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)

        try:
            if method == "GET":
                action = "VIEW_AUDIT" if path == "/api/v1/audit/events" else (
                    "VIEW_DASHBOARD" if path == "/api/v1/transaction-control/status" else "VIEW_PROPOSALS"
                )
                actor = authorize_action(principal, action)
                return self._get(path, query, start_response)

            if method == "POST":
                match = re.fullmatch(r"/api/v1/proposals/([A-Za-z0-9._-]{1,128})/decision", path)
                if not match:
                    return self._response(start_response, "404 Not Found", {"error": "NOT_FOUND"})
                actor = authorize_action(principal, "APPROVE_PROPOSAL")
                if environ.get("v9.csrf_valid") is not True:
                    return self._response(start_response, "403 Forbidden", {"error": "CSRF_VALIDATION_REQUIRED"})
                return self._decide(match.group(1), actor, environ, start_response)

            return self._response(start_response, "405 Method Not Allowed",
                                  {"error": "METHOD_NOT_ALLOWED", "message": "Metode tidak didukung."})
        except AuthorizationError as exc:
            code = str(exc)
            status = "401 Unauthorized" if code == "AUTHENTICATION_REQUIRED" else "403 Forbidden"
            return self._response(start_response, status, {"error": code})
        except RepositoryError:
            return self._response(start_response, "400 Bad Request", {"error": "INVALID_REQUEST"})
        except ProposalError:
            return self._response(start_response, "409 Conflict", {"error": "STATE_CONFLICT"})
        except Exception:
            return self._response(start_response, "503 Service Unavailable",
                                  {"error": "SERVICE_UNAVAILABLE", "message": "Layanan gagal; operasi dihentikan."})

    def _get(self, path: str, query: dict[str, list[str]], start_response: Callable):
        if path == "/api/v1/transaction-control/status":
            audit = self.service.verify_audit()
            hard_blocks = ["EXECUTION_NOT_IMPLEMENTED", "BROKER_NOT_CONNECTED", "LIVE_TRADING_DISABLED"]
            if not audit["valid"]:
                hard_blocks.insert(0, "AUDIT_INTEGRITY_FAILED")
            return self._response(start_response, "200 OK", {
                "mode": "MANUAL_APPROVAL",
                "execution_available": False,
                "orders_enabled": False,
                "new_risk_allowed": False,
                "hard_blocks": hard_blocks,
                "audit_integrity": audit["valid"],
                "server_time": datetime.now(timezone.utc).isoformat(),
            })

        if path == "/api/v1/proposals":
            status_filter = query.get("status", [None])[0]
            allowed = {None, "PROPOSAL_PENDING", "APPROVED", "REJECTED", "EXPIRED", "BLOCKED"}
            if status_filter not in allowed:
                return self._response(start_response, "400 Bad Request",
                                      {"error": "INVALID_REQUEST", "message": "Filter status tidak dikenal."})
            raw_limit = query.get("limit", ["50"])[0]
            if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 100:
                return self._response(start_response, "400 Bad Request",
                                      {"error": "INVALID_REQUEST", "message": "Limit harus 1 sampai 100."})
            limit = int(raw_limit)
            proposals = self.service.repository.list_proposals(status=status_filter, limit=limit)
            return self._response(start_response, "200 OK", {
                "items": [_public_proposal(p) for p in proposals],
                "count": len(proposals),
                "limit": limit,
            })

        match = re.fullmatch(r"/api/v1/proposals/([A-Za-z0-9._-]{1,128})", path)
        if match:
            proposal = self.service.get(match.group(1))
            if proposal is None:
                return self._response(start_response, "404 Not Found", {"error": "NOT_FOUND"})
            return self._response(start_response, "200 OK", _public_proposal(proposal))

        if path == "/api/v1/audit/events":
            raw_limit = query.get("limit", ["50"])[0]
            if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= 100:
                return self._response(start_response, "400 Bad Request",
                                      {"error": "INVALID_REQUEST", "message": "Limit harus 1 sampai 100."})
            events = self.service.list_audit_events()
            integrity = self.service.verify_audit()
            items = events[-int(raw_limit):]
            return self._response(start_response, "200 OK", {
                "items": items,
                "count": len(items),
                "integrity_valid": integrity["valid"],
            })

        return self._response(start_response, "404 Not Found", {"error": "NOT_FOUND"})

    def _decide(self, proposal_id: str, actor: str, environ: dict[str, Any], start_response: Callable):
        raw_length = environ.get("CONTENT_LENGTH", "")
        if not isinstance(raw_length, str) or not raw_length.isdigit():
            return self._response(start_response, "400 Bad Request", {"error": "INVALID_CONTENT_LENGTH"})
        length = int(raw_length)
        if length < 1 or length > _MAX_BODY_BYTES:
            return self._response(start_response, "413 Payload Too Large", {"error": "BODY_SIZE_INVALID"})
        stream = environ.get("wsgi.input")
        if stream is None:
            return self._response(start_response, "400 Bad Request", {"error": "BODY_REQUIRED"})
        raw = stream.read(length)
        if not isinstance(raw, bytes) or len(raw) != length:
            return self._response(start_response, "400 Bad Request", {"error": "BODY_INCOMPLETE"})
        if environ.get("CONTENT_TYPE", "").split(";")[0].strip().lower() != "application/json":
            return self._response(start_response, "415 Unsupported Media Type", {"error": "JSON_REQUIRED"})
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._response(start_response, "400 Bad Request", {"error": "INVALID_JSON"})
        if not isinstance(payload, dict) or set(payload) != {"action", "proposal_hash"}:
            return self._response(start_response, "400 Bad Request", {"error": "INVALID_DECISION_PAYLOAD"})
        action = payload.get("action")
        proposal_hash = payload.get("proposal_hash")
        if action not in {"APPROVE", "REJECT"} or not isinstance(proposal_hash, str) or not re.fullmatch(r"[a-f0-9]{64}", proposal_hash):
            return self._response(start_response, "400 Bad Request", {"error": "INVALID_DECISION_PAYLOAD"})

        result = self.service.decide(
            proposal_id,
            action=action,
            expected_hash=proposal_hash,
            actor=actor,
            now=datetime.now(timezone.utc),
        )
        public = _public_proposal(result)
        if result["status"] == "BLOCKED":
            return self._response(start_response, "422 Unprocessable Entity", {
                "error": "PROPOSAL_CHANGED", "proposal": public,
            })
        if result["status"] == "EXPIRED":
            return self._response(start_response, "410 Gone", {
                "error": "PROPOSAL_EXPIRED", "proposal": public,
            })
        return self._response(start_response, "200 OK", {
            "decision_recorded": True,
            "proposal": public,
            "orders_enabled": False,
            "execution_enabled": False,
        })
