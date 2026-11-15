"use client";

import { useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  Check,
  CircleDashed,
  ChevronDown,
  Code2,
  Globe2,
  ScanLine,
} from "lucide-react";
import styles from "./readiness-lab.module.css";

const EXAMPLES = [
  {
    name: "Pricing",
    path: "/pricing",
    check: "Content in the HTML",
    before: "The page loads. The plans don’t.",
    after: "The important details arrive with the page.",
    evidence:
      "The example response contains an empty app container. Plan information appears only after JavaScript runs.",
    fixedEvidence:
      "The example HTML includes the plan content before JavaScript runs. A re-scan would check the deployed page again.",
    code: '<main id="app"></main>',
    fixedCode:
      "<main>\n  <h1>Plans & pricing</h1>\n  <!-- Render real plan data here -->\n</main>",
    fix: "Render your existing plan information in the initial HTML. Keep the interactive experience.",
  },
  {
    name: "Docs",
    path: "/docs",
    check: "A name for every link",
    before: "A link without a destination’s name.",
    after: "The next step speaks for itself.",
    evidence:
      "The example documentation link contains only an icon. It has no text alternative or accessible name.",
    fixedEvidence:
      "The example link now has a descriptive text label. The destination and behavior remain the same.",
    code: '<a href="/docs">\n  <BookIcon />\n</a>',
    fixedCode:
      '<a href="/docs">\n  <BookIcon aria-hidden="true" />\n  <span>Documentation</span>\n</a>',
    fix: "Give the existing link a descriptive accessible name. Preserve its destination and visual design.",
  },
  {
    name: "Signup",
    path: "/signup",
    check: "Labels that belong to fields",
    before: "A field that leaves the reader guessing.",
    after: "A clear name. A clear next step.",
    evidence:
      "The example email field relies on a placeholder. There is no associated label for people or browser agents.",
    fixedEvidence:
      "The example label is explicitly connected to the email field. This demonstrates markup only; no form is submitted.",
    code: '<input placeholder="Email" />',
    fixedCode:
      '<label for="email">Work email</label>\n<input id="email" type="email" />',
    fix: "Connect a visible label to the existing field. Preserve validation, styling, and submission behavior.",
  },
] as const;

export function ReadinessLab({ wide = false }: { wide?: boolean }) {
  const [selected, setSelected] = useState(0);
  const [showFix, setShowFix] = useState(false);
  const example = EXAMPLES[selected];
  return (
    <aside
      className={`${styles.lab} ${wide ? styles.wide : ""}`}
      aria-label="Interactive illustrative readiness example"
    >
      <header className={styles.header}>
        <span>
          <ScanLine size={15} /> INSIDE A READINESS CHECK
        </span>
        <span className={styles.demo}>Interactive demo</span>
      </header>
      <div
        className={styles.scenarios}
        role="group"
        aria-label="Choose an example journey"
      >
        {EXAMPLES.map((item, index) => (
          <button
            key={item.name}
            type="button"
            aria-pressed={selected === index}
            onClick={() => {
              setSelected(index);
              setShowFix(false);
            }}
          >
            {item.name}
            <ArrowUpRight size={12} />
          </button>
        ))}
      </div>
      <div className={styles.address}>
        <Globe2 size={13} />
        <span>example.com{example.path}</span>
        <span>Public page</span>
      </div>
      <div className={styles.journey} aria-hidden="true">
        <span>
          <ScanLine size={15} /> Scan
        </span>
        <i />
        <span className={showFix ? styles.resolved : styles.barrier}>
          {showFix ? <Check size={15} /> : <CircleDashed size={15} />}
          {showFix ? "Clearer markup" : "Barrier found"}
        </span>
      </div>
      <div
        className={styles.switcher}
        role="group"
        aria-label="Example markup state"
      >
        <button
          type="button"
          aria-pressed={!showFix}
          onClick={() => setShowFix(false)}
        >
          Before
        </button>
        <button
          type="button"
          aria-pressed={showFix}
          onClick={() => setShowFix(true)}
        >
          With the fix <ArrowUpRight size={11} />
        </button>
      </div>
      <div
        className={`${styles.observation} ${showFix ? styles.fixed : ""}`}
        role="region"
        aria-label="Example finding and evidence"
        tabIndex={0}
        aria-live="polite"
        aria-atomic="true"
      >
        <p className={styles.check}>{example.check}</p>
        <h2>{showFix ? example.after : example.before}</h2>
        <details className={styles.evidence} key={`${example.name}-${showFix}`}>
          <summary>
            View the example evidence <ChevronDown size={12} />
          </summary>
          <p>{showFix ? example.fixedEvidence : example.evidence}</p>
        </details>
        <div className={styles.code}>
          <div>
            <Code2 size={12} />
            <span>{showFix ? "Suggested markup" : "Observed markup"}</span>
            <span>HTML</span>
          </div>
          <pre
            tabIndex={0}
            aria-label={`${example.name} ${showFix ? "suggested" : "example"} markup`}
          >
            <code>{showFix ? example.fixedCode : example.code}</code>
          </pre>
        </div>
      </div>
      <div className={styles.next}>
        <ArrowDown size={14} />
        <p>{example.fix}</p>
      </div>
      <footer>
        Illustrative markup. Your report uses your crawl evidence.
      </footer>
    </aside>
  );
}
