"use client";

import Link from "next/link";
import { useCallback, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Bot,
  Check,
  CheckCircle2,
  ChevronDown,
  Circle,
  Download,
  Copy,
  FileSearch,
  Globe2,
  Info,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  FreeReport,
  FreeReportCheck,
  FreeReportInsight,
} from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { Brand, domainOf, Status, ThemeToggle } from "./product-ui";
import { MarketingFooter } from "./marketing-nav";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import { FreeFixKit } from "./free-fix-kit";
import { CustomerFixes } from "./customer-fixes";
import { ScanTransition } from "./scan-transition";
import { ReadinessScore } from "./readiness-score";
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

function reportCategory(value: string) {
  return value
    .replaceAll("_", " ")
    .toLowerCase()
    .replace(/^\w/, (letter) => letter.toUpperCase());
}

function insightCategoryIcon(category: string) {
  const normalized = category.toLowerCase();
  if (/discover|crawl|robots|sitemap/.test(normalized)) return Globe2;
  if (/structured|schema|content/.test(normalized)) return FileSearch;
  if (/navigation|interaction|accessibility|agent/.test(normalized))
    return ShieldCheck;
  return Info;
}

function whyInsightMatters(insight: FreeReportInsight) {
  const finding = `${insight.title} ${insight.description}`.toLowerCase();
  if (
    /accessible name|accessible label|form field|button.*name|link.*name/.test(
      finding,
    )
  )
    return "An accessible name helps an agent identify what this control does before choosing whether to use it.";
  if (/keyboard|clickable|native semantics/.test(finding))
    return "Native controls expose familiar roles and interaction behavior that browser tools can identify more reliably.";
  if (/javascript|rendered comparison|server-render/.test(finding))
    return "If key content appears only after scripts run, some crawlers and agents may miss it or wait longer to understand the page.";
  if (
    /challenge|captcha|bot protection|restricted|crawler access/.test(finding)
  )
    return "A challenge or access rule can stop an automated visitor before it reaches the page. This result reflects only the evidence in this scan.";
  if (/robots/.test(finding))
    return "The inspected robots rule affects this scanner’s access; other agents may follow different rules. Review the specific rule before changing it.";
  if (/sitemap/.test(finding))
    return "A sitemap can help crawlers discover pages directly, while internal links remain another discovery path.";
  if (/llms\.txt/.test(finding))
    return "llms.txt is an optional proposal. Its absence alone does not show that agents cannot discover or use your site.";
  if (/json-ld|structured data|schema/.test(finding))
    return "Valid structured data can make page entities easier for compatible tools to interpret; it does not replace readable page content.";
  if (/http|response|redirect|error/.test(finding))
    return "Unexpected responses or redirects can prevent an agent from reaching the content it was trying to inspect.";

  const category = insight.category.toLowerCase();
  if (/discover|crawl/.test(category))
    return "Agents can only use pages they can discover and access.";
  if (/structured|schema|content/.test(category))
    return "Clear structure helps agents identify the information a page contains.";
  if (/navigation|interaction|accessibility|agent/.test(category))
    return "Accessible names and predictable controls help agents choose the right interaction.";
  if (/reliability/.test(category))
    return "Consistent responses help agents tell whether a page loaded or an action failed.";
  return "This may affect an agent’s ability to find, understand, or use this part of the site.";
}

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="report-frame min-h-screen bg-background text-foreground">
      <header className="nav-glass sticky top-0 z-40 border-b border-border/60">
        <div className="mx-auto flex min-h-16 max-w-5xl items-center justify-between gap-4 px-4 sm:px-8">
          <Brand />
          <div className="flex items-center gap-1.5">
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

