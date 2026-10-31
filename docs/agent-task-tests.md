# Agent task tests

Agent task tests are a separately bounded stage after the deterministic static
audit. Static checks never call an LLM. The static score and its evidence remain
available if inference is unconfigured, unavailable, over budget or times out. Set
`AGENT_PIPELINE_ENABLED=false` to run static-only scans. Manual task starts use the
same task and anonymous admission policy.

## Task and run policy

The automatic anonymous policy enables the built-in pricing, contact and signup/
demo-form tasks. It allows at most two tasks per scan and one run per task. Internal
task creation defaults to two runs and allows at most three; anonymous requests
that exceed the configured free cap are rejected. `FIND_DOCUMENTATION` remains a
legacy/manual task type and is excluded from the default automated set.

Each run is stored as a `WorkflowTest`, with its numbered `AgentStep` trace. An
`AgentTaskTest` groups the runs and stores the aggregate, verification policy,
consistency and counts. Legacy runs have no task parent and remain `unverified`;
they are not retroactively graded or included in the agent score.

| Limit | Default | Setting |
| --- | ---: | --- |
| Agent pipeline | enabled | `AGENT_PIPELINE_ENABLED` |
| Internal repeats per task | 2, max 3 | `AGENT_RUNS_PER_TASK` |
| Anonymous tasks per scan | 2 | `AGENT_FREE_TASK_LIMIT` |
| Anonymous runs per task | 1 | `AGENT_FREE_RUNS_PER_TASK` |
| Per-run wall-clock duration | 90 seconds | `AGENT_DURATION` |
| Per-run steps | 15 | `AGENT_MAX_STEPS` |
| Per-stage duration | 600 seconds | `AGENT_STAGE_DURATION` |
| Concurrent agent stages | 2 | `AGENT_MAX_ACTIVE` |
| Total inference token budget per run | 32,768 | `AGENT_TOKEN_BUDGET` |
| Delay between browser actions | at least 1 second | `AGENT_ACTION_DELAY` |
| Maximum observed interactive elements | 150 | `AGENT_MAX_ELEMENTS` |
| Observation text | 12,000 characters | `AGENT_OBSERVATION_CHARS` |

The policy snapshot stored with a task records the effective limits. Static crawl
time and agent time have separate budgets. A task deadline is durable so recovery
can mark interrupted work failed after a process restart.

## Provider and action behavior

`AGENT_MODEL` selects the model identifier; the default is
`Qwen/Qwen3-4B-Instruct-2507`. Hosted mode uses the Hugging Face router or an
operator-configured Hugging Face Inference Endpoint. `AGENT_LLM_MODE=local` uses a
separate operator-managed, OpenAI-compatible endpoint and does not send HF
credentials. The model and endpoint are configuration; request bodies cannot
override either. No alternative provider is selected automatically.

The provider first requests native tool calls with `tool_choice=required` and
temperature zero. It accepts only one schema-valid call from the bounded set:

- `click(element_id, reason)`
- `type_text(element_id, text, reason)`
- `navigate(url, reason)`
- `scroll(direction, reason)`
- `finish(success, reason)`
- `give_up(reason)`

If the endpoint explicitly lacks tool-call support, the provider asks for a
JSON-only action matching the same schema. This fallback does not use a hardcoded
plan or success result. Malformed output is retried once at the runner level;
transient inference errors use the configured bounded retry count. Token usage and
estimated cost are recorded when available. Set
`AGENT_INPUT_COST_PER_MILLION` and `AGENT_OUTPUT_COST_PER_MILLION` in USD per
million tokens to estimate cost. Blank/unconfigured rates mean cost is unknown.

The model sees only the current URL, page title, and a bounded list of interactive
controls with accessible names and safe destinations/input types. Visible page
content is inspected internally by deterministic success rules and is not passed
as general instructions to the model.
Element identifiers are fresh per observation; page content is treated as
untrusted. The runner limits the action loop to 15 steps and 90 seconds, retains
only recent summarized history, and enforces action pacing and repeat-loop checks.
New task runs stay within the exact host authorized by the scan. No login, purchase,
form submission, credentials, arbitrary selectors or model-generated code is
allowed. See [browser-agent details](browser-agent.md) for the transport boundary.

## Outcome and assurance

Outcomes are `SUCCEEDED`, `FAILED`, `INCONCLUSIVE` and `UNAVAILABLE`. Assurance is
shown separately:

- **rules**: deterministic evidence supports a site outcome after the model chose
  a relevant action;
- **judged**: the configured model judged a bounded observation; this is lower
  assurance and is identified in reports;
- **unverified**: there is no independent verification, including legacy runs.

The task aggregate is the majority outcome among eligible runs. A tie is
`INCONCLUSIVE`; inconsistent repeat outcomes are disclosed. Infrastructure-only
outcomes such as provider billing, timeout or network failures are `UNAVAILABLE`
and excluded from site scoring. They do not become website failures.

When static and eligible agent components both exist, the combined readiness score
uses the configured `AGENT_SCORE_WEIGHT` (default 0.45):

```text
combined = static × (1 − agent_weight) + agent × agent_weight
```

