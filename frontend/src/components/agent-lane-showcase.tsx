import { Reveal } from "./reveal";
import styles from "./agent-lane-showcase.module.css";

// In development. The section says so; nothing here claims it is available today.
const ROUTES = [
  { who: "A person in a browser", to: "Your site, unchanged", lane: false },
  { who: "ChatGPT-User, Claude-User", to: "The agent lane", lane: true },
  { who: "Googlebot and crawlers", to: "Never cloaked", lane: false },
];

export function AgentLaneShowcase() {
  return (
    <section
      id="agent-lane"
      className={styles.section}
      aria-labelledby="agent-lane-title"
    >
      <div className={styles.wrap}>
        <Reveal>
          <p className={styles.label}>Agent lane · in development</p>
          <h2 id="agent-lane-title" className={styles.title}>
            One site. Two lanes.
          </h2>
          <p className={styles.intro}>
            People and search engines see your site exactly as it is. AI agents
            acting for a person get a clean lane at the same addresses, with
            your real prices and stock, and actions they can call.
          </p>
        </Reveal>
        <Reveal delay={100}>
          <ul className={styles.routes} aria-label="How requests are routed">
            {ROUTES.map((route) => (
              <li key={route.who} data-lane={route.lane || undefined}>
                <span className={styles.who}>{route.who}</span>
                <span className={styles.to}>{route.to}</span>
              </li>
            ))}
          </ul>
          <p className={styles.note}>
            Only user-initiated AI agents are routed. Search crawlers always see
            your original site.
          </p>
        </Reveal>
      </div>
    </section>
  );
}
