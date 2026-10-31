# Development and security

## URL safety

`core/urls.py` validates HTTP(S), rejects credentials, local/metadata hostnames and literal non-global IPv4/IPv6 addresses. Pydantic normalizes alternative numeric IPv4 forms before address checks. Tests cover these inputs.

Submission validation alone is not full SSRF protection. The crawler now adds a
validated HTTPcore network backend: all DNS answers must be public, and the TCP
connection receives only a checked numeric address. TLS still verifies the
original hostname. Every redirect re-enters URL scope and robots checks; each
new socket revalidates DNS. Proxies from the environment are disabled for crawling,
while dependency installers retain their existing proxy/CA configuration.

Loopback, private, link-local, reserved, multicast, IPv4-mapped/transition IPv6 and
cloud metadata destinations (including Azure's publicly numbered platform IP)
are denied. Only ports 80/443 are permitted. Streams, requests, redirects, frontier,
sitemaps and total scan duration are bounded. Cookies, custom headers, submitted
credentials, forms and JavaScript are not used. Compressed responses are rejected
to avoid decompression bombs. Feature 1 remains HTTP-only; Feature 2 applies the same transport boundary to browser subresources through its gateway (see docs/browser-agent.md).

Use controlled egress as production defense in depth. HTTPcore backend adapter
versions are bounded in pyproject/lock and must retain their security tests during
upgrades. See [crawler settings and limitations](crawling.md).

## Configuration

`.env` is ignored and `.env.example` contains development defaults. Hosted agent inference uses an optional HF_TOKEN secret; it remains outside source control and response DTOs. There is no application authentication, tenant isolation, billing, rate limiting, durable scheduling or production deployment controls. Change passwords before any shared deployment. Errors exclude SQL/connection details and submitted bodies. `/health` verifies the initial table and database access. OpenAPI documents the error envelope.

## Extending this foundation

Keep HTTP routing in API modules, business operations in services, transactions in services and database queries in repositories. Split `Records` into domain repositories only when needed. Add response schemas rather than exposing arbitrary ORM attributes. Keep score/timestamps null until actual execution establishes values.

The dashboard uses real API data, accessible dialogs, shared error states and bounded-page fetching for complete counts. Project and scan detail views poll every two seconds while scans are PENDING/RUNNING, then stop. Offset pagination is appropriate for this local foundation; move to stable cursors before high-volume concurrent ingestion.

Run tests against migrated PostgreSQL with explicit `TEST_DATABASE_URL`. Savepoints roll back even committed API operations. Use fictional smoke data and remove it after checks. Frozen installs use `uv.lock` and `package-lock.json`. Future CI should provision disposable PostgreSQL, apply migrations and run README checks. A Starlette/httpx compatibility deprecation warning currently appears during pytest; tests still execute against PostgreSQL.

ESLint is pinned to 9.39.5, the latest release accepted by all bundled Next.js import/React/accessibility plugins. npm reports this release as deprecated; moving to ESLint 10 should wait until those plugins declare support. The lint rules remain enabled and pass.
