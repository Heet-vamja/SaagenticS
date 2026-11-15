"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  useEffect,
  useId,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { createPortal } from "react-dom";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  FileSearch,
  Globe2,
  LoaderCircle,
  ShieldCheck,
  Menu,
  X,
  Code2,
  RotateCw,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/button";
import { Brand, ThemeToggle } from "./product-ui";
import styles from "./landing.module.css";
import { InlineError } from "./states";
import { ScanTransition } from "./scan-transition";
import { DomainVerification } from "./domain-verification";
import { AgentLaneShowcase } from "./agent-lane-showcase";
import { HeroScanPreview } from "./hero-scan-preview";
import { MarketingFooter } from "./marketing-nav";
import { Reveal } from "./reveal";
const subscribeToHydration = () => () => {};
const clientReady = () => true;
const serverReady = () => false;
function ScanLaunch({
  website,
  reportPath,
}: {
  website: string;
  reportPath?: string;
}) {
  const screen = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const original = document.body.style.overflow;
    const background = document.getElementById("main-content");
    const originallyInert = background?.inert ?? false;
    document.body.style.overflow = "hidden";
    if (background) background.inert = true;
    screen.current?.focus({ preventScroll: true });
    return () => {
      document.body.style.overflow = original;
      if (background) background.inert = originallyInert;
    };
  }, []);
  return createPortal(
    <div
      ref={screen}
      tabIndex={-1}
      aria-label="Preparing your scan"
      className="fixed inset-0 z-[100] overflow-y-auto bg-background outline-none"
    >
      <ScanTransition website={website} reportPath={reportPath} />
    </div>,
    document.body,
  );
}

