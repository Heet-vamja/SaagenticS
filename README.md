# AgentLane

**Customer launch:** email verification (any mailbox) → free static score and three
insights → optional **$19 one-time full report** with 30 days of same-domain
re-scans. Real AI browser-agent tests are **Coming Christmas 2026**. Start with
[customer launch setup](docs/customer-launch.md) for Gmail SMTP, Stripe test mode,
webhooks and access controls. SMTP/Stripe need configuration before live use.


The customer MVP helps **SaaS businesses** find barriers around public pricing,
documentation and signup/demo discovery, give developers evidence-backed fixes,
and verify improvements. The free report includes a deterministic Fix Center,
validated crawl-derived asset drafts, fix-pack download and linked rescan.
Static readiness and real agent task results are presented separately; anonymous
scans do not call a model. See [the current MVP goal](docs/mvp-plan.md) and
[Fix Center, verification and pilot metrics](docs/fix-center.md).

Modular monolith for understanding how AI agents experience websites. Projects and bounded website crawling feed deterministic static audits, reports and readiness scores. In private internal development mode only, a separately enabled agent stage follows static report preparation and evaluates bounded website tasks using local Raptor 0.6 through Osaurus by default, or an explicitly selected Hugging Face open-weight endpoint. Static checks remain deterministic and retain their own frozen score. User accounts and subscriptions remain out of scope; customer access uses mailbox verification and a one-time domain report purchase. Real-model task success is pending explicit live verification; mock-model integration tests do not establish it.

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

For static-only scans, set `AGENT_PIPELINE_ENABLED=false` in `.env`. The customer release keeps agent execution disabled. Agent policy, cost and network settings are listed in
[Agent Task Tests](docs/agent-task-tests.md); blank token-price settings mean cost
is unknown, not zero. Do not expose the local Compose ports directly to the public
internet.

Managed cloud builds use the optional combined-CA trust override:

```sh
docker compose -f docker-compose.yml -f docker-compose.cloud.yml build
docker compose up -d --wait
```

The override mounts `/etc/ssl/certs/ca-certificates.crt` during dependency installation. Set `CLOUD_CA_BUNDLE` if needed. Keep Docker's injected proxy and TLS verification enabled. Crawling and local Osaurus inference need no paid API credentials. See [Local Osaurus setup](#local-osaurus-raptor-setup) for Docker Desktop networking. Hugging Face fallback requires HF_TOKEN.

### Local Osaurus Raptor setup

The default development provider is Osaurus on your Mac; the FastAPI container
connects to the host at `host.docker.internal:1337`. Install Osaurus **0.25.0 or
newer**, download [Raptor 0.6](https://osaurus.ai/models/raptor-06) (about 3.7 GB;
Apache-2.0 model weights) in its model picker, and enable Osaurus's local API.
Start/check the loopback API on the Mac with:

```sh
osaurus serve
curl --fail http://127.0.0.1:1337/v1/models
```

The Mac-only default listener binds to loopback, so Docker cannot reach it until
you enable **network exposure** in Osaurus (or run `osaurus serve --expose`). Use
Osaurus's access key when network exposure requires one; do not
expose the API to an untrusted network.

Set these values in the root `.env` (the example already contains the defaults).
If `.env` already exists, edit these provider lines manually and keep your database
password and other local settings intact; copying the example does not overwrite it.

```dotenv
AGENT_LLM_PROVIDER=osaurus
AGENT_MODEL=raptor-0.6-4b-jang_6m
AGENT_LLM_BASE_URL=http://host.docker.internal:1337/v1
AGENT_LLM_TIMEOUT=60
OSAURUS_API_KEY=<your-Osaurus-access-key-if-required>
```

Confirm the model appears in Osaurus's OpenAI-compatible model list, then check
reachability from the running backend container without performing inference:

```sh
curl --fail http://localhost:8000/health/llm
```

