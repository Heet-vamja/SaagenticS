# AgentLane MVP: agent variants, edge routing and verified task success

Status: phases 1 and 5 verified live; phases 2–4 implemented, awaiting a Gemini key for the first live model runs. Phase 6 planned. Open items: `docs/TODO.md`. Reviewed 2026-11-15.

## What the MVP proves

One loop, end to end: an AI agent fails a task on a normal site, succeeds on the
agent variant AgentLane generated, and the dashboard shows why. The headline demo
claim has the form "agents completed X of 10 tasks on the original and Y of 10 on
AgentLane, using N× fewer tokens". Every number comes from rule-verified task
outcomes and measured token counts, never from a model saying it finished.

The existing free static scan and $19 report stay as the front door: they show
what is broken; the variant, router and dashboard are the next step.

## Principles

- **Keep the monolith.** FastAPI, PostgreSQL/Alembic and Next.js stay. New features
  are modules in the existing layers (`api`, `schemas`, `services`, `repositories`,
  `models`, `engines`). The edge router is a second ASGI entry point in the same
  backend package, deployed as its own container.
- **Google services are adapters.** Gemini, BigQuery, Firestore, Cloud Run and
  Firebase plug in behind small interfaces with a local default, so the core runs
  with Docker Compose and PostgreSQL alone.
- **Agents get the same facts, presented better.** A variant may restructure
  content, never change prices, stock, policies or claims. Gated content (login,
  checkout, private prices) is never exposed to agents.
- **Honest numbers.** Agent-declared success is not success. Task outcomes are
  verified by rules against the store's real state.

## Pluggable boundaries

| Concern | Interface | Default (local) | Google adapter |
| --- | --- | --- | --- |
| Text generation, extraction, labeling | `LLMProvider` (existing, OpenAI-compatible) | Gemini via OpenAI-compatible endpoint | same |
| Agent QA browser control | `ComputerUseDriver` | Playwright runner with mock driver in tests | Gemini native API `computer_use` tool |
| Request log sink | `RequestLogSink` | PostgreSQL `agent_requests` | BigQuery streaming insert |
| Variant storage | `VariantStore` | PostgreSQL rows | Cloud Storage / Firestore |
| Deployment | Docker images | Docker Compose | Cloud Run (app, edge router, demo store) |
| Dashboard auth | existing mailbox verification | session cookie | Firebase Auth (optional) |

Gemini is the only model family. Configuration: `AGENT_LLM_PROVIDER=gemini`,
`AGENT_MODEL=gemini-3.8-flash`, `AGENT_LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai`,
`GEMINI_API_KEY`. Computer Use is only available through the native Gemini API and
gets its own adapter in phase 4. Tests never call a live model.

## Components

1. **Demo store** (`demo-store/`). A small fictional shoe store with typical agent
   problems: product listings rendered only by JavaScript, an offer pop-up, a
   custom size picker with no labels, and a delivery check that requires login.
   Fixed catalog and prices in INR so every run is repeatable.
2. **Edge router** (`backend/app/edge/`). A reverse proxy keyed by `Host`. Each
   configured site has one fixed origin. Human traffic and unknown clients are
   passed straight through. Known user-initiated agent fetchers are sent to the
   site's published variant when one exists for the path; otherwise they are
   passed through too. Every agent request is logged.
3. **Variant generation** (phase 2, `app/engines/variants/`). Render up to 50 pages
   in a browser (the demo store, like many stores, only shows content after
   JavaScript runs) and capture the same-origin JSON those pages load. Public
   origins render through the existing fail-closed `BrowserSession`; private
   origins are allowed only with `EDGE_ALLOW_PRIVATE_ORIGINS` for local development,
   in a contained browser limited to GET requests on that one origin. Gemini
   extracts a schema-validated catalog (products, prices, sizes and stock, policies,
   key tasks). The parity check is deterministic: every price must appear in the
   evidence or the variant is rejected; a stock claim that contradicts the evidence
   rejects it, and one the evidence cannot confirm is removed. Templates then render
   HTML and Markdown pages at the original paths, JSON-LD and `llms.txt`.
4. **Action API** (phase 2, `app/engines/variants/actions.py`). Three agent actions:
   `search_products`, `get_product` (sizes, stock, price) and `check_delivery` (by
   PIN code, no login). Exposed as REST (`/agent-api/search`, `/agent-api/products/{slug}`,
   `/agent-api/delivery`) and as an MCP server (`POST /mcp`, Streamable HTTP JSON-RPC).
   Product actions read the published, parity-checked catalog and report its
   `as_of` time. Delivery estimates come from owner-configured rules
   (`edge_sites set-delivery`), never from the store's login-gated endpoint. No
   action performs checkout, payment or account operations.
5. **Session labeling** (phase 3, `app/engines/insights/`, `services/insights.py`).
   Agent requests are grouped into sessions deterministically (site, agent, client
   hash, 30-minute idle gap); a returning agent extends its session, which is then
   relabeled. Gemini labels each session with the task it was attempting, the
   outcome and the failing step, plus an explanation and a suggested fix, from a
   schema-validated response. Labels are stored as `label_source="gemini"` and shown
   as model-judged, separate from rule-verified QA results. QA traffic (the
   `AgentLane-QA` identity) is excluded from sessions and agent statistics.
6. **Dashboard** (phase 3, `/dashboard`, `api/dashboard_routes.py`). Three views:
   agents visiting, success rate per task (model-judged) and top failures with a
   Gemini-written explanation and suggested fix, plus the QA comparison. Every API
   route requires the operator token `EDGE_DASHBOARD_TOKEN` (bearer, constant-time
   comparison; the API is off when unset). Suggestions are never applied
   automatically.
