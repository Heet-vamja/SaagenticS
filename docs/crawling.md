# Website crawling

Create a project at `/projects`, open its details, then select **Start Scan**.
The API returns a PENDING scan ID before crawling begins. Refreshing or closing
the browser does not cancel the backend crawl. Scan and project details show
status, discovered/attempted/failed counts, errors and a paginated page table.
Selecting a page URL loads its persisted metadata. Discovery diagnostics include
robots permissions and sitemap warnings. New scans also run deterministic audits and generate static reports; see [static audits](static-audits.md).

## Defaults and configuration

All options below are application environment settings; `.env.example` and Compose
forward the same defaults. Configuration has bounded ranges validated at startup.
Subdomains are excluded unless `CRAWL_ALLOW_SUBDOMAINS=true` is configured by the
operator. Arbitrary ports are always excluded. Scope is the initial normalized
hostname, with HTTP/HTTPS allowed; a `www` redirect is outside scope by default. If the website redirects to `www`,
set the project website URL to that canonical hostname before scanning. Scope
errors identify the configured and destination hosts. Robots existence is `null`
when retrieval could not complete, rather than incorrectly reporting absence.

| Setting | Default |
| --- | --- |
| CRAWL_MAX_PAGES | 20 attempted page URLs |
| CRAWL_MAX_DEPTH | 3 discovery hops (seed 0; sitemap seeds 1) |
| CRAWL_REQUEST_TIMEOUT | 10 seconds, including redirects and request pacing |
| CRAWL_MAX_REDIRECTS | 5 per fetch |
| CRAWL_SITEMAP_ENTRIES | 500 shared budget for sitemap fetches and entries |
| CRAWL_SITEMAP_DEPTH | 3 nested indexes after initial sitemap depth 0 |
| CRAWL_HTML_BYTES | 2097152 |
| CRAWL_SITEMAP_BYTES | 2097152 (also bounds robots.txt) |
| CRAWL_CONCURRENCY | 3 maximum active HTTP requests per scan |
| CRAWL_DURATION | 300 seconds total per scan |
| CRAWL_USER_AGENT | AgentReadinessBot/0.1 |
| CRAWL_ALLOW_SUBDOMAINS | false |

Discovery starts with robots.txt, sitemap directives and conventional sitemap.xml,
then valid same-site sitemap entries and HTML anchor links. A breadth-first queue
prioritizes discovery depth; sitemap seeds at the same depth are sorted by path
depth. Fragments, default ports, dot segments and percent-encoded unreserved
characters are normalized. Query strings and trailing slashes retain their
semantics. Crawl depth is discovery depth, not the number of URL path segments.

Robots 404/410 means no rules exist. A valid 200 response is interpreted by
Protego (including wildcard matching and rule precedence) for the configured agent. Other statuses, retrieval
failures, invalid UTF-8, malformed text and cross-origin robots redirects deny
crawling conservatively. Each new origin (including HTTP-to-HTTPS changes)
requires its own robots check. Delays and request rates pace requests; excessive
delays may exhaust the request/scan deadline rather than bypassing the rules.
Sitemap fetches and every page redirect also respect permissions. Invalid,
external, duplicate, overly deep and over-budget sitemap locations are skipped;
malformed or DTD/entity-bearing XML is rejected and recorded as a warning.

Pages with HTTP failures, forbidden redirects, oversized responses or timeouts
produce error records where possible. A scan with some successful pages completes
with a nonzero failure count. A denied seed, no successful pages, total deadline or
unexpected execution error fails the scan. Non-HTML resources record status and
content type with a skip reason. Discovered counts include queued URLs; attempted
counts can exceed persisted rows when aliases converge on the same final URL.

## Background execution and recovery

FastAPI BackgroundTasks runs after sending the response in the serving process.
The synchronous task occupies a FastAPI thread-pool slot and runs asynchronous
HTTP I/O on its own event loop; SQLAlchemy operations cannot block the API loop.
Every task owns fresh database sessions and commits page results incrementally.
An atomic PENDING-to-RUNNING update prevents duplicate claims. The unique scan/URL
constraint prevents duplicate page rows. There is no external queue. PostgreSQL pending work is retried by the in-process scheduler; see static-audits.md.

Use one API worker for this MVP. PostgreSQL admission limits active static scans
across workers; request pacing remains per scan. Pending work is durable and
retried by the recovery scheduler every two seconds. A claimed scan has a deadline
of SCAN_DURATION plus 15 seconds; expired work fails rather than silently remaining
RUNNING. Interrupted in-flight work is not resumed. Database outages can defer
reconciliation. See [static audit queue and limits](static-audits.md).

## Limits

This is a static HTTP crawler: no JS, forms, authentication, custom headers,
robots bypass, browser testing or full HTML persistence. Obvious state-changing
link names are skipped; arbitrary server-side GET behavior cannot be inferred.
Compressed HTTP responses and .xml.gz sitemaps are unsupported. Servers ignoring
`Accept-Encoding: identity` fail conservatively. Only the first validated DNS
address is attempted; connection fallback/retries are not implemented. HTML and
XML parsing use bounded input in the same process, not a CPU-isolated parser.

No durable scheduling, global scan admission limit or authentication is added.
This remains a trusted local MVP. Use network egress controls before exposing
scan submission to untrusted users.

## Verification

Install frozen dependencies and use a migrated disposable PostgreSQL database as
described in the README. Unit tests use HTTPX mock transports and fictional sites;
no automated test performs a public website crawl.

```sh
cd backend
uv sync --frozen
uv lock --check
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
uv run pytest -q
uv run ruff check app tests alembic
uv run ruff format --check app tests alembic
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic check
# Disposable DB only: verify downgrade/upgrade preservation of the initial schema
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic downgrade 0001
DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
```

```sh
cd frontend
npm ci
npm run lint
npm run typecheck
npm run format:check
npm run build
```

From the root, with the existing `.env`, run `docker compose up --build -d --wait`.
Create a fictional project in API tests or intentionally scan a public site you
control for manual UI validation. Inspect progress, page detail and terminal
polling behavior. Do not use real site crawls in the automated suite.
