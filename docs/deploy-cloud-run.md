# Deploying to Google Cloud (draft)

Status: **draft, not yet deployed.** The commands below follow the architecture in
`docs/agentlane-mvp.md` but have not been run against a real project. Treat each step
as a checklist item to verify; update this file with what actually worked. Open
blockers are listed in `docs/TODO.md`.

Local development keeps Docker Compose and PostgreSQL. On Google Cloud every Google
service is an adapter switched on by configuration; nothing in the code requires it.

## Services

| Compose service | Google Cloud | Entry point |
| --- | --- | --- |
| `db` | Cloud SQL for PostgreSQL | — |
| `backend` | Cloud Run service | `uvicorn app.main:app` (port 8000) |
| `frontend` | Cloud Run service (or Firebase Hosting + Cloud Run) | needs a production image, see blockers |
| `edge` | Cloud Run service on the customer-facing domain | `uvicorn app.edge.main:app` (port 8080) |
| `jobs` | Cloud Run worker pool, or a service with CPU always allocated and one minimum instance | `python -m app.cli.jobs worker` |
| migrations | Cloud Run job | `alembic upgrade head` |
| `demo-store` | Cloud Run service | `uvicorn server:app` (port 4000) |

`backend`, `edge` and `jobs` share one image (`backend/Dockerfile`) with different
commands, as in Compose.

## Configuration

Store secrets in Secret Manager and mount them as environment variables:
`DATABASE_URL`, `GEMINI_API_KEY`, `EDGE_DASHBOARD_TOKEN`, `VERIFICATION_SECRET`.

Production values that differ from local Compose:

- `EDGE_ALLOW_PRIVATE_ORIGINS=false` (the default). Origins must be public host names on
  ports 80/443, and the router connects through the DNS-validated transport.
- `QA_BASE_URL_TEMPLATE=https://{host}` (the default) and `DEV_BROWSER_HOST_RULES` unset.
- `EDGE_BIGQUERY_TABLE=<project>.<dataset>.agent_requests` to stream a copy of the agent
  request log to BigQuery. PostgreSQL stays the primary sink because the dashboard
  reads from it.
- `AGENT_TRUSTED_PROXY_CIDRS`: set to the Google front end ranges only if client
  addresses must be read from `X-Forwarded-For`; otherwise leave empty.

## BigQuery request log

The edge service authenticates with its own service account through the metadata
server (no key file, no Google SDK). Grant that account `roles/bigquery.dataEditor`
on the dataset.

```sh
bq mk --dataset <project>:edge_logs
bq mk --table --time_partitioning_field received_at \
  <project>:edge_logs.agent_requests deploy/bigquery/agent_requests.schema.json
```

The schema is pinned to the logged event by `tests/test_request_log_sinks.py`. Paths
are stored without query strings and clients as keyed hashes, as in PostgreSQL.

## Order of operations

1. Create Cloud SQL, the secrets and an Artifact Registry repository.
2. Build and push `backend/Dockerfile` and `demo-store/Dockerfile` (Cloud Build).
3. Run the migration job, then deploy `backend`, `edge`, `jobs` and `demo-store`.
4. Map the customer-facing domain to the `edge` service and register the site in the
   dashboard with the public host and its origin.
5. Deploy the frontend with `BACKEND_URL` pointing at the `backend` service. Next.js
   resolves rewrites at build time, so the URL must be known when the image is built.

## Blockers before the first deploy

- `frontend/Dockerfile` runs `npm run dev`; a production target (`npm run build` then
  `npm start`) is needed.
- The worker pool vs. always-on service choice for `jobs` needs confirming against the
  current Cloud Run offering.
- Firebase Auth for the dashboard is not implemented; the dashboard uses the operator
  token.
