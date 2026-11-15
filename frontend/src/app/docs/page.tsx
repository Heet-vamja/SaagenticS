import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  CalendarClock,
  Globe2,
  ListChecks,
  Lock,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { MarketingNav, MarketingFooter } from "@/components/marketing-nav";
import { Button } from "@/components/ui/button";

const STEPS = [
  {
    id: "getting-started",
    icon: Globe2,
    tone: "violet",
    step: "01",
    title: "Start with a scan",
    text: "Enter your domain on the homepage and verify any email address you can receive a code at. The free scan checks up to 10 public pages using robots.txt, sitemaps and internal links, without calling a model. The first product focus is SaaS pricing, documentation and signup/demo discovery. The preliminary static score shows only measured checks and their coverage.",
  },
  {
    id: "fixes",
    icon: Bot,
    tone: "lime",
    step: "02",
    title: "Use your Fix Center",
    text: "The $19 one-time domain report unlock includes evidence-backed prompts for confirmed failing checks. Each prompt is intended for a coding assistant, general LLM, or developer ticket. Paid access includes same-domain re-scans for 30 days after payment confirmation, subject to normal scan limits. Validated llms.txt, WebSite markup and sitemap drafts use observed crawl data. Missing facts are listed instead of invented. Review every change before publishing. Download the fix pack to share it with your developer.",
  },
  {
    id: "outcomes",
    icon: ShieldCheck,
    tone: "ink",
    step: "03",
    title: "Re-scan to verify",
    text: "After a change is deployed, use Re-scan to verify from the report. The new report compares against that exact baseline. Only an explicit pass for the same rule and page confirms a fix; missing, untested or inconclusive checks do not. Marking a fix applied is a self-report until a rescan confirms it. Scores never guarantee visibility in AI answers.",
  },
] as const;

const TOC = [
  ["getting-started", "Start with a scan"],
  ["fixes", "Use your Fix Center"],
  ["outcomes", "Re-scan to verify"],
  ["agent", "AI agent testing"],
  ["api", "API essentials"],
  ["data", "Privacy & data handling"],
  ["agentready", "AgentReady mapping"],
] as const;

function SectionIcon({
  icon: Icon,
  tone,
}: {
  icon: typeof Globe2;
  tone: string;
}) {
  return (
    <span className="icon-tile shrink-0" data-tone={tone} aria-hidden="true">
      <Icon size={20} strokeWidth={2} />
    </span>
  );
}

