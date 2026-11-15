import {
  ArrowRight,
  Bot,
  FileText,
  Gauge,
  PlugZap,
  Route,
  Search,
  User,
} from "lucide-react";
import { Button } from "./ui/button";
import { Reveal } from "./reveal";
import styles from "./agent-lane-showcase.module.css";

// In development. The illustration is labeled as such; nothing here claims the
// capability is available today.
const ROUTES = [
  {
    icon: User,
    who: "A person in Chrome",
    to: "Your site, unchanged",
    lane: false,
  },
  { icon: Bot, who: "ChatGPT-User", to: "The agent lane", lane: true },
  {
    icon: Search,
    who: "Googlebot",
    to: "Your site, never cloaked",
    lane: false,
  },
];

const CAPABILITIES = [
  {
    icon: FileText,
    title: "An agent version at the same URLs",
    text: "Clean pages, llms.txt and JSON-LD with your real prices and stock.",
  },
  {
    icon: PlugZap,
    title: "Actions agents can call",
    text: "Search products, check sizes and stock, get a delivery estimate, over API or MCP.",
  },
  {
    icon: Route,
    title: "No rebuild",
    text: "Point your domain through AgentLane. People and search engines see your site as it is.",
  },
  {
    icon: Gauge,
    title: "Proof, not promises",
    text: "See which agents visit, where they fail, and task success before and after.",
  },
];

export function AgentLaneShowcase() {
  return (
    <section
      id="agent-lane"
      className={styles.section}
      aria-labelledby="agent-lane-title"
    >
      <div className={styles.wrap}>
        <Reveal className={styles.copy}>
          <p className="chip">
            <span className="chip-dot" aria-hidden="true" />
            Coming next · In development
          </p>
          <h2 id="agent-lane-title" className="display-lg">
            Give AI agents <span className="mark-lime">their own lane.</span>
          </h2>
          <p className="lede">
            Your site stays exactly as people see it. AI agents get a clean
            version they can read and act on.
          </p>
          <ul className={styles.list}>
            {CAPABILITIES.map((item) => (
              <li key={item.title}>
                <item.icon size={18} strokeWidth={2} aria-hidden="true" />
                <span>
                  <strong>{item.title}.</strong> {item.text}
                </span>
              </li>
            ))}
          </ul>
          <div className={styles.actions}>
            <Button asChild size="lg">
              <a href="#scan">
                Start with a free scan <ArrowRight size={16} />
              </a>
            </Button>
            <p>The free scan shows what the agent lane would fix.</p>
          </div>
        </Reveal>

        <Reveal className={`surface-float ${styles.router}`} delay={120}>
          <div className={styles.routerBar}>
            <span className={styles.host}>yourstore.com</span>
            <span className={styles.tag}>Illustrative</span>
          </div>
          <ul className={styles.routes} aria-label="How requests are routed">
            {ROUTES.map((route) => (
              <li key={route.who} data-lane={route.lane || undefined}>
                <span className={styles.who}>
                  <route.icon size={16} strokeWidth={2} aria-hidden="true" />
                  {route.who}
                </span>
                <span className={styles.track} aria-hidden="true">
                  <i />
                </span>
                <span className={styles.to}>{route.to}</span>
              </li>
            ))}
          </ul>
          <p className={styles.routerNote}>
            Only user-initiated AI agents are routed. Search crawlers always see
            your original site.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
