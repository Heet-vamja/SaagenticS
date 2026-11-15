# Legal pages

The frontend has `/privacy` and `/terms` routes. They share the existing
marketing navigation, footer, fonts and product tokens, with a responsive
section index. Homepage/report footers and workspace navigation link to both.
Copyright notices use the year in `frontend/src/lib/legal.ts`.

## Operator placeholders

The user requested placeholders for operator name, public contact email, and
country/state. Update `frontend/src/lib/legal.ts` when those facts are known;
never substitute a made-up address or legal entity. Both pages visibly identify
themselves as drafts. Remove the draft banner in `components/legal-page.tsx`
only after the missing details and policy review are complete. Set the revision
date to the date the approved terms take effect.

The text is tailored to the current app: public scans, deterministic fixes,
optional feedback/action events, bearer report links, theme local storage, and
separately configured browser-agent inference. It does not claim that link
expiry deletes records, that hosted inference has a particular location, or
that a production retention/deletion process already exists. It does not add a
cookie banner, account flow, subscription terms, or acceptance gate.

## Before public launch

Confirm the real operator/contact, applicable jurisdictions and legal bases,
production processors/locations, retention and deletion procedures, and any
analytics or cookies added by hosting. Arrange an appropriate legal review;
these pages do not establish regulatory compliance or a complete binding
agreement on their own. Review the current developer-workspace limitations
before operating a public multi-user service. Keep policies accurate as the
service changes.

Drafting references:
- [ICO: writing a privacy notice](https://ico.org.uk/for-organisations/advice-for-small-organisations/privacy-notices-and-cookies/how-to-write-a-privacy-notice-and-what-goes-in-it/)
- [FTC: privacy and security guidance](https://www.ftc.gov/business-guidance/privacy-security)

Verify changes with `npm run lint`, `npm run typecheck`,
`npm run format:check`, and `npm run build` from `frontend`.
Browser inspection was not performed under the user's no-computer-control
instruction.