export default function DocumentationPage() {
  return (
    <>
      <MarketingNav />
      <main id="main-content">
        <header className="marketing-wrap pb-14 pt-16 text-center sm:pb-20 sm:pt-24">
          <p className="chip">
            <span className="chip-dot" aria-hidden="true" />
            Documentation
          </p>
          <h1 className="display-lg mx-auto mt-6 max-w-[16ch]">
            A practical guide to{" "}
            <span className="text-primary">AgentLane.</span>
          </h1>
          <p className="lede mx-auto mt-6 max-w-2xl">
            Start with your SaaS website, inspect the evidence, give your
            developer a practical fix prompt, and check the improvement with a
            rescan.
          </p>
        </header>

        <div className="marketing-wrap grid items-start gap-10 pb-20 lg:grid-cols-[220px_minmax(0,1fr)] lg:gap-16">
          <nav
            aria-label="On this page"
            className="rounded-3xl border bg-card p-5 lg:sticky lg:top-24 lg:border-0 lg:bg-transparent lg:p-0"
          >
            <p className="eyebrow mb-3">On this page</p>
            <ol className="grid gap-0.5 sm:grid-cols-2 lg:grid-cols-1">
              {TOC.map(([id, label]) => (
                <li key={id}>
                  <a
                    href={`#${id}`}
                    className="block rounded-xl px-3 py-2 text-[14px] font-medium text-muted-foreground hover:bg-muted hover:text-foreground"
                  >
                    {label}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <div className="min-w-0 max-w-[760px] space-y-6">
            {STEPS.map(({ id, icon, tone, step, title, text }) => (
              <section
                id={id}
                key={id}
                className="surface scroll-mt-24 p-6 sm:p-8"
              >
                <div className="flex items-center gap-4">
                  <SectionIcon icon={icon} tone={tone} />
                  <div>
                    <p className="font-mono text-[12px] tracking-[.08em] text-muted-foreground">
                      STEP {step}
                    </p>
                    <h2 className="text-[24px] leading-tight">{title}</h2>
                  </div>
                </div>
                <p className="mt-5 text-[16px] leading-8 text-muted-foreground">
                  {text}
                </p>
              </section>
            ))}

            <section
              id="agent"
              className="scroll-mt-24 rounded-[var(--radius-card)] bg-accent-soft p-6 sm:p-8"
            >
              <div className="flex flex-wrap items-center gap-4">
                <SectionIcon icon={CalendarClock} tone="violet" />
                <h2 className="text-[24px] leading-tight">
                  AI agent testing{" "}
                  <span className="whitespace-nowrap text-signal">
                    · Coming Christmas 2026
                  </span>
                </h2>
              </div>
              <p className="mt-5 text-[16px] leading-8 text-foreground/80">
                Real browser-agent testing and agent outcome reports are not
                available in the current customer product. They are planned for
                Christmas 2026 and are not included in the $19 static report.
                Today’s score reflects deterministic checks only, not real task
                completion or AI-search visibility.
              </p>
            </section>

            <section id="api" className="surface scroll-mt-24 p-6 sm:p-8">
              <div className="flex items-center gap-4">
                <SectionIcon icon={Terminal} tone="ink" />
                <h2 className="text-[24px] leading-tight">API essentials</h2>
              </div>
              <p className="mt-5 text-[16px] leading-8 text-muted-foreground">
                The frontend uses the existing same-origin /api/v1 API. Lists
                support limit and offset pagination.
              </p>
              <pre
                tabIndex={0}
                aria-label="Free report API endpoints"
                className="mt-6 overflow-x-auto rounded-2xl bg-ink p-5 font-mono text-[13px] leading-7 text-ink-foreground outline-offset-4 dark:border dark:border-border"
              >
                <code>
                  <span className="text-lime">POST</span>
                  {" /api/v1/free-scans\n"}
                  <span className="text-lime">GET </span>
                  {" /api/v1/free-reports/{token}\n"}
                  <span className="text-lime">GET </span>
                  {" /api/v1/free-reports/{token}/fix-center\n"}
                  <span className="text-lime">GET </span>
                  {" /api/v1/free-reports/{token}/fix-pack.zip\n"}
                  <span className="text-lime">POST</span>
                  {" /api/v1/free-reports/{token}/rescan"}
                </code>
              </pre>
            </section>

            <section id="data" className="surface scroll-mt-24 p-6 sm:p-8">
              <div className="flex items-center gap-4">
                <SectionIcon icon={Lock} tone="violet" />
                <h2 className="text-[24px] leading-tight">
                  Privacy & data handling
                </h2>
              </div>
              <p className="mt-5 text-[16px] leading-8 text-muted-foreground">
                Use public, unauthenticated websites. The browser uses an
                isolated context; submissions, uploads, downloads, and private
                network destinations are blocked. Input values and browser
                credentials are excluded from model observations. Page metadata,
                bounded execution traces, and locally stored screenshots are
                retained. Screenshots mask form inputs, but public page content
                may still contain sensitive information. Fix-copy/download
                actions, self-reported applied changes and optional
                usefulness/price-interest feedback are stored against the report
                link to evaluate the product pilot.
              </p>
              <p className="mt-4 text-[16px] leading-8 text-muted-foreground">
                Customer mode requires a verified email session and protects
                full reports and downloads behind a paid entitlement. Legacy
                internal workspace APIs are disabled in customer mode; the
                internal development mode is for trusted local use only.
                In-process jobs do not resume after a restart; expired jobs are
                marked failed. This guide describes the current implementation
                and is not a legal privacy policy.
              </p>
            </section>

            <section
              id="agentready"
              className="scroll-mt-24 rounded-[var(--radius-card)] border bg-muted p-6 sm:p-8"
            >
              <div className="flex items-center gap-4">
                <SectionIcon icon={ListChecks} tone="lime" />
                <h2 className="text-[24px] leading-tight">
                  How our checks relate to AgentReady
                </h2>
              </div>
              <p className="mt-5 text-[16px] leading-8 text-muted-foreground">
                We reference AgentReady v2.0.1 as a versioned checklist, not a
                certification or scoring formula. Our current checks provide
                partial signals for 14 of its 24 requirements: discovery, HTTP
                behavior, rendering, linked resources, code-example annotations,
                llms.txt, JSON-LD, an AI Catalog, Markdown alternates, pricing
                text in HTML, linked OpenAPI contracts and catalog-listed MCP
                server cards. Documentation accuracy, OpenAPI completeness,
                authentication, MCP/CLI usability and agent payments remain
                unassessed. HTML labels do not establish WebMCP support.
              </p>
              <p className="mt-4 text-[16px] leading-8 text-muted-foreground">
                Full reports show which mapped measurements were actually
                recorded and which remain inconclusive or untested. Existing
                scores and free-report limits stay the same. This mapping is
                independent of and is not endorsed by the specification authors.
              </p>
              <a
                className="mt-6 inline-flex items-center gap-1.5 text-[15px] font-semibold text-primary underline decoration-2 underline-offset-4 hover:decoration-primary/40"
                href="https://github.com/agentready-org/standard/blob/main/spec/spec.md"
                target="_blank"
                rel="noopener noreferrer"
              >
                Read the AgentReady specification
                <ArrowUpRight size={15} />
              </a>
            </section>

            <section className="rounded-[var(--radius-card)] bg-primary px-6 py-10 text-center text-primary-foreground sm:px-10 sm:py-14">
              <h2 className="display-md">Ready when you are.</h2>
              <Button asChild variant="lime" size="lg" className="mt-7">
                <Link href="/#scan">
                  Scan your website
                  <ArrowRight size={17} />
                </Link>
              </Button>
            </section>
          </div>
        </div>
      </main>
      <MarketingFooter />
    </>
  );
}
