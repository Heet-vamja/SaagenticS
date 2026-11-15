# AgentReadiness implementation plans

## Fix Center implementation plan (2026-11-01)

> This was an earlier task that the user explicitly stopped. Its checklist is
> retained as history; the active work below is the Free AI Readiness Scan.

### Existing architecture inspected

- FastAPI API routers live in `backend/app/api`; report endpoints are in
  `report_routes.py`, composed by `ReportService` in `services/reports.py`.
- Static findings are persisted in `Finding` with category/severity/title,
  structured evidence, and deterministic recommendation. Existing comparison
  uses check identity and coverage; report links are hashed, expiring bearer
  capabilities.
- SQLAlchemy domain models are centralized in `backend/app/models/domain.py`;
  Alembic revisions are numbered and explicit (`0001`–`0005`).
- Frontend is Next.js App Router. The customer report is
  `frontend/src/components/customer-report.tsx`; API calls and DTOs are in
  `frontend/src/lib/api.ts` and `types.ts`.
- Existing JSON/CSV/PDF export paths consume the report projection. Scan work
  is in-process and should not gain a new queue/job system for deterministic
  generation.

### Design and data model

- Add a pure deterministic `engines/fix_center` package: versioned JSON prompt
  templates, a fixed finding-rule mapping, prompt rendering, site-derived asset
  generators, and strict validators. It may consume only persisted scan,
  finding, and crawl-page evidence; never infer business facts.
- Persist generated prompts (`finding_id`, variant, template version, content),
  generated assets (`scan_id`, type, version, content, validation result), and
  append-only status events (`finding_id`, status, optional asset/prompt refs,
  timestamp). Use finding identity by rule + page key across scans for
  verification; only a finding absent from a completed comparable scan becomes
  `VERIFIED_FIXED`. A missing/unknown check is not a pass.
- Add a reversible Alembic revision after `0005`, uniqueness/index/check
  constraints, and ORM relationships without changing existing report/scanner
  semantics.
- Add versioned `/api/v1/scans/{id}/fix-center` read/generate, prompt/asset
  access, copy/download event tracking, status update, and ZIP fix-pack routes.
  Shared report-token access must use the same live share validation and
  redaction boundary; no internal IDs/paths or query-string secrets leak.
- Add a Fix Center on the existing customer report with finding groups,
  three prompt variants, generated asset preview/copy/download, status controls,
  missing-input disclosure, and re-scan confirmation. Export report projection
  fields to JSON/CSV/PDF and include an asset/prompt ZIP.
- Document limitations: crawled data cannot supply all business identity fields;
  omit unavailable schema properties and list them as missing inputs. Robots
  policy generation must preserve an explicit user-selected preset and show a
  diff; no generated policy is applied automatically.

### Small task checklist and dependencies

- [x] F0: Record this plan and interfaces before implementation. Parent.
- [ ] F1: Deterministic prompt template files, shared prompt DTO/rendering,
  finding-rule mapping and pure tests. Depends F0. Strong-model subagent owns
  only `backend/app/engines/fix_center/prompts*` and their focused tests.
- [ ] F2: Deterministic asset generators/validators (llms.txt, JSON-LD,
  robots policy, sitemap suggestions), AI bot config, and unit tests. Depends
  F0; may share only the new `engines/fix_center/assets*` package files with
  F1 through a pre-agreed package layout; no overlapping files. Strong-model
  subagent owns only asset modules/config and asset tests.
- [ ] F3: ORM entities and explicit reversible migration for prompts, assets,
  and status events. Depends F0. Small-model subagent owns `domain.py`, one new
  migration, and isolated model/migration tests; no service/API/frontend files.
- [ ] F4: Pure finding matching and re-scan verification policy plus tests.
  Depends F1/F3 contract. Strong-model subagent owns `verification.py` and its
  unit tests; it does not modify models or report service.
- [ ] F5: Repository/service/API orchestration, permissions for shared reports,
  pagination/size bounds, tracking and fix-pack endpoint. Depends F1–F4.
  Parent owns backend API/service/schema/repository integration.
- [ ] F6: Report export projection (JSON/CSV/PDF) and ZIP fix pack. Depends F5.
  Parent owns existing report/export files to avoid overlap.
- [ ] F7: Customer report Fix Center UI and frontend API/types. Depends on
  published F5 route/DTO contract. Small-model subagent owns only new
  `fix-center.tsx` and designated new UI tests; parent integrates into report.
