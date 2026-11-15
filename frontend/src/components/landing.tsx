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
  Copy,
  Globe2,
  LoaderCircle,
  Menu,
  Minus,
  X,
} from "lucide-react";
import { api } from "@/lib/api";
import { Button } from "./ui/button";
import { Brand, ThemeToggle } from "./product-ui";
import styles from "./landing.module.css";
import { InlineError } from "./states";
import { ScanTransition } from "./scan-transition";
import { DomainVerification } from "./domain-verification";
import { AgentLaneShowcase } from "./agent-lane-showcase";
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
          Free · up to 10 pages · read-only · email code, no account
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
    title: "See what blocks agents",
    price: "Free",
    text: "Confirm your email and we inspect up to 10 public pages. You get a preliminary score, up to 10 priority issues and your first three fixes.",
  },
  {
    title: "Fix it with exact steps",
    price: "$19 once, per domain",
    text: "Every finding with its evidence, copy-ready prompts for your coding assistant, asset drafts and a downloadable fix pack.",
  },
  {
    title: "Check that it worked",
    price: "Re-scans included for 30 days",
    text: "Re-scan the same domain after you change something. A fix counts only when new evidence confirms it.",
  },
];

// Typical barriers, described generally; the scan reports what it finds on your site.
const FAILURES = [
  {
    title: "Content that only appears after JavaScript",
    text: "The agent reads the page and finds an empty shell. Prices and plans never arrive.",
  },
  {
    title: "Controls without names",
    text: "A size picker made of unlabeled buttons gives the agent nothing to choose from.",
  },
  {
    title: "Facts behind a login or a pop-up",
    text: "Delivery dates behind a sign-in, offers behind a modal: the agent stops there.",
  },
];

const PRINCIPLES = [
  ["Evidence on every finding.", "The page and the markup we saw."],
  ["Unknown stays unknown.", "A check that can’t run never counts as a pass."],
  ["Read-only, always.", "Scans never change your site."],
] as const;

/** The Fix Center's three prompt variants, written for the size-picker example. */
const PROMPTS = [
  {
    id: "assistant",
    label: "Coding assistant",
    text: "On /trail-runner, give each size button its visible size as text (UK 7 to UK 10). Keep UK 10 disabled. Don’t change the layout or styling.",
  },
  {
    id: "general",
    label: "General AI",
    text: "The size buttons on my product page have no text, so AI agents can’t tell the sizes apart. Show me how to give each button its size as visible text and keep the sold-out size disabled.",
  },
  {
    id: "ticket",
    label: "Dev ticket",
    text: "Size picker on /trail-runner: buttons have no accessible names. Add the visible size (UK 7 to UK 10) to each button; keep UK 10 disabled. Done when a re-scan passes.",
  },
] as const;

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

/** A calm example of the report beside the hero copy. Illustrative data only. */
function ExampleReport() {
  return (
    <figure
      className={styles.report}
      aria-label="Example readiness report with illustrative data"
    >
      <div className={styles.reportTop}>
        <span className={styles.reportSite}>northstar.example</span>
        <span className={styles.example}>Example</span>
      </div>
      <p className={styles.score}>
        <strong>42</strong>
        <span>out of 100 · agent readiness</span>
      </p>
      <div className={styles.meter} aria-hidden="true">
        {Array.from({ length: 10 }, (_, i) => (
          <i
            key={i}
            data-on={i < 4 ? "" : undefined}
            style={{ "--i": i } as React.CSSProperties}
          />
        ))}
      </div>
      <ul className={styles.findings}>
        <li>
          <span className={styles.mark} data-tone="danger">
            <X size={12} strokeWidth={2.6} aria-hidden="true" />
          </span>
          <span>Size buttons have no names</span>
          <span>Issue</span>
        </li>
        <li>
          <span className={styles.mark} data-tone="warning">
            <Minus size={12} strokeWidth={2.6} aria-hidden="true" />
          </span>
          <span>Navigation names need review</span>
          <span>Review</span>
        </li>
        <li>
          <span className={styles.mark} data-tone="success">
            <Check size={12} strokeWidth={2.6} aria-hidden="true" />
          </span>
          <span>Sitemap is reachable</span>
          <span>Pass</span>
        </li>
      </ul>
      <figcaption className={styles.reportFoot}>
        <span>
          <strong>3 fixes</strong> ready for your developer
        </span>
        <span>Illustrative</span>
      </figcaption>
    </figure>
  );
}

/** One size picker three ways: as a person sees it, as an agent receives it
 * today, and as an agent receives it once the Fix Kit's change is in. */
/** Fixed markup as [before, added, after]: the added text is highlighted. */
const FIXED_SIZES = [
  ['<div class="sizes">', "", ""],
  ["  <button>", "UK 7", "</button>"],
  ["  <button>", "UK 8", "</button>"],
  ["  <button>", "UK 9", "</button>"],
  ["  <button disabled>", "UK 10", "</button>"],
  ["</div>", "", ""],
] as const;

