# Free AI readiness scan

**Customer mode now requires a verified email (any mailbox) for the scanned website.** The free response
contains the score and up to 10 priority issues with solutions; full evidence, Fix Center and
downloads require the $19 domain unlock. See [customer launch](customer-launch.md)
for OTP/Stripe setup and the 30-day re-scan window. Legacy anonymous curl
examples below require a verified-session cookie in customer mode.

The homepage offers a URL-first scan for anonymous visitors. A submission
creates internal project/scan records, schedules the existing in-process crawl,
and returns an expiring opaque report link. The public flow does not return
project or scan IDs and does not call the configured LLM or browser-agent
provider.

## Behavior and limits

- The crawler follows its existing URL validation, DNS/address validation,
  redirect checks, same-site scope, robots policy, timeouts, and rate limit.
- Free scans crawl at most 10 pages (or the lower configured crawler page cap),
  then run deterministic static checks. They do not wait for agent execution.
- The preliminary score uses rubric `free-static-v4` weights: Discoverability 30%, Content
  understanding 25%, Structured data 20%, and Agent usability 25%. Only
  evaluated checks contribute. Unavailable categories are excluded and the
  remaining weights are normalized. Missing optional `llms.txt` and JSON-LD do
  not lower the score. Agent usability is explicitly untested on this scan and
  omitted from the score. Infrastructure failures do not reduce the score; a
  failed scan has no score.
- The free report shows up to 10 distinct, prioritized findings supported by
  stored evidence and practical solutions. Full per-check outcomes require the
  paid unlock: pass, issue observed,
  inconclusive, informational, or not applicable. Unknown checks are never
  represented as passes. Scanner failures without an HTTP response are
  inconclusive, not website failures.
- The report includes discovered, crawled, and failed page counts and explains
  that static measurements do not prove that an AI agent can or cannot complete
  a task. Paid evidence summaries are short and redacted; URLs omit query strings.
- The Fix Center supplies deterministic prompts, validated asset drafts, a fix
  pack and a linked rescan that confirms only explicit passes. Optional feedback
  supports pilot validation; price interest is not payment. See [Fix Center](fix-center.md).
- Report links follow the existing expiry and revocation settings and send
  `Cache-Control: no-store`, `X-Robots-Tag: noindex, nofollow`, and
  `Referrer-Policy: no-referrer` headers.

## API

Create an anonymous scan:

```sh
curl --fail -X POST http://localhost:8000/api/v1/free-scans \
  -H 'Content-Type: application/json' \
  -d '{"website_url":"https://example.com"}'
```

The response contains `report_path`, `status`, and `expires_at`. Poll the
capability using the API path:

```sh
curl --fail http://localhost:8000/api/v1/free-reports/REPORT_TOKEN
```

The UI navigates to the corresponding Next.js route, `/free-reports/REPORT_TOKEN`.
The old project and scan APIs remain available for workspace users and internal
development.

## Local development

Start PostgreSQL, backend and frontend using the existing instructions in the
[README](../README.md). Open `http://localhost:3000`, enter a public HTTP(S)
website URL, and follow the returned report link. To run the focused integration
coverage, create/migrate the disposable test database as documented in the
README, then run:

```sh
cd backend
TEST_DATABASE_URL=postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test \
  .venv/bin/pytest -q tests/test_free_scan.py
```

In-process background execution is suitable for this development MVP. A backend
process restart can interrupt a pending scan; the existing deadline recovery
will mark interrupted work terminal. Durable distributed jobs are not included.


## Scanner access is not AI-provider access

The report separates our own scanner access, named bots' declared robots
permissions, and real agent execution (not included in the anonymous free
scan). `access_policies` is an additive, bounded response field with a source,
sampled URL, identity, policy state, and retrieval HTTP status. No row claims
verified provider access or search visibility. If robots cannot be inspected,
provider policy is UNKNOWN rather than inferred to be blocked.

Rubric `free-static-v4` excludes our crawler's own robots permission from
readiness. HTTP 401/403/429 encountered by our request remain recorded but do
not become general website readiness failures; inaccessible content is not
assessed. Actual broken links and confirmed page defects still count. Parsed
intentional bot policies remain informational. Network/robots enforcement is
unchanged: no impersonation, bypass, or restricted crawling.

An interrupted scan keeps its FAILED lifecycle and error details. When a
completed audit of crawled pages supports a score, the public report labels it
as partial and preliminary rather than discarding useful evidence. No usable
page evidence means no fabricated score. Historical free-report projection and
Fix Center classification normalize older scanner-only access checks without
rewriting the underlying scan or marking anything verified fixed. The new
access distinctions also appear in PDF exports.

An owner may explicitly allowlist our declared crawler or deployment IP; this
is guidance only, not a new server-side bypass, custom-header feature, or
permission to crawl restricted pages. File-upload/offline analysis remains out
of scope.