The response confirms whether the API is reachable and the configured model is
available. If FastAPI runs natively on the Mac rather than in Docker, set
`AGENT_LLM_BASE_URL=http://127.0.0.1:1337/v1`; leave Osaurus network exposure off.

To use Hugging Face instead, set `AGENT_LLM_PROVIDER=huggingface`,
`AGENT_LLM_MODE=hosted`, `AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507`,
`AGENT_LLM_BASE_URL=https://router.huggingface.co/v1`, and `HF_TOKEN`. Provider
selection is explicit; a local outage never silently falls back to hosted inference.

## Edge router and demo store (MVP phase 1)

The MVP direction (agent variants, edge routing, verified task success) is specified in
[docs/agentlane-mvp.md](docs/agentlane-mvp.md). Phase 1 adds a fictional demo store with
deliberate agent problems and an edge router that proxies it and logs agent traffic.
Compose starts both: the store on port **4000** and the router on **8080**
(`DEMO_STORE_PORT`, `EDGE_PORT`). Register the demo host once:

```sh
docker compose exec edge .venv/bin/python -m app.cli.edge_sites add \
  --host store.localhost --origin http://demo-store:4000 --name "Northstar Shoes"
curl -s http://store.localhost:8080/ -A "Mozilla/5.0 Chrome/130"        # human: passed through, not logged
curl -s http://store.localhost:8080/ -A "Mozilla/5.0; ChatGPT-User/1.0" # agent: passed through and logged
```

Phase 2 builds the agent variant (needs `GEMINI_API_KEY` in `.env`, then recreate the
edge container with `docker compose up -d edge`):

```sh
docker compose exec -T edge .venv/bin/python -m app.cli.edge_sites set-delivery \
  --host store.localhost --rules - < demo-store/delivery-rules.json
docker compose exec edge .venv/bin/python -m app.cli.variants build --host store.localhost
docker compose exec edge .venv/bin/python -m app.cli.variants list --host store.localhost
curl -s http://store.localhost:8080/product/trail-runner -A "ChatGPT-User/1.0"   # agent HTML
curl -s http://store.localhost:8080/llms.txt
curl -s "http://store.localhost:8080/agent-api/search?q=running&size=9&max_price=3000"
```

A build is published only when its parity check passes; otherwise it is kept as
`REJECTED` with the reasons.

Phases 3 and 4 add sessions, labels, agent QA and the owner dashboard at `/dashboard`
(set `EDGE_DASHBOARD_TOKEN` in `.env` and recreate `backend`):

```sh
docker compose exec edge .venv/bin/python -m app.cli.insights sessions --host store.localhost
docker compose exec edge .venv/bin/python -m app.cli.insights label --host store.localhost
docker compose exec edge .venv/bin/python -m app.cli.qa run \
  --host store.localhost --base-url http://store.localhost:8080
```

Session labels are model-judged; QA outcomes are rule-verified and shown separately. Only user-initiated agent fetchers are routable; search and training crawlers are always
passed through (no cloaking) and logged as crawlers. Agent requests land in the
`agent_requests` table with the agent, path (no query string), status, timing and a hashed
client. `EDGE_ALLOW_PRIVATE_ORIGINS=true` exists only so local sites can point at the demo
store on the Docker network; keep it false anywhere else. Demo store tests run with the
backend environment: `backend/.venv/bin/pytest demo-store/tests`.

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

Lists accept `limit=1..100` and nonnegative `offset`. `/api/v1/scans` lists scans. `/scans/{id}/workflow-tests` returns stored workflow records. `/scans/{id}/report` returns static checks and, when available, agent task summaries and score components. The new task/config and report evidence routes are documented in [Agent Task Tests](docs/agent-task-tests.md). Missing records return **404**, invalid requests **422**, database failures **503**, using `{ "error": { "code", "message", "details" } }`.

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
  app/engines/agent/        provider, bounded browser runner and result contracts
  alembic/versions/         explicit reversible migrations
  tests/                    API, health, URL and database tests
