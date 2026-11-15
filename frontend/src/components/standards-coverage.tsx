import { ChevronDown, ExternalLink } from "lucide-react";
import type { StandardsCoverage as Coverage } from "@/lib/types";

const labels = {
  PARTIAL_EVIDENCE: "Partial evidence",
  INCONCLUSIVE: "Inconclusive",
  NOT_TESTED: "Not tested",
};

export function StandardsCoverage({ coverage }: { coverage: Coverage }) {
  return (
    <details className="group/standards surface mt-6 overflow-hidden">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-6 py-5 font-display text-[17px] font-bold tracking-[-.02em] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
        AgentReady reference coverage{" "}
        <ChevronDown
          size={18}
          className="shrink-0 text-muted-foreground transition-transform group-open/standards:rotate-180"
        />
      </summary>
      <div className="space-y-4 border-t p-6">
        <p className="text-[15px] leading-7 text-muted-foreground">
          This maps our existing static measurements to AgentReady v
          {coverage.spec_version}. It is not a certification or a separate
          score. Passing signals do not establish that a complete requirement is
          satisfied. Act-stage applicability and task success have not been
          assessed.
        </p>
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-muted-foreground">
          <a
            href={coverage.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-semibold text-primary underline-offset-4 hover:underline"
          >
            Read the specification <ExternalLink size={12} />
          </a>
          <span>
            Reviewed {coverage.reviewed_on} · Mapping {coverage.mapping_version}
          </span>
        </div>
        {(["FIND", "READ", "ACT"] as const).map((stage) => {
          const rows = coverage.requirements.filter(
            (row) => row.stage === stage,
          );
          return (
            <details key={stage} className="overflow-hidden rounded-2xl border">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 bg-muted px-4 py-3.5 text-sm font-semibold">
                <span>
                  {stage === "FIND"
                    ? "Find · discovery and access"
                    : stage === "READ"
                      ? "Read · content and technical signals"
                      : "Act · interfaces and task completion"}
                </span>
                <span className="shrink-0 text-xs font-normal text-muted-foreground">
                  {rows.length} requirements
                </span>
                <ChevronDown size={13} />
              </summary>
              <div className="divide-y px-4">
                {rows.map((row) => (
                  <article key={row.id} className="py-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted-foreground">
                        {row.id} · {row.level}
                      </span>
                      <span className="rounded-full bg-accent-soft px-2.5 py-1 text-xs font-bold text-signal">
                        {labels[row.assessment]}
                      </span>
                    </div>
                    <h3 className="mt-2 text-[15px]">{row.title}</h3>
                    <p className="mt-1 text-xs leading-6 text-muted-foreground">
                      {row.implementation === "NOT_IMPLEMENTED"
                        ? "No mapped check is implemented."
                        : `Mapped signals: ${row.observations.passed} passed · ${row.observations.issues} issues · ${row.observations.inconclusive} inconclusive · ${row.observations.informational} informational · ${row.observations.not_applicable} not applicable. These are individual check results.`}
                    </p>
                    <p className="mt-2 text-sm leading-6 text-muted-foreground">
                      {row.limitations}
                    </p>
                  </article>
                ))}
              </div>
            </details>
          );
        })}
        {coverage.checks_truncated && (
          <p className="text-xs leading-6 text-muted-foreground">
            Reference coverage is bounded to the first 10,000 stored
            measurements.
          </p>
        )}
      </div>
    </details>
  );
}
