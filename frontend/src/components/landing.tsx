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
import { AgentRace } from "./agent-race";
import { EarlyAccessForm } from "./early-access";
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
  ["Demo", "#demo"],
  ["How it works", "#how-it-works"],
  ["Fix Kit", "#fix-kit"],
  ["Pricing", "#pricing"],
  ["Docs", "/docs"],
] as const;

const STEPS = [
  {
    title: "Connect your domain",
    text: "One DNS record, or a Cloudflare connection. We set it up with you during early access. Your site, hosting and URLs stay exactly the same.",
  },
  {
    title: "We build your agent lane",
    text: "From your public pages: clean pages at the same addresses, llms.txt, structured data, and actions agents can call over an API or MCP. Every price and stock level is checked against your site before it goes live.",
  },
  {
    title: "See every agent visit",
    text: "Which agents came, what they tried to do, where they got stuck and what to fix. We re-test with real AI agents to prove it worked.",
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
    text: "On /trail-runner, label each size button with its size as visible text (for example “UK 9”), taken from the product’s size data. Disable a size whenever its stock is zero, so the buttons follow your inventory. Don’t change the layout or styling.",
  },
  {
    id: "general",
    label: "General AI",
    text: "The size buttons on my product page have no text, so AI agents can’t tell the sizes apart. Show me how to render each size’s name on its button from the product data, and disable the button whenever that size has no stock.",
  },
  {
    id: "ticket",
    label: "Dev ticket",
    text: "Size picker on /trail-runner: buttons have no accessible names. Render each size’s label (e.g. UK 9) from the product’s size data and set disabled when its stock is 0. Done when a re-scan passes.",
  },
] as const;

const QUESTIONS = [
  [
    "Will my visitors notice anything?",
    "No. People always get your site as it is, from your own servers. Only AI agents acting for a person, like ChatGPT-User or Claude-User, are sent to the agent lane.",
  ],
  [
    "Isn’t serving agents a different page cloaking?",
    "Cloaking means showing search engines something different from people. We never do: Googlebot, Bingbot and other crawlers always see your original pages. The agent lane carries the same facts as your site, checked against it before every update.",
  ],
  [
    "Which agents get the agent lane?",
    "Agents that fetch a page because a person asked them to: ChatGPT-User, Claude-User, Perplexity-User, Google’s agents and similar. The list is versioned and kept up to date.",
  ],
  [
    "What happens if Aglanetic goes down?",
    "Your site keeps working. The lane fails open: if anything on our side is unavailable, every visitor, agent or person, is passed straight to your site. You can also pause the lane from your dashboard at any time.",
  ],
  [
    "Do I need Cloudflare?",
    "No. You can point one DNS record at us, or connect your Cloudflare account if you use it. During early access we do the setup with you.",
  ],
  [
    "Will this get my website recommended by ChatGPT?",
    "We make your site easier for agents to read and use, and we measure it. We can’t promise recommendations or rankings in any AI platform.",
  ],
];

// Illustrative names only; the scan does not test any specific model.
// Logos keep each brand's color; the pill stays brand lime.
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

// Illustrative requests on the demo store, routed the way the router routes them.
const LANE_LOG = [
  {
    who: "Chrome",
    what: "A person · /product/trail-runner",
    to: "Your site, unchanged",
    lane: false,
  },
  {
    who: "ChatGPT-User",
    what: "Agent · “Is the Trail Runner in UK 9?”",
    to: "Agent lane",
    lane: true,
  },
  {
    who: "Claude-User",
    what: "Agent · check_delivery 560001",
    to: "Agent lane",
    lane: true,
  },
  {
    who: "Googlebot",
    what: "Search crawler · /",
    to: "Your site, never cloaked",
    lane: false,
  },
];

