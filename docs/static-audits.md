# Deterministic audits and static reports

Static audit checks do not invoke an LLM. By default, a separate bounded agent task
stage follows static report preparation; set `AGENT_PIPELINE_ENABLED=false` for
static-only scan execution. Accounts and billing remain deferred.

A new scan runs discovery, HTML/policy checks, a bounded read-only browser sample,
then report preparation. Findings are generated from measurements, not model text.
Legacy scans remain unchanged; re-scan a project to generate a static report.

## Implemented checks

- **Robots and AI policy:** Protego evaluates the declared crawler and known
  GPTBot/OAI-SearchBot/ChatGPT-User, Claude and Perplexity tokens. Policy results
  are informational: an intentional training-bot block is not automatically a
  readiness failure. These checks inspect rules, not impersonate provider bots
  or prove that provider IPs are allowed by a firewall.
- **llms.txt:** root discovery, HTTP presence, UTF-8/BOM handling, one required H1,
  H2 file-list structure and safe Markdown link schemes. Summary/sections are
  optional. Linked URLs are not fetched. This is a supported structural subset,
  not a general Markdown parser or a guarantee that providers consume this proposal.
- **Sitemaps:** reachability, safe XML parsing, nested indexes, entry counts,
  sampled lastmod parsing and future-date errors. Old dates are reported as hints,
  not automatic failures; absent dates make freshness unknown.
- **Access restrictions:** HTTP 401/403/429, cf-mitigated response headers and
  recognizable challenge/CAPTCHA markup. Text signals are heuristic evidence.
  Restrictions are respected, never bypassed.
- **JavaScript dependence:** compares initial HTML text with the rendered browser
  text on a configurable sample. Substantial growth (>200 characters and >1.5x)
  is flagged. Restricted resources or a failed browser make the result unknown.
- **Structured data:** bounded JSON-LD syntax, recognized schema.org contexts,
  type/property names from a vendored vocabulary and common type field suggestions
  for Product, Article, FAQ, Organization, Offer, etc. Completeness suggestions
  are not claimed to be schema.org mandatory fields. Remote contexts are never
  fetched. This is not full JSON-LD expansion, property range inference, or search
  engine rich-result certification.
- **Semantics:** common button/link names, field labels, clickable div/span role
  and keyboard patterns, titles and H1s in raw and sampled rendered DOM. Evidence
  contains bounded tag/selector examples without field values. This is not a full
  accessibility-tree/WCAG audit; CSS-hidden ancestors and complex custom widgets
  may require manual review.
- **HTTP:** statuses, final URLs, bounded redirect paths, missing Retry-After on
  rate-limited responses and possible HTTP-200 error pages. Only allowlisted
  diagnostic headers are retained; cookies and authorization are not stored.

