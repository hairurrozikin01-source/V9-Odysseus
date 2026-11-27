"""Read-only WSGI API for the V9 Approval Inbox.

Authentication must be supplied by trusted upstream middleware that sets
REMOTE_USER. Never expose this app directly to the internet without TLS,
session authentication, CSRF protections at the proxy, and authorization.
This module exposes no proposal-creation, decision, broker, or order route.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Any, Callable
from urllib.parse import parse_qs

from persistent_transaction_service import PersistentTransactionReviewService
from transaction_repository import RepositoryError

_SAFE_DETAIL_KEYS = {"symbol", "side", "timeframe", "entry", "stop_loss", "take_profit",
                     "risk_percent", "risk_amount", "spread", "atr", "strategy", "reason"}


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
    """Small, authenticated, read-only JSON API facade."""

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

    def __call__(self, environ: dict[str, Any], start_response: Callable):
        if environ.get("REQUEST_METHOD") != "GET":
            return self._response(start_response, "405 Method Not Allowed",
                                  {"error": "METHOD_NOT_ALLOWED", "message": "API ini hanya menyediakan GET."})
        actor = environ.get("REMOTE_USER")
        if not isinstance(actor, str) or not actor.strip():
            return self._response(start_response, "401 Unauthorized",
                                  {"error": "UNAUTHENTICATED", "message": "Sesi terautentikasi diperlukan."})

        path = environ.get("PATH_INFO", "")
        query = parse_qs(environ.get("QUERY_STRING", ""), keep_blank_values=False)
        try:
            if path == "/api/v1/transaction-control/status":
                audit = self.service.verify_audit()
                return self._response(start_response, "200 OK", {
                    "mode": "MANUAL_APPROVAL",
                    "execution_available": False,
                    "orders_enabled": False,
                    "new_risk_allowed": False,
                    "hard_blocks": [] if audit["valid"] else ["AUDIT_INTEGRITY_FAILED"],
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
                if not raw_limit.isdigit():
                    return self._response(start_response, "400 Bad Request",
                                          {"error": "INVALID_REQUEST", "message": "Limit harus angka."})
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
        except RepositoryError as exc:
            return self._response(start_response, "400 Bad Request",
                                  {"error": "INVALID_REQUEST", "message": str(exc)})
        except Exception:
            return self._response(start_response, "503 Service Unavailable",
                                  {"error": "SERVICE_UNAVAILABLE", "message": "Layanan gagal; operasi dihentikan."})
