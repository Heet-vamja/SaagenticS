import { Info } from "lucide-react";
import type { FreeReport } from "@/lib/types";
import { domainOf } from "./product-ui";
import { ReadinessScore } from "./readiness-score";
import { isHighSeverity } from "./report-findings";

function plural(count: number, one: string, many = `${one}s`) {
  return `${count} ${count === 1 ? one : many}`;
}

/** What the score means in a sentence. The score covers finding and reading pages,
 * not using them, so the verdict never claims more than that. */
function verdict(score: number, domain: string) {
  if (score >= 85) return `Agents can find and read most of ${domain}.`;
  if (score >= 65) return `Agents can reach ${domain}, but miss parts of it.`;
  return `Agents struggle to find and read ${domain}.`;
}

/** Score, verdict and per-area breakdown. Areas without scoreable evidence say
 * "Not scored" and still show how many findings they produced. */
export function ReportSummary({
  data,
  scoreValue,
  scoreColor,
  partial,
}: {
  data: FreeReport;
  scoreValue: number | null;
  scoreColor: string;
  partial: boolean;
}) {
  const domain = domainOf(data.website);
  const insights = data.insights.slice(0, 10);
  const unscored = data.category_scores.filter(
    (category) => category.score === null,
  );
  const unscoredHigh = insights.filter(
    (insight) =>
      isHighSeverity(insight.severity) &&
      unscored.some((category) => category.name === insight.category),
  ).length;
  const sample =
    data.pages_discovered > data.pages_crawled
      ? `We checked ${data.pages_crawled} of the ${data.pages_discovered} pages we found.`
      : `We checked ${plural(data.pages_crawled, "public page")}.`;
  const followUp = partial
    ? " Some pages couldn’t be inspected, so the score covers only what we reached."
    : unscoredHigh
      ? ` ${plural(unscoredHigh, "high-priority issue")} ${unscoredHigh === 1 ? "affects" : "affect"} how agents use your pages, which isn’t part of the score yet.`
      : insights.length
        ? ` ${plural(insights.length, "finding")} to review below, highest impact first.`
        : " Nothing in this sample needs a priority fix.";

  return (
    <section className="surface-float overflow-hidden">
      <div className="report-summary grid items-center gap-8 p-6 sm:grid-cols-[auto_1fr] sm:gap-11 sm:p-10">
        <div className="justify-self-center">
          <ReadinessScore value={scoreValue} color={scoreColor} />
        </div>
        <div className="min-w-0">
          <span className="report-score-label inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12.5px] font-semibold">
            <Info size={12} aria-hidden="true" />
            {data.score === null
              ? "Score unavailable"
              : partial
                ? "Partial static assessment"
                : "Preliminary static readiness"}
          </span>
          <h2 className="display-md mt-4">
            {scoreValue === null
              ? "There isn’t enough evidence yet."
              : verdict(scoreValue, domain)}
          </h2>
          <p className="mt-3 max-w-[60ch] text-[15.5px] leading-7 text-muted-foreground">
            {scoreValue === null
              ? "This scan did not gather enough confirmed evidence to calculate a static score. Review any observed issues below."
              : sample + followUp}
          </p>
        </div>
      </div>
      {data.category_scores.length > 0 && (
        <ul
          className="report-areas grid grid-cols-1 border-t min-[480px]:grid-cols-2 lg:grid-cols-4"
          aria-label="Score by area"
        >
          {data.category_scores.map((category) => {
            const found = insights.filter(
              (insight) => insight.category === category.name,
            );
            const high = found.some((insight) =>
              isHighSeverity(insight.severity),
            );
            const scored = category.score !== null;
            return (
              <li
                key={category.name}
                className="px-6 py-5"
                data-unscored={scored ? undefined : ""}
              >
                <div className="flex items-baseline justify-between gap-3 text-[14px] font-semibold">
                  <span>{category.name}</span>
                  {scored ? (
                    <span className="font-mono text-[13px]">
                      {Math.round(category.score as number)}
                    </span>
                  ) : (
                    <span className="text-[12.5px] font-medium text-muted-foreground">
                      Not scored
                    </span>
                  )}
                </div>
                <div
                  className="report-area-bar mt-2.5"
                  aria-hidden="true"
                  data-empty={scored ? undefined : ""}
                >
                  {scored && (
                    <span
                      style={{
                        width: `${Math.max(0, Math.min(100, category.score as number))}%`,
                      }}
                    />
                  )}
                </div>
                <p
                  className={`mt-2 text-[12.5px] ${!scored && high ? "font-medium text-danger" : "text-muted-foreground"}`}
                >
                  {scored
                    ? `${category.evaluated} of ${plural(category.total, "check")}`
                    : found.length
                      ? `${plural(found.length, high ? "high-priority issue" : "issue")}`
                      : category.name === "Agent usability"
                        ? "Needs real agent tests"
                        : "No scoreable checks"}
                </p>
              </li>
            );
          })}
        </ul>
      )}
      <details className="group/score border-t bg-[color-mix(in_srgb,var(--muted)_45%,transparent)] text-[13px] text-muted-foreground">
        <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-x-4 gap-y-1 px-6 py-3.5 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
          <span>
            {data.coverage.checks_passed} checks passed ·{" "}
            {plural(data.coverage.checks_failed, "issue")} ·{" "}
            {data.coverage.checks_inconclusive} inconclusive
          </span>
          <span className="font-semibold text-foreground">
            How this score works
          </span>
        </summary>
        <p className="px-6 pb-5 leading-6">{data.score_explanation}</p>
      </details>
    </section>
  );
}