Task success rates are averaged per task, so a task with more runs does not receive
more weight. If no eligible agent evidence exists, the report retains the static
score and states the fallback reason. If a static sample is absent but eligible
agent evidence exists, the report labels the score `AGENT_READINESS`; when both
components exist it is `COMBINED_READINESS`. An agent-only score is explicitly
limited coverage. The static component and rubric remain unchanged.

## Admission limits and trusted proxies

PostgreSQL stores bounded per-window buckets using a hash of the normalized peer
identity and operation. Defaults are 10 scan submissions and 20 manual task starts
per peer per hour (`AGENT_IP_SCAN_LIMIT`, `AGENT_IP_TASK_LIMIT` and
`AGENT_IP_WINDOW_SECONDS`). Expired buckets are cleaned during admission. This is
anonymous abuse control, not user identity or authentication.

By default the socket peer is the client identity. An `X-Forwarded-For` header is
ignored unless the direct socket peer belongs to `AGENT_TRUSTED_PROXY_CIDRS`. Only
then is the proxy chain walked toward the first untrusted hop. Configure this list
only for proxies you operate. The edge proxy must remove any client-supplied
forwarded headers and write its own chain; never trust arbitrary inbound
`X-Forwarded-For` values. Behind an unconfigured proxy, callers share the proxy's
rate bucket, which is intentionally conservative.

The Compose ports bind to localhost for development. For a production edge, keep
the API private behind a TLS-terminating reverse proxy, restrict direct API access,
overwrite forwarding headers at that proxy, and set only its actual CIDRs in
`AGENT_TRUSTED_PROXY_CIDRS`. Do not add a CIDR for all public addresses.

## HTTP interfaces

Agent task operations use these versioned routes:

| Method and route | Purpose |
| --- | --- |
| `GET /api/v1/agent-config` | Safe model identifier, supported task types and limits; no credentials |
| `POST /api/v1/scans/{id}/agent-tasks` | Start a built-in task, subject to policy and admission limits |
| `GET /api/v1/scans/{id}/agent-tasks` | List task aggregates and progress |
| `GET /api/v1/agent-tasks/{id}` | Read an aggregate task |
| `GET /api/v1/agent-tasks/{id}/runs` | Read its numbered per-run results |

The create body accepts a task type and optional repeat count only. It cannot set
a provider, model, URL, headers, cookies or credentials. Existing `/agent-tests`
read/step/screenshot routes remain compatibility views of individual runs.

Reports, JSON/CSV/PDF exports and comparisons carry static and agent components,
verification, task/run summaries, coverage and fallback reason. Workspace replay
uses the run viewer. Shared reports omit raw observations, local file paths and
internal IDs. When a share contains step screenshots, its `screenshot_url` points
to the same-origin capability route:

```text
GET /api/v1/shares/{token}/evidence/{run_ref}/{step_ref}.png
```

The run and step references are opaque HMAC capabilities rather than database IDs.
They are scoped to an unexpired share. Do not copy workspace screenshot URLs or
filesystem paths into shared report payloads.

## Configuration and model switching

All values can be set in the root `.env`; see [.env.example](../.env.example).
Restart/recreate the backend after changing settings:

```sh
docker compose up -d --force-recreate backend
```

Hosted Hugging Face mode:

```dotenv
HF_TOKEN=<inference-enabled-token>
AGENT_LLM_MODE=hosted
AGENT_LLM_BASE_URL=https://router.huggingface.co/v1
AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507
```

To switch to a separately operated compatible local endpoint:

```dotenv
AGENT_LLM_MODE=local
AGENT_LLM_BASE_URL=http://host.docker.internal:9000/v1
AGENT_MODEL=<compatible-open-weight-model-id>
```

When using local mode, do not put inference credentials in the request. For native
development, use `http://localhost:9000/v1` instead of `host.docker.internal`. A
compatible endpoint must support chat completions and either native tool calls or
JSON-only generation. Verify model weights, licensing, context length and endpoint
behavior independently.

## Setup and verification

Copy `.env.example` to `.env`, set `HF_TOKEN` for hosted inference, then start the
development stack:

```sh
cp .env.example .env  # only when .env does not already exist
docker compose up --build -d --wait
```

The deterministic tests use fixture pages, real Chromium and mocked model
decisions. They do not make hosted inference calls. Use the disposable PostgreSQL
test database described in the [README verification section](../README.md#verification-commands):

```sh
cd backend
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q -k 'not real_model'
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic check
```

The opt-in real-model command is:

```sh
RUN_REAL_HF_TEST=1 uv run pytest tests/test_agent_real_model.py -v -s
```

It sends requests to the configured endpoint while keeping browser traffic on the
local test fixture. It requires usable credentials/endpoint access and is not part
of deterministic CI. Report actual outcomes, steps, duration, usage and errors; do
not infer success from the task card or mock tests.

### Real-model verification status

**Pending.** No live Hugging Face run is claimed by this documentation update. The
completion record must be filled after an explicit bounded run with the configured
model, including each attempted task, outcome, steps, elapsed time, token/cost data
when returned, and any provider or network error. Never include credentials,
private prompts or hidden reasoning in that record.
