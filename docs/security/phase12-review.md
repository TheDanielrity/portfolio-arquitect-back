# Phase 12 security and reliability review

Reviewed on 2026-10-01. This is a code and automated-test review for frontend
integration and pre-production validation, not a penetration test or a dependency
vulnerability certification. The approved SQL/DBML and migration remain unchanged.

## Changes

- Request middleware bounds HTTP bodies before JSON parsing or route execution.
  `MAX_REQUEST_BODY_BYTES` defaults to 1 MiB and accepts 1 KiB–10 MiB. Declared
  oversize bodies and streamed bodies exceeding the limit receive 413; a missing
  or dishonest Content-Length does not bypass actual-byte counting. Disconnects
  during buffering do not execute a route. This API registers metadata, not binary uploads.
- POST login, refresh and logout share a per-peer allowance of 30 attempts per
  fixed 60-second window. Contact has a separate allowance of 10. Configure these
  with `AUTH_REQUESTS_PER_MINUTE` and `CONTACT_REQUESTS_PER_MINUTE` (1–1,000).
  Rejected or invalid attempts count. Limits run before parsing, Argon2 and database
  access. Rejections return 429 with `Retry-After` and `Cache-Control: no-store`.
  Paths with trailing slashes and deployment root paths remain protected.
- Each worker owns its counters; there are no module-global request counters.
  Updates contain no await points. The counter table holds at most 10,000
  peer/group entries, removes expired windows and denies new entries when full.
  Request headers cannot override the ASGI peer within the application.
- Unexpected request failures return a generic JSON 500 and an `X-Error-ID`.
  Logs record the same identifier, exception class, and code file/function/line
  locations. They omit exception text, exception chains, SQL diagnostics, source
  lines, local variables, raw URLs, headers and bodies. Expected domain failures
  retain existing 400/401/404/409/422 contracts. A partially started response is
  aborted with a sanitized exception; cancellation continues to propagate.
  CORS wraps the request/error middleware, including 413/429/500 responses.
- Login and local provisioning reject database-incompatible text and invalid
  Unicode passwords. Valid password whitespace is preserved. JWT decoding also
  rejects nonfinite numeric claims without leaking a conversion exception.
- Media delivery and thumbnail URLs now share the existing content URL policy:
  HTTP(S), at most 2,048 characters, no embedded username/password. Public media
  and social-link models enforce it again on reads, so unsafe legacy records
  fail closed with a generic 500 instead of publishing their URLs. Such records
  require correction through a controlled data-maintenance operation; no automatic
  database rewrite is performed. Query-string signed URLs remain supported and
  must be deliberately intended for public delivery.

The body-limit and throttling status codes follow the
[OWASP REST Security guidance](https://cheatsheetseries.owasp.org/cheatsheets/REST_Security_Cheat_Sheet.html).
Middleware uses the [Starlette pure ASGI interface](https://www.starlette.io/middleware/)
to control request bytes and response handling without BaseHTTPMiddleware.

## Reviewed controls and evidence

| Area | Existing protection and regression coverage |
| --- | --- |
| Passwords and tokens | Argon2 through pwdlib; opaque random refresh secrets persisted only as SHA-256 hashes; fixed JWT algorithm, issuer/audience/type/claim checks. Security and auth suites cover malformed claims, wrong keys, session/user mismatch, uniform login failures and inactive users. |
| Refresh lifecycle | Row locks permit one concurrent refresh winner; rotation revokes the old session and preserves the original deadline. Logout is session-scoped. Replayed tokens are denied. The existing schema does not model token families; replay does not revoke unrelated or successor sessions. |
| Authorization | Every admin operation requires a live administrator session; the cross-module OpenAPI test checks missing and malformed credentials. Expired, revoked and disabled-user sessions are rejected by database-backed checks. |
| Visibility and deletion | Public queries enforce publication/visibility/deletion before loading relationships. The full matrix, private access with an admin token, unlisted direct access, slug reuse, hidden sections/content and soft-deleted child operations are tested. |
| Transactions and concurrency | Request sessions roll back unfinished transactions and close. Tests cover injected refresh-write failure, batch rollback, concurrent cover/profile/section operations and media-reference deletion races. The generic error boundary executes after dependency cleanup. |
| Relational integrity | PostgreSQL constraints and partial indexes remain authoritative. Module and migration tests cover conflicts, a single cover/active profile, soft-delete slug rules, foreign keys and schema parity. |
| Query safety and efficiency | User data goes through SQLAlchemy expressions/bind parameters; search uses escaped literal substrings and sort fields are allowlisted. Pagination bounds collection reads. Public integration tests assert query counts for pages and composed detail. |
| Media | Metadata only; no remote URL fetching or binary parsing. Nullable dimensions and section compatibility are preserved. Assets referenced by deleted projects or inactive profiles cannot be deleted through normal operations. |
| CORS and secrets | Exact configured origins; production rejects wildcard origins and debug mode. Configuration secrets use SecretStr and environment variables. `.env` is excluded by `.gitignore`; `.env.example` contains placeholders. No real credential literals were found in reviewed application source. Git tracking could not be verified because this directory has no Git metadata. |
| Error/log privacy | Validation omits submitted values/context; domain messages are explicit. New tests verify generic 500 JSON, safe logging of chained failures, CORS on errors, partial-response aborts and cancellation. The injected refresh failure still rolls back revocation/insertion. |
| Contact abuse | Actual body limits and per-peer rate limits precede persistence. PostgreSQL tests verify that rate-rejected submissions add no records. Metadata uses the ASGI peer, ignores forwarded headers locally, caps user-agent length and stays out of responses. |

## Deployment responsibilities and limitations

- Terminate TLS, set request/header size and upload timeouts, and enforce global
  connection/concurrency limits at the server or reverse proxy. The application
  limit bounds each body, not total memory across simultaneous clients or slow uploads.
- Configure the ASGI server to trust only known proxy IPs. Otherwise a proxy may
  share one quota across clients, or overly broad server trust can permit spoofing.
- For multiple workers/replicas, enforce a distributed rate limit at the gateway.
  Local quotas reset on restart and each worker grants its own allowance. Fixed
  windows allow a burst across a window boundary; clients behind one NAT share
  a quota. This is baseline abuse protection, not distributed DoS protection.
- CAPTCHA/spam scoring, alerting, retention and credential-attack monitoring still
  require deployment/product decisions. No external provider was introduced.
- Keep tokens in authorization headers or POST bodies, never URLs. Configure
  server/proxy access logs to omit queries and auth data (for Uvicorn, use
  `--no-access-log` if no sanitized access-log configuration is provided). Do not
  enable SQL echo or verbose request-body logging in production. Application
  exception sanitization does not control external infrastructure logs.
- Public media URLs must point to intended public assets. Storage ACLs, URL signing,
  malware scanning and safe frontend text rendering remain separate responsibilities.
- Dependency versions were not changed; `pip check` validates dependency consistency,
  not absence of published vulnerabilities. Maintain a deployment dependency audit.

Final command results and the file inventory are recorded in `PLANS.md`.
