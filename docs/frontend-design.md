# Frontend design and verification

AgentLane uses the **Volt lime** identity (canvas: the "AgentLane brand identity"
design artifact; brief: "AgentLane brand and design brief"). The logo is one path that
forks: the straight paper lane is the site as people and search engines see it, the
lime lane (`#cbf34a`) branches off for AI agents (`LogoMark` in `product-ui.tsx`,
`app/icon.svg`, `app/apple-icon.png`). Its colors come from `--logo-*` tokens: an ink
tile in light mode, a raised `#23262c` tile in dark mode, the same lanes in both.

The guiding rule is restraint, so the product reads premium rather than loud. Ink
(`#0e1013`) and warm paper (`#f6f5ef`) carry every page, and buttons stay ink (chalk
`#f3f2ec` in dark mode). Volt lime `#cbf34a` is the one accent and is always a fill
with ink on it (14.9:1): a painted brush stroke behind the hero's rotating agent name
(an SVG mask, sized to each name), the logo's lane, the paid plan's badge and button.
Lime is never text on paper; accent text is dark olive `#4a6400` on light (6.2:1) and
lime on dark. Green means verified results only; model judgments are neutral grey.
Labels are small and sentence case (no mono capitals); headlines use weight 560 with a
quieter grey second phrase; sections are separated by hairlines, not colored bands. No
gradients, glows, sparkle icons, outlined numerals or fake browser chrome.

The landing follows the brief's story: hero (headline, one sentence, scan box, one
caption line; an example report card beside it), the problem (three common failures and
a size-picker example in three panels: what a person sees, what an agent receives, and the
same markup after the Fix Kit), how it works (three steps and what the scan checks),
principles ("Verified, not claimed"), the agent lane (in development), pricing, FAQ and
a closing scan card with the disclosure. Buttons and controls use `--radius-control`
(12px), badges 8px, cards 20 to 24px. Instrument Sans sets headings and text and
JetBrains Mono (ligatures off) sets code and data. Funnel Display (`--font-agent`) is used
in one place only: the rotating agent name on its volt lime brush stroke in the hero. Dark mode is available from the header and
persists in local storage; Tailwind's `dark:` variant follows that toggle.

## Tokens and components

`frontend/src/app/design-tokens.css` owns every raw color, radius and shadow for
light and dark themes; components use semantic tokens only (`primary`, `signal`,
`lime`, `ink`, `muted`, `success`/`warning`/`danger` and their `-soft` washes).
Text/background pairs were checked for WCAG AA contrast (muted text is 5.0:1 even on the sunken background). `globals.css` maps the
tokens into Tailwind, enlarges the shared radius scale, and provides the shared
primitives: `.surface`, `.surface-float`, `.nav-glass`, `.display-xl|lg|md`,
`.lede`, `.chip`, `.headline-pill`, `.icon-tile[data-tone]`, `.mark-lime`,
`.block-feature|lime|ink`, status badges, tables, skeletons and code panels.
`product-theme.css` holds shared report and legal presentation. Buttons are 12px
rounded rectangles with `default`, `secondary`, `outline`, `ghost`, `ink` and `lime`
variants and `sm`/`default`/`lg` sizes. Fonts (Instrument Sans, JetBrains Mono and, for the
hero agent name only, Funnel Display; SIL OFL) come from `next/font/google`: they are downloaded once at build time and served
from the app, so pages never call a font service, but a build needs network access. Do not fabricate social proof
(logo bars, testimonials, usage statistics) to fill marketing layouts. Reports end
with "Check our work" (`cross-check.tsx`): reproducible public requests and links to
independent, unaffiliated tools (AgentReady, Is Agentic), never their scores.

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
| `/results/[id]` | Customer-facing scan progress and concise free report with up to three real insights |
| `/dashboard` | Real workspace metrics, recent projects and scans |
| `/projects` | Searchable project list and creation dialog |
| `/projects/[id]` | Project information, scan history, execution history and Start Scan |
| `/scans` | Scan history |
| `/scans/[id]` | Crawl progress, paginated pages, metadata, agent tasks and findings |
| `/agent-tests` | Execution history, status filtering and task creation |
| `/agent-tests/[id]` | Dedicated live execution viewer |
| `/docs` | Actual getting-started, inference, API and data-handling guide |

