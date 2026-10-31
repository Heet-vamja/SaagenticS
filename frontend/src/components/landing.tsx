"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  Circle,
  FileSearch,
  Globe2,
  LoaderCircle,
  MousePointer2,
  ShieldCheck,
  Terminal,
  BookOpen,
  Fingerprint,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Project } from "@/lib/types";
import { Button } from "./ui/button";
import { MarketingFooter, MarketingNav } from "./marketing-nav";
import { InlineError } from "./states";
function WebsiteInput({ compact = false }: { compact?: boolean }) {
  const inputId = useId();
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const created = useRef<Project | null>(null);
  return (
    <form
      className={`website-entry ${compact ? "entry-compact" : ""}`}
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          const normalized = new URL(
            /^https?:\/\//i.test(url.trim())
              ? url.trim()
              : `https://${url.trim()}`,
          ).toString();
          let project = created.current;
          if (project?.website_url !== normalized) {
            const existing = await api.projects();
            project =
              existing.find((p) => p.website_url === normalized) ??
              (await api.createProject(
                new URL(normalized).hostname,
                normalized,
              ));
            created.current = project;
          }
          const scan = await api.createScan(project.id);
          router.push(`/scans/${scan.id}`);
        } catch (e) {
          setError(
            e instanceof Error
              ? e.message
              : "Could not start your scan. Please try again.",
          );
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        Website URL
      </label>
      <div className="entry-field">
        <Globe2
          className="ml-3 hidden shrink-0 text-muted-foreground sm:block"
          size={18}
          strokeWidth={1.6}
        />
        <input
          id={inputId}
          type="text"
          inputMode="url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://yourwebsite.com"
          maxLength={2048}
          required
          aria-describedby={
            error ? `${inputId}-error` : `${inputId}-description`
          }
          className="min-h-12 min-w-0 flex-1 rounded-lg bg-transparent px-3 text-sm outline-none placeholder:text-muted-foreground focus-visible:ring-2 focus-visible:ring-ring"
        />
        <Button className="entry-submit" disabled={busy}>
          {busy ? (
            <>
              <LoaderCircle size={15} className="animate-spin" />
              Starting your scan…
            </>
          ) : (
            <>
              Scan your website
              <ArrowRight size={15} />
            </>
          )}
        </Button>
      </div>
      {error ? (
        <div id={`${inputId}-error`} className="mt-3 text-left">
          <InlineError>{error}</InlineError>
        </div>
      ) : (
        <p id={`${inputId}-description`} className="entry-caption">
          <span className="inline-flex items-center gap-1.5">
            <Check size={12} className="text-primary" />
            No account required
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck size={12} className="text-primary" />
            Read-only testing
          </span>
          <span className="inline-flex items-center gap-1.5">
            <Bot size={12} className="text-primary" />
            Real browser agents
          </span>
        </p>
      )}
    </form>
  );
}

