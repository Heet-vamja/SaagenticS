# Browser agent

The browser agent powers the bounded runs described in
[Agent Task Tests](agent-task-tests.md). It observes a website, asks the configured
open-weight model for one validated action, applies that action through Playwright,
and repeats within the run limits. The provider and browser process are separate
from the deterministic static audit.

## Model and inference

Provider is selected with `AGENT_LLM_PROVIDER`. Local development defaults to
`osaurus` with model ID `raptor-0.6-4b-jang_6m`; Osaurus runs Raptor on the Mac and
serves an OpenAI-compatible API. The FastAPI backend does not load model weights.
`AGENT_MODEL`, `AGENT_LLM_BASE_URL` and `AGENT_LLM_TIMEOUT` configure the selected
provider. Provider switching is explicit; an Osaurus failure never triggers
hosted inference.

For Docker Desktop on macOS, the root `.env` uses:

```dotenv
AGENT_LLM_PROVIDER=osaurus
AGENT_MODEL=raptor-0.6-4b-jang_6m
AGENT_LLM_BASE_URL=http://host.docker.internal:1337/v1
AGENT_LLM_TIMEOUT=60
OSAURUS_API_KEY=<access-key-if-required-for-network-exposure>
```

Start and check the API on the Mac with `osaurus serve` and
`curl --fail http://127.0.0.1:1337/v1/models`.

Osaurus's API normally binds to Mac loopback, which containers cannot reach. Enable
network exposure in Osaurus for Docker Desktop (or use `osaurus serve --expose`),
and configure an access key if Osaurus requires one for exposed requests. For
native FastAPI development, set the URL to `http://127.0.0.1:1337/v1` and keep
network exposure disabled. Check the live provider/model from the backend with
`curl --fail http://localhost:8000/health/llm`; it only calls `/v1/models`, not
inference. The API key is sent only as an Authorization header and is not logged.
Osaurus normalizes Raptor's native `<tool_call>…</tool_call>` output into the
OpenAI-compatible `choices[].message.tool_calls[]` response, whose function
arguments are JSON text. AgentLane accepts exactly one such call and validates
the canonical action with Pydantic before Playwright sees it. See the [Osaurus API
guide](https://github.com/osaurus-ai/osaurus/blob/main/docs/OpenAI_API_GUIDE.md#functiontool-calling)
and [Raptor 0.6 model card](https://huggingface.co/OsaurusAI/Raptor-0.6-4B-JANG_6M).

Hugging Face remains an explicit alternative:

```dotenv
AGENT_LLM_PROVIDER=huggingface
AGENT_LLM_MODE=hosted
AGENT_MODEL=Qwen/Qwen3-4B-Instruct-2507
AGENT_LLM_BASE_URL=https://router.huggingface.co/v1
AGENT_LLM_TIMEOUT=25
HF_TOKEN=<inference-enabled-token>
```

The HF provider keeps its HTTPS host restrictions and credential handling. The
endpoint and model remain operator configuration and cannot be supplied by website
content, model output or run APIs.

## Structured decisions

The provider requests native tools with `tool_choice=required`. Hugging Face uses
temperature zero; Osaurus uses Raptor 0.6's declared `temperature=1.0` and
`top_p=0.95` profile. Each response must contain exactly one validated call:

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
