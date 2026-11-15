# MVP: prove a useful improvement

Help SaaS businesses find what prevents agents from understanding their public
website and reaching important information, give developers practical fixes,
and verify improvements. Start with pricing, documentation, and signup/demo
discovery. Form inspection is read-only; submitting forms is outside this MVP.

## Implementation checklist

- [x] 1. Persist capability-scoped fix interactions and explicit rescan baselines (models, migration 0006).
- [x] 2. Generate evidence-grounded fix prompts and validated crawl-derived assets with no inference (fix engines/services, versioned templates).
- [x] 3. Expose fix center, downloads, feedback and linked rescan APIs using expiring report tokens (schemas/routes).
- [x] 4. Build customer Fix Center, separate static/agent results, fix states and confirmed-rescan results (frontend components/types/client).
- [x] 5. Focus homepage on SaaS, add optional usefulness/price-interest feedback and an aggregate pilot metrics command (landing/docs/metrics).
- [x] 6. Verify generators, API permissions, unknown/failed rescan handling, a local sample-site fix cycle, migration and frontend checks.

Tasks 2/3 depend on 1; task 4 depends on 2/3; final validation depends on all.
Preserve existing crawler, agent execution/evaluation and full workspace reports.
No inference is used for this work. No accounts, billing, checkout, paid unlocks
or AI recommendation tracking are added.

## Design and risk decisions

- A report token authorizes only its own scan and the exact baseline attached to
  a rescan link. Never infer an anonymous visitor's baseline from project history.
- Fixed means the same rule and page has an explicit PASS on a completed scan
  under the same rubric. Missing, unknown, skipped and failed scans never count.
- Prompts use versioned files and persisted scan evidence. Website text is
  untrusted quoted context. No execution, deployment or claim of applied fixes.
- Assets use observed public URLs, titles and descriptions; organization facts,
  prices and policies are never inferred from a domain. Validate before offering.
- Robots output is a proposal for manual merge, never an instruction to override
  a site's existing policy. Intentional training restrictions are not failures.
- Applied/copy/download actions are user interactions; only rescan evidence can
  confirm a fix. Optional $39 feedback is interest, not a purchase or validated price.

## Pilot acceptance

Invite 20 distinct SaaS businesses; aim for five to apply a fix and return to
verify it. Record report usefulness and optional interest in a $39 one-time fix
pack. Anonymous domain counts are approximations, not verified businesses.
Build payments only after testing willingness to pay with customers.

## Verification evidence (2026-11-02)

- Full deterministic backend suite: 218 passed, five real-model cases deselected.
- Final focused fix/free-report suite: 62 passed (including an additional applied-after-still-failing regression).
- Local sample-site fix cycle confirmed four issues: unnamed button, unlabeled input, malformed JSON-LD, and missing meta description. All site HTTP was mocked; no inference ran.
- Migration 0006 downgrade/re-upgrade passed on the disposable database; Alembic reports no schema differences. Development database is at 0006.
- Frontend ESLint, TypeScript via production build, Prettier and optimized build passed.
- Mock-API browser flow passed URL submission, pending/completed states, copying, applied action, ZIP download, feedback and linked rescan at 1440, 768, 390 and 320px, with no overflow or WCAG 2.1 AA violations. Actual rendered screenshots were reviewed in /private/tmp/agentreadiness-free-flow/.
- Normal Docker Compose database/backend/frontend are healthy; frontend is available at localhost:13000.
- No live-model execution, external crawls, payments, customer recruitment or willingness-to-pay claims were made. Pilot/customer validation remains pending.
