import type { Metadata } from "next";
import { LegalPage, type LegalSection } from "@/components/legal-page";
import { LEGAL_DETAILS } from "@/lib/legal";

export const metadata: Metadata = {
  title: "Privacy Policy | AgentLane",
  description:
    "How AgentLane handles submitted websites, scan evidence, report links, and browser preferences.",
};
const sections: LegalSection[] = [
  {
    id: "operator",
    title: "Who operates this service",
    content: (
      <>
        <p>
          AgentLane helps website operators identify technical barriers that may
          affect AI agents. This policy describes the current website-scanning
          service and its related reports.
        </p>
        <p>
          Operator: {LEGAL_DETAILS.operator}
          <br />
          Contact: {LEGAL_DETAILS.email}
          <br />
          Location: {LEGAL_DETAILS.jurisdiction}
        </p>
      </>
    ),
  },
  {
    id: "information",
    title: "Information we process",
    content: (
      <>
        <p>
          Before scanning, we process the email address and website domain you
          submit. We send a one-time code through the configured email provider,
          such as Gmail SMTP. Codes are stored as keyed hashes, expire after 10
          minutes, and have attempt and delivery limits. Verified session tokens
          are stored as hashes; email addresses and domain-access records are
          stored in the database. When you start a scan, we process the website
          address you submit and create scan and report records. Crawling and
          auditing can collect public page URLs, titles, descriptions, headings,
          links, response details, structured data, technical findings, and
          bounded evidence snippets.
        </p>
        <p>
          We also store report-related actions, such as copying a fix,
          downloading an asset, marking a change applied, requesting a re-scan,
          and submitting optional usefulness feedback. Technical request
          information may be processed in application or hosting logs for
          operation and abuse prevention.
        </p>
        <p>
          Separately configured browser-agent tests may retain action summaries,
          model identifiers, execution errors, token usage, and screenshots.
          Public page content can contain personal information even when no
          login is required. Do not submit private URLs, credentials, or
          sensitive information.
        </p>
      </>
    ),
  },
  {
    id: "purposes",
    title: "Why we use this information",
    content: (
      <p>
        We use this information to perform the requested checks, calculate
        evidence-based scores, generate reports and deterministic fix materials,
        compare re-scans, diagnose failures, protect the service from abuse, and
        understand whether the product is useful. The current product does not
        include advertising trackers or a personal-data sales feature.
        Operator-specific legal bases for processing must be completed once the
        operator and applicable jurisdictions are confirmed.
      </p>
    ),
  },
  {
    id: "models",
    title: "Static scans and model processing",
    content: (
      <>
        <p>
          The anonymous free scan and deterministic Fix Center do not call an
          LLM. Copying a generated prompt gives you text to review and use with
          your own coding assistant; we do not send that prompt to your
          assistant on your behalf.
        </p>
        <p>
          Real agent tests are coming Christmas 2026 and are disabled in the
          customer product. If enabled separately in a private development
          deployment, agent tests send bounded page observations and task
          context to the configured inference endpoint. That endpoint can run
          locally or use a hosted open-weight model provider. Its operator and
          location depend on the deployment. Review its terms before enabling
          hosted inference. Model observations are designed to exclude
          credentials and form input values; public page text may still contain
          personal information.
        </p>
      </>
    ),
  },
  {
    id: "agent-lane",
    title: "AgentLane router and agent lane (in development)",
    content: (
      <>
        <p>
          These features are in development and apply only to sites whose
          operator has set them up. When an operator routes a domain through the
          AgentLane router, requests to that domain pass through our service.
          Requests from people are forwarded to the operator’s site unchanged
          and are not logged by the router. Requests whose user agent identifies
          a known AI agent or crawler are logged with the agent name and type,
          the user-agent string, the request method, the path without its query
          string, the response status, timing and size, whether the agent lane
          answered, any agent action called, and a keyed hash of the client
          network address. Raw addresses and query strings are not stored.
          Logged requests are grouped into sessions per agent and kept in the
          application database and, if the operator enables it, copied to Google
          BigQuery.
        </p>
        <p>
          To build an agent lane, we render a bounded number of public pages of
          the operator’s site (50 by default) and send the public page text, and
          the public data those pages load, to Google’s Gemini API to extract
          products, prices, policies and common tasks. To label sessions, we
          send Gemini each session’s request list (agent name, times, methods,
          paths, statuses and actions, without client hashes). Agent QA sends
          screenshots of the operator’s own site to Gemini Computer Use. Google
          processes this content under its Gemini API terms, which differ
          between free and paid plans; operators should review them. Session
          labels are model judgments and are shown as such.
        </p>
      </>
    ),
  },
  {
    id: "sharing",
    title: "Report links and other recipients",
    content: (
      <>
        <p>
          Report links are access capabilities. Customer reports also require a
          verified session for the associated website mailbox. Full evidence,
          fixes, and downloads additionally require a confirmed paid
          entitlement. Keep report links private. Unpaid links normally last
          seven days; paid links normally last one year. Same-domain re-scans
          are included for 30 days after payment confirmation. These access
          periods do not automatically delete stored records or exported copies.
        </p>
        <p>
          Gmail SMTP or another configured email provider delivers verification
          codes. Stripe processes hosted checkout and receives your verified
          email, the domain report product, order reference and report return
          link. Payment-card details are entered on Stripe’s website and are not
          stored by this application. We retain payment identifiers, payment
          status and entitlement dates to provide access and handle duplicate
          webhooks, refunds and disputes.
        </p>
        <p>
          Hosting, database and infrastructure providers may process information
          needed to operate the service. A scanned website receives our network
          requests. Processing locations and a deployment-specific provider list
          remain pending operator review. We may disclose information when
          required by applicable law or to investigate misuse.
        </p>
      </>
    ),
  },
  {
    id: "storage",
    title: "Browser storage and cookies",
    content: (
      <p>
        Browser local storage remembers your light or dark theme. A necessary
        HttpOnly, SameSite cookie holds a random verified-session capability for
        up to 30 days. Clearing cookies or session expiry requires mailbox
        verification again; it does not cancel a purchase. The current
        application does not implement advertising cookies or third-party
        analytics scripts. Hosting infrastructure may have its own technical
        logging; deployment-specific disclosures must be added if that changes.
      </p>
    ),
  },
  {
    id: "retention",
    title: "Retention and security",
    content: (
      <>
        <p>
          Scan records, findings, fix events, and generated materials are stored
          in the application database. Separately configured agent screenshots
          are stored with execution artifacts. Report access expires according
          to the deployment settings, but expiry does not automatically delete
          the underlying scan records, exports, logs, or backups. Router logs,
          agent sessions, agent lane versions and QA results are kept until the
          operator removes them.
        </p>
        <p>
          A production retention schedule and deletion contact are not yet
          finalized. Until a deletion or cleanup process is applied by the
          operator, stored records can remain in the deployment. Do not treat an
          expiring link as a deletion guarantee.
        </p>
        <p>
          Controls include bounded scanning, network restrictions, restricted
          report access, and evidence redaction where implemented. No system is
          completely secure. Customer mode restricts access by verified mailbox
          and domain and disables internal workspace APIs. Internal development
          mode lacks account-based tenant isolation and must remain private.
        </p>
      </>
    ),
  },
  {
    id: "rights",
    title: "Your choices and requests",
    content: (
      <>
        <p>
          Depending on the laws that apply to you, you may have rights to
          request access, correction, deletion, restriction, portability, or
          objection to processing, and to raise a concern with a relevant
          supervisory authority. These rights can have exceptions. Where
          processing relies on consent, you may withdraw it without affecting
          earlier lawful processing.
        </p>
        <p>
          Privacy requests should be sent to {LEGAL_DETAILS.email}. This is a
          placeholder, not a working contact address. We may need enough
          information to locate the record and confirm that you are entitled to
          make the request. Do not publish report access keys or sensitive
          evidence in public support channels.
        </p>
      </>
    ),
  },
  {
    id: "children",
    title: "Children and sensitive information",
    content: (
      <p>
        The service is intended for people responsible for business websites,
        not for children. Do not submit children’s information, sensitive
        personal data, authenticated sessions, or private records. If you
        believe such information was stored, contact the operator using the
        completed details above.
      </p>
    ),
  },
  {
    id: "updates",
    title: "Changes to this policy",
    content: (
      <p>
        We may update this policy as the service changes. The latest version
        will appear here with a revised date. Material changes to data handling
        should be communicated before they take effect where applicable law
        requires it.
      </p>
    ),
  },
];
export default function PrivacyPage() {
  return (
    <LegalPage
      title="Privacy Policy"
      description="What we collect, why we need it, and how your scan information is handled. Written for the service we actually provide."
      sections={sections}
    />
  );
}