- [ ] F8: Integration tests for known-issue fixture → prompts/assets → fixed
  copy → re-scan verification, API permission tests, docs and README link.
  Depends F5–F7. Parent owns backend integration tests and README; small-model
  subagent owns new `docs/fix-center.md` only.
- [ ] F9: Full backend suite, Ruff, migration/schema checks, frontend lint/type
  checks/build/UI state checks, ZIP and privacy review. Depends F8. Parent.

### Risks / defaults

- No authentication is present; workspace endpoints follow existing workspace
  access conventions, and shared access is limited to an unexpired, unrevoked
  report token. Keep new shared payloads to report-safe prompts/assets only.
- Prompt-copy/download statuses are interaction signals, not evidence a user
  applied a fix. Only completed re-scan rule/page matching can set verified.
- A generated asset is persisted only after validation; failed generation is an
  error with missing fields, never an unchecked download.
- `robots.txt` defaults need explicit selection; initial generation uses
  `maximize_ai_discoverability` only when the caller selects it, and always
  shows the before/after diff. The product must not silently alter policy.
- Before/after findings can differ in page identity due to URL normalization;
  match with canonical URL/rule when available, then normalized evidence URL.
- Avoid changes to scan scoring: verification is a separate report dimension.

## Free AI Readiness Scan & Report milestone (2026-11-01)

### Current-state audit

- Already present: homepage URL field, internal project/scan creation APIs,
  bounded crawler, deterministic site/page audits, database findings, static
  score and coverage summary, top-five priorities, report API and JSON/CSV/PDF,
  expiring report capabilities, and a customer-facing `/results/{scan_id}` view.
- Incomplete for this milestone: submission currently lists/creates a project
  in the browser and exposes the scan UUID in the results URL; no URL-only
  endpoint returns an opaque report capability; per-scan free crawl cap is not
  enforced; default scan execution can run the optional agent stage; score
  dimensions/weights differ from this milestone; no focused integration test
  proves a no-LLM anonymous scan from URL entry to free report.
- Reuse existing crawl, audit evidence, scanner SSRF/rate controls, report token
  storage, and report views. Do not delete or replace the project workspace or
  agent APIs.

### Contracts and design

- Add `POST /api/v1/free-scans` accepting only `website_url`. It internally
  validates the public URL, creates/reuses internal Project/Scan records,
  consumes the existing spoof-resistant admission bucket, sets a scan mode with
  page limit 10 and `agent_enabled=false`, creates a short-lived report share,
  schedules existing in-process scan execution, and immediately returns an
  opaque report token/path plus pending status. No project ID or scan ID is
  returned.
- Per-scan crawler settings are derived from persisted `scan_mode`; free scans
  cap pages at 10 even when global limits are higher. They run crawler and
  deterministic static audit only; the agent/browser LLM stage is not invoked.
- Public report token uses the existing expiring/revocable share validator.
  Add `GET /api/v1/free-reports/{token}` as a customer-safe projection: score,
  coverage/provisional label, top 3 evidence-backed findings, human-readable
  statuses, and report progress. Keep internal UUIDs, project lists and agent
  execution traces out. Retain existing workspace and shared report APIs.
- Score rubric v2 has Discoverability 30%, Content understanding 25%,
  Structured data 20%, Agent usability 25%. Only evaluated checks contribute;
  if an entire category is unavailable, omit it and normalize remaining
  weights. Infrastructure/provider failures are excluded. Since the free path
  does not run an agent, Agent usability is explicitly untested and excluded;
  score is preliminary and explains coverage. Keep old stored rubric summaries
  readable and deterministic.
- Keep “Unlock fixes” as a clearly marked coming-soon CTA. No payment logic.

### Small task checklist and dependencies

- [x] M0: Record current-state audit, contracts and work breakdown. Parent.
- [x] M1: Implement URL-only free scan request/response schemas, project/scan
  creation, opaque report share, rate-limit identity and endpoint. Depends M0.
  Parent owns backend API/service/schema changes.
- [x] M2: Enforce per-scan max-10 pages and skip agent stage for free scan mode;
  preserve regular scan execution. Depends M1 contract. Parent owns crawl
  orchestration and focused regression tests.
