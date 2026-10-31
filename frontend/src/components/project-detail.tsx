"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  FileSearch,
  LoaderCircle,
  ScanLine,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { AgentTest, Project, Scan } from "@/lib/types";
import { Button } from "./ui/button";
import {
  DomainIcon,
  formatDate,
  Metric,
  PageHeading,
  SectionHeader,
  Status,
  TextLink,
  domainOf,
} from "./product-ui";
import { AgentHistory } from "./agent-testing";
import { ScoreHistory } from "./static-report";
import { EmptyState, ErrorState, InlineError, LoadingState } from "./states";
type Data = { project: Project; scans: Scan[]; tests: AgentTest[] };
const active = (d: Data) =>
  [...d.scans, ...d.tests].some(
    (s) => s.status === "RUNNING" || s.status === "PENDING",
  );
export function ProjectDetail({ id }: { id: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");
  const load = useCallback(async () => {
    const [project, allScans] = await Promise.all([
      api.project(id),
      api.scans(),
    ]);
    const scans = allScans
      .filter((s) => s.project_id === id)
      .sort((a, b) =>
        (b.started_at ?? "9999").localeCompare(a.started_at ?? "9999"),
      );
    return { project, scans, tests: await api.agentTestsForScans(scans) };
  }, [id]);
  const { data, error, retry } = useResource(load, active);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const { project, scans, tests } = data;
  const latest = scans[0];
  return (
    <div className="fade-in">
      <PageHeading
        back={{ href: "/projects", label: "All projects" }}
        eyebrow="Project workspace"
        title={project.name}
        description={project.website_url}
        action={
          <Button
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setActionError("");
              try {
                const scan = await api.createScan(id);
                router.push(`/scans/${scan.id}`);
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
              <LoaderCircle size={14} className="animate-spin" />
            ) : (
              <ScanLine size={14} />
            )}
            Start Scan
          </Button>
        }
      />
      {actionError && (
        <div className="mb-5">
          <InlineError>{actionError}</InlineError>
        </div>
      )}
      <div className="surface mb-6 flex flex-wrap items-center justify-between gap-5 p-5">
        <div className="flex min-w-0 items-center gap-4">
          <DomainIcon className="size-12" />
          <div className="min-w-0">
            <p className="truncate text-sm font-medium">
              {domainOf(project.website_url)}
            </p>
            <p className="mt-1.5 text-[11px] text-muted-foreground">
              Added {formatDate(project.created_at)} · Exact-host crawl scope
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-[10px] text-muted-foreground">Latest scan</span>
          {latest ? (
            <Status value={latest.status} />
          ) : (
            <span className="text-xs text-muted-foreground">Not scanned</span>
          )}
        </div>
      </div>
      <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric icon={ScanLine} label="Total scans" value={scans.length} />
        <Metric
          icon={FileSearch}
          label="Pages crawled"
          value={latest?.pages_crawled ?? 0}
          detail="In the latest scan"
        />
        <Metric
          icon={CheckCircle2}
          label="Completed scans"
          value={scans.filter((s) => s.status === "COMPLETED").length}
        />
        <Metric icon={Bot} label="Agent executions" value={tests.length} />
      </div>
      <ScoreHistory scans={scans} />
      <section className="surface overflow-hidden">
        <SectionHeader
          title="Scan history"
          count={scans.length}
          description="Open a scan to inspect page discovery and run browser-agent tests."
        />
        {scans.length === 0 ? (
          <EmptyState
            title="Your website is ready to explore"
            description="Start your first scan to discover pages and prepare an agent test."
            action={
              <Button
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  try {
                    const scan = await api.createScan(id);
                    router.push(`/scans/${scan.id}`);
                  } catch (e) {
                    setActionError(
                      e instanceof Error ? e.message : "Could not start scan",
                    );
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Start Scan
                <ArrowRight size={13} />
              </Button>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[580px]">
              <thead className="table-head">
                <tr>
                  <th>Scan ID</th>
                  <th>Started</th>
                  <th>Status</th>
                  <th>Pages crawled</th>
                  <th>Errors</th>
                  <th>Static score</th>
                  <th>
                    <span className="sr-only">Open scan</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {scans.map((scan) => (
                  <tr key={scan.id} className="table-row">
                    <td className="mono text-[11px]">
                      <Link
                        className="hover:text-primary"
                        href={`/scans/${scan.id}`}
                      >
                        {scan.id.slice(0, 8)}
                      </Link>
                    </td>
                    <td className="text-[11px] text-muted-foreground">
                      {formatDate(scan.started_at)}
                    </td>
                    <td>
                      <Status value={scan.status} />
                    </td>
                    <td>{scan.pages_crawled}</td>
                    <td
                      className={
                        scan.pages_failed
                          ? "text-danger"
                          : "text-muted-foreground"
                      }
                    >
                      {scan.pages_failed}
                    </td>
                    <td>
                      {scan.audit_summary?.version ? (
                        <Link
                          href={`/scans/${scan.id}/report`}
                          className="font-medium text-primary"
                        >
                          {scan.overall_score ?? "—"}
                          <small className="ml-1 text-[9px] text-muted-foreground">
                            /100
                          </small>
                        </Link>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          Not audited
                        </span>
                      )}
                    </td>
                    <td>
                      <TextLink href={`/scans/${scan.id}`}>
                        View results
                      </TextLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="surface mt-7 overflow-hidden">
        <SectionHeader
          title="Agent executions"
          count={tests.length}
          description="Model-selected browser actions and the evidence they leave behind."
        />
        {tests.length ? (
          <AgentHistory tests={tests} />
        ) : (
          <EmptyState
            title="No agent journeys yet"
            description="Once a scan exists, give an agent a task and follow its execution."
            action={
              latest ? (
                <Button asChild variant="outline">
                  <Link href={`/scans/${latest.id}?tab=agents`}>
                    Run an agent test
                    <Bot size={13} />
                  </Link>
                </Button>
              ) : undefined
            }
          />
        )}
      </section>
    </div>
  );
}
