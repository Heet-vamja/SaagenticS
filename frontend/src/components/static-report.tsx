"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  ArrowDownToLine,
  ArrowLeft,
  ArrowRight,
  Check,
  Copy,
  LoaderCircle,
  Share2,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type {
  AgentTaskSummary,
  AgentTaskStepSummary,
  AuditSummary,
  Scan,
  ScanComparison,
  StaticReport,
} from "@/lib/types";
import { Brand, domainOf, formatDate, PageHeading, Status } from "./product-ui";
import { Button } from "./ui/button";
import { Findings } from "./findings";
import { AgentTaskCards } from "./agent-task-cards";
import { EmptyState, ErrorState, InlineError, LoadingState } from "./states";
import {
  AgentTaskStatusList,
  ScanAgentTaskResults,
} from "./scan-agent-task-results";

type ReportWithAgentResults = StaticReport & {
  score_components?: {
    static_score?: number | null;
    agent_score?: number | null;
    fallback_reason?: string | null;
    eligible_runs?: number;
    excluded_infra_runs?: number;
    inconclusive_runs?: number;
    judged_runs?: number;
    provisional?: boolean;
  };
  agent_tasks?: Array<{
    id?: string;
    task_type: AgentTaskSummary["task_type"];
    description?: string;
    status?: string;
    outcome?: AgentTaskSummary["outcome"];
    consistency?: boolean | null;
    requested_runs?: number;
    runs_completed?: number;
    eligible_runs?: number;
    runs?: Array<{
      id?: string;
      run_number: number;
      status?: string;
      outcome?: AgentTaskSummary["outcome"];
      verification_method?: AgentTaskSummary["runs"][number]["verification_method"];
      failure_category?: AgentTaskSummary["runs"][number]["failure_category"];
      model?: string;
      steps?: number;
      duration_seconds?: number | null;
      prompt_tokens?: number;
      completion_tokens?: number;
      estimated_cost_usd?: number | null;
      step_details?: AgentTaskStepSummary[];
    }>;
  }>;
};

function taskCardsFromReport(
  tasks: NonNullable<ReportWithAgentResults["agent_tasks"]>,
): AgentTaskSummary[] {
  return tasks.map((task) => ({
    id: task.id,
    task_type: task.task_type,
    task_description: task.description,
    status: task.status,
    outcome: task.outcome,
    consistency: task.consistency,
    requested_runs: task.requested_runs,
    runs_completed: task.runs_completed,
    eligible_runs: task.eligible_runs,
    runs: (task.runs ?? []).map((run) => ({
      id: run.id,
      run_number: run.run_number,
      status: run.status,
      outcome: run.outcome,
      verification_method: run.verification_method,
      failure_category: run.failure_category,
      steps_completed: run.steps,
      execution_duration: run.duration_seconds,
      prompt_tokens: run.prompt_tokens,
      completion_tokens: run.completion_tokens,
      estimated_cost_usd: run.estimated_cost_usd,
      model_identifier: run.model,
      steps: run.step_details,
    })),
  }));
}

function ScoreComposition({
  scoreKind,
  score,
  staticScore,
  agentScore,
  fallbackReason,
}: {
  scoreKind: string;
  score: number | null;
  staticScore: number | null;
  agentScore?: number | null;
  fallbackReason?: string | null;
}) {
  const combined = scoreKind === "COMBINED_READINESS";
  const agentOnly = scoreKind === "AGENT_READINESS";
  return (
    <section
      className="surface mb-5 p-5"
      aria-label="Readiness score composition"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-sm font-semibold">
          {combined
            ? "Combined readiness"
            : agentOnly
              ? "Agent readiness"
              : "Static readiness score"}
        </h2>
        <strong className="text-lg">
          {score ?? "—"}
          <span className="ml-1 text-xs font-normal text-muted-foreground">
            /100
          </span>
        </strong>
      </div>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">
        {combined
          ? `Combines the static score (${staticScore ?? "—"}) with agent task results (${agentScore ?? "—"}).`
          : agentOnly
            ? "Static checks were unavailable; this score uses agent task results only and has limited coverage."
            : fallbackReason ||
              "Agent results are missing or inconclusive, so the static score is shown as the fallback."}
      </p>
    </section>
  );
}