- [x] M3: Implement rubric-v2 deterministic score projection and top-3
  customer-safe report schema/endpoint, preserving old workspace report
  contracts. Depends M0; parallel with M1. Parent owns report/schema files.
- [x] M4: Simplify homepage submit flow and create polished URL-token scanning /
  report journey, score, top 3 insights, coverage states, and coming-soon CTA.
  Depends M1/M3 API contract. One subagent owns landing + new free-report
  components/pages only; parent integrates if needed.
- [x] M5: Add local fixture integration coverage: valid/missing metadata, broken
  URLs, robots restrictions, malformed/missing sitemap and JSON-LD, unreachable
  target, partial scan, duplicates, no agent-provider invocation, page cap,
  opaque token permissions and score stability. Depends M1–M3. Test subagent
  owns a dedicated new test file only.
- [x] M6: Run focused/full backend tests, Ruff, migration check (no migration
  expected unless implementation proves otherwise), frontend lint/typecheck/
  build and browser/UI verification where available. Update README with native/
  Docker run instructions and limitations. Parent owns README due pre-existing
  user edits.

### Verification evidence

- Full backend suite: **170 passed, 5 skipped**, with one existing Starlette /
  httpx deprecation warning. Free-scan integration tests cover URL-only
  submission, opaque/revocable links, duplicate active-scan reuse, 10-page cap,
  no agent/LLM provider invocation, successful and partial fixture crawls,
  inaccessible and robots-denied targets, sitemap/JSON-LD/metadata findings,
  score normalization, and evidence-backed top insights.
- Ruff check and formatting pass. Alembic `check` reports **No new upgrade
  operations detected**; this feature required no schema changes.
- Frontend lint, TypeScript, Prettier and production build pass. Browser smoke
  test covered homepage submission → opaque report URL → status polling → score,
  evidence and coming-soon CTA. Desktop and mobile homepage/report layouts had
  no overflow or WCAG 2.1 AA axe violations. Screenshots are in
  `/private/tmp/agentreadiness-free-flow/`.
- No unrestricted public-site crawl was run. Backend fixture tests use mocked
  HTTP transport; browser smoke test mocks only API responses.

### Risks / defaults

- URL domain/canonical matching must not weaken DNS, redirect, robots, rate or
  SSRF protections. Reject private destinations through the existing validator.
- Existing reports are stored with an earlier rubric; never relabel their
  historical score as rubric v2. Mark the score contract/version explicitly.
- If the crawl itself is denied or unavailable, show an honest failed or
  incomplete report; do not manufacture a score or three placeholder findings.
- Report capability remains expiring, revocable and noindex. It is not an
  account system or a replacement for existing workspace endpoints.
- Repeated submissions should reuse an active free scan for the exact same
  normalized website where possible; use bounded results and existing queue
  policies to avoid duplicate work.

## Static assessment trustworthiness pass (2026-11-01)

### Current-state review

- Existing checks already cover robots and known AI bot policies, llms.txt,
  sitemaps, HTTP responses and redirects, challenge signals, raw/rendered
  JavaScript differences, titles/descriptions/canonicals/headings, control
  names/labels, and JSON-LD syntax/type/property checks. The crawler is bounded,
  respects robots, and uses its validated network gateway. Existing workspace
  reports retain detailed checks and sanitized evidence; static work is
  deterministic and does not call an LLM.
- Incomplete: a page with no HTTP response is persisted as a FAIL; non-200
  robots retrieval (including transient server errors) can be reported as a
  confirmed crawl restriction; missing optional sitemap, llms.txt, or JSON-LD
  are failures that can affect the score; some successful checks retain a
  failure-oriented title; the URL-first free report shows aggregate coverage
  and top insights but not per-check states/evidence; it omits pages failed and
  an explicit statement that static results do not prove task success.

### Plan

- [x] T0: Inspect `AGENTS.md`, architecture/static/free-scan docs, crawler,
  checks, scoring, report DTO/API/UI, and tests; record this plan. Parent.
- [x] T1: Correct status classification for fetch failures and robots retrieval;
  treat absence of optional sitemap, llms.txt, and schema coverage as
  informational and keep it out of scored checks. Version changed free rubric
  if score inclusion changes. Correct misleading outcome titles. Add focused
  deterministic tests. Parent owns crawler diagnostics,
  static audit and score projection files/tests.
