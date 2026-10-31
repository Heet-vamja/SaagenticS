# Real AI browser agent

Feature 2 adds a single Observe → Reason → Act loop to the modular monolith.
`WorkflowTest` stores agent executions and `AgentStep` stores bounded observations,
validated actions, observable results and concise explanations. No hidden reasoning
or model thinking fields are stored. Completion means **agent-reported completion**,
never independently verified success; this feature never assigns `PASSED` or a score.

## Model and inference

The default is **Qwen/Qwen3-4B-Instruct-2507** (Apache 2.0), a non-thinking,
instruction-tuned open-weight model. Its model card documents Transformers, vLLM
and SGLang serving. Availability was checked against Hugging Face's model metadata;
HF listed a live conversational inference mapping. Hosted routing is selected by
Hugging Face, not a hardcoded paid provider. No OpenAI, Anthropic or Gemini model
is used. HTTPX implements the compatible chat-completions transport directly.

Sources: [model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507),
[HF chat completion](https://huggingface.co/docs/inference-providers/tasks/chat-completion).

Native tool calling is not assumed. The system prompt supplies a JSON action
schema, and Pydantic rejects invalid JSON, unknown operations, extra arguments and
oversized fields. `AGENT_STRUCTURED_OUTPUT=true` additionally requests server-side
JSON-schema constrained generation, only when the selected endpoint supports it.
There is no heuristic fallback planner, fixed route sequence or mocked production
provider. The model chooses the next action from each actual observation.

### Hosted setup

Put the following in the root `.env` (ignored by Git), using an inference-enabled
Hugging Face credential. Do not paste tokens into source, commands, screenshots or
bug reports. Rotate any credentials shared in a chat before production use.

```dotenv
HF_TOKEN=<your-inference-enabled-token>
AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507
AGENT_LLM_MODE=hosted
AGENT_LLM_BASE_URL=https://router.huggingface.co/v1
AGENT_LLM_TIMEOUT=25
AGENT_STRUCTURED_OUTPUT=false
```

`HF_TOKENS` is accepted as a compatibility input, but only its first token is used;
there is no automatic account or quota rotation. `HF_TOKEN` takes precedence.
Hosted credentials are restricted to the HF HTTPS router or an explicitly configured
`*.endpoints.huggingface.cloud` endpoint. HTTP redirects from inference are rejected.
Only `Qwen/` model IDs are supported in this MVP; verify any alternative model's
weights/license and instruction/JSON compatibility before configuration.

Setup checks for all supplied credentials returned **HTTP 402**. This means
real-model task completion is **UNVERIFIED**, regardless of passing mock-model
browser tests. Configure inference credits/permissions or a working local endpoint
before expecting autonomous model-driven results. No credits are purchased and no
proprietary provider is substituted automatically. The UI records the failure.

### Separate local model server

The same provider can call an operator-configured compatible server. It does not
load model weights in FastAPI. For example, on a suitable separate GPU host:

```sh
vllm serve Qwen/Qwen3-4B-Instruct-2507 --max-model-len 8192 --port 9000
```

```dotenv
AGENT_LLM_MODE=local
AGENT_LLM_BASE_URL=http://your-model-host:9000/v1
AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507
```

Use `host.docker.internal` for a server on a Docker Desktop host. Native inference
with Transformers is also possible behind a separate compatible server but is not
bundled. Hardware sizing depends on precision and context: full-precision 4B weights
alone require roughly 8 GB before runtime/cache overhead; use a suitable GPU/quantized
serving setup. This local server setup has not been demonstrated in this environment.
HF credentials are never sent in local mode. This operator-only endpoint is not
configurable by website content, model output or the agent-test API.

## Running

```sh
docker compose up --build -d --wait
```

Chromium and OS dependencies are installed in the backend image. Open a scan's
**AI Agent Testing** section, select a task and click **Run Agent Test**. Optional
additional domains must be explicitly entered (e.g. `docs.example.com`); `www` is
not implicitly trusted. Each run has its own browser process/context and no saved
login, cookies or browser storage. Task templates are pricing, documentation and
signup/demo-form discovery; none contain website routes or selectors.

Native setup:

```sh
cd backend
uv sync --frozen
uv run playwright install --with-deps chromium
uv run alembic upgrade head
```

The bootstrap navigation opens only the user-authorized starting URL and is stored
as step 1. All subsequent actions are selected by the configured LLM. The 15-step
budget includes this bootstrap step. Maximum execution duration is 120 seconds,
maximum consecutive invalid actions/tool failures is 3, and transient inference
requests have at most 2 retries. Fatal inference configuration/billing errors stop
immediately after recording a failed step. Limits also cover output tokens (700 by
default), observation characters (12000), elements (60), HTTP requests (150), response
bytes (2 MB through the existing fetcher), redirects (5) and tool timeouts.

## Network and action safety

Every intercepted browser HTTP request (navigation, redirect, script, image, etc.)
is fulfilled by the existing validated HTTPX transport. All DNS answers are checked,
only a validated numeric IP is passed to TCP, TLS verifies the original hostname,
and each new connection is revalidated. There is no `route.continue_()` or unrestricted
`route.fetch()` path. Cookies, authorization and browser headers are not forwarded.
Only GET is permitted; unsupported/compressed responses, downloads, external or
private destinations, unsafe query parameters and obvious state-changing paths
fail closed. Robots permissions are respected for fetched resources.

Chromium's own networking is pointed at a local rejecting proxy, including loopback
using `<-loopback>`. Direct DNS, QUIC and non-proxied WebRTC UDP are disabled. This
prevents falling back to a direct connection if an intercept is missed. Service
workers, WebSockets, child-frame navigation, popups and browser network API escape
paths are blocked. Responses receive a restrictive CSP: no forms, workers, frames,
objects or script-initiated connections. A real Chromium test removes routing and
checks that a private loopback listener receives **zero** connections.

Tools never accept code or model-generated CSS selectors. Observation IDs are random
per snapshot and mapped to actual ElementHandles; stale IDs and unavailable elements
are rejected. Observations contain visible text/headings, roles, labels, required/
disabled/expanded states and links; never HTML dumps, cookie/storage values, input
values or headers. Known token/password/email patterns are redacted. Only non-sensitive
search/filter inputs can be filled; form-submit/reset and state-changing controls
are rejected. Browser form submission is also prevented with CSP, DOM hooks and the
network method restriction. Downloads and file choosers are cancelled. CAPTCHAs,
authentication and anti-bot pages cause failure rather than circumvention.

Untrusted page text appears only in a separately delimited observation message;
the fixed system prompt, strict action schema and tool/network permissions remain
outside the website's control. No prompt alone is treated as a security boundary.

## Persistence, APIs and evidence

Migration **0003** extends `workflow_tests` and introduces `agent_steps`. It widens
the existing workflow status column/check to support `COMPLETED` while retaining
legacy statuses. `PASSED` is never used for agent-declared completion.

- `POST /api/v1/scans/{scan_id}/agent-tests` — task type and optional allowed domains;
  returns an initial PENDING execution immediately.
- `GET /api/v1/scans/{scan_id}/agent-tests` — paginated execution history.
- `GET /api/v1/agent-tests/{test_id}` — state, model, metrics and declared result.
- `GET /api/v1/agent-tests/{test_id}/steps` — paginated trace.
- `GET /api/v1/agent-tests/{test_id}/steps/{step_id}/screenshot` — bounded local evidence.

Every response includes `verification: NOT_INDEPENDENTLY_VERIFIED` on executions.
Screenshots mask form inputs and are never sent to the model. Files are served only
through a UUID-associated database step, with path containment checks and `no-store`.
Raw filesystem paths are omitted from DTOs. `backend/artifacts` is ignored by Git
and Docker build context and mounted for development persistence. No retention
scheduler or object store is added; operators must clean up artifacts when appropriate.

Background tasks use the existing thread-pool/independent-session pattern. Execution
claims are atomic, steps commit incrementally, failures are persisted and durable
deadlines allow the periodic recovery loop to fail interrupted runs after restarts.
There is no durable queue, resume or fleet-wide concurrency limiter. Use a single
worker for this trusted local MVP. Structured events record IDs, step/action counts,
failures and duration without prompts, page content or credentials.

## Tests and real-model verification

The local fixture website lives in `backend/tests/fixtures/agent_site`: homepage,
pricing, documentation and a non-submitted signup form. A test-only mock HTTP
transport serves those files to **real Chromium** under a fictional public origin.
No production private-IP exception is introduced. Deterministic tests use a clearly
named mock LLM; these are not evidence that a real model completed the workflows.

Use the migrated disposable PostgreSQL database from the README:

```sh
cd backend
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic check
```

Real model + real browser tests are opt-in and never substitute a mock LLM:

```sh
RUN_REAL_HF_TEST=1 uv run pytest tests/test_agent_real_model.py -v -s
```

Those tests verify the fixture destination and expected pricing/required-field
facts. They require a usable inference endpoint. The default suite explicitly
skips them as **REAL MODEL UNVERIFIED**. Implementation verification: **72 deterministic
tests passed and 3 real-model cases skipped**. A separately enabled real pricing
test reached Hugging Face and failed with HTTP 402. A headless UI smoke check verified task selection, starting execution, polling,
the persisted inference-failure trace and screenshot access. This is not
verification of real-model task success. A 402, unauthorized credential, unavailable
model or timeout is a failed real integration attempt, not a successful agent demo.

## Practical limitations

The conservative CSP and strict first-party GET-only resource scope intentionally
limit heavily dynamic SPAs, third-party assets, embedded forms and authenticated
workflows. Generic server-side GET side effects cannot be inferred perfectly;
this is a trusted local MVP, not a production hostile-browser sandbox. Public visible
text may contain information that pattern redaction cannot recognize; use only
public, unauthenticated websites. Screenshots have the same public-content caveat.
Deploy with dedicated OS/container isolation, controlled egress, admission limits,
authentication and artifact retention before exposing execution to untrusted tenants.

Model results are not independently verified. A separate deterministic outcome
verifier is the recommended next feature; no scoring or AI recommendations are added.


## Implementation file map

New engine files: `backend/app/engines/agent/{actions,privacy,provider,browser,runner}.py`.
New integration files: `backend/app/core/agent_logging.py`,
`backend/app/repositories/agent_tests.py`, `backend/app/services/agents.py`,
`backend/app/schemas/agent.py`, `backend/app/api/agent_routes.py`, and
`backend/alembic/versions/0003_real_browser_agent.py`.
New frontend component: `frontend/src/components/agent-testing.tsx`.
New tests: `backend/tests/agent_fixtures.py`, `test_agent_provider.py`,
`test_agent_browser.py`, `test_agent_runner.py`, `test_agent_integration.py`,
`test_agent_real_model.py`, and four HTML files under `tests/fixtures/agent_site`.

Existing files extended: backend settings, domain models, application routing,
background deadline recovery, crawler FetchResult/redirect control, test fixtures,
pyproject/uv.lock and Dockerfile; frontend scan detail, API client and response types;
Compose, example environment, ignore files, README, AGENTS and architecture/development docs.
The ignored local `.env` holds the configured credential and is not a deliverable.
