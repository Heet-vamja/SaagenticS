# Verified website scans and USD $19 full reports

The public product is now: domain → verified email → static score and up to 10
priority issues with practical solutions → optional one-time $19 full-report unlock. Real browser-agent
execution and outcome reporting are **Coming Christmas 2026**. Customer mode
never runs or resumes model jobs, and model health probing is disabled there.
No account/password or subscription system is introduced.

## Email verification

Any mailbox the requester can receive mail at may verify; the address no longer
has to match the website's domain. Verification still proves mailbox access only,
not website ownership, and each verified session is bound to the one website it
was requested for (subdomains are separate scopes). Scanning another website needs
a new code. The terms still require users to scan only websites they own, manage
or are authorized to assess, and scans stay read-only, robots-aware and bounded.

The published-contact discovery endpoint remains available to API clients but is
no longer offered in the verification dialog. It inspects at most four
robots-permitted, same-site homepage/contact pages through the DNS-pinned
validated transport and never bypasses network, redirect, robots or
authentication restrictions.

Six-digit OTPs use cryptographic randomness and keyed hashes, expire in ten
minutes, allow five attempts, and are consumed once. Per-IP/domain/recipient
limits, a one-minute recipient cooldown, and a pilot-wide 100-email/day cap are
persisted in PostgreSQL to protect the personal sending account. Codes
are never returned in API responses or printed to logs. SMTP failure invalidates
the code. A verified HttpOnly, SameSite=Lax session cookie lasts up to 30 days.
Mailbox verification does not replace the user's responsibility to obtain
permission to scan the website.

## Configure Gmail safely

Put secrets only in the ignored root `.env`, never in source, screenshots or
chat. A local `VERIFICATION_SECRET` has already been generated without printing
it. For a new installation generate a random secret of at least 32 characters.

```dotenv
CUSTOMER_MODE_ENABLED=true
AGENT_PIPELINE_ENABLED=false
VERIFICATION_SECRET=your-generated-random-secret
PUBLIC_SITE_URL=http://localhost:13000
VERIFICATION_COOKIE_SECURE=false
SMTP_HOST=smtp.gmail.com
SMTP_PORT=465
SMTP_STARTTLS=false
SMTP_USERNAME=your-personal-address@gmail.com
SMTP_FROM=AgentLane <your-personal-address@gmail.com>
SMTP_PASSWORD=your-google-app-password
```

Use your actual frontend port. In production use an HTTPS `PUBLIC_SITE_URL` and
`VERIFICATION_COOKIE_SECURE=true`. Google app passwords require 2-Step
Verification and may be unavailable for some account policies. Use an app
password, **not your normal Google password**. Use the same Gmail address or an
approved sending alias for the From field. OAuth 2.0 is an alternative Gmail
transport but is not implemented in this pass. Any SMTP service supporting TLS
can replace Gmail; for STARTTLS use port 587 and `SMTP_STARTTLS=true`.

Gmail is suitable for a small pilot, subject to its delivery limits. No email
was sent during automated verification; delivery needs a configured account.

## Stripe configuration

```dotenv
STRIPE_SECRET_KEY=sk_test_your-key
STRIPE_WEBHOOK_SECRET=whsec_your-endpoint-secret
STRIPE_LIVE_MODE=false
PAID_REPORT_DAYS=365
```

There is no required Stripe Price ID: the server creates a fixed USD 1900-cent
Checkout line item. Price, quantity, currency and target domain cannot be chosen
by the client. Configure `PUBLIC_SITE_URL` correctly; return URLs are never
constructed from untrusted Host headers.

For local testing, use the Stripe CLI in a separate terminal after signing in:

```sh
stripe listen --events checkout.session.completed,checkout.session.async_payment_succeeded,charge.refunded,charge.dispute.created --forward-to http://localhost:18000/api/v1/webhooks/stripe
```

Copy the CLI endpoint secret into `.env`, then recreate the backend. A Dashboard
endpoint has a different signing secret from the CLI. In production register
an HTTPS webhook endpoint for the same events, use `sk_live_...`, its live
`whsec_...`, `STRIPE_LIVE_MODE=true`, HTTPS and secure cookies. Live/test mode
mismatch is rejected before opening Checkout.

Only a signed raw-body webhook with a fresh timestamp and a matching order,
session, currency, USD $19 amount, mode and paid status can unlock a report.
The browser's `?checkout=success` flag never grants access. Processed events and
orders make retries idempotent. A full refund or dispute revokes paid access;
revocation events arriving before fulfillment prevent a later accidental grant.
Disputes require operator review before any manual reinstatement. The app does
not automatically issue refunds or collect subscription payments.

After success the report polls for payment confirmation for up to two minutes.
If confirmation is delayed, reload after the webhook is delivered. Stripe
retries failed webhook deliveries; use the Stripe Dashboard/CLI to diagnose
configuration errors. No actual Checkout or charge was tested without keys.

## Entitlements and API enforcement

The first useful scan preview is free per verified mailbox and domain.
Repeated unpaid requests return that existing preview instead of generating
unlimited new scans. Failed inspections without enough useful page evidence
may be retried free, under normal admission limits. Checkout refuses pending
or unscorable reports.

A paid order unlocks full checks, evidence, Fix Center, validated assets, fix
pack and PDF downloads for its mailbox/domain. Existing preview aliases for
the same verified mailbox/domain also unlock during the active window, avoiding
double charging. New same-domain scans/re-scans are included for 30 days after
first payment confirmation, with the normal page/rate/queue limits. Duplicate
webhooks never reset that clock. Purchased report access survives expiry of
only the re-scan window. Paid links last `PAID_REPORT_DAYS` (default one year);
email re-verification is needed when the session cookie expires. Other domains
and other mailboxes do not inherit a purchase.

