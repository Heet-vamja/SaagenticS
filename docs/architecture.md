# Architecture

One Next.js frontend, one FastAPI process, one PostgreSQL database. The scan
pipeline runs a bounded crawler and deterministic static audit, then optionally
runs a separate bounded agent task stage. `AGENT_PIPELINE_ENABLED` controls the
second stage; it is enabled by default. Static checks never call a model and their
score/evidence stay available if inference is unavailable. No external queue, cache
or object store is required.

```text
Browser → same-origin Next.js rewrite → FastAPI routes → service → repository
       → SQLAlchemy → PostgreSQL
```

Routes validate inputs and serialize DTOs. Services own business rules and
transactions. Repositories query and flush but never commit. Request-scoped
sessions are injected into synchronous FastAPI route handlers. The in-process
scheduler uses fresh sessions for background work. Use the single-worker
development deployment described in the [README](../README.md); database-backed
admission and deadlines protect stored jobs, but this is not a distributed worker
fleet.

The App Router frontend uses `src/lib/api.ts` for HTTP requests and pagination and
`src/lib/types.ts` for response types. Workspace pages compose shared components
with loading/error/empty states. Same-origin browser requests are proxied to the
backend. Authentication, accounts and billing are out of scope; do not expose the
workspace API publicly without an access-control layer.

## Domain and persistence

| Model | Responsibility |
| --- | --- |
| `Project` | Named site and scan history |
| `Scan` | Crawl/static status, frozen static score, pipeline progress and summaries |
| `Page` | Bounded metadata for a fetched page; raw HTML is transient |
| `Finding` | Evidence-backed issue with category, severity and recommendation |
| `AgentTaskTest` | Task goal, repeat policy, aggregate outcome, verification counts and deadline |
| `WorkflowTest` | One per-task run, numbered under an optional task parent |
| `AgentStep` | Bounded per-run observation/action evidence, usage and error type |
| `AdmissionBucket` | Hashed peer identity, operation, time window, count and expiry |
| `ReportShare` | Expiring/revocable report capability stored as a token digest |

Task runs reuse `WorkflowTest` and `AgentStep`; no duplicate run or step tables are
created. Legacy workflow rows stay parentless, with outcome unset and verification
`unverified`. The composite task/scan foreign key prevents attaching a run to a
task from another scan. Scan/project deletion cascades through their dependent
records. The explicit Alembic migrations are independent of live ORM metadata and
must be tested against a disposable PostgreSQL database.

Static report weights and checks use the versioned `static-v1` rubric. Agent
outcome, verification and cost are stored separately from the agent-declared
completion status. See [Agent Task Tests](agent-task-tests.md#outcome-and-assurance)
for aggregation and score blending.

## Engine and service boundaries

| Area | Responsibility |
| --- | --- |
| `engines/crawling` | URL scope, robots/sitemap handling, validated fetches and crawl orchestration |
| `engines/static_audit` | Deterministic policy, metadata, semantics and structured-data checks |
| `engines/agent` | Hugging Face-compatible inference, validated tools, browser observations and bounded runner |
| `services/static_audits` | Persist static findings, score and coverage |
| Agent task service | Claim tasks, persist runs, aggregate repeats, recover deadlines and apply admission limits |
| `services/reports` | Compose report data, compare scans, export and enforce share boundaries |

The agent provider first requests native calls with `tool_choice=required` and
temperature zero. When the configured endpoint rejects tool calls, JSON-only output
with the same strict schema is used. Both paths validate the same fixed action set.
There is no heuristic route planner. Website observations are untrusted and remain
separate from the system instruction. The browser routes network requests through
the validated gateway and rejecting proxy; see [browser-agent details](browser-agent.md).

## Scan and agent pipeline

Scan creation persists `PENDING` and schedules bounded crawl/static work after the
HTTP response. Static audit functions are deterministic and run independently of
model availability. Once static report preparation finishes, the enabled agent
stage starts with a separate duration and concurrency budget. Agent failures,
missing credentials and unavailable inference do not erase or relabel static
evidence. Set `AGENT_PIPELINE_ENABLED=false` for a static-only execution.

Agent task and run orchestration currently lives in `services/agents.py`, with
separate policy/admission and result helpers. Task stages use atomic database
claims and durable deadlines. Each run stores steps incrementally; repeat
aggregation uses eligible verified/judged outcomes. Ties stay
inconclusive, and infrastructure failures remain unavailable instead of becoming
site failures. Per-IP scan/task admission uses PostgreSQL upserts and hashed
identities; forwarded addresses are trusted only behind configured proxy CIDRs.
See [agent task policy](agent-task-tests.md).

The static score remains a separate component. If eligible agent results exist,
reports expose the agent component and, when a static score also exists, a combined
score. When no eligible agent results exist, the report states why it retained the
static score. A score is never a substitute for task-level verification details.

## Reports and evidence

Workspace reports include static checks and agent task/run summaries. JSON, CSV and
PDF exports use the same report service; the PDF renderer runs offline with
JavaScript disabled and scanned-site network access blocked. Before/after
comparisons retain separate static/agent coverage. Public shares are bearer
capabilities stored as digests, expire and can be revoked. Shared report evidence
omits internal IDs, raw observations and local paths. Screenshot previews use
opaque HMAC references scoped to the share. See [agent task HTTP interfaces](agent-task-tests.md#http-interfaces).

The system does not include a durable external queue, object storage, user identity
or account/billing features. Production deployment needs its own access control,
artifact retention, edge TLS and egress controls.
