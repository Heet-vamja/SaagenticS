# AgentReady reference coverage

Reviewed: 2026-11-13 · Spec: 2.0.1 · Mapping: 1.2.0

[Published specification](https://github.com/agentready-org/standard/blob/main/spec/spec.md) · [Requirement facts](https://github.com/agentready-org/standard/blob/main/spec/practices.json) · [Reader guide](https://www.agentready.org/)

This is an independent mapping of our implementation to the published reference. It is not certification, endorsement, a new score, or a claim of complete conformance. The mapping itself makes no network requests. New bounded read-only diagnostics supply measurements; no model, authentication or payment tests are introduced. The existing static rubric is unchanged.

## What is mapped today

| ID | Reference topic | Level | Existing measurements | Remaining limitation |
|---|---|---|---|---|
| AR-FIND-01 | Public-content access | MUST | `robots.access`, `robots.ai_policy`, `access.challenge`, `http.restriction` | Sampled robots policies and our own network responses do not verify reachability from other providers or their infrastructure. |
| AR-FIND-03 | Sitemap discovery | SHOULD | `sitemap.health` | Parsing a sitemap does not verify complete page coverage or its declaration in robots.txt. |
| AR-READ-01 | Useful initial HTML | MUST | `js_dependency` | The bounded raw/rendered text comparison is a heuristic; it does not verify that a specific answer is present. |
| AR-READ-02 | Honest HTTP responses | MUST | `http.status`, `http.soft_error`, `http.rate_limit`, `http.missing_path` | One random missing path and observed HTTP responses are sampled. Redirect intent and throttling reliability are not established. |
| AR-READ-03 | Homepage HTML and navigation | SHOULD | `js_dependency` | Homepage text growth is sampled. Links to documentation, product and pricing destinations are not independently verified. |
| AR-READ-05 | Usable code examples | SHOULD | `content.code_examples` | Only bounded HTML pre/code annotations are inspected. Source Markdown fences, inline examples, language correctness and executability are not verified. |
| AR-READ-06 | Links to discovery resources | SHOULD | `discovery.linked_resources` | Only sampled HTML/HTTP Link references and a bounded same-site validation subset are inspected. Unlinked paths and skipped targets cannot establish full coverage. |
| AR-READ-07 | Described llms.txt index | SHOULD | `llms.presence`, `llms.format` | Presence and structural checks do not verify descriptive coverage, linked destinations or agent adoption. |
| AR-READ-08 | Grounded JSON-LD and visible facts | SHOULD | `schema.coverage`, `schema.syntax`, `schema.fields` | Supported syntax and field checks do not verify business facts, page coverage or agreement with visible text. |
| AR-FIND-04 | Linked AI resource catalog | MAY | `discovery.ai_catalog` | One well-known request plus sampled `rel="ai-catalog"` links. The spec defines no catalog schema; listed resources are not verified. |
| AR-READ-09 | Discoverable Markdown alternatives | MAY | `discovery.markdown_alternate` | Advertisements are counted and at most one mirror is fetched. Agreement with the HTML page and Accept-header negotiation are not assessed. |
| AR-READ-11 | Readable first-party pricing | SHOULD | `content.pricing_text` | Pricing pages are identified by URL or main heading. Price text in initial HTML is observed; completeness and accuracy are not verified. |
| AR-ACT-02 | Public API contract | SHOULD | `api.openapi_contract` | Only linked or catalog-listed contracts are fetched with a basic JSON structure check. Whether a public API exists is not determined. |
| AR-ACT-04 | MCP discovery card | MAY | `discovery.mcp_server_card` | Only a catalog-listed card is fetched and checked as a JSON object. Reserved endpoint paths are not guessed; the server is not tested. |

`render.` is normalized to the underlying rule family. AR-READ-03 uses only same-host homepage observations (with the conventional www alias); documentation/subdomain/query pages cannot supply its homepage evidence. Every implemented mapping remains partial, even when all matching checks pass.

## Unassessed requirements

| ID | Reference topic | Level | Gap |
|---|---|---|---|
| AR-FIND-02 | Canonical first-party documentation | SHOULD | Canonical metadata does not establish that documentation answers customer questions or stays current. |
| AR-READ-04 | Task-answering documentation | SHOULD | Metadata and semantic HTML checks do not assess documentation accuracy or task coverage. |
| AR-ACT-01 | Agent-usable authentication | SHOULD | Authentication metadata and delegated authorization on the target product are not tested. |
| AR-ACT-03 | Usable MCP interface | SHOULD | MCP discovery, transport and tool behavior are not assessed. |
| AR-ACT-05 | Agent-hosted interface | MAY | MCP Apps views are not assessed. |
| AR-ACT-06 | SDK and command-line access | SHOULD | Published SDKs, installation and CLI workflows are not tested. |
| AR-ACT-07 | In-page agent tools | SHOULD | HTML labels are not evidence of WebMCP registration or safe tool behavior. |
| AR-ACT-08 | Agent-usable payments | MAY | The target product’s payment protocols and checkout are not assessed. Our own Stripe integration is not target-site evidence. |
| AR-ACT-09 | Structured question endpoint | MAY | NLWeb discovery and answer behavior are not assessed. |
| AR-ACT-10 | Operable action interface | MUST | MCP/CLI availability and task completion are not assessed. Applicability depends on the target product and remains undetermined. |

AR-READ-10 is retired in the reviewed version and is intentionally excluded. The Act group may not apply to an informational site, but we cannot infer that applicability from an absent check. It remains unassessed, not automatically not-applicable.

## Evidence semantics and access

- `PARTIAL_EVIDENCE`: at least one mapped PASS, FAIL or INFO was recorded. Per-status counts remain visible. This does not mean the requirement passed or failed.
- `INCONCLUSIVE`: only unknown applicable measurements were recorded.
- `NOT_TESTED`: no usable mapped measurement exists; an individual NOT_APPLICABLE does not establish that the overall requirement is inapplicable.
- `conformance` is always `NOT_ASSESSED`. The mapping has no certification result, grade or percentage.
- Existing access normalization is retained: scanner restrictions are not proof that every AI provider is blocked. An intentional training-bot restriction stays informational. Unknown checks are never turned into passes.
- Full verified reports expose `standards_coverage` through the existing free-report GET endpoint and a collapsed reference section. Unpaid previews return null. No raw HTML, target URLs, hidden findings or event traces are added by this projection.
- Our own OTP and Stripe implementation, HTML labels, and future agent-run claims are not evidence of the target product’s authentication, WebMCP, payment or action capabilities.

## Delivered diagnostic subset

- **AR-READ-06:** sampled HTML anchors/head links and HTTP Link headers identify llms.txt, AGENTS.md, OpenAPI and well-known resources. Up to five same-site targets are fetched using the existing DNS-pinned, robots-aware transport; unsupported formats and restricted/out-of-scope targets stay inconclusive.
- **AR-READ-02:** one reserved random missing-path GET; 404 is an observed pass, successful non-redirected HTML is a possible soft-404 finding, and redirects/challenges/auth/rate limits/server errors remain inconclusive. Throttling is never provoked.
- **AR-READ-05:** bounded nonempty HTML pre/code language annotations. Inline code, plain preformatted output, source Markdown fencing and actual code correctness are outside this measurement.

- **AR-FIND-04 / AR-ACT-04:** one robots-aware request to `/.well-known/ai-catalog.json`. Published catalogs use `{"specVersion", "entries": [{"type", "url"}]}`; other JSON shapes are walked generically and bounded to 20 entries. A 404 or an HTML page is "not published" (informational); a challenge or restriction is inconclusive. At most one same-site entry of type `application/mcp-server-card+json` is fetched. Catalog-listed OpenAPI contracts share the existing five-resource budget.
- **AR-READ-09:** `<link rel="alternate" type="text/markdown">` and equivalent Link headers are counted; at most one mirror is fetched after discovery files.
- **AR-READ-11:** pages whose URL path segment or main heading is pricing/plans are measured for currency amounts or an explicit free plan in initial HTML text. Raw prices are not stored. A sample with no pricing page is informational only.

All of these produce existing Check/Finding records and versioned fix prompts. They have zero score weight in this release. Re-scan verification requires explicit passes; a missing or skipped result never confirms a fix. The request budget and detailed semantics are in [static audit diagnostics](static-audits.md#bounded-discovery-and-route-diagnostics).

## Remaining priorities

Homepage docs destination validation, content and pricing accuracy/completeness, Markdown mirror fidelity, MCP endpoint behavior and semantic API/agent-action testing remain unassessed. These are not implied by basic JSON parsing, a language label or a reachable file. Catalog and OpenAPI-specific conformance also remain unassessed even when such a linked JSON document is fetched.

## Updating the reference

The JSON file in `backend/app/engines/standards/agentready-v2.json` is a manually reviewed offline registry. The source URL may advance; no live source fetch occurs during a scan. Review requirement IDs, normative levels and retirements, update the spec/review/mapping versions, and adjust semantic tests. Add a rule mapping only when its stored evidence supports a defensible partial relationship. Do not add a MUST/SHOULD penalty to our score automatically.

`backend/app/engines/standards/agentready-practices-snapshot.json` pins only the upstream requirement facts (ID, phase, level, retirement, version and source commit), not the requirement text. Compare the mapping with the snapshot or a manually downloaded upstream file:

```sh
cd backend
uv run python -m app.cli.agentready_sync                       # pinned snapshot
uv run python -m app.cli.agentready_sync /path/to/practices.json  # exits 1 on drift
uv run python -m app.cli.agentready_sync --write-snapshot /path/to/practices.json
```

Drift (new, removed, retired or re-levelled requirements, or a version change) is printed and must be reviewed by hand. The command never runs during scans.

No database migration or new environment variable is required. Run:

```sh
cd backend
TEST_DATABASE_URL=postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test .venv/bin/pytest -q tests/test_standards_coverage.py tests/test_discovery_diagnostics.py tests/test_customer_fixes.py tests/test_free_scan.py
```
