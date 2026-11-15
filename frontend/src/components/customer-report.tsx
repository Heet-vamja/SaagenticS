"use client";

import Link from "next/link";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  ArrowUpRight,
  CheckCircle2,
  Circle,
  FileSearch,
  LoaderCircle,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Finding, StaticReport } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { Brand, domainOf, formatDate, Status } from "./product-ui";
import { Button } from "./ui/button";
import { ErrorState, InlineError, LoadingState } from "./states";
import { MarketingFooter } from "./marketing-nav";

type CustomerReportData = StaticReport & {
  scan: StaticReport["scan"] & { error_summary?: string | null };
  agent_tasks?: {
    task_type: string;
    status: string;
    outcome: string | null;
    runs_completed: number;
    eligible_runs: number;
  }[];
};

const progressSteps = [
  { phase: "QUEUED", label: "Scan queued" },
  { phase: "CRAWLING", label: "Finding important pages" },
  { phase: "BROWSER_CHECKS", label: "Checking how agents read your site" },
  { phase: "AGENT_TASKS", label: "Trying browser tasks" },
  { phase: "REPORT_READY", label: "Preparing your results" },
];

function coverageCounts(report: CustomerReportData) {
  const coverage = Object.values(report.scan.audit_summary.coverage ?? {});
  return {
    checked: coverage.reduce((total, item) => total + item.evaluated, 0),
    available: coverage.reduce((total, item) => total + item.total, 0),
  };
}

function categoryName(category: string) {
  const names: Record<string, string> = {
    DISCOVERABILITY: "Being found",
    UNDERSTANDABILITY: "Being understood",
    NAVIGABILITY: "Finding your way",
    INTERACTABILITY: "Using the page",
    RELIABILITY: "Site reliability",
  };
  return names[category.toUpperCase()] ?? category.toLowerCase();
}

