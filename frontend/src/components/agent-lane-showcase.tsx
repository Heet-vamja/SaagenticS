import { Check } from "lucide-react";
import { Reveal } from "./reveal";
import styles from "./agent-lane-showcase.module.css";

// What a build produces, with real excerpts from the demo store's agent lane.
const PIECES = [
  {
    title: "Agent pages",
    text: "Every page as clean text, at the same address.",
    code: "/product/trail-runner.md\n# Trail Runner\nPrice: ₹2,799\n| 9 | In stock |",
  },
  {
    title: "llms.txt",
    text: "A map of your site that agents read first.",
    code: "# Northstar Shoes\n- Trail Runner: ₹2,799\n- City Walker: ₹1,999\n- Court Classic: ₹3,499",
  },
  {
    title: "Structured data",
    text: "Products and prices in the standard format.",
    code: '"@type": "Product",\n"name": "Trail Runner",\n"price": 2799,\n"priceCurrency": "INR"',
  },
  {
    title: "Actions, over API and MCP",
    text: "Things agents can do without clicking: a REST API and an MCP server.",
    code: "POST /mcp  tools/list\n→ search_products\n→ get_product\n→ check_delivery",
  },
];

const GUARANTEES = [
  "Humans never affected",
  "No cloaking",
  "Fails open",
  "Read-only actions",
];

/** What the agent lane is made of, shown as built for our demo store. */
export function AgentLaneShowcase() {
  return (
    <section
      id="agent-lane"
      className={styles.section}
      aria-labelledby="agent-lane-title"
    >
      <div className={styles.wrap}>
        <Reveal>
          <p className={styles.label}>What we build</p>
          <h2 id="agent-lane-title" className={styles.title}>
            Everything an agent needs, at your own address.
          </h2>
          <p className={styles.intro}>
            Built from your public pages and kept in step with them. Shown here
            as we built it for our demo store, Northstar Shoes.
          </p>
        </Reveal>
        <Reveal delay={100}>
          <ul
            className={styles.pieces}
            aria-label="What we built for the demo store"
          >
            {PIECES.map((piece) => (
              <li key={piece.title}>
                <h3>{piece.title}</h3>
                <p>{piece.text}</p>
                <pre>{piece.code}</pre>
              </li>
            ))}
          </ul>
          <div className={styles.checked}>
            <p>
              <strong>Checked before it goes live:</strong> 8 of 8 prices and 40
              of 40 stock levels matched the store.
            </p>
            <ul aria-label="Guarantees">
              {GUARANTEES.map((item) => (
                <li key={item}>
                  <Check size={14} strokeWidth={2.6} aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