function PersonVersusAgent() {
  return (
    <figure
      className={styles.versus}
      aria-label="Example: a size picker as a person sees it, as an agent receives it, and after the Fix Kit"
    >
      <div className={styles.versusTop}>
        <span className={styles.reportSite}>
          northstar.example/trail-runner
        </span>
        <span className={styles.example}>Example</span>
      </div>
      <div className={styles.versusBody}>
        <div className={styles.versusPerson}>
          <p className={styles.versusLabel}>What a person sees</p>
          <div className={styles.product}>
            <strong>Trail Runner 2</strong>
            <span>Choose your size</span>
            <ul className={styles.sizes} aria-label="Example sizes">
              <li>UK 7</li>
              <li data-selected="">UK 8</li>
              <li>UK 9</li>
              <li data-sold-out="">UK 10</li>
            </ul>
          </div>
        </div>
        <div className={styles.versusAgent}>
          <p className={styles.versusLabel}>What an agent receives</p>
          <pre>
            {
              '<div class="sizes">\n  <button></button>\n  <button></button>\n  <button></button>\n  <button disabled></button>\n</div>'
            }
          </pre>
          <p className={styles.versusResult}>
            No size names an agent can read.
          </p>
        </div>
        <div className={styles.versusFixed}>
          <p className={styles.versusLabel}>
            After the Fix Kit <span className={styles.fixedTag}>Fixed</span>
          </p>
          {/* One span per line so the fixed markup can appear line by line;
              the text the fix adds is marked. */}
          <pre>
            {FIXED_SIZES.map(([before, added, after]) => (
              <span key={before + added}>
                {before}
                {added && <mark>{added}</mark>}
                {after}
              </span>
            ))}
          </pre>
          <p className={styles.versusResult}>
            Agent reads: UK 7, 8, 9 in stock.
          </p>
        </div>
      </div>
    </figure>
  );
}

/** One fix as the Fix Center shows it: evidence, a prompt in three variants, and
 * the re-scan that verifies it. Example data; the copy button really copies. */