- [x] T2: Extend the free report’s safe response projection with bounded,
  sanitized per-check status/evidence, category/status counts, and failed-page
  coverage. Do not expose internal scan IDs or raw HTML. Parent owns free report
  schema/service/API contract and matching TypeScript DTO.
- [x] T3: Update report UI to show the assessment caveat, page coverage, and
  grouped, expandable check outcomes (including inconclusive/informational and
  not-applicable states), while preserving the top-three insights and existing
  URL-only scan flow. Parent owns the free report component.
- [x] T4: Exercise representative local fixtures for a healthy site, optional
  assets missing, malformed policy/sitemap, redirects, HTTP errors, challenge,
  incomplete metadata/semantics, JS-dependent content, and scanner failures.
  Run focused/full backend tests, Ruff, frontend lint/type/build and browser UI
  checks where available. Update docs with exact assessment limits. Parent.

### Verification evidence

- Backend full suite: **173 passed, 5 skipped**, with one existing Starlette /
  httpx deprecation warning. Focused static/free assessment tests: **30 passed**.
  Tests cover missing/invalid optional files, malformed sitemap and JSON-LD,
  robots allow/deny/transient failures, no-response failures as UNKNOWN, HTTP
  404 and redirects, challenge signals, JS-render differences, page metadata,
  semantics, score eligibility and free-report privacy/status projection.
- Ruff check and formatting pass. Alembic reports **No new upgrade operations
  detected**; no schema migration was needed.
- Frontend lint, TypeScript, Prettier and production build pass. Playwright
  browser smoke test passes the URL-only scan flow, check detail disclosure,
  desktop/mobile homepage and report layout, no horizontal overflow, and no
  WCAG 2.1 AA axe violations. Screenshots are in
  `/private/tmp/agentreadiness-free-flow/`.
- All crawler-facing automated tests use local fixtures and mocked HTTP
  responses; no public-site crawl or LLM call was performed.

### Risks / defaults

- Do not change the crawler’s fail-closed robots behavior. A retrieval failure
  may still stop crawling, but it must be reported as unavailable/inconclusive
  unless an explicit response proves an access restriction.
- Missing `llms.txt` or JSON-LD is an informational opportunity only; presence
  must not by itself raise a readiness score. This correction will be versioned
  so score history does not compare unlike rubrics.
- Preserve the existing static and agent score separation, report capability
  privacy, crawler limits, current backend contracts except the additive free
  report details, and all existing agent configuration.

Source objective: user attachment `pasted-text-1.txt` (2026-11-01). Complete the
feature across persistence, provider, browser loop, scan jobs, scoring, reports,
replay, exports, tests and documentation. Accounts and billing remain excluded.

## Current evidence and approach

The worktree contains completed static audits and a partial HF-powered agent:
`engines/agent/{provider,browser,runner,actions}.py`, WorkflowTest/AgentStep models,
agent endpoints, and screenshot viewer. Reuse these instead of duplicating them.
Missing requirements include native tool calling, contact task, rule/judge grading,
repeat aggregation, cost/token budgets, infrastructure classification, automatic
post-static execution, per-IP limits and agent-aware scores/reports/exports.

The existing worktree has substantial uncommitted implementation from earlier
requested features. Preserve it in a local baseline commit (after checking secret
exclusions), then create small scoped feature commits. Never commit `.env`, model
credentials, generated dependencies, browser screenshots or QA database artifacts.

## Data model / migration

- Add `AgentTaskTest`: scan, extensible task type/goal, requested repeats, stage
  status, aggregate outcome, consistency, eligible-run counts, timestamps, policy
  snapshot. Only the three requested task templates run by default.
- Reuse WorkflowTest for each run: add parent task, run number, verified outcome,
  verification method (`rules`, `judged`, `unverified`), failure_category/reason,
  tokens in/out, estimated cost, model, elapsed time, final evidence. Preserve
  legacy runs and their unverified meaning.
- Extend AgentStep with tokens in/out, LLM latency and typed error category.
- Store per-IP admission buckets in PostgreSQL (hashed normalized peer identity,
  expiry/count), bounded and periodically cleaned. No Redis/Celery.
- Extend scan summaries with frozen static score, agent component, effective
  weights, coverage, fallback reason and pipeline progress. Do not overwrite the
  static evidence or retroactively grade old runs.
- Explicit reversible Alembic migration `0005_agent_task_tests` with constraints,
  indexes, defaults and legacy-safe backfill.