function Insight({ finding, index }: { finding: Finding; index: number }) {
  return (
    <article className="rounded-xl border border-border/80 bg-card p-5 sm:p-6">
      <div className="flex items-start gap-4">
        <span className="grid size-8 shrink-0 place-items-center rounded-lg bg-muted font-mono text-xs font-semibold text-foreground">
          0{index + 1}
        </span>
        <div className="min-w-0 flex-1">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <span className="eyebrow">{categoryName(finding.category)}</span>
            {finding.severity && (
              <span className="rounded-full border px-2 py-0.5 text-[12px] text-muted-foreground">
                {finding.severity.toLowerCase()} priority
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold tracking-tight sm:text-base">
            {finding.title}
          </h3>
          <p className="mt-2 text-xs leading-6 text-muted-foreground sm:text-sm">
            {finding.description}
          </p>
        </div>
      </div>
    </article>
  );
}

export function CustomerReport({ scanId }: { scanId: string }) {
  const router = useRouter();
  const [rescanBusy, setRescanBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const load = useCallback(
    async () => (await api.report(scanId)) as CustomerReportData,
    [scanId],
  );
  const poll = useCallback(
    (report: CustomerReportData) =>
      ["PENDING", "RUNNING"].includes(report.scan.status),
    [],
  );
  const { data, error, retry } = useResource(load, poll);

  if (error) {
    return (
      <CustomerFrame>
        <div className="mx-auto max-w-3xl py-16">
          <ErrorState message={error.message} retry={retry} />
          <p className="mt-4 text-center text-xs text-muted-foreground">
            Your scan is saved. Retry this page to load the report.
          </p>
        </div>
      </CustomerFrame>
    );
  }
  if (!data) {
    return (
      <CustomerFrame>
        <div className="mx-auto max-w-3xl py-16">
          <LoadingState />
        </div>
      </CustomerFrame>
    );
  }

  const active = ["PENDING", "RUNNING"].includes(data.scan.status);
  const currentPhase = data.scan.audit_summary.phase ?? "QUEUED";
  const currentStep = Math.max(
    0,
    progressSteps.findIndex((step) => step.phase === currentPhase),
  );
  const score = data.scan.overall_score;
  const findings = data.priority_fixes.slice(0, 3);
  const coverage = coverageCounts(data);
  const eligibleAgentTasks =
    data.agent_tasks?.filter(
      (task) => task.eligible_runs > 0 && task.outcome !== "UNAVAILABLE",
    ).length ?? 0;
  const failedAgentTask = data.agent_tasks?.some(
    (task) => task.outcome === "UNAVAILABLE",
  );

  const rescan = async () => {
    if (!data.project.id) return;
    setRescanBusy(true);
    setActionError("");
    try {
      const next = await api.createScan(data.project.id);
      router.push(`/results/${next.id}`);
    } catch (cause) {
      setActionError(
        cause instanceof Error
          ? cause.message
          : "Could not start another scan.",
      );
    } finally {
      setRescanBusy(false);
    }
  };

  return (
    <CustomerFrame>
      <main className="mx-auto max-w-4xl px-5 pb-16 pt-8 sm:px-8 sm:pt-12">
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <div>
            <p className="eyebrow">Free website report</p>
            <h1 className="mt-2 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
              {domainOf(data.project.website_url)}
            </h1>
            <p className="mt-2 text-xs text-muted-foreground">
              Scan started {formatDate(data.scan.started_at)}
            </p>
          </div>
          <Status value={data.scan.status} />
        </div>

        {actionError && (
          <div className="mb-5">
            <InlineError>{actionError}</InlineError>
          </div>
        )}

        {active ? (
          <section
            className="rounded-xl border bg-card p-6 sm:p-9"
            aria-live="polite"
          >
            <div className="flex items-start gap-4">
              <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-muted text-foreground">
                <LoaderCircle size={21} className="animate-spin" />
              </span>
              <div>
                <h2 className="text-lg font-semibold tracking-tight sm:text-xl">
                  We’re checking your website
                </h2>
                <p className="mt-2 max-w-xl text-sm leading-6 text-muted-foreground">
                  We’ll look at the pages agents can reach, check how clearly
                  they describe your site, and try a limited browser task.
                </p>
              </div>
            </div>
            <ol className="mt-8 space-y-4 border-l pl-5 sm:ml-5">
              {progressSteps.map((step, index) => {
                const done = index < currentStep;
                const current = index === currentStep;
                const Icon = done
                  ? CheckCircle2
                  : current
                    ? LoaderCircle
                    : Circle;
                return (
                  <li
                    key={step.phase}
                    className="relative flex items-center gap-3"
                  >
                    <span className="absolute -left-[26px] grid size-5 place-items-center rounded-full bg-card">
                      <Icon
                        size={15}
                        className={
                          current
                            ? "animate-spin text-signal"
                            : done
                              ? "text-foreground"
                              : "text-muted-foreground/50"
                        }
                      />
                    </span>
                    <span
                      className={`text-xs ${current ? "font-medium text-foreground" : done ? "text-muted-foreground" : "text-muted-foreground/60"}`}
                    >
                      {step.label}
                    </span>
                  </li>
                );
              })}
            </ol>
            <p className="mt-7 border-t pt-4 text-[13px] leading-5 text-muted-foreground">
              This usually takes a minute or two. Keep this page open; your
              report updates automatically.
            </p>
          </section>
        ) : data.scan.status === "FAILED" ? (
          <section className="rounded-xl border border-danger/20 bg-danger/5 p-6 sm:p-9">
            <h2 className="text-lg font-semibold">
              We couldn’t finish this scan
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {data.scan.error_summary ??
                "The site stopped responding before we could complete the checks."}
            </p>
            {data.project.id && (
              <Button
                className="mt-5"
                onClick={() => void rescan()}
                disabled={rescanBusy}
              >
                {rescanBusy ? (
                  <LoaderCircle size={14} className="animate-spin" />
                ) : (
                  <RefreshCw size={14} />
                )}
                Try another scan
              </Button>
            )}
          </section>
        ) : !data.audited ? (
          <section className="rounded-xl border bg-card p-6 sm:p-9">
            <h2 className="text-lg font-semibold">A new scan is needed</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              This scan doesn’t include the current readiness checks. Start a
              fresh scan to create a report.
            </p>
            {data.project.id && (
              <Button
                className="mt-5"
                onClick={() => void rescan()}
                disabled={rescanBusy}
              >
                Start a new scan <ArrowRight size={14} />
              </Button>
            )}
          </section>
        ) : (
          <>
            <section className="overflow-hidden rounded-xl border bg-card">
              <div className="grid gap-6 bg-muted/50 p-6 sm:grid-cols-[1fr_auto] sm:items-center sm:p-9">
                <div>
                  <p className="eyebrow">Preliminary readiness score</p>
                  <p className="mt-3 max-w-xl text-sm leading-6 text-muted-foreground">
                    A snapshot of the pages and checks completed in this scan.
                    It does not predict whether your site will appear in an AI
                    answer.
                  </p>
                  <p className="mt-3 text-[13px] text-muted-foreground">
                    {data.score_kind === "COMBINED_READINESS"
                      ? "Includes technical checks and evaluated browser-task results."
                      : "Based on deterministic technical checks completed for this scan."}
                  </p>
                </div>
                <div className="flex items-baseline gap-2 sm:justify-self-end">
                  <strong className="font-display text-6xl font-semibold tracking-tight">
                    {score ?? "—"}
                  </strong>
                  <span className="text-sm text-muted-foreground">/ 100</span>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-t px-6 py-4 text-[13px] text-muted-foreground sm:px-9">
                <span className="inline-flex items-center gap-1.5">
                  <FileSearch size={13} /> {data.scan.pages_crawled} pages
                  inspected
                </span>
                {coverage.available > 0 && (
                  <span>
                    {coverage.checked} of {coverage.available} checks completed
                  </span>
                )}
                {data.scan.audit_summary.provisional && (
                  <span className="rounded-full border px-2 py-1">
                    Partial coverage
                  </span>
                )}
              </div>
            </section>

            {data.agent_tasks?.length ? (
              <section className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card px-5 py-4">
                <div>
                  <p className="text-xs font-semibold">Browser-agent check</p>
                  <p className="mt-1 text-[13px] text-muted-foreground">
                    {eligibleAgentTasks > 0
                      ? `${eligibleAgentTasks} of ${data.agent_tasks.length} tasks had enough evidence to evaluate.`
                      : "No browser-task result was available to include in this score."}
                  </p>
                </div>
                <span className="rounded-full border px-2.5 py-1 text-[12px] text-muted-foreground">
                  {eligibleAgentTasks > 0 ? "Evaluated" : "Unavailable"}
                </span>
              </section>
            ) : null}

            <section className="mt-10">
              <div className="mb-5">
                <p className="eyebrow">What to look at first</p>
                <h2 className="mt-2 font-display text-2xl font-semibold tracking-tight sm:text-3xl">
                  Your top insights.
                </h2>
                <p className="mt-2 text-sm leading-6 text-muted-foreground">
                  Up to three of the highest-priority issues found in the checks
                  we actually completed.
                </p>
              </div>
              {findings.length ? (
                <div className="space-y-3">
                  {findings.map((finding, index) => (
                    <Insight
                      key={finding.id ?? `${finding.title}-${index}`}
                      finding={finding}
                      index={index}
                    />
                  ))}
                </div>
              ) : (
                <div className="rounded-xl border bg-card p-6">
                  <div className="flex items-start gap-3">
                    <CheckCircle2
                      size={18}
                      className="mt-0.5 text-foreground"
                    />
                    <div>
                      <h3 className="text-sm font-semibold">
                        No high-priority issues surfaced
                      </h3>
                      <p className="mt-2 text-xs leading-6 text-muted-foreground">
                        That applies only to the checks and pages inspected. Any
                        unknown or untested area is not counted as a pass.
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </section>

            {failedAgentTask && (
              <p className="mt-6 rounded-lg border px-4 py-3 text-xs leading-5 text-muted-foreground">
                The browser-agent check was unavailable for this scan. The score
                uses the completed technical checks only.
              </p>
            )}

            <section className="mt-8 flex flex-col gap-4 rounded-xl border bg-card p-6 sm:flex-row sm:items-center sm:justify-between sm:p-8">
              <div>
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Sparkles size={15} className="text-foreground" />
                  Want to work through the findings?
                </p>
                <p className="mt-2 max-w-xl text-xs leading-5 text-muted-foreground">
                  Review the supporting evidence and the current recommended
                  fixes for this website.
                </p>
              </div>
              <Button asChild className="shrink-0">
                <Link href={`/scans/${scanId}/report`}>
                  Review all findings <ArrowUpRight size={14} />
                </Link>
              </Button>
            </section>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
              <p className="flex items-center gap-2 text-[13px] leading-5 text-muted-foreground">
                <ShieldCheck size={14} /> Results reflect this scan’s evidence,
                not a guarantee of AI-platform visibility.
              </p>
              <Button
                variant="ghost"
                onClick={() => void rescan()}
                disabled={rescanBusy || !data.project.id}
              >
                {rescanBusy ? (
                  <LoaderCircle size={13} className="animate-spin" />
                ) : (
                  <RefreshCw size={13} />
                )}
                Re-scan
              </Button>
            </div>
          </>
        )}
      </main>
    </CustomerFrame>
  );
}

function CustomerFrame({ children }: { children: React.ReactNode }) {
  return (
    <div className="report-frame min-h-screen bg-background">
      <header className="border-b bg-card/90">
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between gap-4 px-5 sm:px-8">
          <Brand />
          <Link
            href="/"
            className="text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            Scan another website{" "}
            <ArrowRight size={13} className="ml-1 inline" />
          </Link>
        </div>
      </header>
      {children}
      <MarketingFooter />
    </div>
  );
}
