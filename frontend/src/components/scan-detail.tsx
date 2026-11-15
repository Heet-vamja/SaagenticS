"use client";
import { useCallback, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  Bot,
  CheckCircle2,
  FileSearch,
  Globe2,
  LoaderCircle,
  ScanLine,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type {
  AgentTest,
  CrawledPage,
  Finding,
  Project,
  Scan,
} from "@/lib/types";
import { AgentHistory, AgentTesting } from "./agent-testing";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";
import {
  CopyButton,
  domainOf,
  formatDate,
  Metric,
  PageHeading,
  SectionHeader,
  Status,
} from "./product-ui";
import { EmptyState, ErrorState, InlineError, LoadingState } from "./states";
import { Findings } from "./findings";
import { Tabs } from "./tabs";
import { ScanScoreComposition, StaticScore } from "./static-report";
import { ScanAgentTaskResults } from "./scan-agent-task-results";
type Data = {
  scan: Scan;
  project: Project;
  pages: CrawledPage[];
  findings: Finding[];
  tests: AgentTest[];
};
const active = (d: Data) =>
  d.scan.status === "PENDING" ||
  d.scan.status === "RUNNING" ||
  d.tests.some((t) => t.status === "PENDING" || t.status === "RUNNING");
export function ScanDetail({ id }: { id: string }) {
  const router = useRouter();
  const params = useSearchParams();
  const [tab, setTab] = useState(
    params.get("tab") === "agents" ? "agents" : "pages",
  );
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<CrawledPage | null>(null);
  const [busy, setBusy] = useState(false);
  const [detailBusy, setDetailBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState("");
  const load = useCallback(async () => {
    const scan = await api.scan(id);
    const [project, pages, findings, tests] = await Promise.all([
      api.project(scan.project_id),
      api.pages(id, offset),
      api.findings(id),
      api.agentTests(id),
    ]);
    return { scan, project, pages, findings, tests };
  }, [id, offset]);
  const { data, error, retry } = useResource(load, active);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const { scan, project, pages, findings, tests } = data;
  const scoreSummary = scan.audit_summary as
    | (typeof scan.audit_summary & {
        score_kind?: string;
        static_score?: number | null;
      })
    | undefined;
  const staticScore =
    scoreSummary?.static_score ??
    (scoreSummary?.score_kind === "STATIC_READINESS" ||
    !scoreSummary?.score_kind
      ? scan.overall_score
      : null);
  return (
    <div className="fade-in">
      <PageHeading
        back={{ href: `/projects/${project.id}`, label: project.name }}
        eyebrow="Website crawl / scan results"
        title={domainOf(project.website_url)}
        description={`Started ${formatDate(scan.started_at)} · ${project.website_url}`}
        action={
          <>
            <Status value={scan.status} />
            <Button
              variant="outline"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setActionError("");
                try {
                  const next = await api.createScan(project.id);
                  router.push(`/scans/${next.id}`);
                } catch (e) {
                  setActionError(
                    e instanceof Error ? e.message : "Could not start scan",
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              {busy ? (
                <LoaderCircle size={13} className="animate-spin" />
              ) : (
                <ScanLine size={13} />
              )}
              New scan
            </Button>
          </>
        }
      />
      <div className="-mt-5 mb-7 flex items-center gap-1 text-[12px] text-muted-foreground">
        <span className="mono break-all">{scan.id}</span>
        <CopyButton value={scan.id} />
      </div>
      {actionError && (
        <div className="mb-5">
          <InlineError>{actionError}</InlineError>
        </div>
      )}
      {scan.error_summary && (
        <div className="mb-5">
          <InlineError>{scan.error_summary}</InlineError>
        </div>
      )}
      {["RUNNING", "PENDING"].includes(scan.status) && (
        <div
          role="status"
          className="mb-5 flex items-center gap-3 rounded-xl border border-signal/20 bg-accent-soft px-5 py-4"
        >
          <LoaderCircle size={16} className="animate-spin text-signal" />
          <div>
            <p className="text-xs font-medium">
              {scan.status === "PENDING"
                ? "Queued for scanning"
                : scan.audit_summary?.phase === "BROWSER_CHECKS"
                  ? "Comparing browser observations"
                  : scan.audit_summary?.phase === "AGENT_TASKS"
                    ? "Running real AI browser tasks"
                    : scan.audit_summary?.phase === "REPORT_READY"
                      ? "Preparing your report"
                      : "Discovering and checking your website"}
            </p>
            <p className="mt-1 text-[13px] text-muted-foreground">
              {scan.audit_summary?.phase === "AGENT_TASKS"
                ? "Static checks are complete; task runs, actions and verification results are updating automatically."
                : "Progress refreshes automatically. Discovery → static checks → browser sample → AI browser tasks → report."}
            </p>
          </div>
        </div>
      )}
      <div className="mb-7 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric
          label="Pages discovered"
          value={scan.pages_discovered}
          icon={Globe2}
        />
        <Metric
          label="Pages crawled"
          value={scan.pages_crawled}
          icon={FileSearch}
        />
        <Metric
          label="Failed pages"
          value={scan.pages_failed}
          icon={AlertTriangle}
        />
        <Metric label="Agent executions" value={tests.length} icon={Bot} />
      </div>
      <ScanScoreComposition scan={scan} />
      <StaticScore
        summary={scan.audit_summary}
        score={staticScore}
        scanId={scan.id}
      />
      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { value: "pages", label: "Crawled pages" },
          { value: "agents", label: "Agent tests", count: tests.length },
          {
            value: "findings",
            label: "Technical findings",
            count: findings.length,
          },
          { value: "discovery", label: "Discovery details" },
        ]}
      >
        {tab === "pages" && (
          <section className="surface overflow-hidden">
            <SectionHeader
              title="Discovered pages, with evidence"
              description="HTTP responses and extracted metadata from actual crawl attempts."
            />
            {pages.length === 0 ? (
              <EmptyState
                title={offset ? "No more pages" : "No crawled pages yet"}
                description={
                  offset
                    ? "Return to the previous page to continue exploring results."
                    : scan.status === "FAILED"
                      ? "The scan stopped before pages could be stored. Review the failure above, then retry with the correct website URL."
                      : "Pages appear here as the crawler finishes requests."
                }
                action={
                  offset ? (
                    <Button
                      variant="outline"
                      onClick={() => setOffset((n) => Math.max(0, n - 30))}
                    >
                      Previous page
                    </Button>
                  ) : undefined
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table min-w-[800px]">
                  <thead className="table-head">
                    <tr>
                      <th>Page URL / title</th>
                      <th>HTTP status</th>
                      <th>Depth</th>
                      <th>Crawl result</th>
                      <th>
                        <span className="sr-only">Page details</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {pages.map((page) => (
                      <tr key={page.id} className="table-row">
                        <td className="max-w-[420px]">
                          <button
                            className="block max-w-full text-left"
                            disabled={detailBusy !== null}
                            onClick={async () => {
                              setDetailBusy(page.id);
                              try {
                                setSelected(await api.page(id, page.id));
                              } catch (e) {
                                setActionError(
                                  e instanceof Error
                                    ? e.message
                                    : "Could not load page details",
                                );
                              } finally {
                                setDetailBusy(null);
                              }
                            }}
                          >
                            <span
                              className="mono block max-w-full truncate text-[12px] text-signal"
                              title={page.url}
                            >
                              {page.url}
                            </span>
                            <span className="mt-1.5 block truncate text-[13px] text-muted-foreground">
                              {page.title ?? "No title found"}
                            </span>
                          </button>
                        </td>
                        <td>
                          <span
                            className={`rounded border px-2 py-1 font-mono text-[12px] ${page.status_code && page.status_code < 400 ? "border-signal/15 bg-accent-soft text-signal" : "border-danger/15 bg-danger/5 text-danger"}`}
                          >
                            {page.status_code ?? "—"}
                          </span>
                        </td>
                        <td className="mono text-[12px]">{page.crawl_depth}</td>
                        <td className="max-w-[250px]">
                          <span
                            className={`inline-flex items-center gap-1.5 text-[12px] ${page.crawl_error ? "text-danger" : "text-muted-foreground"}`}
                          >
                            {page.crawl_error ? (
                              <AlertTriangle size={12} />
                            ) : (
                              <CheckCircle2 size={12} className="text-signal" />
                            )}
                            {page.crawl_error ??
                              (page.page_metadata.skipped
                                ? "Skipped (non-HTML)"
                                : "Crawled")}
                          </span>
                        </td>
                        <td>
                          {detailBusy === page.id && (
                            <LoaderCircle className="animate-spin" size={14} />
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="flex items-center justify-between border-t px-5 py-3">
              <span className="text-[12px] text-muted-foreground">
                Page {offset / 30 + 1}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  disabled={offset === 0}
                  onClick={() => setOffset((n) => Math.max(0, n - 30))}
                  className="h-8 px-3 text-[12px]"
                >
                  <ArrowLeft size={12} />
                  Previous
                </Button>
                <Button
                  variant="outline"
                  disabled={pages.length < 30}
                  onClick={() => setOffset((n) => n + 30)}
                  className="h-8 px-3 text-[12px]"
                >
                  Next
                  <ArrowRight size={12} />
                </Button>
              </div>
            </div>
          </section>
        )}
        {tab === "agents" && (
          <div className="space-y-6">
            <AgentTesting scanId={id} />
            <section>
              <SectionHeader
                title="Agent task results"
                description="Run outcomes, verification level, and recorded browser replay evidence."
              />
              <ScanAgentTaskResults scanId={id} />
            </section>
            <section className="surface overflow-hidden">
              <SectionHeader
                title="Execution history"
                count={tests.length}
                description="Agent-reported outcomes are always distinct from independently verified success."
              />
              {tests.length ? (
                <AgentHistory tests={tests} />
              ) : (
                <EmptyState
                  title="Your first agent journey starts here"
                  description="Choose a task above. Each run records the model’s actions, observations, and available browser evidence."
                />
              )}
            </section>
          </div>
        )}
        {tab === "findings" && <Findings findings={findings} />}{" "}
        {tab === "discovery" && (
          <section className="surface p-6">
            <h2 className="section-title">Discovery diagnostics</h2>
            <p className="mt-2 text-xs leading-6 text-muted-foreground">
              Robots permissions and sitemap warnings recorded by this scan.
            </p>
            <pre tabIndex={0} className="code-panel mt-5">
              {JSON.stringify(scan.crawl_metadata, null, 2)}
            </pre>
          </section>
        )}
      </Tabs>
      <Dialog
        open={selected !== null}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <span className="eyebrow">Page evidence</span>
          <DialogTitle className="mt-2 pr-5 text-xl font-semibold tracking-tight">
            {selected?.title ?? "Page metadata"}
          </DialogTitle>
          <DialogDescription className="mono mt-3 break-all text-[12px] leading-5 text-muted-foreground">
            {selected?.url}
          </DialogDescription>
          {selected && (
            <>
              <div className="my-6 grid grid-cols-3 gap-3">
                {[
                  ["HTTP status", selected.status_code ?? "Unknown"],
                  ["Crawl depth", selected.crawl_depth],
                  ["Result", selected.crawl_error ? "Failed" : "Crawled"],
                ].map(([label, value]) => (
                  <div
                    key={label}
                    className="rounded-lg border bg-background p-3"
                  >
                    <p className="text-[12px] text-muted-foreground">{label}</p>
                    <p className="mt-2 text-xs font-medium">{value}</p>
                  </div>
                ))}
              </div>
              {selected.crawl_error && (
                <InlineError>{selected.crawl_error}</InlineError>
              )}
              <dl className="space-y-4 text-xs">
                <div>
                  <dt className="eyebrow text-[12px]">Meta description</dt>
                  <dd className="mt-2 leading-6 text-muted-foreground">
                    {selected.meta_description || "Not provided"}
                  </dd>
                </div>
                <div>
                  <dt className="eyebrow text-[12px]">Canonical URL</dt>
                  <dd className="mono mt-2 break-all text-[12px] text-muted-foreground">
                    {selected.canonical_url || "Not provided"}
                  </dd>
                </div>
                <div>
                  <dt className="eyebrow text-[12px]">Content type</dt>
                  <dd className="mono mt-2 text-[12px] text-muted-foreground">
                    {selected.content_type || "Unknown"}
                  </dd>
                </div>
              </dl>
              <details className="mt-6 text-xs">
                <summary>Extracted metadata</summary>
                <pre tabIndex={0} className="code-panel mt-3">
                  {JSON.stringify(selected.page_metadata, null, 2)}
                </pre>
              </details>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
