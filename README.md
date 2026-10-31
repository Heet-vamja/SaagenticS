# AgentReadiness

Modular monolith for understanding how AI agents experience websites. This foundation implements projects and pending scan records. Crawling, audits, browser tests, scoring, recommendations and reports are not implemented; results are never fabricated.

## Docker development

Requires Docker Engine and Compose v2. From the repository root:

```sh
cp .env.example .env  # first setup only; preserve existing configuration
docker compose up --build -d --wait
```

Frontend: port **3000**. FastAPI: **8000**, interactive OpenAPI docs at `/docs`. PostgreSQL: **5432**. Ports bind only to localhost. The backend migrates before starting; `/health` checks database access and the initial table. Next.js proxies browser `/api/v1` requests to the backend. Source mounts and reload support development; this is not a production deployment.

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

The override mounts `/etc/ssl/certs/ca-certificates.crt` during dependency installation. Set `CLOUD_CA_BUNDLE` if needed. Keep Docker's injected proxy and TLS verification enabled. No external API secrets are needed.

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
curl --fail http://localhost:8000/api/v1/scans/SCAN_ID/findings
```

Lists accept `limit=1..100` and nonnegative `offset`. `/api/v1/scans` lists scans. `/scans/{id}/workflow-tests` returns stored workflow records, initially empty. `/scans/{id}/report` validates scan existence then returns **501**. Missing records return **404**, invalid requests **422**, database failures **503**, using `{ "error": { "code", "message", "details" } }`.

## Structure

```text
frontend/
  src/app/(dashboard)/      overview, projects, scans, scans/[id]
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
  app/engines/contracts.py  future engine contracts only
  alembic/versions/         initial reversible migration
  tests/                    API, health, URL and database tests
docs/                       architecture and development/security notes
docker-compose.yml          development services
docker-compose.cloud.yml    optional managed-cloud build trust
.env.example                configuration template
AGENTS.md                   guidance for future coding sessions
```

See [architecture](docs/architecture.md) and [development](docs/development.md). Next recommended task: a bounded HTTP crawler with transport-enforced SSRF protection, starting with robots.txt and sitemap discovery.
