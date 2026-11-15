# Verified-domain customer launch

- [x] Persist email challenges, verified sessions, Stripe orders and processed events (migration 0007).
- [x] Email OTP verification (any mailbox, session bound to one website), bounded owner-contact discovery API, Gmail SMTP delivery.
- [x] Enforce verification and paid report access in the backend; close legacy public API bypasses.
- [x] Stripe hosted Checkout for USD 19; signed, idempotent webhooks; 30-day domain re-scans.
- [x] Customer verification modal, preview/paywall, payment refresh, Christmas 2026 agent placeholders.
- [x] Remove obsolete theme CSS and update policy/configuration docs.
- [x] Mocked tests, migration checks, frontend checks.

Decisions: `@valorx.com` does not prove control of `valorxteam.com`; direct
verification uses the exact hostname (www alias normalized), not a substring.
A fallback email must be selected from bounded same-site homepage/contact-page
inspection, then verified by OTP. No SMTP or Stripe credentials are required
for mocked tests; missing production configuration fails closed. No account or
subscription system is introduced. Email sessions are HttpOnly capabilities.
Payment grants full report/fix access; only re-scans expire after 30 days.
Paid report links last one year by default, with mailbox re-verification when
the session expires. No LLM calls. Existing internal APIs remain available only
when customer mode is explicitly disabled for trusted local development.


Validation: 235 backend tests passed with real-model and browser suites excluded;
SMTP delivery and Stripe API responses/webhooks were mocked. Frontend ESLint,
TypeScript, Prettier and production build passed. Migration 0007 was applied to
the local app database and passed down/up/schema checks on the disposable test
database. No live email, payment or model inference was performed. Browser UI
visual verification remains omitted at the user's request.

Configuration still required by operator: Gmail SMTP username/from/app password,
Stripe secret key and endpoint signing secret, then test-mode end-to-end
confirmation before enabling live mode. Operator/contact/legal placeholders
remain as explicitly requested. The local verification secret was generated in
the ignored `.env` without printing it.
