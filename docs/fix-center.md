# Customer Fix Center

The first customer audience is SaaS businesses with public pricing, docs and
signup/demo entry points. The URL scanner still accepts other public websites;
it does not guess a company's business type or reject other sites.

## Customer journey

Enter a domain, read evidence, copy a deterministic prompt or download a
validated draft, apply changes with a developer, then **Re-scan to verify**.
All guidance is currently free. No model is called to generate prompts, assets,
feedback or comparison results. No payment or account is required.

The report presents two distinct assessments: a preliminary static score with
coverage, and real agent tasks explicitly marked **Not run**. Existing workspace
agent tests and evaluation keep their own evidence and verification labels.
This work does not enable live inference or change those algorithms.

## Contracts and permissions

Every endpoint requires a live free-report capability:

- `GET /api/v1/free-reports/{token}/fix-center`
- `POST /api/v1/free-reports/{token}/fix-events`
- `GET /api/v1/free-reports/{token}/assets/{filename}`
- `GET /api/v1/free-reports/{token}/fix-pack.zip`
- `POST /api/v1/free-reports/{token}/rescan`

Asset/center/pack requests accept `robots_preset=keep_existing` (default),
`allow_search`, or `block_training`. Invalid presets fail validation.
Files are returned only from the generated/validated whitelist, with attachment
headers and no external requests or filesystem path input.

Rescan creates an opaque new report link with an explicit baseline attached to
that link. Other anonymous visitors' scans and project history are not used.
Existing admission limits, queue, URL scope and crawler protections apply.
Expiry/revocation is checked on all reads, events, downloads and rescan creation.
Migration `0006` adds `report_shares.baseline_scan_id` and idempotent,
share-scoped `report_fix_events`. Repeated identical events do not add rows.

## Guidance and assets

Fixes come from confirmed failing checks; unknown results do not become fixes.
Up to 100 unique rule/page pairs are prioritized by severity. Prompts have
coding-assistant, general-LLM and developer-ticket variants. Quoted evidence is
redacted and labelled untrusted, with visual/behavior preservation constraints
and a rescan acceptance step.

Edit `backend/app/engines/fixes/templates/v1.1.json` for prompt wording. Preserve
versioned templates once shipped; create a new file/version and select it in
`prompts.py` for substantive revisions. Add rule IDs under `rules`; unknown rules
receive the generic evidence-and-recommendation template.

Assets are generated on demand from persisted scan data and carry a version:

- `llms.txt`: observed homepage title/summary and grouped successful page links.
  Missing descriptions are explicitly flagged.
- `website.jsonld`: only observed WebSite name, URL and description.
- `breadcrumbs.jsonld`: optional two-level example only when both pages were
  crawled and the homepage directly linked to the child.
- `sitemap-suggestions.xml`: successful public pages from the bounded crawl,
  with no invented modification dates. It is not a complete replacement map or
  a claim that these URLs are missing from an existing sitemap.
- `robots-policy-proposal.txt`: opt-in proposed groups; search access is limited
  to exact sampled public paths. The training-block preset blocks listed
  training bots. Owner review/merge is required; the original robots file is
  never overwritten. The bot list is versioned in `ai_agents.json`.

Missing Organization/Product/Article/FAQ/LocalBusiness facts are listed instead
of inventing names, logos, addresses, prices or answers. Current crawl records do
not retain enough confirmed facts for those generators. Structural validation
does not certify factual accuracy, rich-result eligibility or agent visibility.
Asset output that fails validation is withheld with a reason.

To add an asset type: implement a generator and strict offline validator in
`engines/fixes/assets.py`, call the validated `add` helper, provide placement and
provenance, then cover grounded/invalid/unsafe-input cases with tests.

The ZIP includes assets, placement instructions, a serialized fix/status snapshot
and ordered fix-everything prompts split at 24,000 characters. The separate PDF
download continues to represent the free report; it does not claim fixes applied.

## Verification

Only a completed linked rescan under the same rubric with an explicit PASS for
the same rule and page can confirm a fix. A missing/unknown/informational/
not-applicable check, another page, changed rubric or failed scan cannot.
Raw/rendered check IDs and query-variant page identities remain distinct.
Conservative duplicate resolution keeps a failure or unknown from being
overwritten by a pass. A rescan that began before the baseline finished cannot
verify it. Score deltas are omitted when coverage/basis is not comparable.

Copying a prompt, receiving an asset, or clicking **I've applied this fix** is
an interaction/self-report, never independent evidence. Confirmation describes
the sampled check passing, not proof of a causal patch or overall task success.

## Pilot and pricing validation

Optional report usefulness feedback is persisted. After a user reports applying
a fix or has a confirmed fix, the UI may ask about interest in a $39 one-time
reviewed fix pack and follow-up verification. It states there is no
purchase or checkout. This is hypothetical interest, not payment validation.

Run aggregate local metrics (no domain names, report tokens or personal data):

```sh
cd backend
.venv/bin/python -m app.cli.pilot_metrics --days 30
```

Aim to recruit 20 businesses, have five apply an improvement, and observe them
return to verify it. Interview those customers about paid help before building
billing. Domain counts are only a proxy for distinct businesses. Customer
recruitment and actual willingness-to-pay validation remain human work.

## Verification commands

```sh
cd backend
DATABASE_URL="$TEST_DATABASE_URL" .venv/bin/alembic upgrade head
.venv/bin/pytest -q tests/test_customer_fixes.py tests/test_free_scan.py
.venv/bin/ruff check app tests alembic
```

The sample SaaS site lives in `tests/fixtures/saas_site`. The integration test
scans it via mocked HTTP, generates prompts/assets, applies fixes to a local
copy, rescans and checks confirmed findings, without inference or external crawls.
