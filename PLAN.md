# Agent Task Test implementation plan

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
- [ ] T9: Full tests, migrations, lint/typecheck/build, browser QA, live configured
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

T9 remains open only for final diff/safety review, post-final-edit build checks,
small scoped commits and the explicitly unverified real-model run if inference
becomes available. The user requested that live agent work stop at RUNNING and
pending tasks be skipped; the last smoke run instead terminated quickly on HF
HTTP 402, and no additional live agent runs will be started during this pass.
