"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  ArrowUpRight,
  MousePointer2,
  LockKeyhole,
  Pause,
  Play,
} from "lucide-react";
import styles from "./hero-scan-preview.module.css";

/** Marketing specimen only: never calls scanning, browser-agent or model APIs. */
export function HeroScanPreview() {
  const [view, setView] = useState<"agent" | "human">("agent");
  const [count, setCount] = useState(0);
  const [paused, setPaused] = useState(false);
  const specimen = useRef<HTMLElement>(null);
  useEffect(() => {
    let frame = 0;
    let started = false;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || started) return;
        started = true;
        const start = performance.now();
        const tick = (now: number) => {
          const progress = Math.min(1, (now - start) / 1100);
          setCount(Math.round(42 * (1 - (1 - progress) ** 3)));
          if (progress < 1) frame = requestAnimationFrame(tick);
        };
        frame = requestAnimationFrame(tick);
        observer.disconnect();
      },
      { threshold: 0 },
    );
    // Reduced motion: show the specimen's final value without a count-up.
    if (reduced.matches) frame = requestAnimationFrame(() => setCount(42));
    else if (specimen.current) observer.observe(specimen.current);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, []);
  return (
    <aside
      ref={specimen}
      className={`${styles.card} ${paused ? styles.paused : ""}`}
      aria-label="Illustrative readiness report, demo data"
    >
      <header className={styles.header}>
        <span className={styles.lights} aria-hidden="true">
          <i />
          <i />
          <i />
        </span>
        <span className={styles.address}>
          <span className={styles.siteIcon}>N</span> northstar.example
        </span>
        <div className={styles.demoControls}>
          <span className={styles.demo}>Demo report</span>
          <button
            type="button"
            aria-label={
              paused ? "Resume demo animation" : "Pause demo animation"
            }
            title={paused ? "Resume demo animation" : "Pause demo animation"}
            aria-pressed={paused}
            onClick={() => setPaused((value) => !value)}
          >
            {paused ? <Play size={13} /> : <Pause size={13} />}
          </button>
        </div>
      </header>
      <div className={styles.body}>
        <div className={styles.summary}>
          <div className={styles.scoreRow}>
            <DemoScoreRing value={count} />
            <div>
              <p className={styles.scoreLabel}>Preliminary readiness</p>
              <h2>
                A page can load.
                <br />
                <span>And still lose an agent.</span>
              </h2>
            </div>
          </div>
          <ul
            className={styles.findings}
            aria-label="Illustrative static findings"
          >
            <li className={styles.revealed}>
              <span>Pricing content missing from HTML</span>
              <small className={styles.red}>Issue</small>
            </li>
            <li>
              <span>Navigation names need review</span>
              <small className={styles.amber}>Review</small>
            </li>
            <li>
              <span>Sitemap is reachable</span>
              <small className={styles.green}>Pass</small>
            </li>
          </ul>
        </div>
        <div className={styles.comparison}>
          <div
            className={styles.switcher}
            role="group"
            aria-label="Compare illustrative page views"
          >
            <button
              type="button"
              aria-pressed={view === "agent"}
              onClick={() => setView("agent")}
            >
              What an agent sees
            </button>
            <button
              type="button"
              aria-pressed={view === "human"}
              onClick={() => setView("human")}
            >
              What a human sees
            </button>
          </div>
          <div className={styles.browser}>
            <div className={styles.browserBar}>
              <span>northstar.example</span>
              <span className={styles.pricing}>
                Pricing <ArrowUpRight size={11} />
              </span>
            </div>
            <div
              className={styles.scene}
              role="region"
              aria-label={`${view} view, illustrative example`}
            >
              {view === "agent" ? (
                <div className={styles.empty}>
                  <code>&lt;main&gt;&lt;/main&gt;</code>
                  <span>The plans aren’t in the initial HTML.</span>
                  <span className={styles.blocked}>
                    <LockKeyhole size={12} /> Content unavailable in this
                    example
                  </span>
                </div>
              ) : (
                <div className={styles.plans}>
                  <div>
                    <span>Report</span>
                    <strong>$0</strong>
                    <small>Readiness insights</small>
                  </div>
                  <div>
                    <span>Fix Kit</span>
                    <strong>$19</strong>
                    <small>Implementation guidance</small>
                  </div>
                </div>
              )}
            </div>
            {view === "agent" && (
              <span className={styles.cursor} aria-hidden="true">
                <MousePointer2 size={23} />
                <span>Agent</span>
              </span>
            )}
          </div>
        </div>
      </div>
      <footer>
        Illustrative static findings and cursor animation. No agent task is
        running.
      </footer>
    </aside>
  );
}

export function DemoScoreRing({
  value,
  compact = false,
}: {
  value: number;
  compact?: boolean;
}) {
  const score = Math.max(0, Math.min(100, value));
  const gradient = `demo-ring-${useId().replace(/:/g, "")}`;
  return (
    <div
      className={`${styles.gauge} ${compact ? styles.compact : ""}`}
      role="img"
      aria-label="Illustrative readiness score: 42 out of 100, not a real scan result"
    >
      <svg viewBox="0 0 120 120" aria-hidden="true">
        <defs>
          <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
            {/* 42 is a "fair" score: use the same status colors as real reports. */}
            <stop offset="0%" stopColor="var(--score-fair-start)" />
            <stop offset="100%" stopColor="var(--score-fair)" />
          </linearGradient>
        </defs>
        <circle cx="60" cy="60" r="51" className={styles.track} />
        <circle
          cx="60"
          cy="60"
          r="51"
          className={styles.progress}
          stroke={`url(#${gradient})`}
          pathLength="100"
          strokeDasharray={`${score} 100`}
        />
      </svg>
      <div aria-hidden="true">
        <strong>{score}</strong>
        <span>/ 100</span>
      </div>
    </div>
  );
}
