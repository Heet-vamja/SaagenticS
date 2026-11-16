"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Download,
  FileSearch,
  Globe2,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type { CustomerFix, FreeReport, FreeReportInsight } from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { Brand, domainOf, Status, ThemeToggle } from "./product-ui";
import { MarketingFooter } from "./marketing-nav";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import { AssetDrafts, FindingList } from "./report-findings";
import { ReportSummary } from "./report-summary";
import { CheckResults, checkTotals, failingPages } from "./report-checks";
import { CustomerFixes } from "./customer-fixes";
import { ScanTransition } from "./scan-transition";
import { AccessPolicyPanel } from "./access-policy-panel";
import { ReportUnlock, ReportVerification } from "./report-unlock";
import { StandardsCoverage } from "./standards-coverage";
import { CrossCheck } from "./cross-check";
import { AgentComingSoon } from "./agent-coming-soon";

const stages = [
  {
    phase: "QUEUED",
    title: "Getting ready",
    detail: "Your website is in the scan queue.",
  },
  {
    phase: "CRAWLING",
    title: "Discovering your pages",
    detail: "Following public links, robots rules, and sitemaps.",
  },
  {
    phase: "BROWSER_CHECKS",
    title: "Checking the essentials",
    detail: "Inspecting content, markup, and common navigation barriers.",
  },
  {
    phase: "REPORT_READY",
    title: "Bringing it together",
    detail: "Calculating your score and choosing the most useful insights.",
  },
];

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="report-frame min-h-screen bg-background text-foreground">
      <header className="nav-glass sticky top-0 z-40 border-b border-border/60">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center justify-between gap-3 px-3 min-[360px]:px-4 sm:px-8">
          <Brand />
          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Button asChild size="sm" className="max-[359px]:px-3">
              <Link href="/#scan">
                New scan{" "}
                <ArrowUpRight
                  size={14}
                  className="hidden min-[360px]:block"
                  aria-hidden="true"
                />
              </Link>
            </Button>
          </div>
        </div>
      </header>
      {children}
      <MarketingFooter />
    </div>
  );
}

function FindingsSection({
  insights,
  mode,
  fixes = [],
  loadingFixes = false,
  pages,
}: {
  insights: FreeReportInsight[];
  mode: "locked" | "unlocked";
  fixes?: CustomerFix[];
  loadingFixes?: boolean;
  pages?: Record<string, string[]>;
}) {
  const titles = new Set(insights.map((insight) => insight.title));
  const free = fixes.filter((fix) => titles.has(fix.title)).length;
  const locked = mode === "locked" && insights.length > free;
  return (
    <section className="mt-16 sm:mt-20" aria-labelledby="insights-heading">
      <p className="eyebrow">Findings</p>
      <h2 id="insights-heading" className="display-md mt-2">
        {insights.length ? "What to fix first" : "No priority problems found"}
      </h2>
      <p className="mt-3 max-w-2xl text-[15.5px] leading-7 text-muted-foreground">
        {!insights.length
          ? "The inspected sample didn’t produce a priority finding. Untested checks are not passes."
          : `${insights.length} ${insights.length === 1 ? "finding" : "findings"}, highest impact first.` +
            (mode === "unlocked"
              ? " Ready prompts, asset drafts and progress tracking are in your Fix Center below."
              : loadingFixes
                ? " Preparing your free fixes…"
                : free === insights.length
                  ? " Each comes with a complete fix, free."
                  : free === 1
                    ? " One of them comes with a complete fix, free."
                    : free
                      ? ` ${free} of them come with a complete fix, free.`
                      : "")}
      </p>
      {insights.length > 0 && (
        <div className="mt-7">
          <FindingList
            insights={insights}
            fixes={fixes}
            mode={mode}
            pages={pages}
          />
        </div>
      )}
      {locked && !loadingFixes && (
        <p className="mt-3 text-[13.5px] leading-6 text-muted-foreground">
          Locked findings still show what to change. The Fix Kit adds the
          affected page, the evidence and a ready prompt.
        </p>
      )}
    </section>
  );
}

/** Before purchase: the findings with the free fixes folded in, then the offer,
 * which counts exactly what the Fix Kit adds for this report. */
