import Link from "next/link";
import { ArrowRight, Bot, Globe2, ShieldCheck } from "lucide-react";
import { MarketingNav, MarketingFooter } from "@/components/marketing-nav";
export default function DocumentationPage() {
  return (
    <>
      <MarketingNav />
      <main className="marketing-wrap max-w-[850px] py-16">
        <p className="eyebrow text-primary">Documentation</p>
        <h1 className="mt-4 text-4xl font-medium tracking-[-.05em]">
          A practical guide to AgentReadiness.
        </h1>
        <p className="mt-5 text-sm leading-7 text-muted-foreground">
          Start with a website, discover its pages, and give a real browser
          agent a task. Here is what the current product does—and how to read
          its results.
        </p>
        <div className="mt-10 space-y-6">
          {[
            {
              id: "getting-started",
              icon: Globe2,
              title: "01 / Start with a scan",
              text: "Enter a public HTTP or HTTPS website URL on the homepage, or create a project in your workspace. A scan inspects robots.txt, sitemaps, and internal pages. By default, it crawls up to 30 pages and follows only the configured hostname. If your website redirects to www, use its canonical www URL.",
            },
            {
              id: "agent",
              icon: Bot,
              title: "02 / Run an agent test",
              text: "Open a scan and choose Find Pricing, Find Documentation, or Find Signup or Demo Form. A configured Hugging Face model chooses actions from observations in a real Playwright browser. Additional domains must be explicitly authorized. Execution is limited to 15 steps and 120 seconds. Hosted inference requires a working HF_TOKEN and inference credits; a compatible local model server is also supported.",
            },
            {
              id: "outcomes",
              icon: ShieldCheck,
              title: "03 / Read the evidence",
              text: "Select an execution to see its timeline, model, action results, observations, and screenshots. Completed means the agent declared completion. It is not independently verified success. New scans include static readiness scores, deterministic findings, priority fixes, exports, and shareable reports. Static scores exclude agent task success. Checks blocked by network policy or execution limits are inconclusive. An HTTP 402 inference error means model credits or billing must be configured.",
            },
          ].map(({ id, icon: Icon, title, text }) => (
            <section id={id} key={id} className="surface p-7">
              <Icon className="mb-5 text-primary" size={24} strokeWidth={1.5} />
              <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
              <p className="mt-3 text-sm leading-7 text-muted-foreground">
                {text}
              </p>
            </section>
          ))}
          <section id="api" className="surface p-7">
            <h2 className="text-lg font-semibold tracking-tight">
              API essentials
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              The frontend uses the existing same-origin /api/v1 API. Lists
              support limit and offset pagination.
            </p>
            <pre
              tabIndex={0}
              className="code-panel mt-5"
            >{`POST /api/v1/projects\nPOST /api/v1/projects/{project_id}/scans\nGET  /api/v1/scans/{scan_id}/pages\nPOST /api/v1/scans/{scan_id}/agent-tests\nGET  /api/v1/agent-tests/{test_id}\nGET  /api/v1/agent-tests/{test_id}/steps`}</pre>
          </section>
          <section id="data" className="surface p-7">
            <h2 className="text-lg font-semibold tracking-tight">
              Privacy & data handling
            </h2>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              Use public, unauthenticated websites. The browser uses an isolated
              context; submissions, uploads, downloads, and private network
              destinations are blocked. Input values and browser credentials are
              excluded from model observations. Page metadata, bounded execution
              traces, and locally stored screenshots are retained. Screenshots
              mask form inputs, but public page content may still contain
              sensitive information.
            </p>
            <p className="mt-3 text-sm leading-7 text-muted-foreground">
              This development workspace has no authentication or tenant
              isolation. It is intended for trusted local use. In-process jobs
              do not resume after a restart; expired jobs are marked failed.
              This guide describes the current implementation and is not a legal
              privacy policy.
            </p>
          </section>
        </div>
        <Link
          href="/dashboard"
          className="mt-8 inline-flex items-center gap-2 text-sm font-medium text-primary"
        >
          Open your workspace
          <ArrowRight size={15} />
        </Link>
      </main>
      <MarketingFooter />
    </>
  );
}
