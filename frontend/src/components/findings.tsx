import Link from "next/link";
import { ArrowRight, ChevronRight, Lightbulb } from "lucide-react";
import type { Finding } from "@/lib/types";
import { Button } from "./ui/button";
import { EmptyState } from "./states";
import { CopyButton } from "./product-ui";

export function Findings({
  findings,
  expanded = false,
}: {
  findings: Finding[];
  expanded?: boolean;
}) {
  if (!findings.length)
    return (
      <div className="surface">
        <EmptyState
          title="No issues recorded in this view"
          description="Review check coverage before interpreting an empty issue list. Unknown or untested checks do not count as passes."
          action={
            <Button asChild variant="outline">
              <Link href="/docs#outcomes">
                Understand current results
                <ArrowRight size={13} />
              </Link>
            </Button>
          }
        />
      </div>
    );
  const groups = new Map<string, Finding[]>();
  for (const finding of findings) {
    const rule = String(finding.evidence.rule ?? finding.title).replace(
      /^render\./,
      "",
    );
    groups.set(rule, [...(groups.get(rule) ?? []), finding]);
  }
  return (
    <div className="space-y-3">
      {[...groups.entries()].map(([rule, items]) => {
        const first = items[0];
        const pages = new Set(
          items
            .map((f) => String(f.evidence.page_key ?? f.evidence.url ?? ""))
            .filter(Boolean),
        );
        const affected =
          typeof first.evidence.affected_page_count === "number"
            ? first.evidence.affected_page_count
            : Array.isArray(first.evidence.affected_pages)
              ? first.evidence.affected_pages.length
              : pages.size;
        return (
          <details
            key={rule}
            open={expanded}
            className="surface group overflow-hidden"
          >
            <summary className="flex cursor-pointer list-none items-start gap-3 p-5 sm:items-center">
              <ChevronRight
                size={15}
                className="mt-0.5 shrink-0 text-muted-foreground transition-transform group-open:rotate-90"
              />
              <div className="min-w-0 flex-1">
                <h3 className="text-sm font-semibold">{first.title}</h3>
                <p className="mono mt-1.5 break-all text-[9px] text-muted-foreground">
                  {rule} · {affected || 1} {affected === 1 ? "page" : "pages"}{" "}
                  affected
                  {items.length > pages.size
                    ? " · raw and rendered evidence"
                    : ""}
                </p>
              </div>
              <span
                className={`status-badge ${["HIGH", "CRITICAL"].includes(first.severity) ? "status-failed" : first.severity === "MEDIUM" ? "status-pending" : "status-running"}`}
              >
                {first.severity.toLowerCase()}
              </span>
            </summary>
            <div className="border-t px-5 pb-5">
              <p className="mt-4 text-xs leading-6 text-muted-foreground">
                {first.description}
              </p>
              {first.recommendation && (
                <div className="mt-4 flex gap-3 rounded-lg bg-accent-soft p-4">
                  <Lightbulb
                    size={16}
                    className="mt-0.5 shrink-0 text-primary"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="mb-2 flex items-center justify-between">
                      <span className="text-[10px] font-medium text-primary">
                        Recommended fix
                      </span>
                      <CopyButton value={first.recommendation} />
                    </div>
                    <pre
                      tabIndex={0}
                      className="whitespace-pre-wrap break-words font-sans text-xs leading-6"
                    >
                      {first.recommendation}
                    </pre>
                  </div>
                </div>
              )}
              <details className="mt-4 text-xs">
                <summary>Page evidence ({items.length} observations)</summary>
                <div className="mt-3 space-y-4">
                  {items.slice(0, 10).map((finding, index) => (
                    <div key={finding.id ?? index}>
                      <p className="mono break-all text-[10px] text-muted-foreground">
                        {String(finding.evidence.url ?? "Site-wide check")}
                      </p>
                      <pre tabIndex={0} className="code-panel mt-2">
                        {JSON.stringify(finding.evidence, null, 2)}
                      </pre>
                    </div>
                  ))}
                  {items.length > 10 && (
                    <p className="text-[11px] text-muted-foreground">
                      Showing 10 evidence entries. Export JSON or CSV for every
                      occurrence.
                    </p>
                  )}
                </div>
              </details>
            </div>
          </details>
        );
      })}
    </div>
  );
}