function Insight({
  insight,
  index,
}: {
  insight: FreeReportInsight;
  index: number;
}) {
  const [copyState, setCopyState] = useState("Copy fix");
  const safeUrl =
    insight.evidence_url && /^https?:\/\//i.test(insight.evidence_url)
      ? insight.evidence_url
      : null;
  const severity = insight.severity.toUpperCase();
  const severityStyle =
    severity === "CRITICAL" || severity === "HIGH"
      ? "bg-danger-soft text-danger"
      : severity === "MEDIUM"
        ? "bg-warning-soft text-warning"
        : "bg-muted text-muted-foreground";
  return (
    <article className="group flex flex-col py-5 first:pt-6 last:pb-6">
      <div className="mb-3 flex items-center justify-between gap-3">
        <span className="grid size-8 shrink-0 place-items-center rounded-full bg-ink font-mono text-[12px] font-semibold text-ink-foreground dark:bg-foreground dark:text-background">
          {String(index + 1).padStart(2, "0")}
        </span>
        <span
          className={`rounded-full px-2.5 py-1 text-[12px] font-bold uppercase tracking-wide ${severityStyle}`}
        >
          {severity} priority
        </span>
      </div>

      <p className="eyebrow mb-1.5">Observed issue</p>
      <h4 className="text-[17px] leading-snug sm:text-[19px]">
        {insight.title}
      </h4>
      <p className="mt-2 flex-1 text-[14px] leading-6 text-muted-foreground">
        {insight.description}
      </p>

      {insight.recommendation && (
        <div className="mt-4 rounded-2xl bg-action-soft p-4 dark:bg-accent-soft">
          <p className="text-[12px] font-bold uppercase tracking-[.1em] text-primary">
            How to fix it
          </p>
          <p className="mt-2 whitespace-pre-wrap break-words text-[14px] leading-6 text-foreground">
            {insight.recommendation}
          </p>
          <button
            type="button"
            className="mt-3 inline-flex min-h-9 items-center gap-1.5 rounded-full bg-card px-3.5 text-[13px] font-semibold text-foreground shadow-[var(--shadow-card)] transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
            aria-live="polite"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(
                  `${insight.title}\n\n${insight.recommendation}`,
                );
                setCopyState("Copied");
              } catch {
                setCopyState("Copy unavailable — select the text above");
              }
            }}
          >
            <Copy size={12} /> {copyState}
          </button>
        </div>
      )}
      {(safeUrl || insight.evidence_summary) && (
        <details className="group/evidence mt-4 border-t pt-3 text-xs">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-full py-1 font-semibold text-foreground focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40">
            Evidence & next step
            <ChevronDown
              size={14}
              className="shrink-0 transition-transform group-open/evidence:rotate-180"
            />
          </summary>
          <div className="mt-3 space-y-3 rounded-2xl bg-muted p-4 text-muted-foreground">
            <div>
              <p className="mb-1 text-[12px] font-semibold uppercase tracking-wider">
                Why this matters for this finding
              </p>
              <p className="leading-5">{whyInsightMatters(insight)}</p>
            </div>
            {insight.evidence_summary && (
              <div>
                <p className="mb-1 text-[12px] font-semibold uppercase tracking-wider">
                  What we observed
                </p>
                <p className="whitespace-pre-wrap break-words leading-5">
                  {insight.evidence_summary}
                </p>
              </div>
            )}
            {safeUrl && (
              <div>
                <p className="mb-1 text-[12px] font-semibold uppercase tracking-wider">
                  Affected page
                </p>
                <a
                  href={safeUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex max-w-full items-center gap-1.5 break-all font-mono text-[12px] text-foreground underline decoration-border underline-offset-4 hover:decoration-foreground"
                >
                  {safeUrl}
                  <ArrowUpRight size={11} className="shrink-0" />
                </a>
              </div>
            )}
          </div>
        </details>
      )}
    </article>
  );
}

const checkStatus = {
  PASS: { label: "Passed", style: "text-success bg-success-soft" },
  FAIL: { label: "Issue observed", style: "text-warning bg-warning-soft" },
  UNKNOWN: { label: "Not assessed", style: "text-muted-foreground bg-muted" },
  INFO: { label: "Informational", style: "text-muted-foreground bg-muted" },
  NOT_APPLICABLE: {
    label: "Not applicable",
    style: "text-muted-foreground bg-muted",
  },
} as const;

