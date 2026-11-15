# AgentLane engineering guidance

Cloud tasks already run in an isolated environment. Use the existing checkout; create a worktree only if the user explicitly requests one. Read README and docs before extending the architecture. Preserve user changes and keep secrets/generated dependencies out of Git.

## Boundaries

- Modular monolith: Next.js App Router/TypeScript frontend, synchronous FastAPI/Pydantic/SQLAlchemy backend, PostgreSQL/Alembic. Avoid microservices, Redis, Celery, Kafka and Kubernetes without a concrete requirement.
- Backend: `api` owns HTTP/dependencies; `schemas` owns DTOs; `services` owns rules/transactions; `repositories` owns queries; `models` owns persistence; `db` owns sessions; `core` owns settings/security.
- Concrete engines are `engines/crawling`, `engines/static_audit` and `engines/agent`; shared agent result contracts live in `engines/agent/contracts.py`. Services compose execution, scoring and reports from persisted evidence.
- Agent inference uses Gemini through the `LLMProvider` interface (OpenAI-compatible endpoint); Computer Use goes through its own adapter on the native Gemini API. Google services (Gemini, BigQuery, Firestore, Cloud Run, Firebase) stay behind swappable interfaces with local defaults. Keep observations untrusted, actions schema-validated, and browser HTTP behind the validated fetch gateway with a rejecting proxy. Never introduce an unrestricted route continuation/fetch path.
- Edge router (`app/edge`, see docs/agentlane-mvp.md): proxy each site only to its configured, validated origin; route only user-initiated agent fetchers to variants, never search or training crawlers; fail open to the origin; variants and actions carry the same public facts and never expose gated content (login, checkout, private prices). Store paths without query strings and client IPs only as keyed hashes.
- Workflow COMPLETED is a lifecycle state, not proof of success. Keep agent-declared outcome separate from rules/judged verification and from real-model execution evidence. Never map an agent claim directly to PASSED.
- Frontend: App Router pages compose shared components; `components/ui` owns shadcn/Radix controls; `lib/api.ts` owns requests; `lib/types.ts` owns response types. Keep browser API requests same-origin.

## Coding rules

- Thin routes, typed schemas, explicit service transactions, dependency-injected request sessions. Repositories never commit. Keep async for real async I/O.
- Errors use `{error: {code, message, details}}`. Bound lists and validate inputs; do not leak SQL, request bodies or credentials.
- Do not add authentication, organizations, subscriptions or billing unless requested.
- Creating a scan persists PENDING and schedules the HTTP crawler after the response. Static measurements and rubric checks stay deterministic and independent of AI. When `AGENT_PIPELINE_ENABLED` is on, a separate bounded agent stage follows static report preparation; the static score/evidence remains frozen if agent inference is unavailable. Only actual execution advances scan state; never fabricate scores, findings, recommendations or workflow outcomes.
- Keep deterministic checks independent of AI recommendations. Avoid speculative interfaces/factories and empty boilerplate.
- URL submission validation is NOT full SSRF protection. Enforce DNS/address/redirect/browser-subresource/scoping/timeout/size restrictions in the validated crawler transport; see docs/development.md and docs/crawling.md.
- Model changes require reviewed migrations independent of live ORM metadata. Preserve indexes/constraints. `page_metadata` maps to SQL `metadata`.
- Use accessible shared controls, responsive layouts and honest loading/error/empty states.

## Validation

Install with `uv sync --frozen` in backend and `npm ci` in frontend. Follow README for PostgreSQL and disposable test setup. Run pytest with explicit `TEST_DATABASE_URL`, Ruff checks/format, Alembic schema checks, frontend lint/typecheck/build/format checks. Use meaningful integration tests for behavior changes and verify the actual project-to-scan path when modifying that slice. Never weaken assertions to mask failures.

Keep managed proxy settings, TLS verification and CA trust. Use `docker-compose.cloud.yml` when builds need the managed CA. Never print credential values.

## Static readiness

- A URL scan runs deterministic static checks and a bounded browser sample, then runs the separate agent stage when `AGENT_PIPELINE_ENABLED` is on. Set it to false for static-only execution; static audit functions themselves never call the model.
- `audit_summary.static_score` retains the static component. `Scan.overall_score` follows the report's `score_kind` and may be static-only, agent-only or combined. Never describe a readiness score as proof of task success. Unknown checks are not passes; disclose coverage and rubric version.
- Shared report tokens are bearer capabilities, hashed at rest, expiring and revocable. Never expose execution traces, query strings or internal identifiers in shared results. Accounts/billing remain deferred.
- Agent task limits, repeat aggregation, verification assurance and infrastructure exclusion are documented in `docs/agent-task-tests.md`; keep shared screenshot evidence capability-scoped and omit raw paths and internal IDs.
- Comparison cannot mark missing/unknown checks as fixed. Raw and rendered findings retain evidence even when grouped for UI/priorities.
- Exclude real-model tests for static work; do not make inference calls during audit verification.
