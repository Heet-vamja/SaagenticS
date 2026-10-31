# Frontend design and verification

AgentReadiness uses a light-first workspace with warm neutral surfaces, charcoal text,
moss surfaces, citrus accents, Space Grotesk headings, Manrope body text and Geist Mono metadata. The marketing page explains real
browser-agent testing; the workspace prioritizes scans, execution traces and recorded
evidence. Dark mode is available from the header and persists in local storage.

## Tokens and components

`frontend/src/app/globals.css` owns semantic light/dark color tokens, typography,
12–16px surface radii, borders, restrained shadows, status colors, table styles,
skeletons, focus rings and reduced-motion behavior. Muted colors were checked with
axe for contrast. The fonts are self-hosted. Space Grotesk and Manrope variable font files and their OFL licenses live in `src/app/fonts/`; builds do not request a font service. Geist Mono remains installed locally for technical metadata.

- `product-ui.tsx`: brand, theme, status badges, headings, metrics, domain icon,
  dates, durations, ID copying and the independent-verification notice.
- `shell.tsx`: collapsible desktop sidebar, mobile Radix navigation drawer,
  breadcrumbs and keyboard skip link.
- `states.tsx`, `tabs.tsx`, `findings.tsx`: shared loading/error/empty states,
  keyboard-navigable tabs and expandable evidence/recommendations for findings.
- `project-dialog.tsx`: shared project creation with visible validation errors.
- `agent-testing.tsx`: task picker and execution history shared by scan/project views.
- `agent-detail.tsx`: selectable action timeline, expandable execution details,
  real screenshots, observations and diagnostics. The panels stack on mobile.
- `lib/api.ts`, `lib/types.ts`, `lib/use-resource.ts`: same-origin typed API access,
  network/timeout errors, unmount-safe resource updates and bounded polling.

The existing shadcn/Radix controls remain locally owned in `components/ui`.
Lucide supplies icons. No dashboard or agent framework was introduced.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Public landing page; website CTA creates/reuses a project and starts a scan |
| `/dashboard` | Real workspace metrics, recent projects and scans |
| `/projects` | Searchable project list and creation dialog |
| `/projects/[id]` | Project information, scan history, execution history and Start Scan |
| `/scans` | Scan history |
| `/scans/[id]` | Crawl progress, paginated pages, metadata, agent tasks and findings |
| `/agent-tests` | Execution history, status filtering and task creation |
| `/agent-tests/[id]` | Dedicated live execution viewer |
| `/docs` | Actual getting-started, inference, API and data-handling guide |

The existing project, scan and page endpoints are unchanged. The former root
overview moved to `/dashboard` to make room for the public landing page. Polling
stops when execution reaches a terminal status. Agent `COMPLETED` always means
agent-reported completion; it does not mean independently verified success.

## Honest data boundaries

The landing preview is explicitly labeled an illustrative demo, including its
score and example improvements. Production pages never calculate or invent scores,
audit findings or recommendations. Unimplemented categories are labeled planned.
No authentication, settings, legal policy or billing screens are implied.

The backend does not expose a global agent-test list or the configured model before
execution. The frontend aggregates existing per-scan list endpoints with concurrency
limited to six, and displays the model recorded on each execution. This works for
the MVP but should become a paginated backend listing as history grows. History is paginated through existing collection endpoints; large workspaces
therefore require additional requests. Favicons are replaced by a
domain icon to avoid unsolicited third-party image requests. Missing screenshots
have a useful placeholder. No database changes were made for the redesign.

## Run and verify

Start the existing stack with `docker compose up --build -d --wait`. The default
frontend port is 3000; the current development environment uses 13000. For native
frontend development:

```sh
cd frontend
npm ci
npm run dev
npm run lint
npm run typecheck
npm run format:check
npm run build
```

The browser checks reuse Python Playwright from the backend environment:

```sh
cd backend
uv sync --frozen
uv run playwright install chromium
cd ../frontend
UI_BASE_URL=http://localhost:13000 npm run test:states
UI_BASE_URL=http://localhost:13000 npm run test:ui
```

`test:states` intercepts API responses inside an isolated browser. Fixture data is
never persisted. It checks pending/running/completed/timeout/missing/empty states,
API retry, invalid URL feedback, missing screenshots and polling termination.

`test:ui` uses the running real APIs. It creates disposable `Design QA` projects,
crawls only `https://example.com/`, starts one real configured model request, opens
page metadata/evidence/history, and checks sidebar, theme and mobile navigation.
It runs axe WCAG A/AA checks and overflow assertions at desktop, 768px, 390px and
320px. Screenshots and exact owned record IDs are written to `QA_OUTPUT` (default
`/private/tmp/agentreadiness-redesign`). Use a development database: these tests
create records and consume inference credits if available. Remove only the IDs
in `records.json` when cleaning up the test projects.

The live model currently responds HTTP 402. The redesigned viewer displays its
real failure and captured browser evidence; this is not a successful real-model
integration test. Deterministic UI fixtures verify successful display states
separately and never appear in production data.

## Verification result (2026-10-31)

ESLint, TypeScript, Prettier and the production Next.js build passed. Both browser
suites passed. A total of 35 rendered checkpoints passed axe WCAG A/AA and page
overflow checks, covering desktop, tablet, 390px/320px mobile, light/dark themes
and isolated empty/failure states. Real API smoke checks verified project creation,
URL submission, crawl creation/progress, metadata details, agent creation/history,
recorded evidence, navigation and keyboard focus. All six owned disposable QA
projects and their screenshot folders were removed; existing user projects remain.
Docker frontend, backend and PostgreSQL remained healthy.

Screenshots are saved locally under `artifacts/ui-redesign/` (ignored build artifacts).
These capture actual rendered UI, including an honest HTTP 402 inference failure.
Automated accessibility checks complement the visual and keyboard review; they
do not establish full WCAG conformance. Real-model task completion remains unverified.

## Screenshot-led editorial refinement

The supplied Dedica reference and a fresh rendered Chromium capture guided the
second visual pass. The homepage now uses a split ink-teal hero, a compact agent
session illustration, paired browser examples, a discovery report preview, an
execution console and a lavender URL-entry section. Existing submission behavior
is preserved in both URL forms; their labels and error descriptions have unique
IDs. All marketing values and traces are explicitly illustrative.

The workspace shares the ink-teal sidebar, lilac active states, a continuous metric
strip and a framed browser evidence panel. Timeline selections use a subtle lilac
surface. Light and dark palettes are coordinated. No APIs, data contracts, backend
code or agent behavior changed in this design pass.

Two rendered refinement passes corrected label contrast, the floating preview
note, metric density and failure-state contrast. Final captures are stored in
`artifacts/editorial-redesign/`. Screenshots include an actual model billing failure;
they do not imply a successful real-model run.

## Original identity refinement

The latest design uses a centered oversized Space Grotesk headline, Manrope body
text, moss/cream/citrus surfaces and a three-panel agent workbench. The workbench
shows a navigation path, decision stream and an annotated example browser view.
It is explicitly illustrative and contains no functional submission controls.
Comparison panels use an asymmetric layout with a sticky introduction; numbered
process rows replace the repeated card grid. Larger inputs, section headings,
labels and workspace metadata improve readability. Existing form handlers and
API contracts are unchanged. The logo symbol now uses a connected path motif.

The local variable fonts come from the Google Fonts repository, with their OFL
license files included alongside the assets. Screenshots for this refinement are
saved under `artifacts/fieldwork-redesign/`.