Unpaid API responses exclude raw check rows, evidence, fix prompts,
recommendations, assets and downloads. The UI is not the security boundary.
Full-report endpoints return 402 without an entitlement. Expired sessions
return 401 and reports belonging to another verified mailbox return 403.
Legacy project/scan/share/agent APIs are blocked in customer mode to prevent
ownership and payment bypasses. Old workspace screens redirect to the homepage;
agent screens display the Christmas placeholder. Their implementation remains
in the repository for private development only.

`CUSTOMER_MODE_ENABLED=false` intentionally restores the internal development
API surface for trusted local development. **Never expose this mode publicly.**
It is also explicitly used by legacy internal API tests; launch tests enable
customer mode to verify the real access controls.

## Run and verify

```sh
docker compose up -d --build --force-recreate backend frontend
# Backend startup applies Alembic migration 0007.
```

Use your configured local ports. Enter a domain, receive its email OTP, review
the preview, complete Stripe **test-mode** Checkout, and verify that the webhook
unlocks the report. Re-scan once to confirm the new report inherits the purchase.
The app fails closed with configuration errors while SMTP or Stripe is blank.

Automated tests use captured email deliveries and mocked Stripe API responses,
never real recipients, payments or model calls:

```sh
cd backend
TEST_DATABASE_URL=postgresql+psycopg://agentreadiness:local-development-only@localhost:5432/agentreadiness_test .venv/bin/pytest -q tests/test_customer_launch.py
```

The launch migration adds verified mailbox sessions, domain purchases, webhook
receipts and report ownership/order references. It does not add user accounts.
Privacy and terms pages now disclose email verification, session cookies,
email/Stripe processors and the offer. The user-requested legal operator/contact
placeholders remain and need completion/review before live payments.

References: [Google app passwords](https://support.google.com/accounts/answer/185833),
[Gmail SMTP/OAuth](https://developers.google.com/workspace/gmail/imap/imap-smtp),
[Stripe fulfillment](https://docs.stripe.com/checkout/fulfillment), and
[Stripe webhook verification](https://docs.stripe.com/events/manage-webhook-endpoints).


## Optional local development skips

Set these in the ignored `.env` and recreate the backend:

```dotenv
APP_ENVIRONMENT=development
DEV_EMAIL_SHORTCUT_ENABLED=true
DEV_ACCESS_EMAIL=your-development-email
PUBLIC_SITE_URL=http://localhost:13000
VERIFICATION_COOKIE_SECURE=false
STRIPE_LIVE_MODE=false
```

The normal screens and actions remain the default:

1. Enter the public website, then an email. Local development permits any valid
   email, including a personal Gmail address, without requiring the website domain.
2. **Send verification code** attempts real delivery using configured SMTP. Enter
   the received code to test the normal flow, or explicitly choose
   **Skip verification (development)** on the OTP screen. When SMTP is unavailable,
   the screen clearly states that no email was sent and still offers the skip.
3. After the scan, the report stays locked. Use normal Stripe test checkout with
   configured test keys/webhook, or explicitly choose **Skip payment (development)**.
   Verification skips never automatically unlock payment.
4. A skipped payment grants this report and its re-scans development access, with
   no fabricated Stripe payment or paid order. The report/PDF labels the skip.

`DEV_ACCESS_EMAIL` supplies a convenient input hint; it is not a production
allowlist. Neither a matching address nor an untrusted Host/Origin header enables
skips. The server requires the explicit flag, development environment, loopback
`PUBLIC_SITE_URL`, and Stripe live mode off. Crawler/robots/SSRF protections and
per-domain session scope remain active. Never expose this development configuration
publicly. Production requires ordinary domain/published-email verification.

Migration 0008 labels development sessions; 0009 separates explicit report skips
from real entitlements and records Stripe test/live mode. Turning development
access off invalidates skipped/off-domain sessions and removes skipped report
unlocks. Test-mode purchases cannot unlock live-mode reports. Migration 0009
classifies existing payment rows as test-mode; reconcile any historical live
purchases before using it on an existing paid deployment.

Regression tests mock SMTP and Stripe; they never send mail or charge a card.
Real delivery and Stripe Checkout require your configured credentials.

## Free issue solutions and agent launch announcement

Free verified reports include up to 10 distinct issue types, prioritized using
existing severity/affected-page ranking, with deterministic recommendations.
Fewer real issues means fewer cards; no issues or fixes are fabricated. Solutions
are visible and copyable. Raw evidence, affected-page details, complete checks,
Fix Center prompts/assets, exports and 30-day re-scans remain paid.

The shared Christmas 2026 announcement highlights planned real-browser tasks.
It clearly states that these are coming soon and excluded from current scoring
and the $19 purchase. This change makes no model calls.

## Try-before-purchase Fix Kit

Verified, unpaid reports can fetch `GET /api/v1/free-reports/{token}/fix-preview`.
It returns at most **three items total**: distinct prioritized fix prompts first,
then structurally validated crawl-grounded asset drafts for unused slots.
The response includes remaining item counts, never the omitted contents.
No confirmed issues or usable pages means no fabricated sample. Existing
expiry, revocation, domain and mailbox rules apply. Full Fix Center, presets,
ZIP/PDF exports, event tracking and re-scans retain their paid access checks.

The free UI allows copying selected prompts and copying/downloading returned
asset drafts locally. This does not unlock other asset URLs or call an LLM.
The existing 10 short issue recommendations remain available; this preview adds
three practical, complete items from the paid kit so users can try the workflow.
