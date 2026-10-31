# Development and security

## URL safety

`core/urls.py` validates HTTP(S), rejects credentials, local/metadata hostnames and literal non-global IPv4/IPv6 addresses. Pydantic normalizes alternative numeric IPv4 forms before address checks. Tests cover these inputs.

**This is not full SSRF protection.** No external website request exists. A public hostname can resolve to a private address or change its answer later. Before adding HTTP or browser requests:

1. Validate every DNS answer and reject non-global addresses, including mapped IPv6 and metadata endpoints.
2. Enforce the approved address at connection time to prevent rebinding, preserving TLS hostname verification.
3. Validate each redirect before following it; disable automatic redirects.
4. Enforce hostname/port scope, page/depth/redirect/byte limits and timeouts for every request.
5. Apply equivalent restrictions to browser subresources, popups, workers, navigations and downloads.
6. Add controlled egress as defense in depth and tests for DNS/redirect/rebinding attacks.

Do not fetch submitted URLs in validators or serializers, or describe submission validation as transport-level safety.

## Configuration

`.env` is ignored and `.env.example` contains development defaults. There are no external secrets, authentication, tenants, billing, rate limiting, scheduling or production deployment controls. Change passwords before any shared deployment. Errors exclude SQL/connection details and submitted bodies. `/health` verifies the initial table and database access. OpenAPI documents the error envelope.

## Extending this foundation

Keep HTTP routing in API modules, business operations in services, transactions in services and database queries in repositories. Split `Records` into domain repositories only when needed. Add response schemas rather than exposing arbitrary ORM attributes. Keep score/timestamps null until actual execution establishes values.

The dashboard uses real API data, accessible dialogs, shared error states and bounded-page fetching for complete counts. Pending scans do not poll because no worker advances them. Offset pagination is appropriate for this local foundation; move to stable cursors before high-volume concurrent ingestion.

Run tests against migrated PostgreSQL with explicit `TEST_DATABASE_URL`. Savepoints roll back even committed API operations. Use fictional smoke data and remove it after checks. Frozen installs use `uv.lock` and `package-lock.json`. Future CI should provision disposable PostgreSQL, apply migrations and run README checks. A Starlette/httpx compatibility deprecation warning currently appears during pytest; tests still execute against PostgreSQL.

ESLint is pinned to 9.39.5, the latest release accepted by all bundled Next.js import/React/accessibility plugins. npm reports this release as deprecated; moving to ESLint 10 should wait until those plugins declare support. The lint rules remain enabled and pass.
