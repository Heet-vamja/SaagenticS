import Link from "next/link";
import { ArrowRight, Compass, FileSearch, MousePointer2 } from "lucide-react";
import styles from "./agent-coming-soon.module.css";

const journeys = [
  {
    icon: Compass,
    label: "Find your pricing",
    detail: "Follow the navigation",
    tone: "violet",
  },
  {
    icon: FileSearch,
    label: "Explore your docs",
    detail: "Find the right information",
    tone: "lime",
  },
  {
    icon: MousePointer2,
    label: "Reach your signup",
    detail: "Inspect without submitting",
    tone: "ink",
  },
];

export function AgentComingSoon({ compact = false }: { compact?: boolean }) {
  return (
    <section
      className={`${styles.launch} ${compact ? styles.compact : ""}`}
      aria-label="Real AI agent testing, coming Christmas 2026"
    >
      <div className={styles.main}>
        <div className={styles.copy}>
          <p className={styles.eyebrow}>
            <span aria-hidden="true" /> On the horizon · Real AI agent testing
          </p>
          <h2>
            Your next tester is an <span>AI agent.</span>
          </h2>
          <p className={styles.description}>
            A real model. A real browser. No scripted shortcuts. Watch an agent
            navigate your website—and see exactly where the journey breaks.
          </p>
          <ul className={styles.promise}>
            <li>Every action.</li>
            <li>Every wrong turn.</li>
            <li>All in the trace.</li>
          </ul>
          {!compact && (
            <Link className={styles.link} href="/#scan">
              Start with your static scan <ArrowRight size={16} />
            </Link>
          )}
        </div>
        <div className={styles.release}>
          <div className={styles.calendar}>
            <span className={styles.releaseLabel}>The Christmas release</span>
            <div className={styles.date}>
              <span className={styles.day}>25</span>
              <span className={styles.monthYear}>
                <span>December</span>
                <span>2026</span>
              </span>
            </div>
            <span className={styles.planned}>Planned release</span>
          </div>
          <ol className={styles.journeys} aria-label="Planned agent workflows">
            {journeys.map(({ icon: Icon, label, detail, tone }, index) => (
              <li className={styles.journey} key={label}>
                <span className="icon-tile" data-tone={tone} aria-hidden="true">
                  <Icon size={18} strokeWidth={2} />
                </span>
                <div>
                  <p>{label}</p>
                  <span>{detail}</span>
                </div>
                <span className={styles.number} aria-hidden="true">
                  0{index + 1}
                </span>
              </li>
            ))}
          </ol>
        </div>
      </div>
      <footer className={styles.footer}>
        <span className={styles.badge}>Coming Christmas 2026</span>
        <p>
          Something to look forward to. Separate from today’s static score and
          $19 report.
        </p>
      </footer>
    </section>
  );
}