function WebsiteInput({ compact = false }: { compact?: boolean }) {
  const inputId = useId();
  const router = useRouter();
  // Prevent a native GET/reload before React has attached the submit handler.
  const hydrated = useSyncExternalStore(
    subscribeToHydration,
    clientReady,
    serverReady,
  );
  const [url, setUrl] = useState("");
  const [verificationUrl, setVerificationUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [submittedDomain, setSubmittedDomain] = useState("");
  const [reportPath, setReportPath] = useState<string>();
  const inFlight = useRef(false);
  const input = useRef<HTMLInputElement>(null);
  async function startScan(normalized: string) {
    if (inFlight.current) return;
    inFlight.current = true;
    setSubmittedDomain(new URL(normalized).hostname);
    setBusy(true);
    setError("");
    try {
      const scan = await api.startFreeScan(normalized);
      if (!/^\/free-reports\/[A-Za-z0-9_-]+$/.test(scan.report_path))
        throw new Error("Invalid report link. Please try again.");
      setReportPath(scan.report_path);
      router.push(scan.report_path);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not start your scan.");
      inFlight.current = false;
      setBusy(false);
      window.requestAnimationFrame(() => input.current?.focus());
    }
  }
  return (
    <form
      className={`website-entry ${styles.scanForm} ${compact ? "entry-compact" : ""}`}
      onSubmit={(e) => {
        e.preventDefault();
        if (inFlight.current) return;
        setError("");
        try {
          const normalized = new URL(
            /^https?:\/\//i.test(url.trim())
              ? url.trim()
              : `https://${url.trim()}`,
          ).toString();
          setVerificationUrl(normalized);
        } catch {
          setError("Enter a valid public website domain.");
        }
      }}
    >
      <label htmlFor={inputId} className="sr-only">
        Website URL
      </label>
      <div className="entry-field">
        <Globe2
          className="hidden shrink-0 text-muted-foreground sm:block"
          size={19}
          strokeWidth={1.8}
          aria-hidden="true"
        />
        <input
          ref={input}
          id={inputId}
          type="text"
          inputMode="url"
          value={url}
          disabled={busy || !hydrated}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="yourdomain.com"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          maxLength={2048}
          required
          aria-describedby={
            error ? `${inputId}-error` : `${inputId}-description`
          }
          className="min-h-12 min-w-0 flex-1 bg-transparent px-3 outline-none placeholder:text-muted-foreground"
        />
        <Button className="entry-submit" size="lg" disabled={busy || !hydrated}>
          {busy ? (
            <>
              <LoaderCircle size={15} className="animate-spin" />
              Starting scan…
            </>
          ) : (
            <>
              Scan Website
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
            <Check size={14} aria-hidden="true" />
            Email verification required
          </span>
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck size={14} aria-hidden="true" />
            Read-only testing
          </span>
          <span className="inline-flex items-center gap-1.5">
            <FileSearch size={14} aria-hidden="true" />
            Up to 10 pages
          </span>
        </p>
      )}
      {verificationUrl && (
        <DomainVerification
          key={verificationUrl}
          website={verificationUrl}
          open
          onClose={() => setVerificationUrl(null)}
          onVerified={() => {
            const target = verificationUrl;
            setVerificationUrl(null);
            void startScan(target);
          }}
        />
      )}
      {busy && <ScanLaunch website={submittedDomain} reportPath={reportPath} />}
    </form>
  );
}

// What the free scan measures today (deterministic checks; see /docs for coverage).
const CHECKS = [
  "Robots and AI crawler policies",
  "Sitemaps",
  "HTTP status and soft 404s",
  "Content in the initial HTML",
  "Rendered pages",
  "JSON-LD structured data",
  "llms.txt",
  "Pricing shown as text",
  "Accessible names and labels",
];

const NAV_LINKS = [
  ["How it works", "#how-it-works"],
  ["Pricing", "#pricing"],
  ["Agent lane", "#agent-lane"],
  ["Docs", "/docs"],
] as const;

const STEPS = [
  {
    icon: Globe2,
    title: "Find what’s getting in the way.",
    text: "Verify your email, then we inspect up to 10 public pages. Your preliminary score and up to 10 priority issues with practical fixes are free.",
  },
  {
    icon: Code2,
    title: "Turn the finding into a change.",
    text: "Try up to three complete fix prompts or crawl-grounded assets free. Unlock the complete Fix Kit for $19 when you’re ready.",
  },
  {
    icon: RotateCw,
    title: "Check what actually improved.",
    text: "After unlocking, re-scan the same domain at no extra charge for 30 days. See which checks now pass and which still need attention.",
  },
];

const QUESTIONS = [
  [
    "Does the free scan run real AI agents?",
    "Not yet. Today’s report uses deterministic checks of your public pages, content, access policies and markup. Real browser-agent testing is planned for Christmas 2026 and is separate from the current report.",
  ],
  [
    "Will this get my website recommended by ChatGPT?",
    "We can identify technical barriers, not guarantee recommendations, rankings or visibility in any AI platform. The score reflects only the checks actually completed.",
  ],
  [
    "Do you change anything on my website?",
    "No. Scanning is read-only. You or your developer choose which fixes to apply. Asset drafts must be reviewed before publishing.",
  ],
  [
    "Is the agent lane available today?",
    "Not yet. It’s in development: an agent version of your site at the same URLs, actions agents can call, and a dashboard of agent visits and failures. The free scan and Fix Kit are available now, and the scan shows what the agent lane would fix.",
  ],
];

// Illustrative names only; the scan does not test any specific model.
// Logos keep each brand's color; the pill stays AgentLane lime.
const AGENT_NAMES: {
  name: string;
  logo?: string;
  color?: string;
  size?: string;
}[] = [
  { name: "AI agents" },
  {
    name: "ChatGPT",
    logo: "/agent-logos/chatgpt.svg",
    color: "#10a37f",
    // This file carries extra internal padding; enlarge it to match the others.
    size: "130%",
  },
  {
    name: "Claude",
    logo: "/agent-logos/claude.svg",
    color: "#d97757",
  },
  {
    name: "Gemini",
    logo: "/agent-logos/gemini.svg",
    color: "linear-gradient(135deg, #4796e3, #9177c7 55%, #ca6673)",
  },
  {
    name: "Perplexity",
    logo: "/agent-logos/perplexity.svg",
    color: "#20808d",
  },
];

function RotatingAgentName() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const timer = window.setInterval(() => {
      const active = document.activeElement;
      // Hold still while the tab is hidden or someone is typing a domain.
      if (document.hidden || active?.closest("form.website-entry")) return;
      setIndex((current) => (current + 1) % AGENT_NAMES.length);
    }, 2600);
    return () => window.clearInterval(timer);
  }, []);
  const previous = (index - 1 + AGENT_NAMES.length) % AGENT_NAMES.length;
  return (
    <span className={`headline-pill ${styles.agentPill}`}>
      {/* A stable accessible name; the rotation is visual only. */}
      <span className="sr-only">AI agents</span>
      <span className={styles.agentNames} aria-hidden="true">
        {AGENT_NAMES.map(({ name, logo, color, size }, i) => (
          <span
            key={name}
            data-state={
              i === index ? "active" : i === previous ? "leaving" : "waiting"
            }
          >
            {logo && (
              <span className={styles.agentMark}>
                {/* The single-color SVG is used as a mask so it takes the brand color. */}
                <span
                  className={styles.agentLogo}
                  style={{
                    WebkitMaskImage: `url(${logo})`,
                    maskImage: `url(${logo})`,
                    WebkitMaskSize: size,
                    maskSize: size,
                    background: color,
                  }}
                />
              </span>
            )}
            {name}
          </span>
        ))}
      </span>
    </span>
  );
}