function LockedFindings({
  token,
  data,
  insights,
  onUnlocked,
}: {
  token: string;
  data: FreeReport;
  insights: FreeReportInsight[];
  onUnlocked: () => void;
}) {
  const load = useCallback(() => api.fixPreview(token), [token]);
  const { data: preview, error, retry } = useResource(load);
  const fixes = preview?.fixes ?? [];
  const titles = new Set(fixes.map((fix) => fix.title));
  return (
    <>
      <FindingsSection
        insights={insights}
        mode="locked"
        fixes={fixes}
        loadingFixes={!preview && !error}
      />
      {error && (
        <div className="mt-4">
          <InlineError>
            {error.message}{" "}
            <button type="button" className="underline" onClick={retry}>
              Retry free fixes
            </button>
          </InlineError>
        </div>
      )}
      {preview && <AssetDrafts assets={preview.assets} />}
      <ReportUnlock
        token={token}
        website={data.website}
        scoreAvailable={data.score !== null}
        developmentSkipAvailable={data.development_skip_available}
        onUnlocked={onUnlocked}
        offer={
          preview
            ? {
                findings: insights.length,
                lockedFindings: insights.filter(
                  (insight) => !titles.has(insight.title),
                ).length,
                remainingFixes: preview.remaining_fixes,
                remainingAssets: preview.remaining_assets,
                truncated: preview.truncated,
              }
            : undefined
        }
      />
    </>
  );
}

