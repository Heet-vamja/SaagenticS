"use client";

import { useState } from "react";
import { ArrowUpRight, ChevronDown } from "lucide-react";
import type { FreeReportCheck } from "@/lib/types";

type Status = FreeReportCheck["status"];

const ORDER: Record<Status, number> = {
  FAIL: 0,
  UNKNOWN: 1,
  PASS: 2,
  INFO: 3,
  NOT_APPLICABLE: 4,
};

const STATUS: Record<Status, { label: string; style: string }> = {
  PASS: { label: "Passed", style: "text-success bg-success-soft" },
  FAIL: { label: "Issue", style: "text-warning bg-warning-soft" },
  UNKNOWN: { label: "Inconclusive", style: "text-muted-foreground bg-muted" },
  INFO: { label: "Informational", style: "text-muted-foreground bg-muted" },
  NOT_APPLICABLE: {
    label: "Not applicable",
    style: "text-muted-foreground bg-muted",
  },
};

type CheckGroup = {
  key: string;
  title: string;
  description: string;
  recommendation: string | null;
  status: Status;
  rows: FreeReportCheck[];
  pages: number;
};

function pathOf(url: string | null) {
  if (!url || !/^https?:\/\//i.test(url)) return null;
  return url.replace(/^https?:\/\//, "");
}

function pages(count: number) {
  return `${count} ${count === 1 ? "page" : "pages"}`;
}

/** One line per check, across pages: "Issue on 1 of 10 pages". */
function groupSummary(group: CheckGroup) {
  const count = (status: Status) =>
    new Set(
      group.rows
        .filter((row) => row.status === status)
        .map((row) => row.url ?? ""),
    ).size;
  const share = (status: Status) => {
    const hits = count(status);
    if (hits === group.pages)
      return hits === 1 ? "1 page" : `all ${pages(hits)}`;
    return `${hits} of ${pages(group.pages)}`;
  };
  if (group.status === "FAIL") return `Issue on ${share("FAIL")}`;
  if (group.status === "UNKNOWN") return `Inconclusive on ${share("UNKNOWN")}`;
  if (group.status === "PASS") return `Passed on ${pages(group.pages)}`;
  if (group.status === "INFO") return `Recorded on ${pages(group.pages)}`;
  return `Not applicable on ${pages(group.pages)}`;
}

function groupChecks(checks: FreeReportCheck[]) {
  const categories = new Map<string, Map<string, CheckGroup>>();
  for (const check of checks) {
    const groups = categories.get(check.category) ?? new Map();
    categories.set(check.category, groups);
    const group: CheckGroup = groups.get(check.title) ?? {
      key: `${check.category}:${check.title}`,
      title: check.title,
      description: check.description,
      recommendation: check.recommendation,
      status: check.status,
      rows: [],
      pages: 0,
    };
    group.rows.push(check);
    if (ORDER[check.status] < ORDER[group.status]) group.status = check.status;
    group.recommendation ??= check.recommendation;
    groups.set(check.title, group);
  }
  return [...categories.entries()]
    .map(([category, groups]) => {
      const rows = [...groups.values()].map((group) => ({
        ...group,
        pages: new Set(group.rows.map((row) => row.url ?? "")).size,
        rows: [...group.rows].sort((a, b) => ORDER[a.status] - ORDER[b.status]),
      }));
      rows.sort(
        (a, b) =>
          ORDER[a.status] - ORDER[b.status] || a.title.localeCompare(b.title),
      );
      return {
        category,
        groups: rows,
        issues: rows.filter((group) => group.status === "FAIL").length,
      };
    })
    .sort(
      (a, b) => b.issues - a.issues || a.category.localeCompare(b.category),
    );
}

function CheckRow({ group }: { group: CheckGroup }) {
  const status = STATUS[group.status];
  return (
    <details className="group/check px-4">
      <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-x-3 gap-y-1 py-3.5 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40">
        <span className="min-w-0 flex-1">
          <span className="block text-[14px] font-medium">{group.title}</span>
          <span className="mt-0.5 block text-[12.5px] text-muted-foreground">
            {groupSummary(group)}
          </span>
        </span>
        <span
          className={`rounded-full px-2.5 py-1 text-[12px] font-semibold ${status.style}`}
        >
          {status.label}
        </span>
        <ChevronDown
          size={14}
          className="shrink-0 text-muted-foreground transition-transform group-open/check:rotate-180"
          aria-hidden="true"
        />
      </summary>
      <div className="space-y-3 border-t py-3 text-[13px] leading-5 text-muted-foreground">
        <p>{group.description}</p>
        {group.recommendation && (
          <p>
            <span className="font-medium text-foreground">
              What to review:{" "}
            </span>
            {group.recommendation}
          </p>
        )}
        <ul className="divide-y rounded-xl border bg-card">
          {group.rows.map((row, index) => {
            const path = pathOf(row.url);
            const rowStatus = STATUS[row.status];
            return (
              <li
                key={`${row.url ?? "site"}-${index}`}
                className="space-y-1 px-3 py-2.5"
              >
                <div className="flex items-center justify-between gap-3">
                  {path ? (
                    <a
                      href={row.url as string}
                      target="_blank"
                      rel="noopener noreferrer"
                      title={row.url as string}
                      className="inline-flex min-w-0 items-center gap-1 font-mono text-[12px] text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
                    >
                      <span className="truncate">{path}</span>
                      <ArrowUpRight size={11} className="shrink-0" />
                    </a>
                  ) : (
                    <span className="text-[12px]">Whole site</span>
                  )}
                  <span
                    className={`shrink-0 rounded-full px-2 py-0.5 text-[11.5px] font-semibold ${rowStatus.style}`}
                  >
                    {rowStatus.label}
                  </span>
                </div>
                {row.description !== group.description && (
                  <p>{row.description}</p>
                )}
                {row.evidence_summary && (
                  <p className="break-words">{row.evidence_summary}</p>
                )}
              </li>
            );
          })}
        </ul>
      </div>
    </details>
  );
}

/** Every check once, with its result across the sampled pages. Problems come first;
 * informational and not-applicable checks are tucked behind a toggle. */
export function CheckResults({
  checks,
  truncated,
}: {
  checks: FreeReportCheck[];
  truncated: boolean;
}) {
  const [showBackground, setShowBackground] = useState(false);
  if (checks.length === 0) {
    return (
      <p className="mt-4 text-xs leading-6 text-muted-foreground">
        No individual check results were available for this scan. Review the
        scan status and try again if the website was unreachable.
      </p>
    );
  }
  const categories = groupChecks(checks);
  const background = categories.reduce(
    (total, { groups }) =>
      total +
      groups.filter((group) => ORDER[group.status] >= ORDER.INFO).length,
    0,
  );
  return (
    <div className="mt-5 space-y-6">
      {categories.map(({ category, groups }) => {
        const visible = showBackground
          ? groups
          : groups.filter((group) => ORDER[group.status] < ORDER.INFO);
        if (!visible.length) return null;
        return (
          <section key={category} aria-label={`${category} checks`}>
            <h3 className="mb-2.5 text-[15px]">{category}</h3>
            <div className="divide-y overflow-hidden rounded-2xl border bg-background">
              {visible.map((group) => (
                <CheckRow key={group.key} group={group} />
              ))}
            </div>
          </section>
        );
      })}
      {background > 0 && (
        <button
          type="button"
          aria-expanded={showBackground}
          onClick={() => setShowBackground((value) => !value)}
          className="rounded-full border bg-card px-4 py-2 text-[13px] font-semibold transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
        >
          {showBackground
            ? "Hide informational and not-applicable checks"
            : `Show ${background} informational and not-applicable checks`}
        </button>
      )}
      {truncated && (
        <p className="text-[12px] text-muted-foreground">
          The report shows the first 300 check results.
        </p>
      )}
    </div>
  );
}

/** Distinct pages and checks behind the per-page results, for the section header. */
export function checkTotals(checks: FreeReportCheck[]) {
  return {
    checks: new Set(checks.map((check) => `${check.category}:${check.title}`))
      .size,
    pages: new Set(checks.map((check) => check.url).filter(Boolean)).size,
  };
}

/** Pages where each failing check was seen, keyed by title, for the findings list. */
export function failingPages(checks: FreeReportCheck[]) {
  const map: Record<string, string[]> = {};
  for (const check of checks) {
    if (check.status !== "FAIL" || !check.url) continue;
    const list = (map[check.title] ??= []);
    if (!list.includes(check.url)) list.push(check.url);
  }
  return map;
}
