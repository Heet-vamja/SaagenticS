# AgentReadiness

Modular monolith for understanding how AI agents experience websites. Projects and background website crawling are implemented: robots.txt, sitemap discovery, bounded internal HTTP crawling, persisted metadata and live progress. A real open-weight LLM browser-agent execution path is also implemented; real-model task completion remains unverified until a usable inference endpoint is configured. Deterministic audits, static readiness scores, evidence-backed fixes, reports, comparisons, sharing and exports are implemented. Accounts/billing and verified agent task evaluation remain deferred.

## Docker development

Requires Docker Engine and Compose v2. From the repository root:

```sh
cp .env.example .env  # first setup only; preserve existing configuration
docker compose up --build -d --wait
```

Frontend: port **3000**. FastAPI: **8000**, interactive OpenAPI docs at `/docs`. PostgreSQL: **5432**. Ports bind only to localhost. Set `FRONTEND_PORT` and `BACKEND_PORT` in `.env` to avoid occupied host ports; defaults remain 3000 and 8000. The backend migrates before starting; `/health` checks database access and the initial table. Next.js proxies browser `/api/v1` requests to the backend. Source mounts and reload support development; this is not a production deployment.

```sh
docker compose logs -f backend frontend
docker compose exec backend .venv/bin/alembic current
docker compose exec backend .venv/bin/alembic upgrade head
docker compose stop
docker compose up -d --wait
```

The database volume survives stop/down. `docker compose down -v` destroys local data; use only for an intentional reset.

Managed cloud builds use the optional combined-CA trust override:

```sh
docker compose -f docker-compose.yml -f docker-compose.cloud.yml build
docker compose up -d --wait
```

The override mounts `/etc/ssl/certs/ca-certificates.crt` during dependency installation. Set `CLOUD_CA_BUNDLE` if needed. Keep Docker's injected proxy and TLS verification enabled. Crawling needs no external API secret; hosted browser-agent inference requires HF_TOKEN.

## Native development

Requires Python **3.12+**, **uv**, Node.js **22.13+** (24 also supported), and PostgreSQL 17.

```sh
# Root, first setup only:
cp .env.example .env
docker compose up -d --wait db
cd backend
uv sync --frozen
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Backend configuration reads the root `.env` from the `backend/` working directory. Native frontend defaults to `BACKEND_URL=http://localhost:8000`; Compose sets `http://backend:8000`. Set this variable in the Next.js process if changing the backend address. CORS origins use a JSON array. Use URL-safe local passwords for Compose's interpolated database URL; URL-encode credentials in custom connection strings. `.env.example` values are local defaults only.

Next.js uses the supported Webpack compiler because Turbopack's compiler subprocess cannot bind a local port in this managed runtime. Build parallelism is limited to two workers.

## Verification commands

Tests require real, migrated PostgreSQL and roll back each case using savepoints, including API commits. Missing `TEST_DATABASE_URL` fails explicitly. Create a separate disposable database once:

```sh
# Root; assumes the example development credentials:
docker compose exec db createdb -U agentreadiness agentreadiness_test
cd backend
export TEST_DATABASE_URL=postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
uv run alembic check
```

For custom credentials, set the matching test URL securely. Inside a backend container use hostname `db`, migrate that disposable database, and run `.venv/bin/pytest -q` with its URL.

```sh
cd frontend
npm run lint
npm run typecheck
npm run build
npm run format:check
# npm start serves the completed production build on port 3000.
```

## API slice

```sh
curl --fail http://localhost:8000/health
curl --fail -X POST http://localhost:8000/api/v1/projects \
  -H 'Content-Type: application/json' \
  -d '{"name":"Example","website_url":"https://example.com"}'
curl --fail http://localhost:8000/api/v1/projects
# Substitute returned UUIDs below:
curl --fail http://localhost:8000/api/v1/projects/PROJECT_ID
curl --fail -X POST http://localhost:8000/api/v1/scans \
  -H 'Content-Type: application/json' -d '{"project_id":"PROJECT_ID"}'
curl --fail http://localhost:8000/api/v1/scans/SCAN_ID
curl --fail http://localhost:8000/api/v1/scans/SCAN_ID/pages?limit=30
curl --fail http://localhost:8000/api/v1/scans/SCAN_ID/pages/PAGE_ID
```

