# TODO

Running list of open work. Newest context first within each section. Remove items
when done; link the commit or doc that closed them if useful.

## Blocked on a Gemini API key

- Set `GEMINI_API_KEY` in `.env`, recreate `edge` and `jobs`. Then use the dashboard buttons
  (Build agent lane, Label sessions, Run agent QA) or the CLIs.
- First live variant build for the demo store; fix what the real extraction output reveals
  (catalog shape, parity rejections, rendering).
- First live session labeling run; check label quality and the failure explanations.
- First live Computer Use QA batch; confirm the Interactions API request/response shapes
  in `engines/qa/computer_use.py` (`steps`/`outputs`, `function_result`, usage field names),
  which were written from documentation without a live call.
- Write tests for phases 2–4 with mocked Gemini responses (extraction, labeling, QA driver,
  QA verification, dashboard overview with data), using the real response shapes captured
  above as fixtures.
- Record the demo: "X of 10 tasks on the original, Y of 10 on AgentLane, N× fewer tokens".

## MVP gaps

- Google's user-initiated agents are not in the router registry (`app/edge/agents.py`).
  Verify the exact published user-agent tokens before adding them.
- BigQuery request-log sink behind `RequestLogSink` (PostgreSQL stays the default).
- Cloud Run deployment (app, edge router, jobs worker, demo store) and Firebase
  Hosting/Auth as optional adapters.
- Optional: one real Shopify store to show the variant works outside the sandbox.
- QA suite has no cart task ("buy size 9 under ₹3,000"); the variant offers no cart. Decide
  whether an `add_to_cart` action belongs in the MVP.

## Product and copy

- Privacy policy and terms do not yet cover edge router logging (agent requests, hashed
  client identity) or agent variants.
- Landing still labels the agent lane "In development"; update only when it is live for
  a real customer.
- Set a real `EDGE_DASHBOARD_TOKEN` in `.env` (local runs used a temporary value).

## Engineering hygiene

- 2 pre-existing failing tests: `test_agent_integration.py::test_scan_pipeline_crawls_then_runs_three_rule_checked_tasks`
  and `::test_agent_inference_failure_keeps_completed_static_scan`.
- Stale browser scripts: `npm run test:states` and `npm run test:free-flow` no longer match
  the current UI.
- Delivery rules can only be set from the CLI (`edge_sites set-delivery`).
- Sites cannot be edited or removed from the dashboard (CLI or SQL only).
- The jobs worker does not hot-reload; run `docker compose restart jobs` after backend
  code changes.
- Variant builds render all pages before the model call; a missing Gemini key is only
  reported after rendering (about 7 s for the demo store). Consider checking first.
