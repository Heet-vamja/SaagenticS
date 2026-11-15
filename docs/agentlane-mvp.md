# AgentLane MVP: agent variants, edge routing and verified task success

Status: phase 1 done; phase 2 implemented, awaiting a Gemini key for the first live build and tests. Reviewed 2026-11-15.

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
5. **Session labeling** (phase 3). Requests are grouped into sessions
   deterministically (site, agent, client hash, 30-minute idle gap). Gemini labels
   each session with the task it was attempting, success or failure and the
   failing step, from a schema-validated response. Labels are marked as
   model-judged, separate from rule-verified QA results.
6. **Dashboard** (phase 3). Three views: agents visiting, success rate per task,
   and top failures with a Gemini-written explanation and suggested fix.
   Suggestions are never applied automatically.
7. **Agent QA** (phase 4). The same task (for example "buy size 9 shoes under
   ₹3,000") runs on the original and on the variant through the Computer Use
   driver inside the existing restricted browser. Success is checked by rules
   against the demo store's order/cart state. Results and token usage are shown
   side by side.

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
- Each site proxies only to its own configured origin. The origin is validated
  with the existing URL checks when the site is configured; the router never
  fetches client-supplied URLs.
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
| `agent_sessions` | 3 | site_id, agent, started/ended, request count, task, outcome, failed_step, label_source |
| `qa_runs` | 4 | site_id, task, target (original/variant), outcome, verification, steps, tokens |

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

## Out of scope (roadmap)

One-click auto-apply of fixes, signed agent identity, Gemma or private enterprise
deployment, multi-tenant billing and plans, and a full content-parity guard beyond
price and stock.