## Interfaces and ownership

Canonical model tools: `click(element_id, reason)`, `type_text(element_id, text,
reason)`, `navigate(url, reason)`, `scroll(direction, reason)`, `finish(success,
reason)`, `give_up(reason)`. Stored legacy actions remain viewable. Provider
returns validated AgentAction plus usage counters; typed exceptions distinguish
malformed output from infrastructure failures. Native tool calling uses
`tool_choice=required`, temperature 0; unsupported tool calling falls back to
JSON-only generation, never a hardcoded planner.

Browser observation keeps `url`, `title`, compact numbered interactive elements
and an internal fresh ID->handle map. Observation text is bounded, names <=80
characters, <=150 elements, viewport/nav/main prioritized. No arbitrary selectors,
code, credentials, cookies or input values are exposed. Public contact methods
can be verified by rules without revealing sensitive fields to the model.

Runner result includes outcome, verification method/evidence, failure category,
reason, steps, duration, tokens and cost. It enforces 15 steps, 90s, token budget,
last four summarized steps, one malformed-output retry, action pacing >=1s and
same-action/same-URL loop detection at three repetitions. Rule verification
requires an actual model-selected action; judged fallback is explicitly labeled.

Task service owns claims, run persistence, repeat aggregation and recovery.
Aggregate uses majority among eligible outcomes; ties are inconclusive and
inconsistency is disclosed. Infrastructure-only runs are unavailable and excluded
from site scoring. Run-level evidence remains accessible for mixed outcomes.

## API

Preserve existing `/api/v1/.../agent-tests` run/read/step/screenshot routes as
compatibility views. Add:
- `GET /agent-config` — configured model, safe limits and supported tasks, no keys.
- `POST /scans/{id}/agent-tasks` — start a built-in task with policy-limited repeats.
- `GET /scans/{id}/agent-tasks` — parent task results/progress, paginated.
- `GET /agent-tasks/{id}` and `/agent-tasks/{id}/runs` — aggregate and per-run data.
Manual and automatic starts share admission/safety rules. No API-supplied provider
URL, model, headers or credentials. Additional-domain navigation is disabled for
new executions; the target is the scan's exact authorized host.

## Pipeline / rate limits

After static audits, schedule/execute a separate agent stage with its own budget
and progress. The static scan must complete even when inference is missing,
billing fails, retries exhaust, or agent work times out. Defaults for anonymous
scans: two tasks, one run each. Internal task repeat default is two, max three;
operator configuration can disable anonymous caps for trusted full-run installs.
Separate static/agent budgets and durable deadlines prevent stale RUNNING jobs.
Per-IP limits cover scan submission and manual task creation. Trust forwarded
addresses only from explicitly configured proxy networks; default to the actual
socket peer, so untrusted X-Forwarded-For cannot evade limits. Document conservative
shared buckets behind an unconfigured proxy and secure production proxy setup.

## Scoring / report contract

Keep static-v1 score and sub-scores unchanged. Add an agent component with default
45% weight, configurable 0..1. Eligible verified/judged run success rates are
averaged per task; task aggregate outcome and consistency are reported separately.
Exclude infrastructure errors, unavailable runs and unverified legacy runs. If no
eligible results exist, retain the static score and explicitly explain fallback.
Missing categories/components never become passes. Preserve rubric versions and
compare static and agent components/coverage separately across scans.

Map site/agent failure categories to evidence-backed findings and practical fixes.
Never label transient model/network/provider problems as website defects. Include
screenshots/step references in workspace evidence. Shared reports retain existing
redaction rules and use capability-scoped evidence URLs; do not expose raw paths,
internal IDs, query strings or unrestricted execution content.

## UI / exports

- Scan progress: static phase, then per-task/per-run agent progress/unavailable state.
- Task cards: success/failure/inconclusive/unavailable, verification method,
  consistency, steps, time, failure reason, link to run replay.
- Viewer: run selection, action reason, screenshot replay and verification evidence;
  agent-declared finish remains distinct from rule-verified or judged completion.
- Report: static/agent components, effective combined score or fallback reason,
  task cards, prioritized findings and coverage.
- JSON/CSV/PDF: task/run outcomes, model, steps, time, tokens, cost, categories and
  verification; comparisons/history retain component breakdown.