The landing CTA now routes to `/results/[id]`, which polls the existing report API
and presents scan progress, the score returned by the audit, coverage and up to
three real priority findings. The detailed `/scans/[id]/report` remains available
for evidence and recommendations. No checkout is shown while payment is deferred.
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
CUSTOMER_REPORT_SCAN_ID=<existing-scan-id> UI_BASE_URL=http://localhost:13000 npm run test:ui
```

`test:states` intercepts API responses inside an isolated browser. Fixture data is
never persisted. It checks pending/running/completed/timeout/missing/empty states,
API retry, invalid URL feedback, missing screenshots and polling termination.

`test:ui` checks the customer report against an existing scan identified by
`CUSTOMER_REPORT_SCAN_ID`. It does not create projects or scans and does not start
agent tests or call a model. It runs axe WCAG A/AA checks and overflow assertions
at desktop, 768px, 390px and 320px, and saves screenshots under `QA_OUTPUT`.

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

## Scan handoff and report stability

The previous homepage used ink, periwinkle and coral with an illustrative
evidence-to-fix preview. Its three-line headline put website last;
provider rotation pauses while the domain input is focused and for reduced
motion. Legacy green headline and scan-button overrides have been removed.

Both domain forms show a full-viewport handoff as soon as a valid submission
starts. One in-flight request is allowed; the busy state persists until route
navigation, and errors restore the existing form for retry. SSR controls are
disabled until their React submit handler is ready. The free-report route has
a loading boundary using the same transition screen. The root HTML declares
smooth scrolling so Next can suppress it during route navigation. Development
origins explicitly allow the loopback hostname as well as default localhost.

The score ring stays aligned to the top of its grid row when the methodology
accordion grows. Frozen report check lists retain separate raw/rendered
observations and include their row position in keys, avoiding duplicate
title/URL collisions without discarding evidence.

The mocked browser flow checks pending creation, duplicate submission rejection,
API failure/retry in the footer form, stationary score-ring geometry, duplicate
check disclosures and console warnings, plus desktop/tablet/mobile contrast and
overflow. Captures are in `/private/tmp/agentreadiness-free-flow/`.


## Light editorial homepage

The homepage now takes visual direction from the user-supplied Manicule
screenshot: white paper, charcoal typography, restrained rust-orange actions,
fine section rules, and left-aligned editorial layouts. It uses the existing
local Manrope and Space Grotesk fonts and adds no dependencies or remote assets.
The design is scoped in `components/landing.module.css`; report and dashboard
tokens remain unchanged.

The three-line hero keeps “Can” at a fixed horizontal position while provider
names rotate. Rotation pauses during input and respects reduced motion. The
report receipt uses a question mark instead of a fabricated score. The
finding-to-code illustration is labeled as sample data, and browser-agent
capability is clearly separate from the free static scan. The existing domain
normalization, request handler, hydration guard, error recovery, and immediate
scan transition are preserved. Both scan forms share the same implementation.

Responsive breakpoints stack the hero and agent preview, simplify navigation,
and give the mobile scan action its own full-width row. Two source-review
passes refined layout, legacy color overrides, and text contrast. Browser
inspection and screenshot capture were intentionally omitted because the user
requested no computer/browser control; rendered visual quality remains for
manual review.

### Readiness field guide refinement

The current homepage combines the supplied references' clarity and product
storytelling with an original field-guide identity: warm ivory, ink, rust-orange
calls to action, cobalt evidence markers, numbered sections, and a connected
scan/fix/verify motif. The hero retains three lines and a stationary “Can” while
provider names rotate. The previous passive report receipt is replaced by
`ReadinessLab`, an interactive, explicitly illustrative markup inspector.

The lab offers pricing, documentation, and signup examples, independent before
and suggested-fix controls, and expandable evidence. It never requests a scan,
submits a form, calls a model, or presents example changes as deployed/verified
results. The initial scan and footer scan retain the existing shared handler.
Homepage CSS remains scoped; backend, report data, and dashboard contracts are
unchanged. No customer logos, invented outcome metrics, pricing offers, or
competitor assets have been added.

This refinement was reviewed in source for desktop/mobile breakpoints,
keyboard controls, fixed headline alignment, reduced motion, and sample-data
labeling. Per the user's no-computer-control request, browser rendering and
interactive browser tests were not run; manual visual review is still needed.

## Shared product design language

`src/app/design-tokens.css` now owns the shared light/dark palette. Fixed
`--brand-*` tokens also feed the light-first homepage so its palette stays
aligned with reports and the workspace. `src/app/product-theme.css` contains
shared presentation for report frames, evidence panels, page headings, tables,
metric strips, and navigation. Page behavior and response contracts are unchanged.

| Role | Treatment |
| --- | --- |
| Background | Warm ivory; neutral charcoal in dark mode |
| Primary action | Rust orange (`--primary`) |
| Evidence, links, selection, completed checks | Cobalt (`--signal`) |
| Quiet surface | Warm neutral (`--muted`) |
| Evidence highlight | Pale cobalt (`--accent-soft`) |
| Warnings / failures | Amber / red, accompanied by text labels |
| Display / body / technical text | Space Grotesk / Manrope / Geist Mono |

Reports, Fix Center, progress/loading screens, projects/scans, agent test
selection/history/execution, and documentation use the shared roles. The
workspace's separate purple sidebar theme has been removed. Score thresholds
and calculation are unchanged; the existing ring uses theme-aware score colors
and a neutral track. Mobile sidebar controls, tables, polling, exports, prompts,
re-scan actions, and evidence expansion keep their existing behavior.

When styling new screens, use `text-signal`, `border-signal`, and
`bg-accent-soft` for evidence and selection; reserve the default orange Button
for primary actions. Avoid local hex overrides for product surfaces.

Motion and interaction (from the website-redesign skill, adapted): elevation uses
`shadow-card` at rest and `shadow-elevated` on hover; primary buttons darken with a
glow on hover and press in on click (200ms); every clickable element shows a pointer;
arrow icons nudge toward their destination on hover. `components/reveal.tsx` gives
once-only, staggered scroll entrances with IntersectionObserver (no animation library):
server-rendered content stays visible, only below-the-fold elements animate, and reduced
motion shows everything immediately. Interactive marketing cards use `.lift`.
Landing choreography is CSS only, animates transform, opacity or clip-path, and is
switched off under reduced motion: each agent name's brush stroke paints in left to
right; the example report's meter fills segment by segment and its findings settle in;
the "After the Fix Kit" panel lands its tag, then its markup line by line, then the
agent's reading; the agent-lane routes arrive in turn and the lane tag pings three
times. Animations inside a `Reveal` are paused (`animation-play-state`) until it is
shown, so they play when seen. The landing
navbar is scroll-aware (clear at the top, frosted over the hero, solid with a shadow past
it); other pages add a shadow once scrolled. Large panels share a 28px radius. The shared
`MarketingFooter` has Product, Resources and Legal columns with real links only. Dark mode
is supplied by the existing `data-theme` switch. This pass was checked with
TypeScript, ESLint, Prettier and a production build. Browser rendering and
browser-based interaction suites remain unverified under the user's existing
no-computer-control instruction.

### Quieter report accents

Report content now uses charcoal icons, ordinary links, check badges, and
progress bars with warm neutral panels. The report score ring uses an ink tone
for high scores, retaining amber/red for lower ranges; thresholds and values
are unchanged. Orange remains the primary action color. Cobalt is limited to
active loading indicators, keyboard focus, and shared selected controls. This
also applies to Fix Center and static/shared report content, with theme-aware
colors in dark mode.


## Customer launch presentation

Scanning opens a domain-verification dialog before starting any full crawl.
Free reports show a score and three concise insights; paid API fields and the
Fix Center are only loaded after a confirmed entitlement. A $19 Checkout card
explains the one-time purchase and 30-day same-domain re-scans. Failed/no-score
reports offer a free retry rather than a payment. Payment returns poll briefly
for webhook confirmation; they never grant access in the browser.

Real agent execution routes show the Christmas 2026 placeholder; old workspace
customer routes redirect to the URL-first homepage. Obsolete landing CSS was
removed (more than 500 unreachable rules), the old dark marketing variant was
removed, and surviving illustrative preview colors use the paper/ink/orange
palette. Internal components remain in source but are not a customer bypass.
Public legal documents now disclose verified sessions, OTP email and Stripe.
No browser screenshots were taken under the user's no-computer-control request.

## Homepage editorial refinement — November 2026

The latest supplied competitor screenshot informed a quieter homepage treatment:
Georgia editorial headings, existing Manrope/Geist Mono UI text, warm paper,
charcoal navigation, restrained burnt-orange actions, fine rules and soft shadows.
The rotating provider names retain the fixed `Can` position and three-line hero.
The interactive example keeps its controls and bounded evidence region, with a
shorter body and no decorative tape or offset shadow. Marketing previews remain
explicitly illustrative.

Pricing now explains the real free allowance and the $19 one-time domain Fix Kit,
with FAQs covering verification, static scoring limitations and the planned
Christmas agent release. Both pricing actions use the existing verified scan
flow. These are presentation/content changes; API and execution logic are
unchanged. This pass used the supplied screenshot, not a live browser capture.
TypeScript, ESLint and production build passed; rendered desktop/mobile visual
review was not performed in this pass.

## Readability pass

Shared Tailwind small text is now 13px (`text-xs`) and 15px (`text-sm`).
Explicit component captions use at least 12px, with most helper text at 13px
and body/control text at 14–15px. Homepage, report, Fix Kit, verification,
workspace and launch-preview typography use this scale. Hero sizes stay
independent. Buttons grow with their content, narrow launch dates wrap, and
mobile demo controls leave room for larger labels.

## Homepage contrast refinement

The warm editorial base now has stronger focal points: a larger hero, darker
supporting copy, a more saturated orange scan action, and orange rules around
illustrative product evidence. The interactive example distinguishes the active
before state from the warm orange fixed-markup state without changing its
navigation or evidence behavior. A full-width charcoal improvement section
introduces a stronger visual rhythm between the audit categories and pricing.
Repetitive section labels were reduced. Illustrative examples and current static
coverage disclosures remain explicit. This presentation pass passed TypeScript,
ESLint, formatting and production build; it was not browser visually reviewed.

## Current direction: neutral developer product with blue actions

This supersedes the cream/serif homepage treatment above. The customer requested
more presence while keeping the design professional and restrained. Shared
surfaces now use white, cool neutral borders and ink text, with blue for primary
actions and evidence. The existing `brand-orange` CSS variable name remains as
a compatibility alias for the new primary color; semantic warning/error colors
are unchanged.

The homepage places a stable rotating-provider headline alongside the scan offer.
A wide interactive specimen follows on a charcoal surface, with navigation and
before/after controls beside bounded evidence. Audit areas are rows; the
improvement loop uses three compact columns. Pricing, FAQs and the Christmas
announcement use the same neutral palette. Fixed-height evidence still scrolls
internally. At narrow widths the specimen and hero stack. Motion is limited to
the existing provider transition and honors reduced-motion preferences.

All scan, verification, preview and checkout interactions use their existing API
calls. No new network calls, fabricated results or agent execution were added.
TypeScript, lint, formatting and build passed. Browser visual verification was
not performed in this pass.

## Current direction: cleaned editorial design with light and dark modes

This replaces the blue/sans-serif experiment. The homepage returns to the serif
headline, warm neutral surfaces and side-by-side interactive example. Compact
audit rows and readable 12–15px supporting text remain. Primary actions use a
warm accent; evidence uses a quieter secondary color. The headline stays in
three rows and the `Can` position stays fixed during provider rotation.

The homepage and free-report header now expose the existing shared theme toggle.
A static pre-paint initializer in the root layout restores the saved `ar-theme`
preference, or follows the OS preference when none is saved. Both modes are
applied through shared semantic surface/text/border tokens, including the demo,
Fix Kit, pricing and launch announcement. Provider logo tiles intentionally stay
white so black brand marks remain legible. There is no theme-specific data or
backend behavior.

Validation: TypeScript, ESLint, formatting and production build passed. The actual
initializer passed five execution checks covering saved light/dark, system
preferences, invalid stored values and unavailable storage. Browser visual review
was not performed.

## Landing page: contrast, score signature and conversion flow

The editorial serif and terracotta identity now follows a deliberate sequence:
light hero, dark sample report, light audit cards, terracotta improvement steps,
light pricing, dark Christmas teaser, light FAQ and a full-width terracotta CTA.
Desktop explanatory text is 17–18px or larger, with secondary technical labels
kept smaller. Dark/accent sections define their own semantic surface/text tokens
so they retain contrast in either theme.

`HeroScanPreview` is an isolated marketing specimen: a bounded count-up to the
explicitly illustrative score 42, three example findings, an agent/human view
switch, and a cursor loop. It never calls scanning, agent or model APIs. Its
score ring repeats in the sample report, with the existing cursor icon motif.
Motion has a pause button, reduced-motion support and CSS-only scroll/hover
effects. The sample's green “Fixed · demo” state is an illustration, never a
verified result.

The free allowance strip uses actual product limits, not customer counts. A code
TODO marks where verified usage aggregates can replace it later. No fictitious
logos, testimonials or “most popular” claim was added. The paid badge describes
the complete kit. A Notify me form is deferred because there is no notification
subscription endpoint; the Christmas teaser and $0/$19 offer remain unchanged.

Run `npm run test:landing` against the running app (default localhost:13000). It
checks 375, 768 and 1280px in both themes: overflow, WCAG 2.1 AA axe rules, layout
shift, demo toggles, reduced motion, theme persistence, FAQ keyboard operation
and domain-only verification entry. Verification responses are mocked and other
API requests are blocked during that entry check. No scans, emails, payments or
model calls are made. Screenshots default to `/private/tmp/agentreadiness-landing`.
The observed layout-shift total was 0.000 in all six combinations. Lighthouse
performance scores were not measured; no new runtime dependencies were added.
