# Mini SOC — SQL Injection & XSS Defences

The platform is designed so that **SQL injection and cross-site scripting (XSS)
are not possible**, not merely "hardened". This page records what makes that
true and which automated tests prove it.

## SQL injection — impossible by construction

Every database access goes through **SQLAlchemy's ORM**, which binds all values
as query parameters:

- `backend/app/routers/*.py` only use `db.query(...)`/`.filter(...)` with bound
  values — there is no string concatenation into SQL.
- The only raw `text()` SQL in the repo is inside the Alembic migrations
  (`backend/migrations/`), where the statements are static and contain no user
  input.
- Free-text filters (e.g. `src_ip`, `host`, `log_type`, `severity`, `status`)
  are passed as bound parameters, so a payload such as `'; DROP TABLE alerts;
  --` is compared as a literal string.

Proof: `backend/tests/test_security.py` (`TestSQLiXSS`) exercises the event and
alert filters with injection payloads and asserts they are handled as data.

## XSS — blocked at every layer

| Layer | Defence |
|---|---|
| **Dashboard (React)** | Values render as React text nodes, which are HTML-escaped by default. There is **no `dangerouslySetInnerHTML`/`innerHTML`** anywhere in `frontend/src` (verified by search). |
| **Generated reports** | Every interpolated field goes through `esc()` / `esc_list()` in `backend/app/utils/report_html.py`, which uses `html.escape(..., quote=True)`. |
| **Report shell** | Reports embed a restrictive `Content-Security-Policy` meta tag (`CSP_META`): `default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'`. Even if an escaping bug slipped through, the browser refuses to execute inline/remote script. |
| **Evidence downloads** | `GET /api/evidence/{id}/download` always returns `application/octet-stream` + `attachment`, so an uploaded `.html`/`.svg` can never render in the app origin (stored XSS). |

Proof: `test_security.py::TestSQLiXSS` creates an incident titled
`<script>alert('xss')</script>` and asserts the raw script tag is **not**
present in the rendered report (it is escaped to `&lt;script&gt;`), and that the
evidence download response is `application/octet-stream`.

## Transport/browser hardening

`backend/app/main.py` adds a middleware that stamps every non-docs response with:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`
- `Cross-Origin-Opener-Policy: same-origin`
- `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'`

`deploy/nginx/mini-soc.conf` mirrors this for the SPA itself (with
`script-src 'self'`, `connect-src 'self'` for the API, `object-src 'none'` and
`frame-ancestors 'none'`). Together these also stop clickjacking, MIME sniffing
and referrer leakage.

Proof: `test_security.py::TestSecurityHeaders`.

## Input validation notes

Enum-like values (incident severity/status, user role) are validated in the
router layer against an allowlist. Deliberately, the free-text event/alert
filters are **not** rejected by value — the ORM already parameterises them, and
rejecting on value would break legitimate searching. SQL injection is prevented
by parameterisation, not by input filtering.

## Related tests

- `backend/tests/test_security.py` — SQLi filters, report XSS escaping, evidence
  content type, security headers, JWT/IDOR/upload/IPS checks.
- `backend/tests/test_rules_stats.py` — rule loading fallback and the
  `include_disabled` option used by the Rules page.
- `backend/tests/test_users_route.py` — user management guardrails (create,
  role change, password reset, deactivate/reactivate, self/last-admin guards).
- `frontend/src/__tests__/EventSearch.test.jsx`, `Reports.test.jsx`,
  `Users.test.jsx` — page-level behaviour for live search, summary report and
  user deactivation.