export function FreeScanReport({ token }: { token: string }) {
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const paymentDeadline = useRef(0);
  const load = useCallback(() => api.freeReport(token), [token]);
  const poll = useCallback((report: FreeReport) => {
    if (!paymentDeadline.current) paymentDeadline.current = Date.now() + 120000;
    return (
      ["PENDING", "RUNNING"].includes(report.status) ||
      (typeof window !== "undefined" &&
        new URLSearchParams(window.location.search).get("checkout") ===
          "success" &&
        report.full_report_unlocked === false &&
        Date.now() < paymentDeadline.current)
    );
  }, []);
  const { data, error, retry } = useResource(load, poll);

  if (!data && !error) return <ScanTransition />;
  if (!data) {
    if (error instanceof ApiError && [401, 403].includes(error.status))
      return (
        <Frame>
          <ReportVerification token={token} onVerified={retry} />
        </Frame>
      );
    const missing = error instanceof ApiError && error.status === 404;
    return (
      <Frame>
        <main className="mx-auto max-w-2xl px-4 py-20 text-center sm:px-8 sm:py-28">
          <span className="icon-tile mx-auto mb-6 size-14 rounded-2xl">
            <FileSearch size={24} strokeWidth={1.8} />
          </span>
          <h1 className="display-md">
            {missing
              ? "This report link has expired"
              : "Your report couldn’t load"}
          </h1>
          <p className="lede mx-auto mt-4 max-w-lg">
            {missing
              ? "Report links are temporary. Start a fresh scan to see the latest results for your website."
              : error?.message}
          </p>
          <div className="mt-8 flex flex-wrap justify-center gap-3">
            {!missing && (
              <Button onClick={retry}>
                Try again <ArrowRight size={14} />
              </Button>
            )}
            <Button asChild variant={missing ? "default" : "outline"}>
              <Link href="/#scan">
                Scan a website <ArrowUpRight size={14} />
              </Link>
            </Button>
          </div>
        </main>
      </Frame>
    );
  }

  const scoreValue =
    data.score === null
      ? null
      : Math.max(0, Math.min(100, Math.round(data.score)));
  const scoreColor =
    scoreValue === null
      ? "var(--muted-foreground)"
      : scoreValue >= 80
        ? "var(--score-good)"
        : scoreValue >= 60
          ? "var(--score-fair)"
          : "var(--score-low)";
  const unlocked = data.full_report_unlocked !== false;
  const active = ["PENDING", "RUNNING"].includes(data.status);
  const partial =
    !active &&
    data.score !== null &&
    (data.status === "FAILED" || data.pages_failed > 0);
  async function downloadReport() {
    if (!data) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const blob = await api.exportFreeReport(token);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename = domainOf(data.website)
        .toLowerCase()
        .replace(/[^a-z0-9.-]+/g, "-");
      link.href = url;
      link.download = `${filename || "website"}-agentlane-report.pdf`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (downloadFailure) {
      setDownloadError(
        downloadFailure instanceof Error
          ? downloadFailure.message
          : "Could not download this report. Please retry.",
      );
    } finally {
      setDownloading(false);
    }
  }
  const currentStage = Math.max(
    0,
    stages.findIndex((stage) => stage.phase === data.phase),
  );
  const insights = data.insights.slice(0, 10);

  return (
    <Frame>
      <main className="mx-auto max-w-5xl px-4 pb-20 pt-10 sm:px-8 sm:pt-16">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-5 sm:mb-12">
          <div className="min-w-0">
            <p className="chip">
              <span className="chip-dot" aria-hidden="true" />
              {unlocked
                ? "Your readiness report"
                : "Your free readiness report"}
            </p>
            <h1 className="display-lg mt-5 break-words">
              {domainOf(data.website)}
            </h1>
            <p className="mt-4 flex items-center gap-1.5 text-[14px] text-muted-foreground">
              <ShieldCheck size={15} className="text-primary" /> Public pages
              only. Read-only checks.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            {partial ? (
              <span className="status-badge bg-warning-soft text-warning">
                Partial report
              </span>
            ) : (
              <Status value={data.status} />
            )}
            {unlocked && (
              <Button
                variant="outline"
                onClick={downloadReport}
                disabled={active || downloading}
                aria-label="Download report as PDF"
              >
                {downloading ? (
                  <LoaderCircle
                    size={14}
                    className="animate-spin text-signal"
                  />
                ) : (
                  <Download size={14} className="text-foreground" />
                )}
                {downloading ? "Preparing PDF…" : "Download report"}
              </Button>
            )}
          </div>
        </div>
        {unlocked && (
          <AccessPolicyPanel
            policies={data.access_policies}
            inspectionLimited={
              data.status === "FAILED" || data.pages_failed > 0
            }
          />
        )}
        {data.development_access && (
          <p className="mb-5 rounded-2xl bg-warning-soft px-4 py-3 text-[13px] font-medium leading-5 text-warning">
            {data.development_payment_skipped
              ? "Payment skipped in development. No Stripe purchase recorded."
              : "Local development session. Payment remains a separate step; test checkout or skip it explicitly."}
          </p>
        )}
        {downloadError && (
          <div className="mb-5" role="alert">
            <InlineError>{downloadError}</InlineError>
          </div>
        )}
        {error && (
          <div className="mb-5">
            <InlineError>
              {error.message}{" "}
              <button
                className="ml-1 font-semibold underline underline-offset-4"
                onClick={retry}
              >
                Retry updates
              </button>
            </InlineError>
          </div>
        )}

        {active ? (
          <section className="surface-float overflow-hidden" aria-live="polite">
            <div className="border-b bg-accent-soft/60 p-6 sm:p-10">
              <div className="flex items-start gap-4 sm:gap-5">
                <span className="icon-tile size-12 shrink-0 rounded-2xl">
                  <LoaderCircle
                    size={23}
                    className="animate-spin motion-reduce:animate-none"
                  />
                </span>
                <div>
                  <h2 className="display-md">We’re checking your website</h2>
                  <p className="mt-2 text-[15px] leading-6 text-muted-foreground">
                    {data.progress_message}
                  </p>
                </div>
              </div>
            </div>
            <ol className="space-y-0 px-6 py-6 sm:px-10 sm:py-8">
              {stages.map((stage, index) => {
                const done = index < currentStage;
                const current = index === currentStage;
                const Icon = done
                  ? CheckCircle2
                  : current
                    ? LoaderCircle
                    : Circle;
                return (
                  <li key={stage.phase} className="relative flex gap-4 py-3.5">
                    {index < stages.length - 1 && (
                      <span
                        className={`absolute bottom-[-14px] left-[9px] top-9 border-l-2 ${done ? "border-primary" : "border-border"}`}
                      />
                    )}
                    <Icon
                      size={20}
                      className={`relative z-10 mt-0.5 shrink-0 rounded-full bg-card ${done ? "text-primary" : current ? "animate-spin text-signal motion-reduce:animate-none" : "text-muted-foreground/60"}`}
                    />
                    <div>
                      <p
                        className={`text-[15px] ${current ? "font-bold" : done ? "font-medium text-muted-foreground" : "text-muted-foreground"}`}
                      >
                        {stage.title}
                      </p>
                      {current && (
                        <p className="mt-1 text-xs leading-6 text-muted-foreground">
                          {stage.detail}
                        </p>
                      )}
                    </div>
                  </li>
                );
              })}
            </ol>
            <div className="flex flex-wrap items-center justify-between gap-3 border-t bg-muted/60 px-6 py-4 text-[13px] text-muted-foreground sm:px-10">
              <span>
                {data.pages_crawled}{" "}
                {data.pages_crawled === 1 ? "page checked" : "pages checked"} ·
                {data.pages_discovered} discovered · {data.pages_failed} failed
              </span>
              <span className="flex items-center gap-1.5">
                <span className="size-2 animate-pulse rounded-full bg-primary motion-reduce:animate-none" />{" "}
                Updates automatically
              </span>
            </div>
          </section>
        ) : (
          <>
            {data.failure_message && (
              <div className="mb-6 rounded-[20px] bg-warning-soft p-5 sm:p-6">
                <h2 className="text-[17px] text-warning">
                  {data.score === null
                    ? "We couldn’t complete this scan"
                    : "Some checks could not finish"}
                </h2>
                <p className="mt-2 text-[14px] leading-6 text-foreground">
                  {data.failure_message}
                </p>
              </div>
            )}
            <ReportSummary
              data={data}
              scoreValue={scoreValue}
              scoreColor={scoreColor}
              partial={partial}
            />

            {unlocked ? (
              <>
                <FindingsSection
                  insights={insights}
                  mode="unlocked"
                  pages={failingPages(data.checks)}
                />
                <CustomerFixes token={token} />
                <details className="group/checked surface mt-10 overflow-hidden">
                  <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3 gap-y-1 px-6 py-5 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                    <span className="font-display text-[17px] font-bold tracking-[-.02em]">
                      What was checked
                    </span>
                    <span className="text-[13px] text-muted-foreground">
                      {checkTotals(data.checks).checks} checks across{" "}
                      {data.pages_crawled}{" "}
                      {data.pages_crawled === 1 ? "page" : "pages"}, issues
                      first
                    </span>
                    <ChevronDown
                      size={18}
                      className="ml-auto shrink-0 text-muted-foreground transition-transform group-open/checked:rotate-180"
                    />
                  </summary>
                  <div className="border-t px-6 pb-6 pt-4">
                    <p className="flex items-start gap-2 text-[13px] leading-6 text-muted-foreground">
                      <Globe2 size={14} className="mt-1 shrink-0" />
                      {data.pages_crawled}{" "}
                      {data.pages_crawled === 1 ? "page was" : "pages were"}{" "}
                      checked in a bounded sample ({data.pages_discovered}{" "}
                      discovered, {data.pages_failed} failed). This static
                      assessment does not prove that an AI agent can or cannot
                      complete a task, and it does not guarantee visibility in
                      AI platforms.
                    </p>
                    <CheckResults
                      checks={data.checks}
                      truncated={data.checks_truncated}
                    />
                  </div>
                </details>
                {data.standards_coverage && (
                  <StandardsCoverage coverage={data.standards_coverage} />
                )}
              </>
            ) : (
              <LockedFindings
                token={token}
                data={data}
                insights={insights}
                onUnlocked={retry}
              />
            )}
            <CrossCheck website={data.website} />
            <div className="mt-6">
              <AgentComingSoon compact />
            </div>
          </>
        )}
        <p className="mt-10 flex items-center justify-center gap-1.5 text-center text-[13px] leading-5 text-muted-foreground">
          <Check size={14} className="shrink-0 text-success" />{" "}
          {data.development_access ? "Development access" : "Email verified"}.
          Read-only checks. No changes made to your website.
        </p>
      </main>
    </Frame>
  );
}