docs/                       architecture and development/security notes
docker-compose.yml          development services
docker-compose.cloud.yml    optional managed-cloud build trust
.env.example                configuration template
AGENTS.md                   guidance for future coding sessions
```

See [frontend design, routes and browser checks](docs/frontend-design.md).

See [architecture](docs/architecture.md) and [development](docs/development.md). See [crawler behavior and limitations](docs/crawling.md), [static audits, scoring, queue, reports and exports](docs/static-audits.md), and [agent task tests](docs/agent-task-tests.md).


## Agent task tests

By default, scan execution runs the deterministic static stage first, then a
separately bounded agent stage. The agent can find pricing, public contact details,
and signup/demo forms. Each task records multiple run results, verification method,
usage, aggregate outcome and consistency. A documentation task remains available
for compatibility but is not in the default automated task set. The interface
labels rule-verified, judge-assisted and unverified results separately.

See [agent task tests](docs/agent-task-tests.md) for default limits, API contracts,
admission/IP handling, report/evidence boundaries and exact configuration. See
[browser-agent implementation details](docs/browser-agent.md) for tool and browser
safety. `AGENT_LLM_PROVIDER=osaurus` selects local Raptor 0.6 by default;
`AGENT_LLM_PROVIDER=huggingface` keeps the Hugging Face open-weight route available
as an explicit alternative. No provider failover occurs automatically.

The homepage's URL-first free scan uses a separate opaque report link, crawls at
most 10 pages, and runs deterministic checks only. It never calls the configured
LLM or waits for the optional agent stage used by workspace scans. The free score
is preliminary: unavailable categories (including agent usability) are excluded
and remaining weights are normalized. “Unlock Fixes” is a coming-soon state;
payments are not implemented. See the [free scan guide](docs/free-scan.md).

## Redesigned frontend

The public landing page is at `/`; the workspace overview is at `/dashboard`.
Projects, scan results and the dedicated `/agent-tests/{id}` execution viewer use
real API data. The illustrative landing preview is labeled as a demo. Scan results
distinguish the static score from any agent component and disclose static fallback
when no eligible agent evidence exists. See the [frontend guide](docs/frontend-design.md)
for component structure, browser test commands, responsive checks and known limits.

## Deterministic audits and reports

Start a scan to generate static findings and scores; older scans are preserved
unscored. Open **Open report, priority fixes and exports** from scan results.
Reports support JSON/CSV/PDF, revocable expiring share links, before/after comparison
and per-site static score history. Static audit checks themselves never call an
LLM. With the default pipeline enabled, a separate agent stage follows static report
preparation. Disabling `AGENT_PIPELINE_ENABLED` leaves the static audit available.
Defaults are 20 pages, a 120-second static execution budget, and a three-page
browser sample.
See [setup, rubric, APIs, tests and limitations](docs/static-audits.md).

## Anonymous URL-first scan

Open `http://localhost:3000`, enter a public website URL, and follow the opaque
report link. No sign-up, project selection, or scan ID is required. The same flow
is available through `POST /api/v1/free-scans`; poll the returned path at
`GET /api/v1/free-reports/{token}`. Free report links expire according to
`REPORT_SHARE_DAYS`. See the [free scan guide](docs/free-scan.md) for API details,
score coverage, limits, and verification commands.

## Privacy and terms pages

The frontend provides `/privacy` and `/terms`, linked from public footers and
workspace navigation. Operator name, contact email and jurisdiction are
intentional placeholders in `frontend/src/lib/legal.ts`; both pages are marked
as drafts pending completion and review. See [legal page setup](docs/legal-pages.md).

AgentReady reference mapping: see [coverage, explicit gaps and interpretation](docs/agentready-coverage.md). It is an independent, versioned reference—not certification or a change to our scoring rubric.

Bounded resource-link, missing-path and code-example diagnostics are available without inference. See [limits, configuration and interpretation](docs/static-audits.md#bounded-discovery-and-route-diagnostics). They add fix guidance without changing current score weights.