export function ScanScoreComposition({ scan }: { scan: Scan }) {
  const summary = scan.audit_summary as
    | (AuditSummary & {
        score_kind?: string;
        static_score?: number | null;
        agent?: {
          agent_score?: number | null;
          fallback_reason?: string | null;
        };
      })
    | undefined;
  if (!summary?.version && !summary?.score_kind) return null;
  const scoreKind = summary?.score_kind ?? "STATIC_READINESS";
  const staticScore =
    summary?.static_score ??
    (scoreKind === "STATIC_READINESS" ? scan.overall_score : null);
  return (
    <ScoreComposition
      scoreKind={scoreKind}
      score={scan.overall_score}
      staticScore={staticScore}
      agentScore={summary?.agent?.agent_score}
      fallbackReason={summary?.agent?.fallback_reason}
    />
  );
}

export function StaticScore({
  summary,
  score,
  scanId,
}: {
  summary?: AuditSummary;
  score: number | null;
  scanId?: string;
}) {
  if (!summary?.version) return null;
  const known = Object.values(summary.coverage ?? {}).reduce(
    (n, c) => n + c.evaluated,
    0,
  );
  const total = Object.values(summary.coverage ?? {}).reduce(
    (n, c) => n + c.total,
    0,
  );
  return (
    <section
      className="surface mb-7 overflow-hidden"
      aria-label="Static readiness score"
    >
      <div className="grid md:grid-cols-[.85fr_1.15fr]">
        <div className="bg-muted p-6 sm:p-8">
          <p className="eyebrow">Static readiness · {summary.version}</p>
          <p className="my-4 font-display text-6xl font-medium tracking-tight">
            {score ?? "—"}
            <span className="ml-2 text-lg text-muted-foreground">/ 100</span>
          </p>
          <p className="text-xs leading-6 text-muted-foreground">
            Deterministic website checks. Agent task success is not included.
          </p>
          <span className="mt-3 inline-flex rounded border bg-card px-2 py-1 text-[12px]">
            {summary.provisional ? "Partial coverage" : "Evaluated sample"} ·{" "}
            {known}/{total} checks evaluated
          </span>
          {scanId && (
            <Link
              className="mt-5 flex items-center gap-2 text-xs font-medium text-foreground"
              href={`/scans/${scanId}/report`}
            >
              Open report, priority fixes and exports <ArrowRight size={14} />
            </Link>
          )}
        </div>
        <div className="space-y-5 p-6 sm:p-8">
          {Object.entries(summary.category_scores ?? {}).map(
            ([name, value]) => (
              <div key={name}>
                <div className="mb-2 flex justify-between text-xs">
                  <span>
                    {name}
                    <small className="ml-2 text-muted-foreground">
                      {summary.weights?.[name]}% weight
                    </small>
                  </span>
                  <strong>{value ?? "Not evaluated"}</strong>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted">
                  <span
                    className="block h-full rounded-full bg-foreground/70"
                    style={{ width: `${value ?? 0}%` }}
                  />
                </div>
              </div>
            ),
          )}
        </div>
      </div>
      <div className="flex flex-wrap gap-4 border-t px-6 py-3 text-[13px] text-muted-foreground">
        <span>{summary.counts?.PASS ?? 0} passed</span>
        <span>{summary.counts?.FAIL ?? 0} failed</span>
        <span>{summary.counts?.UNKNOWN ?? 0} inconclusive</span>
        <span>{summary.counts?.NOT_APPLICABLE ?? 0} not applicable</span>
      </div>
    </section>
  );
}

export function ScoreHistory({ scans }: { scans: Scan[] }) {
  const scored = scans
    .filter((s) => s.audit_summary?.version && s.overall_score !== null)
    .slice(0, 8)
    .reverse();
  if (!scored.length) return null;
  return (
    <section className="surface mb-7 p-6">
      <h2 className="section-title">Readiness score history</h2>
      <p className="mt-2 text-xs text-muted-foreground">
        Scores reflect the rubric and evidence available on each scan. Open a
        report to compare components and coverage.
      </p>
      <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {scored.map((scan) =>
          (() => {
            const summary = scan.audit_summary;
            const kind = summary?.score_kind ?? "STATIC_READINESS";
            return (
              <Link
                href={`/scans/${scan.id}/report`}
                className="rounded-lg border p-4 hover:bg-muted"
                key={scan.id}
              >
                <span className="text-[12px] text-muted-foreground">
                  {formatDate(scan.started_at)}
                </span>
                <strong className="my-2 block text-2xl">
                  {scan.overall_score}
                  <small className="ml-1 text-xs font-normal text-muted-foreground">
                    /100
                  </small>
                </strong>
                <span className="block h-1 rounded bg-muted">
                  <span
                    className="block h-full rounded bg-foreground/60"
                    style={{ width: `${scan.overall_score}%` }}
                  />
                </span>
                <small className="mt-2 block text-[12px] text-muted-foreground">
                  {kind.replaceAll("_", " ")} · {summary?.version} ·{" "}
                  {summary?.provisional
                    ? "partial coverage"
                    : "evaluated sample"}
                </small>
                {summary?.static_score != null &&
                  summary.agent?.agent_score != null && (
                    <small className="mt-2 block text-[12px] text-muted-foreground">
                      Static {summary.static_score} · Agent{" "}
                      {summary.agent.agent_score}
                    </small>
                  )}
              </Link>
            );
          })(),
        )}
      </div>
    </section>
  );
}