function FixKitPreview() {
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);
  const tabs = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();
  const prompt = PROMPTS[active];
  const select = (index: number) => {
    setActive(index);
    setCopied(false);
  };
  const onKeyDown = (event: React.KeyboardEvent) => {
    const step =
      event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
    if (!step) return;
    event.preventDefault();
    const next = (active + step + PROMPTS.length) % PROMPTS.length;
    select(next);
    tabs.current[next]?.focus();
  };
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(prompt.text);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  return (
    <figure
      className={styles.fix}
      aria-label="Example: one fix from the Fix Kit"
    >
      <div className={styles.fixTop}>
        <p>
          <span>Fix 1 of 7 · Issue</span>
          <strong>Size buttons have no names</strong>
        </p>
        <span className={styles.example}>Example</span>
      </div>
      <div className={styles.fixEvidence}>
        <p>
          Evidence · <code>/trail-runner</code>
        </p>
        <pre>{"<button></button>  4 buttons, no accessible name"}</pre>
      </div>
      <div className={styles.fixPrompt}>
        <div
          className={styles.fixTabs}
          role="tablist"
          aria-label="Prompt for"
          onKeyDown={onKeyDown}
        >
          {PROMPTS.map((item, i) => (
            <button
              key={item.id}
              ref={(node) => {
                tabs.current[i] = node;
              }}
              type="button"
              role="tab"
              id={`${id}-${item.id}`}
              aria-selected={i === active}
              aria-controls={`${id}-panel`}
              tabIndex={i === active ? 0 : -1}
              onClick={() => select(i)}
            >
              {item.label}
            </button>
          ))}
        </div>
        <p
          id={`${id}-panel`}
          role="tabpanel"
          aria-labelledby={`${id}-${prompt.id}`}
          className={styles.fixText}
        >
          {prompt.text}
        </p>
        <div className={styles.fixActions}>
          <Button type="button" variant="ink" size="sm" onClick={copy}>
            {copied ? <Check size={14} /> : <Copy size={14} />}
            {copied ? "Copied" : "Copy prompt"}
          </Button>
          <span>
            Then <strong>Re-scan to verify</strong>
          </span>
        </div>
        <span className="sr-only" aria-live="polite">
          {copied ? "Prompt copied" : ""}
        </span>
      </div>
    </figure>
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
        <div className={`${styles.wrap} ${styles.heroGrid}`}>
          <div>
            <h1 className={styles.headline}>
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
            <p className={styles.heroLede}>
              Find what blocks AI agents on your public pages, hand your
              developer the fix, and check that it worked.
            </p>
            <WebsiteInput />
          </div>
          <ExampleReport />
        </div>
      </section>

      <section className={styles.section} aria-labelledby="problem-title">
        <div className={styles.wrap}>
          <div className={`${styles.split} ${styles.splitTop}`}>
            <Reveal>
              <p className={styles.label}>The problem</p>
              <h2 id="problem-title" className={styles.title}>
                Your site works for people. <span>Agents fail quietly.</span>
              </h2>
              <p className={styles.intro}>
                More people ask an AI assistant to find a price or check stock
                instead of browsing. When the agent can’t, nobody tells you.
              </p>
            </Reveal>
            <Reveal delay={100}>
              <ol className={styles.failures} aria-label="Common examples">
                {FAILURES.map((failure, i) => (
                  <li key={failure.title}>
                    <span>0{i + 1}</span>
                    <div>
                      <strong>{failure.title}</strong>
                      <p>{failure.text}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </Reveal>
          </div>
          <Reveal className={styles.compare}>
            <PersonVersusAgent />
          </Reveal>
        </div>
      </section>

      <section
        id="how-it-works"
        className={styles.section}
        aria-labelledby="how-title"
      >
        <div className={styles.wrap}>
          <Reveal>
            <p className={styles.label}>How it works</p>
            <h2 id="how-title" className={styles.title}>
              Find it. Fix it. Check it again.
            </h2>
          </Reveal>
          <ol className={styles.steps}>
            {STEPS.map((step, i) => (
              <Reveal as="li" key={step.title} delay={i * 80}>
                <span className={styles.stepNumber}>0{i + 1}</span>
                <h3>{step.title}</h3>
                <p className={styles.stepPrice}>{step.price}</p>
                <p>{step.text}</p>
              </Reveal>
            ))}
          </ol>
          <Reveal className={styles.checks}>
            <p className={styles.label}>What the free scan checks</p>
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

      <section
        id="fix-kit"
        className={`${styles.section} ${styles.kit}`}
        aria-labelledby="kit-title"
      >
        <div className={`${styles.wrap} ${styles.split}`}>
          <Reveal>
            <p className={styles.label}>Inside the Fix Kit</p>
            <h2 id="kit-title" className={styles.title}>
              Every fix comes with proof and a prompt.
            </h2>
            <p className={styles.intro}>
              Hand it to your developer or paste it into your coding assistant.
              Then re-scan: a fix counts only when new evidence confirms it.
            </p>
            <ul className={styles.proof}>
              {PRINCIPLES.map(([title, text]) => (
                <li key={title}>
                  <span aria-hidden="true">
                    <Check size={13} strokeWidth={3} />
                  </span>
                  <p>
                    <strong>{title}</strong> {text}
                  </p>
                </li>
              ))}
            </ul>
          </Reveal>
          <Reveal delay={100}>
            <FixKitPreview />
          </Reveal>
        </div>
      </section>

      <AgentLaneShowcase />

      <section
        id="pricing"
        className={styles.section}
        aria-labelledby="pricing-title"
      >
        <div className={styles.wrap}>
          <Reveal>
            <p className={styles.label}>Pricing</p>
            <h2 id="pricing-title" className={styles.title}>
              Start free. Pay once when you want the kit.
            </h2>
          </Reveal>
          <div className={styles.prices}>
            <Reveal as="article" className={styles.plan}>
              <div className={styles.planTop}>
                <p className={styles.planName}>Free scan</p>
              </div>
              <p className={styles.amount}>
                <strong>$0</strong>
                <span>for your domain</span>
              </p>
              <h3 className={styles.planFor}>Your readiness report.</h3>
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
              <p className={styles.planHint}>Email code, no account.</p>
            </Reveal>
            <Reveal
              as="article"
              delay={100}
              className={`${styles.plan} ${styles.planPaid}`}
            >
              <div className={styles.planTop}>
                <p className={styles.planName}>Fix Kit</p>
                <span className={styles.oneTime}>One-time payment</span>
              </div>
              <p className={styles.amount}>
                <strong>$19</strong>
                <span>USD per domain</span>
              </p>
              <h3 className={styles.planFor}>
                From insight to implementation.
              </h3>
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
                  Get the Fix Kit <ArrowRight size={16} />
                </a>
              </Button>
              <p className={styles.planHint}>
                Starts with a free scan of your domain.
              </p>
            </Reveal>
          </div>
          <p className={styles.priceNote}>
            Email verification required. Assets are generated only when
            supported by your crawl. AI agent testing is coming separately.
          </p>
        </div>
      </section>

      <section className={styles.section} aria-labelledby="homepage-questions">
        <div className={`${styles.wrap} ${styles.split} ${styles.splitTop}`}>
          <div>
            <p className={styles.label}>Questions</p>
            <h2 id="homepage-questions" className={styles.title}>
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

      <section className={styles.closing}>
        <div className={styles.wrap}>
          <Reveal className={styles.closingCard}>
            <h2>Find out what agents run into on your site.</h2>
            <WebsiteInput compact />
            <p className={styles.disclosure}>
              Static checks only. Agent names and logos are examples, belong to
              their owners and don’t endorse AgentLane; the scan doesn’t test
              specific models.
            </p>
          </Reveal>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
