import type { Metadata } from "next";
import Link from "next/link";
import { LegalPage, type LegalSection } from "@/components/legal-page";
import { LEGAL_DETAILS } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Terms & Conditions | AgentLane",
  description:
    "Terms for responsible website scanning, readiness reports, generated fixes, and use of AgentLane.",
};
const sections: LegalSection[] = [
  {
    id: "agreement",
    title: "About these terms",
    content: (
      <>
        <p>
          These Terms & Conditions describe the conditions for using AgentLane,
          including website scans, reports, generated fix materials, and paid
          domain report unlocks. Real browser-agent testing is coming Christmas
          2026 and is not included in the current purchase. Use the service only
          if you have legal capacity to enter an agreement and accept these
          terms. If you do not agree, do not use the service.
        </p>
        <p>
          Service operator: {LEGAL_DETAILS.operator}
          <br />
          Contact: {LEGAL_DETAILS.email}
        </p>
      </>
    ),
  },
  {
    id: "service",
    title: "What the service provides",
    content: (
      <>
        <p>
          AgentLane inspects public website content and technical signals to
          identify potential barriers for AI agents. Reports can include
          preliminary scores, findings, evidence, deterministic fix prompts,
          generated asset drafts, and re-scan comparisons. Availability and
          coverage depend on the deployment and the website being inspected.
        </p>
        <p>
          A static score does not prove that an agent can complete a task and
          does not guarantee ranking, recommendations, or visibility in ChatGPT
          or any other AI product. Agent-declared completion is separate from
          independently verified success. Our references to third-party models
          and brands do not imply affiliation or endorsement.
        </p>
      </>
    ),
  },
  {
    id: "authorization",
    title: "Your authority and responsibilities",
    content: (
      <>
        <p>
          Submit only public websites you own, manage, or are authorized to
          assess. You must receive a one-time code at an email address you
          control. This verifies mailbox access, not website ownership; you must
          still have authorization. Public availability alone does not grant you
          permission to conduct every type of test. You are responsible for
          complying with applicable laws, the website’s terms, and the scope of
          your authorization.
        </p>
        <p>
          Do not submit credentials, private access tokens, sensitive
          information, or authenticated sessions. Obtain any necessary consent
          or permissions before providing third-party information. You remain
          responsible for your website, code, deployment decisions, and any
          changes you apply.
        </p>
      </>
    ),
  },
  {
    id: "acceptable-use",
    title: "Acceptable use",
    content: (
      <ul>
        <li>
          Do not use the service for unlawful activity, harassment, unauthorized
          security testing, or collecting private information.
        </li>
        <li>
          Do not bypass robots restrictions, authentication, CAPTCHAs, rate
          limits, domain restrictions, or other safeguards.
        </li>
        <li>
          Do not attempt to access internal networks, attack the service,
          overload websites, or interfere with other users.
        </li>
        <li>
          Do not enable purchases, account creation, deletions, form
          submissions, or other state-changing interactions through read-only
          tests.
        </li>
        <li>
          Do not misrepresent a report, claim that an untested workflow passed,
          or imply endorsement by an AI provider.
        </li>
      </ul>
    ),
  },
  {
    id: "results",
    title: "Reports, fixes, and limitations",
    content: (
      <>
        <p>
          Results are limited to the pages, observations, and checks actually
          performed at the time of a scan. Blocked access, JavaScript behavior,
          network failures, sampling limits, and later website changes may
          affect completeness. Unknown or inconclusive checks are not
          confirmations of success.
        </p>
        <p>
          Generated prompts and assets are drafts. Review them for accuracy,
          completeness, accessibility, compatibility, security, and legal
          suitability before use. Back up your code and test changes before
          deployment. A robots policy proposal must not weaken existing
          protections. Never publish invented or unverified business facts in
          generated structured data.
        </p>
        <p>
          A re-scan can confirm a specific check only when new evidence supports
          it. It cannot guarantee that every problem is fixed or that every AI
          agent will behave the same way.
        </p>
      </>
    ),
  },
  {
    id: "data",
    title: "Your data and report access",
    content: (
      <>
        <p>
          You retain the rights you hold in submitted website content and other
          materials. You authorize the operator to fetch, process, store, and
          display that material as needed to provide the requested service,
          reports, fixes, and re-scan comparisons, subject to the{" "}
          <Link href="/privacy">Privacy Policy</Link>.
        </p>
        <p>
          You are responsible for protecting report links and for sharing
          reports and exports appropriately. Expiration of an access link does
          not erase copies already exported or shared. Use of a report does not
          transfer ownership of the scanned website or its content.
        </p>
      </>
    ),
  },
  {
    id: "intellectual-property",
    title: "Intellectual property and copyright",
    content: (
      <>
        <p>
          Original AgentLane branding, interface design, and website content
          belong to their respective rights holders. Do not copy branding,
          remove attribution notices, impersonate the service, or use the
          interface in a misleading way.
        </p>
        <p>
          You may use and adapt generated fix prompts and asset drafts for
          websites you are authorized to manage, subject to any rights in source
          content. Third-party content, trademarks, fonts, and open-source
          software remain subject to their own licenses and rights. A website
          copyright notice does not replace an applicable open-source license or
          change its permissions.
        </p>
      </>
    ),
  },
  {
    id: "availability",
    title: "Availability and service changes",
    content: (
      <>
        <p>
          A full static report costs USD $19 as a one-time payment through
          Stripe. It includes detailed evidence, deterministic fix materials and
          same-domain re-scans for 30 days after payment confirmation, subject
          to normal page, queue, and rate limits. There is no subscription or
          automatic renewal. Access is associated with the verified mailbox and
          domain and does not unlock other domains. Real AI browser-agent
          testing is coming Christmas 2026 and is not included.
        </p>
        <p>
          Purchased report links normally remain available for one year. Mailbox
          re-verification is required when a session expires. The 30-day re-scan
          window expires separately; it does not remove access to an existing
          paid report while its link remains valid. A payment success redirect
          does not establish payment; access begins only after server-side
          confirmation. Refund requests should be sent to the operator contact,
          subject to mandatory legal rights. A full refund or disputed payment
          may suspend paid access.
        </p>
        <p>
          The service is an MVP and may contain errors or become unavailable. We
          may apply limits, interrupt scans, restrict misuse, or discontinue
          features. Do not use it as your only security, accessibility,
          compliance, or business-critical monitoring tool. Where no useful page
          evidence is available, the service does not offer a paid unlock; you
          may retry verification and scanning within normal usage limits.
        </p>
      </>
    ),
  },
  {
    id: "disclaimers",
    title: "Disclaimers and liability",
    content: (
      <>
        <p>
          To the extent permitted by applicable law, the service and its outputs
          are provided “as is” and “as available,” without guarantees of
          uninterrupted availability, accuracy, fitness for a particular
          purpose, or compatibility with every website or agent.
        </p>
        <p>
          To the extent permitted by applicable law, the operator is not
          responsible for indirect or consequential losses resulting from
          reliance on reports, generated materials, third-party services, or
          changes you choose to deploy. Nothing in these terms excludes
          liability that cannot lawfully be excluded, or limits mandatory
          consumer rights or other non-waivable protections.
        </p>
      </>
    ),
  },
  {
    id: "law",
    title: "Applicable law and disputes",
    content: (
      <p>
        Governing jurisdiction: {LEGAL_DETAILS.jurisdiction}. This detail
        remains pending operator review; no exclusive court or arbitration
        arrangement is specified in this draft. Mandatory rights and applicable
        laws continue to apply. Please contact the operator first if you have a
        concern so there is an opportunity to resolve it.
      </p>
    ),
  },
  {
    id: "changes",
    title: "Changes and contact",
    content: (
      <>
        <p>
          Revised terms will be posted here with an updated date. Material
          changes should be brought to users’ attention where required. These
          terms do not retroactively remove rights that applicable law protects.
        </p>
        <p>
          Questions about the service or these terms: {LEGAL_DETAILS.email}.
          This placeholder must be replaced with a working public contact before
          launch.
        </p>
      </>
    ),
  },
];
export default function TermsPage() {
  return (
    <LegalPage
      title="Terms & Conditions"
      description="A clear agreement for responsible scanning, useful reports, and careful implementation of the fixes you choose."
      sections={sections}
    />
  );
}