7. **Agent QA** (phase 4, `app/engines/qa/`, `services/qa.py`). Ten fixed, read-only
   demo-store tasks (prices, sizes in stock, cheapest product, returns window, free
   delivery threshold, delivery estimate) run once on the original site and once
   on the variant through the Gemini Computer Use driver (native Interactions API).
   Original runs use a normal browser identity, which the router passes through;
   variant runs use `AgentLane-QA`, which the router serves the variant. The final
   answer is checked by rules against the store's known facts. Inference failures
   and confirmation requests (never auto-confirmed) are ERROR and excluded from the
   rates. Success rates and token usage are stored per run and compared on the
   dashboard. Cart and checkout tasks are left out: the variant offers no cart.

8. **Onboarding and jobs** (phase 5, `services/site_jobs.py`, `cli/jobs.py`). The
   owner adds a site (public host + origin) and starts variant builds, session
   labeling and QA from the dashboard. The API only queues a `site_jobs` row; the
   `jobs` worker (same image, `python -m app.cli.jobs worker`) claims jobs with
   `FOR UPDATE SKIP LOCKED` and records the real outcome. One active job per site and
   kind (partial unique index); jobs past `JOB_MAX_DURATION` are failed. Failures show
   our own error message, or only the exception type for unexpected errors. A rejected
   variant build is a finished job whose result says it was rejected. Locally, QA opens
   `http://<host>:8080` and the contained browser maps `*.localhost` to the edge
   container (`DEV_BROWSER_HOST_RULES`); production uses `https://<host>`.

## Routing rules

- Routed agents are user-initiated fetchers only: ChatGPT-User, Claude-User,
  Perplexity-User and similar, kept in a versioned registry in code.
- Search and training crawlers (Googlebot, Bingbot, GPTBot, ClaudeBot,
  PerplexityBot, CCBot and similar) are never routed. Serving them different
  content is cloaking. They are passed through and logged as crawlers.
- Classification is by user-agent only and can be spoofed; that is acceptable
  because the variant contains only public facts. Signed agent identity is on
  the roadmap.
- The agent-friendly HTML at an original URL is served only to routable agents.
  Explicitly agent-facing URLs (`.md` mirrors, `/llms.txt`, `/agent-api/*`, `/mcp`)
  answer every caller and are logged as agent traffic with the action name.
- The router fails open: if the variant or logging is unavailable, the request is
  passed to the origin unchanged.
- Each site proxies only to its own configured origin; the router never fetches
  client-supplied URLs. Unless `EDGE_ALLOW_PRIVATE_ORIGINS` is on (local Docker only),
  origins must be public host names on ports 80/443 when registered, and the router
  connects through the crawler's DNS-validated transport, so a name that later
  resolves to a private address is refused (502).
- Hop-by-hop headers are stripped; `X-Forwarded-For/Proto/Host` are set. Query
  strings and client IPs are not stored raw: paths are stored without query
  strings and IPs as keyed hashes.

## Data model

| Table | Phase | Key columns |
| --- | --- | --- |
| `edge_sites` | 1 | host (unique), origin_url, name, routing_enabled |
| `agent_requests` | 1 | site_id, received_at, agent, agent_kind, method, path, action, status, duration_ms, served_by, response_bytes, client_hash |
| `site_variants`, `variant_pages` | 2 | site_id, version, status (DRAFT/PUBLISHED/REJECTED/SUPERSEDED), catalog JSON, parity report, evidence summary, llms.txt, model, usage; path, markdown, html |
| `edge_sites.delivery_rules` | 2 | owner-approved delivery estimates for `check_delivery` |
| `agent_sessions` (+ `agent_requests.session_id`) | 3 | site_id, agent, client hash, started/ended, request/error/variant counts, task, outcome, failed_step, explanation, suggested_fix, label_source |
| `site_jobs` | 5 | site_id, kind (build_variant/label_sessions/run_qa), status (PENDING/RUNNING/SUCCEEDED/FAILED), result, detail, created/started/finished |
| `qa_runs` | 4 | site_id, batch, task, target (original/variant), outcome, verification, answer, steps, input/output tokens, duration, model |

All tables come with reviewed Alembic migrations independent of ORM metadata.

## Phases and acceptance

1. **Demo store, router, logging.** The demo store runs in Compose; the router
   serves it on a local host name; a request with a ChatGPT-User agent and one
   with a browser agent both reach the store; only the agent request is logged
   with agent, path, status and timing; Googlebot is passed through and logged as
   a crawler. Covered by integration tests with a mock origin.
2. **Crawl, catalog, variant and actions.** One command builds a variant for the
   demo store; the parity check passes; agents get Markdown pages, `llms.txt` and
   JSON-LD; the three actions work over REST and MCP.
3. **Sessions and dashboard.** Sessions are grouped and labeled; the three
   dashboard views render from real logged traffic.
4. **Agent QA.** Ten fixed tasks run on original and variant with rule
   verification; the comparison view shows success rates and token usage.

5. **Onboarding and jobs.** A site can be added from the dashboard; build, label and
   QA buttons queue jobs that the worker runs and records; the dashboard polls and
   shows queued, running, failed (with reason) and finished states. Covered by
   integration tests with stubbed execution; verified live up to the model call.
6. **Google adapters and agents (planned).** Google's user-initiated agents in the
   registry after checking their published user-agent tokens; a BigQuery
   `RequestLogSink` behind the existing interface (PostgreSQL stays the default);
   Cloud Run service definitions for app, edge, jobs and demo store.

## Out of scope (roadmap)

One-click auto-apply of fixes, signed agent identity, Gemma or private enterprise
deployment, multi-tenant billing and plans, and a full content-parity guard beyond
price and stock.