/** Navbar state: clear at the top, frosted over the hero, solid past it. */
function useNavState(hero: React.RefObject<HTMLElement | null>) {
  const [state, setState] = useState<"top" | "glass" | "solid">("top");
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const heroBottom = hero.current?.getBoundingClientRect().bottom ?? 0;
      setState(
        window.scrollY < 8 ? "top" : heroBottom > 64 ? "glass" : "solid",
      );
    };
    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [hero]);
  return state;
}

export function Landing() {
  const [menuOpen, setMenuOpen] = useState(false);
  const hero = useRef<HTMLElement>(null);
  const navState = useNavState(hero);
  return (
    <main id="main-content" className={styles.page}>
      <header
        className={`nav-glass ${styles.nav}`}
        data-state={menuOpen ? "solid" : navState}
      >
        <div className={styles.navInner}>
          <Brand />
          <nav className={styles.desktopNav} aria-label="Main navigation">
            {NAV_LINKS.map(([label, href]) => (
              <Link key={href} href={href}>
                {label}
              </Link>
            ))}
          </nav>
          <div className={styles.navActions}>
            <ThemeToggle />
            <Button asChild size="sm" className={styles.navCta}>
              <a href="#scan">
                Scan your site <ArrowRight size={14} />
              </a>
            </Button>
            <button
              className={styles.menuButton}
              onClick={() => setMenuOpen(!menuOpen)}
              aria-expanded={menuOpen}
              aria-controls="homepage-mobile-nav"
              aria-label={menuOpen ? "Close navigation" : "Open navigation"}
            >
              {menuOpen ? <X size={20} /> : <Menu size={20} />}
            </button>
          </div>
        </div>
        {menuOpen && (
          <nav
            id="homepage-mobile-nav"
            className={styles.mobileNav}
            aria-label="Mobile navigation"
          >
            {[...NAV_LINKS, ["Scan your site", "#scan"] as const].map(
              ([label, href]) => (
                <Link key={href} href={href} onClick={() => setMenuOpen(false)}>
                  {label}
                  <ArrowUpRight size={16} />
                </Link>
              ),
            )}
          </nav>
        )}
      </header>

      <section ref={hero} className={styles.hero} id="scan">
        <div className={styles.heroGlow} aria-hidden="true" />
        <div className={`${styles.wrap} ${styles.heroInner}`}>
          <p className="chip">
            <span className="chip-dot" /> Free agent-readiness report
          </p>
          <h1 className={`display-xl ${styles.headline}`}>
            <span className={`hero-title-row ${styles.row}`}>
              Be the website
            </span>
            <span className={`hero-title-row ${styles.row}`}>
              <RotatingAgentName />
            </span>
            <span className={`hero-title-row ${styles.row}`}>
              can actually use.
            </span>
          </h1>
          <p className={`lede ${styles.heroLede}`}>
            Find what blocks AI agents on your public pages, hand your developer
            the fix, and check that it worked.
          </p>
          <WebsiteInput />
          <p className={styles.freeNote}>
            Free score. Real findings. Your first fixes, on us.
          </p>
          <p className={styles.disclosure}>
            Static checks only. Agent names and logos are examples, belong to
            their owners and don’t endorse AgentLane; the scan doesn’t test
            specific models.
          </p>
        </div>
        <div className={`${styles.wrap} ${styles.heroStage}`}>
          <HeroScanPreview />
        </div>
      </section>

      <section id="how-it-works" className={`${styles.band} ${styles.bandInk}`}>
        <div className={styles.wrap}>
          <Reveal className={styles.centerHeading}>
            <p className={styles.inkEyebrow}>
              The part that makes a difference
            </p>
            <h2 className="display-lg">
              Find it. Fix it.
              <br />
              <span className={styles.limeText}>Check it again.</span>
            </h2>
            <p className={styles.inkLede}>
              Verify your email to get started. No changes made to your website.
            </p>
          </Reveal>
          <ol className={styles.steps}>
            {STEPS.map((step, i) => (
              <Reveal as="li" key={step.title} delay={i * 100} className="lift">
                <span className={styles.stepNumber}>0{i + 1}</span>
                <step.icon size={22} strokeWidth={1.8} aria-hidden="true" />
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </Reveal>
            ))}
          </ol>
          <Reveal className={styles.checks}>
            <p className={styles.checksLabel}>What the free scan checks</p>
            <ul>
              {CHECKS.map((check) => (
                <li key={check}>{check}</li>
              ))}
            </ul>
            <p className={styles.checksNote}>
              Static evidence finds likely barriers; it doesn’t prove an AI
              agent can finish a task.{" "}
              <Link href="/docs">
                Read about coverage <ArrowUpRight size={13} />
              </Link>
            </p>
          </Reveal>
        </div>
      </section>

      <section id="pricing" className={styles.band}>
        <div className={styles.wrap}>
          <Reveal className={styles.centerHeading}>
            <p className="eyebrow">Your next step</p>
            <h2 className="display-lg">
              Start with evidence.
              <br />
              Pay when you want the kit.
            </h2>
            <p className="lede">
              No subscription. No mystery score. Just what we checked, what we
              found, and what you can do about it.
            </p>
          </Reveal>
          <div className={styles.priceGrid}>
            <Reveal as="article" className={`${styles.freePrice} lift`}>
              <div className={styles.priceTop}>
                <p className={styles.priceLabel}>The first look</p>
              </div>
              <h3>Your readiness report.</h3>
              <p className={styles.price}>
                <strong>$0</strong>
                <span>Start with your domain</span>
              </p>
              <ul>
                <li>
                  <Check size={16} aria-hidden="true" /> Up to 10 public pages
                  inspected
                </li>
                <li>
                  <Check size={16} aria-hidden="true" /> Preliminary score and
                  up to 10 priority insights
                </li>
                <li>
                  <Check size={16} aria-hidden="true" /> Up to 3 complete fix
                  prompts or validated asset drafts
                </li>
              </ul>
              <Button asChild size="lg">
                <a href="#scan">
                  Get your free report <ArrowRight size={16} />
                </a>
              </Button>
            </Reveal>
            <Reveal
              as="article"
              delay={120}
              className={`${styles.paidPrice} lift`}
            >
              <div className={styles.priceTop}>
                <p className={styles.priceLabel}>The complete Fix Kit</p>
                <span className={styles.valueBadge}>One-time payment</span>
              </div>
              <h3>From insight to implementation.</h3>
              <p className={styles.price}>
                <strong>$19</strong>
                <span>USD / for this domain</span>
              </p>
              <ul>
                <li>
                  <Check size={16} aria-hidden="true" /> Remaining fixes with
                  detailed evidence
                </li>
                <li>
                  <Check size={16} aria-hidden="true" /> Coding prompts,
                  available asset drafts and exports
                </li>
                <li>
                  <Check size={16} aria-hidden="true" /> Same-domain re-scans
                  included for 30 days
                </li>
              </ul>
              <Button asChild variant="lime" size="lg">
                <a href="#scan">
                  Start with a free scan <ArrowRight size={16} />
                </a>
              </Button>
            </Reveal>
          </div>
          <p className={styles.priceNote}>
            Email verification required. Assets are generated only when
            supported by your crawl. AI agent testing is coming separately.
          </p>
        </div>
      </section>

      <AgentLaneShowcase />

      <section
        className={`${styles.band} ${styles.questions}`}
        aria-labelledby="homepage-questions"
      >
        <div className={`${styles.wrap} ${styles.questionsGrid}`}>
          <div>
            <p className="eyebrow">A few things worth knowing</p>
            <h2 id="homepage-questions" className="display-lg">
              Good questions.
            </h2>
            <Link href="/docs" className={styles.docsLink}>
              The details are in our docs <ArrowUpRight size={14} />
            </Link>
          </div>
          <Reveal className={styles.faq} delay={100}>
            {QUESTIONS.map(([question, answer]) => (
              <details key={question}>
                <summary>
                  {question}
                  <span aria-hidden="true">+</span>
                </summary>
                <p>{answer}</p>
              </details>
            ))}
          </Reveal>
        </div>
      </section>

      <section className={styles.closingBand}>
        <div className={`${styles.wrap}`}>
          <Reveal className={`block-feature ${styles.closing}`}>
            <p className={styles.closingEyebrow}>
              Your next visitor won’t always click like you
            </p>
            <h2 className="display-lg">
              Your next improvement?
              <br />
              <span className={styles.limeText}>It starts with a scan.</span>
            </h2>
            <WebsiteInput compact />
            <p className={styles.closingNote}>
              A practical starting point. Grounded in your public pages.
            </p>
          </Reveal>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