function CheckResults({
  checks,
  truncated,
}: {
  checks: FreeReportCheck[];
  truncated: boolean;
}) {
  const groups = new Map<string, FreeReportCheck[]>();
  for (const check of checks) {
    groups.set(check.category, [...(groups.get(check.category) ?? []), check]);
  }
  if (checks.length === 0) {
    return (
      <p className="mt-4 text-xs leading-6 text-muted-foreground">
        No individual check results were available for this scan. Review the
        scan status and try again if the website was unreachable.
      </p>
    );
  }
  return (
    <div className="mt-5 space-y-6">
      {[...groups.entries()].map(([category, rows]) => (
        <section key={category} aria-label={`${category} checks`}>
          <h3 className="mb-2.5 text-[15px]">{category}</h3>
          <div className="divide-y overflow-hidden rounded-2xl border bg-background">
            {rows.map((check, index) => {
              const status = checkStatus[check.status];
              const safeUrl =
                check.url && /^https?:\/\//i.test(check.url) ? check.url : null;
              return (
                <details
                  key={`${check.title}-${safeUrl ?? "site"}-${index}`}
                  className="group/check px-4"
                >
                  <summary className="flex cursor-pointer list-none flex-wrap items-center justify-between gap-3 py-3.5 focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40">
                    <span className="min-w-0 flex-1 text-[14px] font-medium">
                      {check.title}
                    </span>
                    <span
                      className={`rounded-full px-2.5 py-1 text-[12px] font-bold ${status.style}`}
                    >
                      {status.label}
                    </span>
                  </summary>
                  <div className="space-y-3 border-t py-3 text-[13px] leading-5 text-muted-foreground">
                    <p>{check.description}</p>
                    {check.evidence_summary && (
                      <p>
                        <span className="font-medium text-foreground">
                          Observed:
                        </span>
                        {check.evidence_summary}
                      </p>
                    )}
                    {safeUrl && (
                      <a
                        href={safeUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block break-all font-mono text-[12px] underline decoration-border underline-offset-4"
                      >
                        {safeUrl}
                      </a>
                    )}
                    {check.recommendation && (
                      <p>
                        <span className="font-medium text-foreground">
                          What to review:
                        </span>
                        {check.recommendation}
                      </p>
                    )}
                  </div>
                </details>
              );
            })}
          </div>
        </section>
      ))}
      {truncated && (
        <p className="text-[12px] text-muted-foreground">
          The report shows the first 300 check results.
        </p>
      )}
    </div>
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
  const insightGroups = insights.reduce<
    Array<{
      category: string;
      rows: Array<{ insight: FreeReportInsight; index: number }>;
    }>
  >((groups, insight, index) => {
    const group = groups.find((item) => item.category === insight.category);
    if (group) group.rows.push({ insight, index });
    else
      groups.push({ category: insight.category, rows: [{ insight, index }] });
    return groups;
  }, []);

  return (
    <Frame>
      <main className="mx-auto max-w-5xl px-4 pb-20 pt-10 sm:px-8 sm:pt-16">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-5 sm:mb-12">
          <div className="min-w-0">
            <p className="chip">
              <span className="chip-dot" aria-hidden="true" />
              Your free readiness report
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
            <section className="surface-float overflow-hidden">
              <div className="report-summary grid items-start gap-8 p-6 sm:grid-cols-[auto_1fr] sm:gap-12 sm:p-10">
                <div className="report-score-stage grid place-items-center rounded-[24px] p-5 sm:p-7">
                  <ReadinessScore value={scoreValue} color={scoreColor} />
                </div>
                <div className="min-w-0">
                  <span className="report-score-label mb-4 inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-[12px] font-bold">
                    <Info size={12} />
                    {data.score === null
                      ? "Score unavailable"
                      : partial
                        ? "Partial static assessment"
                        : "Preliminary static readiness"}
                  </span>
                  <h2 className="display-md">
                    {data.score === null
                      ? "There isn’t enough evidence yet."
                      : "A clearer view of your website."}
                  </h2>
                  <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
                    {data.score === null
                      ? "This scan did not gather enough confirmed evidence to calculate a static score. Review coverage and any observed issues below."
                      : `We checked ${data.pages_crawled} public ${data.pages_crawled === 1 ? "page" : "pages"} and observed ${data.coverage.checks_failed} ${data.coverage.checks_failed === 1 ? "issue" : "issues"}. Use the evidence and fix guidance below to decide what to improve first.`}
                  </p>
                  <div
                    className="mt-5 flex flex-wrap gap-2"
                    aria-label="Score coverage"
                  >
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-[12px] font-medium text-muted-foreground">
                      <CheckCircle2 size={13} className="text-success" />
                      {data.coverage.evaluated} of {data.coverage.total}{" "}
                      scoreable checks evaluated
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-[12px] font-medium text-muted-foreground">
                      <Globe2 size={12} /> {data.pages_crawled}{" "}
                      {data.pages_crawled === 1 ? "page" : "pages"} crawled
                    </span>
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-muted px-3 py-1.5 text-[12px] font-medium text-muted-foreground">
                      <Bot size={12} /> Agent tests · Christmas 2026
                    </span>
                  </div>
                  <details className="mt-4 text-xs text-muted-foreground">
                    <summary className="cursor-pointer py-1 font-semibold text-primary">
                      How this score works
                    </summary>
                    <p className="mt-2 leading-6">{data.score_explanation}</p>
                  </details>
                </div>
              </div>
              <div className="grid grid-cols-1 border-t sm:grid-cols-3">
                {[
                  [
                    CheckCircle2,
                    data.coverage.checks_passed,
                    "Checks passed",
                    "text-success",
                  ],
                  [
                    Info,
                    data.coverage.checks_failed,
                    "Issues observed",
                    "text-warning",
                  ],
                  [
                    Circle,
                    data.coverage.checks_inconclusive,
                    "Inconclusive",
                    "text-muted-foreground",
                  ],
                ].map(([Icon, count, label, color]) => {
                  const I = Icon as typeof CheckCircle2;
                  return (
                    <div
                      key={String(label)}
                      className="border-b px-6 py-5 last:border-0 sm:border-b-0 sm:border-r sm:px-8 sm:py-6"
                    >
                      <div
                        className={`mb-1.5 flex items-center gap-2 ${String(color)}`}
                      >
                        <I size={16} strokeWidth={2.2} />
                        <span className="font-display text-[34px] font-extrabold leading-none tracking-[-.025em] text-foreground">
                          {Number(count)}
                        </span>
                      </div>
                      <p className="text-[13px] font-medium leading-5 text-muted-foreground">
                        {String(label)}
                      </p>
                    </div>
                  );
                })}
              </div>
            </section>

            <section
              className="mt-16 sm:mt-20"
              aria-labelledby="insights-heading"
            >
              <div className="mb-1 flex flex-wrap items-end justify-between gap-3">
                <div>
                  <p className="eyebrow text-primary">Priority areas</p>
                  <h2 id="insights-heading" className="display-md mt-2">
                    {insights.length
                      ? "What to improve first"
                      : "No priority problems found"}
                  </h2>
                  {insights.length > 0 && (
                    <p className="mt-3 max-w-xl text-[15px] leading-7 text-muted-foreground">
                      Up to 10 priority issues with practical fixes, free. Start
                      here, then re-check your changes.
                    </p>
                  )}
                </div>
                {insights.length > 0 && (
                  <p className="rounded-full bg-muted px-3 py-1.5 text-[13px] font-medium text-muted-foreground">
                    {insights.length} priority{" "}
                    {insights.length === 1 ? "finding" : "findings"} across{" "}
                    {insightGroups.length}{" "}
                    {insightGroups.length === 1 ? "area" : "areas"}
                  </p>
                )}
              </div>
              {insights.length ? (
                <div
                  className={`mt-7 grid items-start gap-5 ${insightGroups.length > 1 ? "md:grid-cols-2" : ""}`}
                >
                  {insightGroups.map(({ category, rows }) => {
                    const CategoryIcon = insightCategoryIcon(category);
                    return (
                      <section
                        key={category}
                        className="report-category surface overflow-hidden"
                        aria-label={`${reportCategory(category)} insights`}
                      >
                        <header className="flex items-center gap-3 border-b px-5 py-4">
                          <span
                            className="icon-tile size-10 shrink-0 rounded-xl"
                            data-tone={
                              CategoryIcon === Globe2
                                ? "lime"
                                : CategoryIcon === FileSearch
                                  ? "ink"
                                  : CategoryIcon === Info
                                    ? "ink"
                                    : undefined
                            }
                          >
                            <CategoryIcon size={18} strokeWidth={2} />
                          </span>
                          <div className="min-w-0 flex-1">
                            <p className="eyebrow">Audit area</p>
                            <h3 className="mt-0.5 break-words text-[16px] leading-snug">
                              {reportCategory(category)}
                            </h3>
                          </div>
                          <span className="rounded-full bg-muted px-2.5 py-1 font-mono text-[12px] font-medium text-muted-foreground">
                            {String(rows.length).padStart(2, "0")}
                          </span>
                        </header>
                        <div className="divide-y px-5">
                          {rows.map(({ insight, index }) => (
                            <Insight
                              key={`${index}-${insight.title}-${insight.evidence_url ?? "site"}`}
                              insight={insight}
                              index={index}
                            />
                          ))}
                        </div>
                      </section>
                    );
                  })}
                </div>
              ) : (
                <div className="surface mt-7 flex items-start gap-4 p-6">
                  <span
                    className="icon-tile size-10 shrink-0 rounded-xl"
                    data-tone="lime"
                  >
                    <CheckCircle2 size={19} />
                  </span>
                  <p className="text-[15px] leading-7 text-muted-foreground">
                    {data.score === null
                      ? "We need more accessible page evidence before we can identify useful insights. Try again once your website is reachable."
                      : "The inspected sample didn’t produce a priority finding. Review the coverage below; untested checks are not passes."}
                  </p>
                </div>
              )}
            </section>

            {unlocked ? (
              <CustomerFixes token={token} />
            ) : (
              <>
                <FreeFixKit token={token} />
                <ReportUnlock
                  token={token}
                  website={data.website}
                  scoreAvailable={data.score !== null}
                  developmentSkipAvailable={data.development_skip_available}
                  onUnlocked={retry}
                />
              </>
            )}
            {unlocked && data.standards_coverage && (
              <StandardsCoverage coverage={data.standards_coverage} />
            )}
            <CrossCheck website={data.website} />
            <div className="mt-6">
              <AgentComingSoon compact />
            </div>

            {unlocked && (
              <details className="group/checked surface mt-6 overflow-hidden">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-6 py-5 font-display text-[17px] font-bold tracking-[-.02em] focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-ring/40">
                  What was checked{" "}
                  <ChevronDown
                    size={18}
                    className="shrink-0 text-muted-foreground transition-transform group-open/checked:rotate-180"
                  />
                </summary>
                <div className="border-t px-6 pb-6 pt-2">
                  {data.category_scores.map((category) => (
                    <div
                      key={category.name}
                      className="grid grid-cols-[1fr_auto] items-center gap-x-5 gap-y-2 border-b py-4 last:border-0"
                    >
                      <div>
                        <h3 className="text-[15px]">{category.name}</h3>
                        <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
                          {category.name === "Agent usability"
                            ? "Real AI agent tasks were not run · excluded from this score"
                            : category.tested
                              ? `${category.evaluated} of ${category.total} score-eligible checks had a confirmed result · ${category.weight}% base weight`
                              : "No score-eligible checks were available · see the check results below"}
                        </p>
                      </div>
                      <span className="font-mono text-xs font-medium text-foreground">
                        {category.score !== null
                          ? `${Math.round(category.score)}/100`
                          : category.tested
                            ? "Inconclusive"
                            : "Untested"}
                      </span>
                      {category.tested && category.score !== null && (
                        <div className="col-span-2 h-2 overflow-hidden rounded-full bg-muted">
                          <span
                            className="block h-full rounded-full bg-primary"
                            style={{
                              width: `${Math.max(0, Math.min(100, category.score))}%`,
                            }}
                          />
                        </div>
                      )}
                    </div>
                  ))}
                  <div className="mt-4 flex items-start gap-2 text-[13px] leading-6 text-muted-foreground">
                    <Globe2 size={14} className="mt-1 shrink-0" />
                    <p>
                      {data.pages_crawled}{" "}
                      {data.pages_crawled === 1 ? "page was" : "pages were"}{" "}
                      checked in a bounded sample ({data.pages_discovered}{" "}
                      discovered, {data.pages_failed} failed). This static
                      assessment does not prove that an AI agent can or cannot
                      complete a task. It does not guarantee visibility in AI
                      platforms.
                    </p>
                  </div>
                  <div className="mt-6 border-t pt-5">
                    <div className="flex flex-wrap gap-x-4 gap-y-2 text-[12px] text-muted-foreground">
                      <span>
                        {data.coverage.checks_informational} informational
                      </span>
                      <span>
                        {data.coverage.checks_not_applicable} not applicable
                      </span>
                    </div>
                    <CheckResults
                      checks={data.checks}
                      truncated={data.checks_truncated}
                    />
                  </div>
                </div>
              </details>
            )}
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