- Config/model is read from API, not hardcoded in presentation.

## Checklist and dependencies (small reviewable tasks)

- [x] T0: Local baseline checkpoint and plan commit. Parent owns PLAN.md and review.
- [x] T1: Shared action/result contracts and config interface. Depends T0. Parent.
- [x] T2: Native tool calling, JSON fallback, transient retries, usage/cost budget
  accounting. Depends T1. Small-model subagent owns provider + provider tests only.
- [x] T3: Observation builder, safety tools, success rules/judge interface and
  bounded agent loop. Depends T1. Strong-model subagent owns browser/runner/success
  modules + their unit/fixture tests; no persistence/provider files.
- [x] T4: Models, migration, schemas and repository operations. Depends T1.
  Small-model subagent owns domain models, migration 0005, agent schemas/repository
  and focused persistence tests; no services/config/frontend edits.
- [x] T5: Task service, repeat aggregation, DB/IP admission, API and scan-stage
  orchestration/recovery. Depends T2/T3/T4. Parent.
- [x] T6: Score blending, failure findings, reports/shares/export/comparison.
  Depends T4/T5. Parent; strong review for infra exclusion and coverage semantics.
- [x] T7: Task cards, viewer/run selection, report/progress/history integration.
  Depends stable T4/T5/T6 contracts. Small-model UI subagent with exclusive frontend
  file ownership; parent reviews rendered results.
- [x] T8: Config/env/README/docs and isolated deterministic integration tests.
  Depends stable interfaces. Small-model subagent with exclusive docs/test files.
- [x] T9: Full tests, migrations, lint/typecheck/build, browser QA, live configured
  HF attempts on 3–5 bounded sites, final stronger-model safety/completion review.
  Depends all above. Parent + independent strong review, no overlapping edits.

After each task: inspect diff, run focused checks, fix problems, commit the scoped
change, and record authoritative evidence here before checking its box.

## Verification / completion gates

- Unit tests: 150-element/name/size/prioritization limits, tool parsing/fallback,
  unsafe IDs/domains/actions, rule and judge outcomes, retries/429/5xx/timeouts,
  one malformed retry, loop detection, last-four history and token budgets.
- Deterministic full-loop integration: real Chromium behind the validated gateway,
  a local fixture via mock HTTP transport, mocked LLM decisions; database, API,
  repeated runs, infrastructure exclusion, exports, share boundaries and cleanup.
- Alembic upgrade/downgrade/schema check on disposable PostgreSQL; preserve data.
- Full backend tests, Ruff lint/format, frontend ESLint/TypeScript/format/build.
- Render desktop/mobile scan/report/viewer pages; verify polling, errors, screenshots,
  aggregate cards, combined score/fallback, exports, history and comparisons.
- If HF_TOKEN exists, attempt 3–5 bounded public sites using the configured model.
  Record exact success/steps/time/tokens/failure table; no claims of real-model
  success when credentials, endpoint billing or network prevent it. No token values
  or hidden chain of thought in logs, artifacts, code or commits.
- Final independent strong review checks every attachment requirement, safety,
  failure isolation, cost limits and unfinished code. Goal stays active until all
  implementation/gates are verified; external inference limitations are explicit.

## Risks / decisions

- Tool calling varies by HF model; fallback is transport capability recovery,
  never success fabrication. Model identifier is configuration, not provider code.
- Two repeats can tie; show inconclusive/inconsistent instead of inventing a majority.
- Rule evidence can be limited by JS restrictions/CAPTCHA; judged fallback is lower
  assurance and labeled. No purchases, login or final submit, including via Enter.
- All anonymous users behind an unconfigured proxy share a stricter rate bucket.
  Secure forwarding requires an edge that overwrites client headers and an explicit
  trusted-proxy allowlist. Header spoofing is never accepted by default.
- HF token availability is checked without printing secrets. Prior HTTP 402 results
  are historical, not proof of current availability; verify again only after tests.
- Existing broad dirty worktree is preserved before scoped commits. No destructive
  reset, data wipe, auth/billing additions or proprietary runtime model substitution.

### T0/T1 evidence

- Local checkpoint `d094452` preserved prior implementation; secret-shaped file
  scan and `.env` exclusion passed. Planning commit `793dedd`.
- Shared contracts are in `engines/agent/contracts.py`; added contact task and
  canonical tools while preserving legacy stored actions. Config now defines
  repeat/free/token/pacing/judge/score/IP limits. These are configuration only;
  downstream services must enforce them.