function AgentIllustration() {
  return (
    <div className="agent-illustration reveal-in">
      <div className="journey-heading">
        <span>
          <span className="signal-dot" /> THE AGENT’S VIEW
        </span>
        <span className="demo-label">ILLUSTRATIVE PRODUCT WALKTHROUGH</span>
      </div>
      <div className="journey-workbench">
        <aside className="journey-map">
          <span className="mini-eyebrow">THE PATH IT CHOSE</span>
          <ol>
            <li>
              <Globe2 size={16} />
              <div>
                Homepage<small>Observe navigation</small>
              </div>
              <Check size={12} />
            </li>
            <li>
              <MousePointer2 size={16} />
              <div>
                Pricing<small>Choose a relevant link</small>
              </div>
              <Check size={12} />
            </li>
            <li>
              <FileSearch size={16} />
              <div>
                Signup<small>Inspect required fields</small>
              </div>
              <Circle size={12} />
            </li>
          </ol>
          <div className="journey-model">
            <Bot size={16} />
            <span>
              Open-weight reasoning<small>Real Playwright browser</small>
            </span>
          </div>
        </aside>
        <div className="agent-window">
          <div className="demo-window-heading">
            <span>
              <Bot size={18} /> Decision stream
            </span>
            <span className="stream-tag">STEP 03</span>
          </div>
          <div className="session-body">
            <div className="session-task">
              <span className="mini-eyebrow">USER GOAL</span>Find pricing and
              inspect the signup form.
            </div>
            <ol className="session-actions">
              <li>
                <CheckCircle2 size={16} />
                <span>Pricing link discovered</span>
              </li>
              <li>
                <CheckCircle2 size={16} />
                <span>Available plans identified</span>
              </li>
              <li>
                <Circle size={16} />
                <span>Inspecting form controls</span>
              </li>
            </ol>
            <div className="agent-reply">
              <span className="agent-avatar">
                <Bot size={15} />
              </span>
              <p>
                The email field has a label. I can identify the required input
                without submitting the form.
              </p>
            </div>
            <div className="session-input">
              <span>observe</span>
              <ArrowRight size={12} />
              <span>reason</span>
              <ArrowRight size={12} />
              <span>act</span>
            </div>
          </div>
        </div>
        <div className="journey-page">
          <div className="browser-toolbar">
            <span className="traffic-dots">
              <i />
              <i />
              <i />
            </span>
            <span className="browser-address">northstar.example/signup</span>
            <ShieldCheck size={12} />
          </div>
          <div className="journey-page-content">
            <span className="sample-wordmark">
              <span />
              northstar
            </span>
            <h3>
              Make room
              <br />
              for your next idea.
            </h3>
            <p>
              A little less setup.
              <br />A lot more possibility.
            </p>
            <div className="sample-field">
              Work email <span>*</span>
              <span className="sample-input">you@company.com</span>
            </div>
            <div className="observed-control">
              <span>element_04</span>
              <span>Required · email</span>
            </div>
            <span className="sample-cta">
              Start your workspace <ArrowRight size={13} />
            </span>
            <span className="sample-readonly">
              <ShieldCheck size={11} />
              Illustration · forms are never submitted
            </span>
          </div>
        </div>
      </div>
      <div className="journey-footer">
        <span>
          <Fingerprint size={15} /> An explanation, an observation, and a
          screenshot at every step.
        </span>
        <span>Agent-declared outcomes are not independently verified.</span>
      </div>
    </div>
  );
}
function BrowserExample({ blocked = false }: { blocked?: boolean }) {
  return (
    <div>
      <div className="example-browser">
        <div className="browser-toolbar">
          <span className="traffic-dots">
            <i />
            <i />
            <i />
          </span>
          <span className="browser-address">
            northstar.example/{blocked ? "signup" : "pricing"}
          </span>
          <span className={blocked ? "http-bad" : "http-good"}>
            {blocked ? "403" : "200"}
          </span>
        </div>
        <div className="example-viewport">
          {blocked ? (
            <div className="blocked-content">
              <ShieldCheck size={28} strokeWidth={1} />
              <strong>One more step to continue.</strong>
              <span>Verifying your browser…</span>
              <div className="challenge-dots">
                <i />
                <i />
                <i />
              </div>
            </div>
          ) : (
            <div className="pricing-content">
              <span className="mini-eyebrow">A PLAN FOR YOUR NEXT CHAPTER</span>
              <h4>Build something great.</h4>
              <div className="mini-plans">
                {[
                  ["Starter", "$12"],
                  ["Team", "$29"],
                  ["Business", "$59"],
                ].map(([name, price], i) => (
                  <div key={name} className={i === 1 ? "featured-plan" : ""}>
                    <span>{name}</span>
                    <strong>
                      {price}
                      <small>/mo</small>
                    </strong>
                    <span className="mini-plan-button">
                      {i === 1 ? "Choose Team" : "Get started"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
        <div
          className={`browser-observation ${blocked ? "observation-bad" : ""}`}
        >
          <Terminal size={12} />
          <span>
            {blocked
              ? "Agent observed: access restricted"
              : "Agent observed: plan names, prices, signup links"}
          </span>
        </div>
      </div>
      <div className="example-caption">
        <span className={blocked ? "caption-dot bad" : "caption-dot"} />
        <h3>
          {blocked ? "A journey that stops." : "A journey that continues."}
        </h3>
        <p>
          {blocked
            ? "A page can work for a person while an agent encounters an access restriction. We record the failure and stop."
            : "Clear content and usable controls let an agent find the information it needs and decide what to do next."}
        </p>
      </div>
    </div>
  );
}
export function ProductPreview() {
  return (
    <div className="readiness-report">
      <div className="report-heading">
        <span className="report-site">
          <span>N</span>northstar.example
        </span>
        <span className="demo-label">ILLUSTRATIVE PRODUCT DEMO</span>
      </div>
      <div className="report-columns">
        <div className="report-overview">
          <span className="mini-eyebrow">WEBSITE DISCOVERY</span>
          <div className="report-number">
            24<span>pages found</span>
          </div>
          <p>A map of what an agent can reach.</p>
          <div className="report-bars">
            {[
              ["Pages crawled", 90],
              ["Internal links", 76],
              ["Page metadata", 64],
            ].map(([name, width]) => (
              <div key={name}>
                <span>{name}</span>
                <i>
                  <b style={{ width: `${width}%` }} />
                </i>
              </div>
            ))}
          </div>
          <span className="report-footnote">
            Example values · No readiness score calculated
          </span>
        </div>
        <div className="report-results">
          <span className="mini-eyebrow">FOLLOW THE EVIDENCE</span>
          {[
            [Globe2, "Discovery", "Pages, links, robots and sitemaps"],
            [
              MousePointer2,
              "Browser navigation",
              "The action chosen at each step",
            ],
            [
              FileSearch,
              "Observed friction",
              "Errors, missing labels and stopped journeys",
            ],
          ].map(([Icon, title, description], i) => {
            const I = Icon as typeof Bot;
            return (
              <div className="report-result" key={String(title)}>
                <span className="report-index">0{i + 1}</span>
                <div>
                  <strong>{String(title)}</strong>
                  <p>{String(description)}</p>
                </div>
                <I size={16} />
              </div>
            );
          })}
          <p className="report-disclaimer">
            Illustrative observations. Live scans now include deterministic
            audits; agent task evaluation remains separate.
          </p>
        </div>
      </div>
    </div>
  );
}
export function Landing() {
  return (
    <main className="landing-editorial" id="main-content">
      <div className="landing-dark hero-region">
        <MarketingNav dark />
        <div>
          <section id="scan" className="editorial-wrap hero-layout">
            <div className="hero-copy reveal-in">
              <p className="hero-kicker">
                <span className="signal-dot" /> THE WEB HAS A NEW KIND OF USER
              </p>
              <h1>
                Can AI agents <span className="hero-highlight">actually</span>
                <br className="hero-linebreak" />
                use your website?
              </h1>
              <p className="hero-description">
                Test your website with real AI browser agents. Discover
                navigation failures, broken workflows, and opportunities to
                become agent-ready.
              </p>
              <WebsiteInput />
              <Link className="hero-underlink" href="/docs#agent">
                See what happens inside a real agent test{" "}
                <ArrowUpRight size={12} />
              </Link>
            </div>
            <AgentIllustration />
            <div className="hero-capabilities">
              <span>Built on an open stack</span>
              <span>
                <Bot size={16} /> Hugging Face
              </span>
              <span>
                <MousePointer2 size={16} /> Playwright
              </span>
              <span>
                <Globe2 size={16} /> Real websites
              </span>
              <span>
                <Fingerprint size={16} /> Recorded evidence
              </span>
            </div>
            <div className="agent-principles">
              <span>
                Human-designed interfaces.
                <br />
                <strong>Agent-tested experiences.</strong>
              </span>
              <p>
                From the first click to the point of friction.
                <br />
                See your product from the other side of the browser.
              </p>
              <Link href="/docs#agent">
                Inside the agent <ArrowUpRight size={17} />
              </Link>
            </div>
          </section>
        </div>
      </div>
      <section
        id="product"
        className="editorial-section pale-section audience-section"
      >
        <div className="editorial-wrap">
          <div className="editorial-heading">
            <p className="mini-eyebrow">THROUGH AN AGENT’S EYES</p>
            <h2>
              Your UI has
              <br />
              two audiences.
            </h2>
            <p>
              Your visitors can see a page. Can an agent make sense of it? Real
              browser tests reveal the difference, one interaction at a time.
            </p>
          </div>
          <div className="browser-comparison">
            <BrowserExample blocked />
            <BrowserExample />
          </div>
          <p className="section-disclaimer">
            Illustrative browser examples · not customer scan results
          </p>
        </div>
      </section>
      <section className="editorial-section white-section report-section">
        <div className="editorial-wrap">
          <div className="editorial-heading">
            <p className="mini-eyebrow">FROM A URL TO THE EVIDENCE</p>
            <h2>
              A map of the journey.
              <br />
              <span className="heading-soft">And the moments that matter.</span>
            </h2>
            <p>
              Connect website discovery with real agent behavior. Inspect the
              pages, follow the decisions, and understand what happened.
            </p>
          </div>
          <ProductPreview />
        </div>
      </section>
      <section className="landing-dark editorial-section" id="features">
        <div className="editorial-wrap execution-story">
          <div className="editorial-heading">
            <p className="mini-eyebrow">REAL AGENTS. REAL BROWSERS.</p>
            <h2>
              Give it a goal.
              <br />
              Watch it find a way.
            </h2>
            <p>
              An open-weight model observes your website and chooses its next
              action. No predefined route. No website-specific script.
            </p>
            <div className="story-tasks">
              <span>
                <Check size={13} /> Find pricing
              </span>
              <span>
                <Check size={13} /> Find documentation
              </span>
              <span>
                <Check size={13} /> Inspect signup forms
              </span>
            </div>
            <Link className="editorial-link" href="/docs#agent">
              Explore the agent architecture <ArrowUpRight size={14} />
            </Link>
          </div>
          <div className="trace-console">
            <div className="console-heading">
              <span>
                <Terminal size={13} /> agent / execution
              </span>
              <span>ILLUSTRATIVE TRACE</span>
            </div>
            <div className="console-task">
              <span>TASK</span>Find the pricing page and identify the available
              plans.
            </div>
            {[
              [
                "01",
                "observe",
                "Read the homepage navigation",
                "Links and visible controls captured",
              ],
              [
                "02",
                "reason → act",
                "Choose the pricing link",
                "click(element_id: 4)",
              ],
              [
                "03",
                "observe",
                "Read the pricing page",
                "Plan names and displayed prices found",
              ],
              [
                "04",
                "finish",
                "Agent declared completion",
                "Not independently verified",
              ],
            ].map(([n, kind, title, note]) => (
              <div className="console-step" key={n}>
                <span>{n}</span>
                <div>
                  <small>{kind}</small>
                  <strong>{title}</strong>
                  <p>{note}</p>
                </div>
                <Check size={13} />
              </div>
            ))}
            <div className="console-footer">
              <span className="signal-dot" />
              Bounded execution. Inspectable evidence.
            </div>
          </div>
        </div>
      </section>
      <section id="how-it-works" className="editorial-section pale-section">
        <div className="editorial-wrap">
          <div className="editorial-heading">
            <p className="mini-eyebrow">A CLEARER PATH FOR YOUR NEXT USER</p>
            <h2>Discover. Test. Understand.</h2>
          </div>
          <div className="how-grid">
            {[
              [
                Globe2,
                "01",
                "Start with your URL",
                "Discover pages through robots, sitemaps, and internal links.",
              ],
              [
                Bot,
                "02",
                "Give an agent a task",
                "Let a real model choose how to navigate in an isolated browser.",
              ],
              [
                FileSearch,
                "03",
                "Inspect the journey",
                "Review screenshots, observations, and the exact point of failure.",
              ],
            ].map(([Icon, n, title, text]) => {
              const I = Icon as typeof Bot;
              return (
                <div className="how-step" key={String(n)}>
                  <span className="how-number">{String(n)}</span>
                  <div className="how-visual">
                    <I size={24} strokeWidth={1.3} />
                    <span className="how-line" />
                    <ChevronRight size={15} />
                  </div>
                  <h3>{String(title)}</h3>
                  <p>{String(text)}</p>
                </div>
              );
            })}
          </div>
          <div className="availability-note">
            <BookOpen size={17} />
            <p>
              <strong>
                Discovery, static audits and reports are available today.
              </strong>{" "}
              Static scores describe inspected evidence. Independent agent task
              evaluation remains separate.
            </p>
            <Link href="/docs">
              Read the guide <ArrowUpRight size={13} />
            </Link>
          </div>
        </div>
      </section>
      <section className="closing-section">
        <div className="editorial-wrap closing-layout">
          <div>
            <p className="mini-eyebrow">MEET YOUR WEBSITE’S NEXT VISITOR</p>
            <h2>
              Find out where
              <br />
              agents get stuck.
            </h2>
            <WebsiteInput compact />
          </div>
          <div className="closing-report">
            <div className="report-site">
              <span>
                <Globe2 size={15} />
              </span>
              Your website<span className="demo-label">YOUR NEXT SCAN</span>
            </div>
            <div className="closing-placeholder">
              ?<span>What will an agent discover?</span>
            </div>
            {["Page discovery", "Browser navigation", "Execution evidence"].map(
              (x) => (
                <div className="closing-row" key={x}>
                  <span>{x}</span>
                  <i />
                  <small>Awaiting scan</small>
                </div>
              ),
            )}
            <p>Enter your domain to start exploring.</p>
          </div>
        </div>
      </section>
      <MarketingFooter />
    </main>
  );
}
