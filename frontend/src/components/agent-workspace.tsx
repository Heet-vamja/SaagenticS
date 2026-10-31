"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  Clock3,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { AgentTest, Project, Scan } from "@/lib/types";
import { AgentHistory, AgentTesting } from "./agent-testing";
import { Button } from "./ui/button";
import { Metric, PageHeading, SectionHeader } from "./product-ui";
import { EmptyState, ErrorState, LoadingState } from "./states";
type Data = { projects: Project[]; scans: Scan[]; tests: AgentTest[] };
const active = (d: Data) =>
  d.tests.some((t) => t.status === "PENDING" || t.status === "RUNNING");
export function AgentWorkspace() {
  const [filter, setFilter] = useState("all");
  const [create, setCreate] = useState(false);
  const [selectedScan, setSelectedScan] = useState("");
  const load = useCallback(async () => {
    const [projects, scans] = await Promise.all([api.projects(), api.scans()]);
    return { projects, scans, tests: await api.agentTestsForScans(scans) };
  }, []);
  const { data, error, retry } = useResource(load, active);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const { projects, scans, tests } = data;
  const filtered = tests.filter((t) => filter === "all" || t.status === filter);
  return (
    <div className="fade-in">
      <PageHeading
        eyebrow="Observe. Decide. Act."
        title="Real agents. Every step, visible."
        description="Give a browser agent a real task, then inspect the decisions, observations, and evidence behind its outcome."
        action={
          <Button onClick={() => setCreate((v) => !v)}>
            <Bot size={14} />
            {create ? "Close task picker" : "Run agent test"}
          </Button>
        }
      />
      <div className="mb-7 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Metric icon={Bot} label="Executions" value={tests.length} />
        <Metric
          icon={Clock3}
          label="Active runs"
          value={
            tests.filter((t) => ["PENDING", "RUNNING"].includes(t.status))
              .length
          }
        />
        <Metric
          icon={CheckCircle2}
          label="Agent-completed"
          value={tests.filter((t) => t.status === "COMPLETED").length}
          detail="Not independently verified"
        />
        <Metric
          icon={ShieldCheck}
          label="Read-only workflows"
          value="3"
          detail="Pricing · documentation · forms"
        />
      </div>
      {create && (
        <div className="mb-7 space-y-4">
          <div className="surface p-5">
            <label className="text-xs font-medium" htmlFor="test-scan">
              Choose a scan
            </label>
            <p className="mb-3 mt-1 text-[11px] text-muted-foreground">
              Your agent starts at the website associated with this scan.
            </p>
            <select
              id="test-scan"
              className="field max-w-lg"
              value={selectedScan}
              onChange={(e) => setSelectedScan(e.target.value)}
            >
              <option value="">Select a website scan…</option>
              {scans.map((scan) => (
                <option key={scan.id} value={scan.id}>
                  {projects.find((p) => p.id === scan.project_id)?.name ??
                    "Website"}{" "}
                  · {scan.id.slice(0, 8)} · {scan.status.toLowerCase()}
                </option>
              ))}
            </select>
            {!scans.length && (
              <Link
                href="/projects"
                className="mt-3 inline-flex items-center gap-2 text-xs text-primary"
              >
                Create a project and scan first
                <ArrowRight size={13} />
              </Link>
            )}
          </div>
          {selectedScan && <AgentTesting scanId={selectedScan} />}
        </div>
      )}
      <section className="surface overflow-hidden">
        <SectionHeader
          title="Execution history"
          count={tests.length}
          description="All outcomes are agent-reported. Independent evaluation is not yet enabled."
          action={
            <select
              aria-label="Filter executions by status"
              className="rounded-lg border bg-background px-3 py-2 text-[10px] text-muted-foreground"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            >
              <option value="all">All statuses</option>
              <option value="RUNNING">Running</option>
              <option value="PENDING">Pending</option>
              <option value="COMPLETED">Agent-completed</option>
              <option value="FAILED">Failed</option>
            </select>
          }
        />
        {filtered.length ? (
          <AgentHistory tests={filtered} />
        ) : (
          <EmptyState
            title={
              filter === "all"
                ? "Meet your website’s next visitor"
                : "No executions match this status"
            }
            description={
              filter === "all"
                ? "Choose a scan and a task. The model will find its own way through your website while you follow the trace."
                : "Choose another status to explore your execution history."
            }
            action={
              <Button
                variant="outline"
                onClick={() =>
                  filter === "all" ? setCreate(true) : setFilter("all")
                }
              >
                {filter === "all" ? "Choose a task" : "Show all executions"}
                <ArrowRight size={13} />
              </Button>
            }
          />
        )}
      </section>
    </div>
  );
}