### T2/T4 evidence

- Provider reviewed for strict native tools, mode-neutral fallback, HF host/token
  safety, UTF-8 budget reservation and configurable models. Mocked HTTP provider
  tests: 19 passed; Ruff check/format passed. No live calls.
- Migration 0005 applied to disposable PostgreSQL; Alembic check reports no new
  operations. Persistence/schema tests: 5 passed, including atomic task claim and
  cross-scan run/task composite-FK rejection. Legacy rows remain unverified.

### T3/T5/T6/T7/T8 and final verification evidence

- Browser loop exposes only the canonical tools, bounded interactive-only
  observations and fresh element IDs. Deterministic pricing/contact/signup rules,
  loop limits, invalid-action handling, isolated browser cleanup and network
  gateway checks are covered by unit and local-fixture integration tests.
- Scan-stage integration runs the configured built-in tasks after static audits,
  records task/run progress, enforces anonymous admission limits and recovers
  expired agent work to a completed static report. A 25-test focused run and the
  full backend run cover API persistence, reports, scoring, exports and restart
  recovery.
- Report/share/export work keeps share URLs redacted and uses short-lived
  share-scoped screenshot capabilities. The tamper test now changes a capability
  byte rather than occasionally replacing a byte with itself.
- Frontend includes task aggregates, run selection, evidence replay, truthful
  verification labels, combined/static score context, and responsive agent,
  scan, project and dashboard states. Live Playwright UI verification passed at
  desktop, tablet, mobile and small-mobile sizes with WCAG/overflow checks; the
  isolated state harness passed pending/running/completed/timeout/missing/error
  paths. Screenshots are in `/private/tmp/agentreadiness-qa-final/`.
- Backend: 147 passed, 4 intentionally skipped (opt-in real-HF runs), 1 warning.
  Ruff check and format check pass. Frontend lint, TypeScript, Prettier, optimized
  build and UI state/browser flows pass. Compose health endpoint is healthy.
- Alembic 0005 is applied both to the disposable test DB and the running Compose
  database; Compose database revision verified at `0005 (head)`. Test DB
  `alembic check` reports no new operations.
- Real inference was attempted once with the configured model and token, with a
  120-token output cap and retries disabled. Hugging Face returned HTTP 402
  (credits/billing required); the browser UI records this as `UNAVAILABLE` and
  excludes it from site scoring. No real-model site runs were attempted after
  this credential/billing failure. To verify after configuring a funded endpoint:
  `cd backend && RUN_REAL_HF_TEST=1 .venv/bin/pytest -q tests/test_agent_real_model.py`.

The final diff/safety review, post-edit build checks and scoped commits are done
(commits `7db5816`, `ce6e3c2`, `3a130cb`, `9283a8b`, `e3a3dc1`, `2a6d767`).
The configured token is present but Hugging Face returned HTTP 402, so real-model
site execution remains explicitly unverified until credits/billing or a working
local endpoint are configured. The optional real-model fixture command above is
the next verification step after that configuration. The user requested stopping
live agent work at RUNNING and skipping pending tasks; the last smoke task instead
terminated quickly as UNAVAILABLE on HTTP 402, and no additional live agent runs
were started.


## 2026-11-02 — SaaS-focused evidence → fix → verify MVP

Implemented the five agreed product adjustments; the scoped checklist, risks and
verification evidence are in [docs/mvp-plan.md](docs/mvp-plan.md).

- [x] SaaS-first homepage and pricing/docs/signup task framing.
- [x] Evidence and deterministic fix guidance, three prompt variants and validated asset drafts.
- [x] Static readiness separated from real agent tasks explicitly marked Not run in the free report.
- [x] Fix Center, tracked user actions, ZIP pack and capability-scoped linked rescan verification.
- [x] Optional usefulness/price-interest feedback and anonymous aggregate pilot metrics; no checkout.
- [x] Migration 0006, backend/fixture/API regression tests, frontend checks and rendered desktop/mobile accessibility flow.

No LLM calls were made. Actual pilot recruitment and willingness-to-pay validation
are pending; the UI only records hypothetical interest. Live agent inference
remains deferred and unverified. Current implementation details and asset
limitations are in [docs/fix-center.md](docs/fix-center.md).