Measurements are stored in Page metadata; full HTML is never persisted.
Findings reuse the existing model. The static audit summary stores versioned checks,
coverage, phase and sub-scores. Its static component is preserved when the later
agent stage completes. A combined report score must not be presented as a static
score or as proof that an agent task succeeded. See
[Agent Task Tests](agent-task-tests.md#outcome-and-assurance) for the blended score
and fallback contract.

## Scoring and priorities

Rubric `static-v1`: Access **30%**, Readability **25%**, Actionability **30%**,
Reliability **15%**. Occurrences of a rule are averaged before rules are weighted,
so repeating the same issue on more pages does not automatically dominate the
score. Rule weights are exposed in check records. Unavailable categories are
excluded and remaining category weights are normalized.

PASS and FAIL affect score. UNKNOWN never becomes a pass; it is excluded with
visible coverage counts. NOT_APPLICABLE and informational bot policies are not
scored. Missing categories or unknown checks mark a score as provisional. A
100 with partial coverage means the evaluated sample passed; it does not mean
untested checks passed. All weights are a transparent product rubric, not an
empirically validated measure of agent task success.

Priority fixes are deterministic: severity first, then breadth across page
observations, with stable tie breaks. The top five cover distinct rules; raw and
rendered variants are combined for prioritization. The UI groups repeated
occurrences while retaining per-page evidence and complete JSON/CSV exports.

## Limits and queue

The default page cap is **20**, crawl depth **3**, concurrency **3**, minimum
request spacing **0.1s**, respecting larger robots delays. A scan has a **120s**
execution budget after admission; discovery uses at most 65% of that budget.
The default browser sample is **3 pages**, **8s per page**, using the existing
validated/pinned HTTP gateway and rejecting Chromium proxy. There are no
navigation clicks or form submissions during static rendering.

PostgreSQL stores PENDING work. Atomic advisory-lock admission allows **2** active
static scans, with a **30-record** admission bound and **600s** queue wait deadline.
Repeated requests for a project reuse its active scan. A periodic in-process
scheduler retries pending work after restart. In-flight scans cannot resume;
expired runs are failed and retain partial evidence. No Redis/Celery was added.
Queue wait is separate from execution, so two-minute completion is a target for
an admitted scan, not a guaranteed end-to-end SLA. Use one worker for this MVP;
DB admission is shared across workers, but browser resources and PDF slots are
bounded per process, not by a global browser fleet controller.

Settings: `CRAWL_MAX_PAGES`, `CRAWL_MIN_DELAY`, `SCAN_DURATION`, `SCAN_MAX_ACTIVE`,
`SCAN_QUEUE_LIMIT`, `SCAN_QUEUE_WAIT`, `AUDIT_RENDER_PAGES`, `AUDIT_RENDER_TIMEOUT`,
`AUDIT_BROWSER_ENABLED`, `REPORT_SHARE_DAYS`. Configuration defaults are forwarded
by Compose. The separate agent stage has its own duration/concurrency, token and
per-IP budgets; see [agent task configuration](agent-task-tests.md#task-and-run-policy).
Existing origin/domain/SSRF/streaming limits remain enforced.

## Reports, sharing and export

- `GET /api/v1/scans/{id}/report` — typed report, findings, top five fixes and coverage.
- `GET /api/v1/scans/{id}/comparison?before={id}` — explicit or previous baseline.
- `GET /api/v1/projects/{id}/history` — paginated scan/score history.
- `POST /api/v1/scans/{id}/shares` — creates an expiring anyone-with-link URL.
- `POST /api/v1/scans/{id}/shares/revoke` — revokes that scan's existing links.
- `GET /api/v1/shares/{token}` — redacted report; invalid/revoked/expired links return 404.
- `GET /api/v1/scans/{id}/export?format=json|csv|pdf` — export a workspace report.
- `GET /api/v1/shares/{token}/export?format=json|csv|pdf` — export a shared report.

The workspace report lives at `/scans/{id}/report`; public links use `/reports/{token}`.
Shared reports remove internal project/scan/page IDs, execution traces and query
strings. Random capability tokens are stored as SHA-256 digests, expire after
7 days by default and can be revoked. Shared responses use no-store/noindex and
no-referrer policies. Links are bearer access, not authenticated private reports.
Accounts and owner authorization are deliberately out of scope: existing workspace
APIs remain intended for a trusted local deployment, not anonymous internet hosting.

JSON and CSV include every finding. CSV cells are escaped against spreadsheet
formula execution. PDF uses offline Chromium with JavaScript disabled and network
requests blocked; all report strings are HTML-escaped. PDF includes up to 100
findings and explicitly states that limit. Two PDF render slots per process and
a 20s render timeout bound exports. If Chromium cannot render, the UI reports the
error and JSON/CSV remain available.

Comparison uses rule+page identity under the same rubric. An old issue is resolved
only if the current check explicitly passes or is not applicable. A skipped,
missing or unknown check is **not retested**, not fixed. Coverage changes are shown
alongside score differences. Legacy scans cannot be compared as scored audits.

## Verification

Migration `0004` adds Scan.created_at/audit_summary, a status/creation index and
report_shares. Migration `0005` adds agent task/run metadata while preserving old
runs as unverified. Run migrations before loading the new API; use a disposable
test database for downgrade checks.

```sh
cd backend
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q -k 'not real_model'
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic check
cd ../frontend
npm run lint
npm run typecheck
npm run format:check
npm run build
```

The deterministic suite includes mocked site-policy/HTML fixtures, real Chromium
JavaScript comparison, persistence, score/ranking/coverage, queue admission,
comparison, share hashing/expiry/revocation and actual PDF bytes. Static audit
checks never make inference calls. To test a static-only scan, disable
`AGENT_PIPELINE_ENABLED`; real-model tests are excluded from deterministic runs.

`frontend/scripts/verify_static.py` reviews locally persisted, explicitly named
fixture scans. Set `STATIC_QA_RECORDS` to a JSON manifest with `project_id`, `before`
and `after` UUIDs. It verifies real report/export/share endpoints, resolved evidence,
score history, axe and overflow at desktop, tablet and 390px/320px widths. It makes
no model requests or external crawls. Test fixtures are removed after review.

## Sources and vocabulary snapshot

- [llms.txt proposal](https://llmstxt.org/) — supported structural checks.
- [OpenAI crawler tokens](https://developers.openai.com/api/docs/bots).
- [Claude crawler tokens](https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-from-the-web-and-how-can-site-owners-block-the-crawler).
- [Perplexity crawler tokens](https://docs.perplexity.ai/docs/resources/perplexity-crawlers).
- [Schema.org vocabulary](https://schema.org/version/latest/schemaorg-current-https.jsonld).

The local `schema_vocabulary.json` snapshot records its source/retrieval date.
Vocabulary names are used offline; custom namespaces are not dereferenced.

Historical static-only baseline, before the agent task stage: a bounded manual
static scan completed with 20 pages and no crawl failures. Its score was explicitly
provisional because rendered comparisons were sampled. That result did not invoke
an agent or verify a real model. Run the current verification commands above for
the state of the integrated worktree.
