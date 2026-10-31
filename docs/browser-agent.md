# Browser agent

The browser agent powers the bounded runs described in
[Agent Task Tests](agent-task-tests.md). It observes a website, asks the configured
open-weight model for one validated action, applies that action through Playwright,
and repeats within the run limits. The provider and browser process are separate
from the deterministic static audit.

## Model and inference

The model identifier is configured through `AGENT_MODEL`; its default is
`Qwen/Qwen3-4B-Instruct-2507`. Hosted mode (`AGENT_LLM_MODE=hosted`) uses the
Hugging Face router or a Hugging Face Inference Endpoint. Local mode
(`AGENT_LLM_MODE=local`) uses an operator-managed OpenAI-compatible chat-completion
server. The backend does not load model weights. The inference provider remains
Hugging Face compatible; there is no automatic fallback to another vendor.

Hosted setup uses the root `.env`:

```dotenv
HF_TOKEN=<inference-enabled-token>
AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507
AGENT_LLM_MODE=hosted
AGENT_LLM_BASE_URL=https://router.huggingface.co/v1
AGENT_LLM_TIMEOUT=25
AGENT_LLM_RETRIES=2
```

Credentials are never printed in logs or included in browser observations. In
hosted mode, endpoint URL checks constrain traffic to approved Hugging Face HTTPS
hosts; redirects are rejected. The model identifier stays configurable. Confirm
the selected model supports the chat interface, required context and either native
tools or the JSON fallback, and review its weights/license before use.

A separate compatible local server can be selected without sending an HF token:

```dotenv
AGENT_LLM_MODE=local
AGENT_LLM_BASE_URL=http://host.docker.internal:9000/v1
AGENT_MODEL=<compatible-open-weight-model-id>
```

Use `localhost` instead of `host.docker.internal` when running FastAPI directly on
the host. The endpoint is operator configuration and cannot be supplied by the
website, model output or run API. Keep local inference endpoints on a trusted
network; the browser agent's website-fetch protections do not secure arbitrary
operator endpoint configuration.

## Structured decisions

The provider requests native tools with `tool_choice=required` and temperature
zero. Each response must contain exactly one validated call:

```text
click(element_id, reason)
type_text(element_id, text, reason)
navigate(url, reason)
scroll(direction, reason)
finish(success, reason)
give_up(reason)
```

If the endpoint explicitly rejects native tool calls, the provider retries the
decision using a JSON-only schema with the same allowed operations. A server that
silently returns text instead of a tool call gets the same schema fallback. There
is no heuristic planner, predetermined route sequence or fabricated success. The
runner validates arguments and browser IDs before taking action. One malformed
decision retry is allowed; transient provider errors follow the configured retry
limit and infrastructure failures are recorded separately from website outcomes.

The configured run limits are 15 steps, 90 seconds, 32,768 tokens and at least one
second between browser actions. Observations contain at most 150 interactive
elements and 12,000 characters by default. Run history is bounded; loop detection
stops repeated action/URL combinations. These values can be lowered through the
`AGENT_*` settings but are bounded by `Settings` validation.

## Browser boundary

Each run gets an isolated Chromium context with no saved login, cookies or browser
storage. The run begins at the scan-authorized URL. New task runs stay on that exact
authorized host; additional-domain navigation is disabled. A fresh random ID maps
to each observed ElementHandle, so the model cannot send selectors or stale handles.
The model sees the URL, title and bounded interactive controls with compact
accessible names and safe destinations or input types. Visible text used for
deterministic success checks is kept separate from the model prompt. The model
never receives HTML, input values, cookies, headers or credentials. Page content
is untrusted and cannot alter the system rules or the set of available actions.

Browser HTTP requests are routed through the validated fetch gateway and a local
rejecting proxy. The transport checks DNS/address policy and redirects, pins the
validated numeric destination while preserving origin TLS verification, and
rejects unsafe/private destinations. No unrestricted browser route continuation
is available. Cookies and authorization are not forwarded. Browser actions cannot
submit forms, purchase, log in, download files, use arbitrary code or navigate to
unapproved hosts. CAPTCHAs and anti-bot challenges fail safely rather than being
bypassed. These controls are not a substitute for dedicated OS/container
isolation, controlled egress, admission control and authentication in a hostile
multi-tenant production deployment.

## Persistence, replay and screenshots

Each per-run record reuses `WorkflowTest`; `AgentStep` stores bounded action traces,
usage and error categories. A parent task stores repeat policy, aggregate outcome,
verification and counts. Legacy run records remain parentless and unverified.

Workspace users can replay a run and view its screenshots through the existing
per-run read/step/screenshot APIs. Shared reports never contain local file paths,
raw observations or internal database IDs. A shared screenshot is served through
the report capability path, using opaque references bound to an active share. See
[Agent Task Tests](agent-task-tests.md#http-interfaces) for the task APIs and
capability route.

Artifacts are stored under the configured `AGENT_SCREENSHOT_DIR` (the Compose
container path is `/app/artifacts/agent`) and are not included in Git. No artifact
retention scheduler or object store is configured; operators should define cleanup
before exposing the service beyond a trusted environment.

## Tests and verification

Deterministic tests use real Chromium against local fixture pages and a clearly
named mock provider. They validate bounded observations, actions, transport
controls, persistence and error handling without an inference request. The
opt-in real-model tests are separate:

```sh
cd backend
RUN_REAL_HF_TEST=1 uv run pytest tests/test_agent_real_model.py -v -s
```

Run them only after configuring a working model and credentials; they incur the
provider's configured usage. Record model, task, result, steps, elapsed time,
returned token/cost details and any provider errors. Mock-provider results are not
evidence of real-model completion. The current verification status belongs in the
[task test guide](agent-task-tests.md#real-model-verification-status).