/** Requests arriving at one site and the lane each one takes. Illustrative. */
function LaneLog() {
  return (
    <figure
      className={styles.report}
      aria-label="Example: requests to one site and the lane each takes"
    >
      <div className={styles.reportTop}>
        <span className={styles.reportSite}>
          northstar.example · live requests
        </span>
        <span className={styles.example}>Example</span>
      </div>
      <ul className={styles.lanes}>
        {LANE_LOG.map((row) => (
          <li key={row.who}>
            <span>
              <strong>{row.who}</strong>
              <span>{row.what}</span>
            </span>
            <span className={row.lane ? styles.laneTag : styles.laneTo}>
              {row.to}
            </span>
          </li>
        ))}
      </ul>
      <figcaption className={styles.reportFoot}>
        <span>
          <strong>2 agents</strong> served in the last minute
        </span>
        <span>Illustrative</span>
      </figcaption>
    </figure>
  );
}

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
            <p className={styles.liveBadge}>
              <span aria-hidden="true" />
              The agent lane is live
            </p>
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
              Aglanetic gives AI agents their own lane to your site. People see
              it exactly as it is. ChatGPT, Claude and other agents get a
              version they can read and act on, and you see every visit.
            </p>
            <WebsiteInput />
            <a href="#early-access" className={styles.earlyLink}>
              Want the agent lane on your site? Request early access{" "}
              <ArrowRight size={14} aria-hidden="true" />
            </a>
          </div>
          <LaneLog />
        </div>
      </section>

      <AgentRace />

      <section className={styles.section} aria-labelledby="problem-title">
        <div className={styles.wrap}>
          <div className={`${styles.split} ${styles.splitTop}`}>
            <Reveal>
              <p className={styles.label}>Why it happens</p>
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
              Connect. We build the lane. You watch it work.
            </h2>
          </Reveal>
          <ol className={styles.steps}>
            {STEPS.map((step, i) => (
              <Reveal as="li" key={step.title} delay={i * 80}>
                <span className={styles.stepNumber}>0{i + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      <AgentLaneShowcase />

      <section
        id="fix-kit"
        className={`${styles.section} ${styles.kit}`}
        aria-labelledby="kit-title"
      >
        <div className={styles.wrap}>
          <div className={styles.split}>
            <Reveal>
              <p className={styles.label}>Prefer to fix it yourself?</p>
              <h2 id="kit-title" className={styles.title}>
                The Fix Kit: every fix with proof and a prompt.
              </h2>
              <p className={styles.intro}>
                Start with the free scan, then hand each fix to your developer
                or paste it into your coding assistant. A fix counts only when a
                re-scan confirms it.
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
          <Reveal className={styles.compare}>
            <PersonVersusAgent />
          </Reveal>
        </div>
      </section>

      <section
        id="pricing"
        className={styles.section}
        aria-labelledby="pricing-title"
      >
        <div className={styles.wrap}>
          <Reveal>
            <p className={styles.label}>Pricing</p>
            <h2 id="pricing-title" className={styles.title}>
              Start free. Go as far as you need.
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
            <Reveal as="article" delay={80} className={styles.plan}>
              <div className={styles.planTop}>
                <p className={styles.planName}>Fix Kit</p>
                <span className={`${styles.oneTime} ${styles.oneTimeQuiet}`}>
                  One-time payment
                </span>
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
              <Button asChild size="lg">
                <a href="#scan">
                  Get the Fix Kit <ArrowRight size={16} />
                </a>
              </Button>
              <p className={styles.planHint}>
                Starts with a free scan of your domain.
              </p>
            </Reveal>
            <Reveal
              as="article"
              delay={160}
              id="early-access"
              className={`${styles.plan} ${styles.planPaid} ${styles.planEarly}`}
            >
              <div className={styles.planTop}>
                <p className={styles.planName}>Agent lane</p>
                <span className={styles.oneTime}>Early access</span>
              </div>
              <p className={styles.amount}>
                <strong className={styles.amountWords}>
                  Be one of the first sites agents can really use.
                </strong>
              </p>
              <p className={styles.earlyPitch}>
                We’re setting up a small number of sites by hand, with you. Tell
                us where to start.
              </p>
              <EarlyAccessForm />
            </Reveal>
          </div>
          <p className={styles.priceNote}>
            Email verification required. Assets are generated only when
            supported by your crawl.
          </p>
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
            <a href="#early-access" className={styles.closingLink}>
              Want us to run an agent lane for you? Request early access{" "}
              <ArrowRight size={14} aria-hidden="true" />
            </a>
            <p className={styles.disclosure}>
              The free scan uses static checks. Agent names and logos are
              examples, belong to their owners and don’t endorse Aglanetic.
            </p>
          </Reveal>
        </div>
      </section>

      <MarketingFooter />
    </main>
  );
}