function Comparison({ id, projectId }: { id: string; projectId?: string }) {
  const [before, setBefore] = useState("");
  const load = useCallback(
    async () => ({
      comparison: await api.comparison(id, before || undefined),
      history: projectId ? await api.history(projectId) : [],
    }),
    [id, before, projectId],
  );
  const { data, error, retry } = useResource(load);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const compare: ScanComparison = data.comparison;
  return (
    <section className="surface mb-7 p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <h2 className="section-title">Before / after</h2>
        <label className="text-xs text-muted-foreground">
          Compare with
          <select
            className="field mt-2 max-w-xs"
            value={before}
            onChange={(e) => setBefore(e.target.value)}
          >
            <option value="">Previous scan</option>
            {data.history
              .filter(
                (s) =>
                  s.id !== id && !["RUNNING", "PENDING"].includes(s.status),
              )
              .map((s) => (
                <option key={s.id} value={s.id}>
                  {formatDate(s.started_at)} · {s.id.slice(0, 8)} ·{" "}
                  {s.overall_score ?? "not scored"}
                </option>
              ))}
          </select>
        </label>
      </div>
      {!compare.available ? (
        <p className="mt-5 text-xs leading-6 text-muted-foreground">
          {compare.reason}
        </p>
      ) : (
        <>
          <div className="my-6 grid grid-cols-2 gap-4 sm:grid-cols-5">
            {[
              [
                "Score change",
                compare.score_delta == null
                  ? "—"
                  : `${compare.score_delta > 0 ? "+" : ""}${compare.score_delta}`,
              ],
              ["Resolved", compare.resolved?.length ?? 0],
              ["New issues", compare.added?.length ?? 0],
              ["Still present", compare.unchanged?.length ?? 0],
              ["Not retested", compare.not_retested?.length ?? 0],
            ].map(([label, value]) => (
              <div key={label}>
                <span className="text-[12px] text-muted-foreground">
                  {label}
                </span>
                <strong className="mt-2 block text-2xl font-medium">
                  {value}
                </strong>
              </div>
            ))}
          </div>
          <p className="text-[13px] leading-6 text-muted-foreground">
            {compare.note}
            {compare.coverage_changed &&
              " Coverage changed between these scans."}
            {compare.agent_coverage_changed &&
              " Agent task coverage changed; compare task outcomes separately."}
          </p>
          {compare.score_components && (
            <div className="mt-4 grid gap-3 rounded-lg border bg-muted/30 p-4 text-[12px] sm:grid-cols-3">
              <span>
                Static score change:{" "}
                {compare.score_components.static_delta == null
                  ? "not comparable"
                  : `${compare.score_components.static_delta > 0 ? "+" : ""}${compare.score_components.static_delta}`}
              </span>
              <span>
                Agent score change:{" "}
                {compare.score_components.agent_delta == null
                  ? "not comparable"
                  : `${compare.score_components.agent_delta > 0 ? "+" : ""}${compare.score_components.agent_delta}`}
              </span>
              <span>
                {compare.score_components.score_comparable
                  ? "Overall scores use comparable coverage."
                  : "Overall score change is hidden because scoring coverage or weights differ."}
              </span>
            </div>
          )}
          {!!compare.agent_task_changes?.length && (
            <div className="mt-4 rounded-lg border p-4">
              <h3 className="text-xs font-medium">
                Agent task outcome changes
              </h3>
              <div className="mt-3 space-y-2">
                {compare.agent_task_changes.map((task) => (
                  <div
                    key={task.task_type}
                    className="flex flex-wrap justify-between gap-2 text-[12px]"
                  >
                    <span className="font-medium">
                      {task.task_type.replaceAll("_", " ")}
                    </span>
                    <span className="text-muted-foreground">
                      {task.before ?? "No earlier result"} →{" "}
                      {task.after ?? "No current result"} ·{" "}
                      {task.after_eligible_runs} eligible runs now
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {(
            [
              ["Resolved", compare.resolved],
              ["New issues", compare.added],
              ["Not retested", compare.not_retested],
            ] as const
          ).map(([title, checks]) =>
            checks?.length ? (
              <details key={title} className="mt-4 border-t pt-4 text-xs">
                <summary>
                  {title} ({checks.length})
                </summary>
                <ul className="mt-3 space-y-3">
                  {checks.map((c, i) => (
                    <li key={i}>
                      <strong>{c.title}</strong>
                      <span className="mono mt-1 block break-all text-[12px] text-muted-foreground">
                        {c.url}
                      </span>
                    </li>
                  ))}
                </ul>
              </details>
            ) : null,
          )}
        </>
      )}
    </section>
  );
}

export function ReportView({
  scanId,
  token,
}: {
  scanId?: string;
  token?: string;
}) {
  const load = useCallback(
    () => (token ? api.sharedReport(token) : api.report(scanId!)),
    [scanId, token],
  );
  const poll = useCallback(
    (r: StaticReport) => ["RUNNING", "PENDING"].includes(r.scan.status),
    [],
  );
  const { data, error, retry } = useResource(load, poll);
  const [busy, setBusy] = useState("");
  const [actionError, setActionError] = useState("");
  const [share, setShare] = useState<{ url: string; expires: string } | null>(
    null,
  );
  const [copied, setCopied] = useState(false);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const reportData = data as ReportWithAgentResults;
  const staticScore =
    reportData.score_components?.static_score ??
    (data.score_kind === "STATIC_READINESS" ? data.scan.overall_score : null);
  const active = ["PENDING", "RUNNING"].includes(data.scan.status);
  const download = async (format: "json" | "csv" | "pdf") => {
    setBusy(format);
    setActionError("");
    try {
      const blob = await api.exportReport(
        token ?? scanId!,
        format,
        Boolean(token),
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `agentlane-report.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setActionError(
        e instanceof Error ? e.message : "Could not export report",
      );
    } finally {
      setBusy("");
    }
  };
  return (
    <div className={token ? "mx-auto max-w-6xl px-5 py-8 sm:px-8" : "fade-in"}>
      {token && (
        <div className="mb-10 flex flex-wrap items-center justify-between gap-4">
          <Brand />
          <span className="rounded-full border px-3 py-2 text-[12px] text-muted-foreground">
            Shared static report · anyone with this link
          </span>
        </div>
      )}
      <PageHeading
        back={
          scanId
            ? { href: `/scans/${scanId}`, label: "Back to scan" }
            : undefined
        }
        eyebrow="Evidence-based website checks"
        title={domainOf(data.project.website_url)}
        description={`Static readiness report · ${formatDate(data.scan.started_at)}`}
        action={<Status value={data.scan.status} />}
      />
      <div className="mb-6 flex flex-wrap gap-2">
        {(["json", "csv", "pdf"] as const).map((format) => (
          <Button
            key={format}
            variant="outline"
            disabled={Boolean(busy) || active}
            onClick={() => void download(format)}
          >
            {busy === format ? (
              <LoaderCircle className="animate-spin" size={14} />
            ) : (
              <ArrowDownToLine size={14} />
            )}
            Export {format.toUpperCase()}
          </Button>
        ))}
        {scanId && (
          <>
            <Button
              variant="outline"
              disabled={Boolean(busy) || active}
              onClick={async () => {
                setBusy("share");
                setActionError("");
                try {
                  const result = await api.shareReport(scanId);
                  setShare({
                    url: location.origin + result.path,
                    expires: result.expires_at,
                  });
                } catch (e) {
                  setActionError(
                    e instanceof Error ? e.message : "Could not share report",
                  );
                } finally {
                  setBusy("");
                }
              }}
            >
              <Share2 size={14} />
              Create share link
            </Button>
            <Button
              variant="ghost"
              disabled={Boolean(busy)}
              onClick={async () => {
                setBusy("revoke");
                setActionError("");
                try {
                  await api.revokeShares(scanId);
                  setShare(null);
                } catch (e) {
                  setActionError(
                    e instanceof Error ? e.message : "Could not revoke links",
                  );
                } finally {
                  setBusy("");
                }
              }}
            >
              Revoke share links
            </Button>
          </>
        )}
      </div>
      {actionError && (
        <div className="mb-5">
          <InlineError>{actionError}</InlineError>
        </div>
      )}
      {share && (
        <div className="surface mb-6 p-5">
          <p className="text-xs font-medium">
            Anyone with this link can view this report until{" "}
            {formatDate(share.expires)}.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <input
              aria-label="Share report link"
              readOnly
              value={share.url}
              className="field min-w-0 flex-1"
            />
            <Button
              variant="outline"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(share.url);
                  setCopied(true);
                  setTimeout(() => setCopied(false), 2000);
                } catch {
                  setActionError("Select and copy the link above.");
                }
              }}
            >
              {copied ? <Check size={14} /> : <Copy size={14} />}Copy link
            </Button>
          </div>
        </div>
      )}
      {!data.audited ? (
        <div className="surface">
          <EmptyState
            title={
              active
                ? "Your report is being prepared"
                : "This scan predates static audits"
            }
            description={
              active
                ? "The scan performs discovery, static checks and a bounded browser comparison. No LLM is called."
                : "Start a new scan to calculate a static readiness score and generate evidence-backed findings."
            }
          />
        </div>
      ) : (
        <>
          <ScoreComposition
            scoreKind={data.score_kind}
            score={data.scan.overall_score}
            staticScore={staticScore}
            agentScore={reportData.score_components?.agent_score}
            fallbackReason={reportData.score_components?.fallback_reason}
          />
          <StaticScore summary={data.scan.audit_summary} score={staticScore} />
          <section className="mb-7">
            <h2 className="section-title mb-2">Agent task results</h2>
            <p className="mb-5 text-xs leading-5 text-muted-foreground">
              Each task shows its run outcome and verification level. Completion
              alone does not establish success.{" "}
              {scanId
                ? "Recorded step replay is available below when captured."
                : "Shared reports contain task summaries; replay stays in the scan workspace."}
            </p>
            {scanId ? (
              <ScanAgentTaskResults scanId={scanId} />
            ) : (
              <>
                <AgentTaskStatusList
                  tasks={taskCardsFromReport(reportData.agent_tasks ?? [])}
                />
                <AgentTaskCards
                  tasks={taskCardsFromReport(reportData.agent_tasks ?? [])}
                />
              </>
            )}
          </section>
          <section className="mb-7">
            <h2 className="section-title mb-2">Top priority fixes</h2>
            <p className="mb-5 text-xs text-muted-foreground">
              Up to five distinct checks, ranked by severity and number of
              affected pages.
            </p>
            <Findings findings={data.priority_fixes} expanded />
          </section>
          {scanId && !active && (
            <Comparison id={scanId} projectId={data.project.id} />
          )}
          <section>
            <h2 className="section-title mb-5">
              All findings ({data.findings.length})
            </h2>
            <Findings findings={data.findings} />
          </section>
          <details className="surface mt-7 p-6">
            <summary className="text-sm font-medium">
              Check coverage and scoring rubric
            </summary>
            <p className="mt-4 text-xs leading-6 text-muted-foreground">
              Within each category, occurrences are averaged per rule before
              weighting. Categories use Access 30%, Readability 25%,
              Actionability 30%, Reliability 15%. Unknown checks are excluded
              and coverage is disclosed. Missing categories make the score
              provisional. Agent task success contributes a separately weighted
              component when eligible runs are available; incomplete or
              infrastructure-only runs fall back to this static score.
            </p>
            <div className="mt-5 overflow-x-auto">
              <table className="data-table min-w-[650px]">
                <thead className="table-head">
                  <tr>
                    <th>Check</th>
                    <th>Category</th>
                    <th>Result</th>
                    <th>Page / evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {data.scan.audit_summary.checks?.map((c, i) => (
                    <tr className="table-row" key={i}>
                      <td>{c.rule}</td>
                      <td>{c.bucket}</td>
                      <td>{c.status.replaceAll("_", " ")}</td>
                      <td>
                        <span
                          className="mono block max-w-[300px] truncate text-[12px]"
                          title={c.url ?? undefined}
                        >
                          {c.url}
                        </span>
                        <details className="mt-2 text-[12px]">
                          <summary>Details</summary>
                          <p className="mt-2 leading-5">{c.description}</p>
                          <pre tabIndex={0} className="code-panel mt-2">
                            {JSON.stringify(c.evidence, null, 2)}
                          </pre>
                        </details>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <ul className="mt-5 list-disc space-y-2 pl-4 text-[13px] leading-6 text-muted-foreground">
              {data.scan.audit_summary.limitations?.map((text) => (
                <li key={text}>{text}</li>
              ))}
            </ul>
          </details>
        </>
      )}
      <p className="mt-7 flex items-start gap-2 text-[13px] leading-6 text-muted-foreground">
        <ShieldCheck size={15} className="mt-1 shrink-0" />
        Static readiness measures the inspected sample. It does not certify
        accessibility or independently verify agent task success.
      </p>
      {token && (
        <Link
          href="/"
          className="mt-6 inline-flex items-center gap-2 text-xs font-medium text-foreground"
        >
          <ArrowLeft size={14} />
          Scan your own website
        </Link>
      )}
    </div>
  );
}
