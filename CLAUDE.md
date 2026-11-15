# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

**Read `AGENTS.md` first** — it holds the binding architecture boundaries, coding rules, and safety invariants (SSRF transport, agent outcome vs. verification, share-token rules, migrations). This file adds commands and the cross-file picture; it does not repeat those rules. `frontend/AGENTS.md` warns that this Next.js (16.x) differs from training data: read `frontend/node_modules/next/dist/docs/` before writing Next.js code.

## What this is

AgentLane: a modular monolith that scans a website and reports how well AI agents can use it (pricing, docs, signup/demo discovery). One Next.js App Router frontend, one synchronous FastAPI backend, one PostgreSQL database. No queue, cache, or object store — background work is in-process.

## Commands

All backend commands run from `backend/` (config reads the root `.env` from there). Tests need a real, migrated, disposable PostgreSQL; there is no SQLite fallback and a missing `TEST_DATABASE_URL` fails explicitly.

```sh
# Full stack (from repo root; cp .env.example .env on first setup only)
docker compose up --build -d --wait          # frontend :3000, backend :8000 (/docs), db :5432
docker compose -f docker-compose.yml -f docker-compose.cloud.yml build   # managed-CA builds

# Native backend
docker compose up -d --wait db
cd backend && uv sync --frozen && uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Backend tests (one-time: docker compose exec db createdb -U agentreadiness agentreadiness_test)
export TEST_DATABASE_URL=postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q
uv run pytest tests/test_static_audits.py::test_name -q     # single test
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
uv run alembic check

# Frontend (from frontend/)
npm ci && npm run dev        # proxies /api/v1 to BACKEND_URL (default http://localhost:8000)
npm run lint && npm run typecheck && npm run format:check && npm run build
```

Frontend browser checks use Python Playwright from the backend venv (`cd backend && uv run playwright install chromium` once), against a running app:
`UI_BASE_URL=http://localhost:13000 npm run test:states` (API-intercepted fixtures) and `CUSTOMER_REPORT_SCAN_ID=<id> UI_BASE_URL=... npm run test:ui` (axe + responsive checks on an existing scan). Also `test:free-flow`, `test:landing`; scripts live in `frontend/scripts/`.

Real-model tests are opt-in and skipped by default (`RUN_REAL_HF_TEST=1`, `RUN_REAL_OSAURUS_TEST=1`). Don't enable them for static/audit work.

## Test harness behavior (`backend/tests/conftest.py`)

- Each test runs in an outer transaction with `join_transaction_mode="create_savepoint"`, so even API commits roll back.
- The `client` fixture stubs `execute_scan`, `execute_agent_test`, `execute_agent_task` and scan recovery — API tests never crawl live sites. Integration tests drive mocked crawls explicitly (see `agent_fixtures.py`, `tests/fixtures/`).
- An autouse fixture forces `agent_pipeline_enabled=False` and `customer_mode_enabled=False`; tests that need either must re-enable it.

## Architecture: the scan pipeline

Request path: browser → same-origin Next.js rewrite (`next.config.ts`) → `app/api/*_routes.py` → `services/` → `repositories/` → SQLAlchemy → PostgreSQL.

1. `POST /api/v1/projects/{id}/scans` (or `/api/v1/scans`) persists a `PENDING` `Scan` and schedules execution after the response (`services/crawls.py` / `services/audits.py`). Background work uses fresh sessions, not the request session. Admission/queue limits and deadlines are database-backed (`AdmissionBucket`, `SCAN_*` settings); `recover_expired_scans` runs from the app lifespan.
2. **Crawl** — `engines/crawling/`: `transport.py` is the validated HTTPcore backend (public-DNS-only, checked numeric address, ports 80/443, no env proxies); `crawler.py` orchestrates robots/sitemap/frontier within byte/time/page bounds. Raw HTML is transient; only bounded `Page` metadata is stored.
3. **Static audit** — `engines/static_audit/` (`checks.py`, `html.py`, `site.py`, `render.py` for the small Playwright render sample, `resources.py`) is deterministic; `services/static_audits.py` persists `Finding`s, coverage and the frozen static score under the versioned rubric (`static-v2`).
4. **Agent stage** (only if `AGENT_PIPELINE_ENABLED`; code default is `false`, and the customer release keeps it off) — `services/agents.py` claims `AgentTaskTest`s atomically, runs repeats via `engines/agent/runner.py` (`provider.py` LLM client with native tool calls → JSON-schema fallback; `browser.py` routes all browser traffic through the validated gateway + rejecting proxy; `actions.py` fixed action set/tasks; `success.py` rule verification). Runs reuse `WorkflowTest`/`AgentStep` rows. `services/agent_policy.py` (limits, IP admission), `agent_results.py` (repeat aggregation), `agent_findings.py`, `agent_evidence.py`.
5. **Reports** — `services/reports.py` composes static + agent components (`score_kind`: static/agent/combined), comparisons, JSON/CSV; `report_pdf.py` renders offline. Share tokens are digests in `ReportShare`.

Other slices:
- **Free scan** (`services/free_reports.py`, `/api/v1/free-scans`, `/api/v1/free-reports/{token}`): anonymous, ≤10 pages, static only, opaque token link. See `docs/free-scan.md`.
- **Customer mode** (`CUSTOMER_MODE_ENABLED`, default `true` in config and compose): middleware in `app/main.py` returns 403 `customer_only` for every `/api/v1/*` path except free scans/reports, `verification/`, and the Stripe webhook. `services/website_access.py` (mailbox OTP) and `services/payments.py` (one-time domain purchase) own it. Set it to `false` to use the internal workspace UI/API locally. See `docs/customer-launch.md`.
- **Fix Center** (`engines/fixes/`, `services/customer_fixes.py`, `api/fix_routes.py`): deterministic fix guidance and asset drafts. See `docs/fix-center.md`.
- **Standards coverage** (`engines/standards/`): versioned AgentReady reference mapping, not part of scoring.

Models all live in `app/models/domain.py`; schemas are split by area in `app/schemas/`. Migrations are hand-written in `backend/alembic/versions/` (sequential `000N_*.py`).

## Inference providers and the MVP direction

The product is moving to agent variants, an edge router and verified task success (`docs/agentlane-mvp.md`, phased plan). Gemini is the target model family (`gemini-3.8-flash` through the OpenAI-compatible endpoint; Computer Use only via the native Gemini API, in its own adapter). The existing Osaurus/Hugging Face providers remain in code until the Gemini provider replaces them. Google services stay behind swappable interfaces with local defaults (PostgreSQL, Docker Compose). `GET /health/llm` checks reachability without inference.

## Docs map

`docs/architecture.md` (domain table, boundaries), `docs/development.md` (URL safety/SSRF), `docs/crawling.md`, `docs/static-audits.md` (rubric, scoring, exports), `docs/agent-task-tests.md` (agent limits, aggregation, HTTP contracts), `docs/browser-agent.md` (browser safety), `docs/frontend-design.md` (routes, components, UI checks). Some docs describe the agent pipeline as "enabled by default"; the code (`core/config.py`) and compose default it to off.