`POST /api/v1/projects/{project_id}/scans` starts a crawl; the existing `POST /api/v1/scans` remains compatible and also starts execution. Both return a persisted PENDING scan immediately; polling `GET /api/v1/scans/{id}` provides progress. Page lists and detail use `/scans/{id}/pages` and `/scans/{id}/pages/{page_id}`. In the UI, create a project, open its details and click **Start Scan**. The project and scan views poll active work and show metadata when a page URL is selected.

Lists accept `limit=1..100` and nonnegative `offset`. `/api/v1/scans` lists scans. `/scans/{id}/workflow-tests` returns stored workflow records, initially empty. `/scans/{id}/report` returns the deterministic static report and its coverage. Missing records return **404**, invalid requests **422**, database failures **503**, using `{ "error": { "code", "message", "details" } }`.

## Structure

```text
frontend/
  src/app/page.tsx          public landing page and website scan CTA
  src/app/(dashboard)/      dashboard, projects, scans and agent execution views
  src/app/docs/             product and inference setup guide
  src/components/           workspace, scan detail, shell, shared states
  src/components/ui/        locally owned shadcn/Radix components
  src/lib/                  API client, types, style utilities
  components.json           shadcn/ui configuration
backend/
  app/api/                  versioned routes and dependencies
  app/core/                 configuration and URL validation
  app/db/                   engine and session lifecycle
  app/models/               SQLAlchemy models and enums
  app/schemas/              request/response/error schemas
  app/repositories/         database access
  app/services/             business rules and transactions
  app/engines/crawling/     URL security, validated transport, parsers, crawl orchestration
  app/engines/contracts.py  later engine contracts
  alembic/versions/         explicit reversible migrations
  tests/                    API, health, URL and database tests
docs/                       architecture and development/security notes
docker-compose.yml          development services
docker-compose.cloud.yml    optional managed-cloud build trust
.env.example                configuration template
AGENTS.md                   guidance for future coding sessions
```

See [frontend design, routes and browser checks](docs/frontend-design.md).

See [architecture](docs/architecture.md) and [development](docs/development.md). See [crawler behavior and limitations](docs/crawling.md). See [static audits, scoring, queue, reports and exports](docs/static-audits.md). Next recommended feature: usable model inference and independent agent task evaluation.


## Real AI browser agent (Feature 2)

Open a scan and use **AI Agent Testing** to select pricing, documentation or signup/
demo-form discovery. The Hugging Face model receives bounded observations and
chooses structured actions that Playwright executes. Execution traces and masked
screenshots are persisted. Agent-declared completion is always marked **not
independently verified**.

See [browser agent setup, API, security boundaries and real-model tests](docs/browser-agent.md).
Default model: `Qwen/Qwen3-4B-Instruct-2507`; configure `HF_TOKEN` in `.env`, then
`docker compose up --build -d --wait`. A compatible separate local server is also
supported. The supplied inference credential returned HTTP 402 during verification;
no successful real-model task is claimed. Deterministic tests use a mock LLM and
real Chromium against local fixture files.

## Redesigned frontend

The public landing page is at `/`; the workspace overview is at `/dashboard`.
Projects, scan results and the dedicated `/agent-tests/{id}` execution viewer use
real API data. The illustrative landing preview is labeled as a demo. New scans produce static scores; independent agent task evaluation remains unimplemented. See the [frontend guide](docs/frontend-design.md)
for component structure, browser test commands, responsive checks and known limits.

## Deterministic audits and reports

Start a new scan to generate static findings and scores; older scans are preserved
unscored. Open **Open report, priority fixes and exports** from scan results.
Reports support JSON/CSV/PDF, revocable expiring share links, before/after comparison
and per-site static score history. No LLM is called by this pipeline. Defaults are
20 pages, a 120-second execution budget, and a three-page browser sample.
See [setup, rubric, APIs, tests and limitations](docs/static-audits.md).
