# V9.7 — Secure Transaction Platform Foundation

**Status: development / READ ONLY / not production authentication.**

V9.7 starts a separate development line from `v9.6-multi-market-foundation`.
The existing V9.6 pull request and the default branch are not modified.

## Scope of this first slice

- Define a fail-closed authorization policy for dashboard reads and manual proposal decisions.
- Restrict APPROVE/REJECT decisions to the authenticated `owner` role.
- Keep a `viewer` role strictly read-only.
- Reject unknown actions, malformed identities, missing principals, and unauthenticated principals.
- Add recursive redaction for credential-like audit field names.
- Add unit tests for the policy and redaction behavior.

## Important security boundary

`transaction_authorization.py` is an authorization policy helper, **not an authentication provider**.
It does not verify passwords, create sessions, issue cookies, or establish identity. Its
principal must be created by trusted server-side authentication middleware. Never construct
a principal from browser-supplied role or identity fields.

Production login must use a vetted identity/authentication framework or provider rather
than a custom password/session implementation. Before deployment, require HTTPS for the
entire session, secure HttpOnly cookies where cookie sessions are used, CSRF protection,
server-side idle and absolute session expiry, session rotation after authentication,
rate limiting, MFA for sensitive actions, and security review.

Audit redaction is defense in depth only. Do not submit credentials, broker passwords,
API keys, session IDs, cookies, or private keys to audit storage in the first place.
Audit records must also avoid unnecessary personal/account identifiers.

## Transaction and trading restrictions

- No broker connectivity or order-submission code is introduced.
- No live Exness credentials are requested or stored.
- Manual approval is a review decision only; it does not authorize an order.
- Automatic execution remains locked and is not an allowed authorization action.
- Missing, stale, or invalid market/risk data must continue to block proposals.
- Odysseus remains independent and read-only.

## Validation

Run:

```bash
python -m unittest discover -s tests -v
```

GitHub Actions success validates the Python checks only. It does not prove production
authentication, MT5 connectivity, MQL5 compilation, strategy profitability, or live-trading
readiness.

## Security references

- OWASP Authentication Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html
- OWASP Session Management Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html
- OWASP Logging Cheat Sheet:
  https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html
