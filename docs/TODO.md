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

- First real Google Cloud deploy following `docs/deploy-cloud-run.md` (draft): jobs as a
  worker pool or always-on service, BigQuery sink verified against a real table. The
  production frontend image (`--target prod`) is built and verified locally.
- Firebase Auth for the dashboard (optional adapter; the operator token is used today).
- Google's agent tokens change: `Google-NotebookLM` is accepted until August 2026 per
  Google's fetcher docs; drop it from the registry after that.
- Optional: one real Shopify store to show the variant works outside the sandbox.
- QA suite has no cart task ("buy size 9 under ₹3,000"); the variant offers no cart. Decide
  whether an `add_to_cart` action belongs in the MVP.

## Product and copy

- Review the new "AgentLane router and agent lane" sections in `/privacy` and `/terms`
  (drafted 2026-11-15 from the code's actual behavior). Operator name, contact and
  jurisdiction are still placeholders in `frontend/src/lib/legal.ts`.
- Landing still labels the agent lane "In development"; update only when it is live for
  a real customer.
- Set a real `EDGE_DASHBOARD_TOKEN` in `.env` (local runs used a temporary value).

## Engineering hygiene

- The jobs worker does not hot-reload; run `docker compose restart jobs` after backend
  code changes.
