"use client";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  ArrowRight,
  Bot,
  CheckCircle2,
  ChevronRight,
  FolderKanban,
  Globe2,
  ScanLine,
  Search,
  Waypoints,
} from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { AgentTest, Project, Scan } from "@/lib/types";
import { Button } from "./ui/button";
import { ProjectDialog } from "./project-dialog";
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
import { EmptyState, ErrorState, LoadingState } from "./states";
export { ProjectDialog } from "./project-dialog";
export { Status } from "./product-ui";
type WorkspaceData = { projects: Project[]; scans: Scan[]; tests: AgentTest[] };
const active = (data: WorkspaceData) =>
  [...data.scans, ...data.tests].some(
    (r) => r.status === "PENDING" || r.status === "RUNNING",
  );
export function Workspace({
  view = "overview",
}: {
  view?: "overview" | "projects" | "scans";
}) {
  const [search, setSearch] = useState("");
  const load = useCallback(async () => {
    const [projects, scans] = await Promise.all([api.projects(), api.scans()]);
    const tests = await api.agentTestsForScans(scans);
    return { projects, scans, tests };
  }, []);
  const { data, error, retry } = useResource(load, active);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const { projects, scans, tests } = data;
  const latest = [...scans].sort((a, b) =>
    (b.started_at ?? "9999").localeCompare(a.started_at ?? "9999"),
  );
  const filtered = projects.filter((p) =>
    `${p.name} ${p.website_url}`.toLowerCase().includes(search.toLowerCase()),
  );
  return (
    <div className="fade-in">
      <PageHeading
        eyebrow="Your workspace"
        title={
          view === "overview"
            ? "See your website through an agent’s eyes."
            : view === "projects"
              ? "Your projects"
              : "Scan history"
        }
        description={
          view === "overview"
            ? "Understand what agents can discover—and what happens when they try to use it."
            : view === "projects"
              ? "Your websites, their scans, and every agent journey in one place."
              : "Follow discovery progress and open the evidence behind every crawl."
        }
        action={<ProjectDialog onCreated={() => retry()} />}
      />
      {view === "overview" && (
        <>
          <section className="workspace-welcome relative mb-6 flex flex-wrap items-center justify-between gap-5 overflow-hidden rounded-xl border border-primary/15 bg-accent-soft px-6 py-6">
            <div className="flex items-start gap-4">
              <span className="hidden size-11 shrink-0 place-items-center rounded-xl border border-primary/15 bg-card/70 text-primary sm:grid">
                <Waypoints size={23} strokeWidth={1.5} />
              </span>
              <div>
                <h2 className="text-sm font-semibold tracking-tight">
                  Your website has a new kind of visitor.
                </h2>
                <p className="mt-2 max-w-xl text-xs leading-6 text-muted-foreground">
                  Give an AI agent a task. Watch its decisions. See exactly
                  where it gets stuck.
                </p>
              </div>
            </div>
            <Button variant="outline" asChild className="bg-card">
              <Link href="/agent-tests">
                Explore agent tests
                <ArrowRight size={13} />
              </Link>
            </Button>
          </section>
          <div className="mb-8 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Metric
              label="Total projects"
              value={projects.length}
              icon={FolderKanban}
              detail="Websites in your workspace"
            />
            <Metric
              label="Total scans"
              value={scans.length}
              icon={ScanLine}
              detail="Discovery runs created"
            />
            <Metric
              label="Completed scans"
              value={scans.filter((s) => s.status === "COMPLETED").length}
              icon={CheckCircle2}
              detail="Crawls that reached completion"
            />
            <Metric
              label="Agent tests executed"
              value={tests.filter((t) => t.status !== "PENDING").length}
              icon={Bot}
              detail="Real execution records, no demo data"
            />
          </div>
        </>
      )}
      {view !== "scans" && (
        <section className="surface overflow-hidden">
          <SectionHeader
            title={view === "overview" ? "Recent projects" : "All projects"}
            count={projects.length}
            action={
              view === "overview" ? (
                <TextLink href="/projects">View all projects</TextLink>
              ) : (
                <label className="flex items-center gap-2 rounded-lg border bg-background px-3 py-2 text-muted-foreground">
                  <Search size={13} />
                  <input
                    aria-label="Search projects"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search projects…"
                    className="w-36 bg-transparent text-[11px] outline-none"
                  />
                </label>
              )
            }
          />
          {filtered.length === 0 ? (
            <EmptyState
              title={
                search
                  ? "No matching projects"
                  : "Start with your first website"
              }
              description={
                search
                  ? "Try searching by project name or domain."
                  : "Create a project to discover its pages and test real agent journeys."
              }
              action={
                search ? (
                  <Button variant="outline" onClick={() => setSearch("")}>
                    Clear search
                  </Button>
                ) : (
                  <ProjectDialog onCreated={() => retry()} />
                )
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[540px]">
                <thead className="table-head">
                  <tr>
                    <th>Project</th>
                    <th>Latest scan</th>
                    <th>Pages crawled</th>
                    <th>Agent tests</th>
                    <th>
                      <span className="sr-only">Open</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(view === "overview" ? filtered.slice(0, 4) : filtered).map(
                    (project) => {
                      const scan = latest.find(
                        (s) => s.project_id === project.id,
                      );
                      const projectScanIds = new Set(
                        scans
                          .filter((s) => s.project_id === project.id)
                          .map((s) => s.id),
                      );
                      return (
                        <tr key={project.id} className="table-row">
                          <td>
                            <Link
                              href={`/projects/${project.id}`}
                              className="group inline-flex items-center gap-3"
                            >
                              <DomainIcon className="size-9 rounded-lg" />
                              <span>
                                <span className="block text-xs font-medium group-hover:text-primary">
                                  {project.name}
                                </span>
                                <span className="mono mt-1 block text-[10px] text-muted-foreground">
                                  {domainOf(project.website_url)}
                                </span>
                              </span>
                            </Link>
                          </td>
                          <td>
                            {scan ? (
                              <Status value={scan.status} />
                            ) : (
                              <span className="text-[11px] text-muted-foreground">
                                Not scanned yet
                              </span>
                            )}
                          </td>
                          <td className="tabular-nums">
                            {scan?.pages_crawled ?? "—"}
                          </td>
                          <td className="tabular-nums">
                            {
                              tests.filter((t) => projectScanIds.has(t.scan_id))
                                .length
                            }
                          </td>
                          <td>
                            <Link
                              href={`/projects/${project.id}`}
                              aria-label={`Open ${project.name}`}
                              className="grid size-8 place-items-center rounded-lg text-muted-foreground hover:bg-muted"
                            >
                              <ChevronRight size={15} />
                            </Link>
                          </td>
                        </tr>
                      );
                    },
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      {view !== "projects" && (
        <section
          className={`surface overflow-hidden ${view === "overview" ? "mt-7" : ""}`}
        >
          <SectionHeader
            title={view === "overview" ? "Recent scan activity" : "All scans"}
            count={scans.length}
            action={
              view === "overview" ? (
                <TextLink href="/scans">View scan history</TextLink>
              ) : undefined
            }
          />
          {scans.length === 0 ? (
            <EmptyState
              title="No scans yet"
              description="Open a project and start a scan to discover its pages and inspect crawl results."
              action={
                <Button asChild variant="outline">
                  <Link href="/projects">
                    Go to projects
                    <ArrowRight size={13} />
                  </Link>
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="data-table min-w-[580px]">
                <thead className="table-head">
                  <tr>
                    <th>Website / Scan</th>
                    <th>Status</th>
                    <th>Pages</th>
                    <th>Started</th>
                    <th>
                      <span className="sr-only">Results</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {(view === "overview" ? latest.slice(0, 5) : latest).map(
                    (scan) => (
                      <tr key={scan.id} className="table-row">
                        <td>
                          <Link
                            className="font-medium hover:text-primary"
                            href={`/scans/${scan.id}`}
                          >
                            {projects.find((p) => p.id === scan.project_id)
                              ?.name ?? "Website scan"}
                          </Link>
                          <p className="mono mt-1 text-[9px] text-muted-foreground">
                            {scan.id.slice(0, 8)}
                          </p>
                        </td>
                        <td>
                          <Status value={scan.status} />
                        </td>
                        <td>
                          {scan.pages_crawled}
                          <span className="text-muted-foreground">
                            {" "}
                            / {scan.pages_discovered}
                          </span>
                        </td>
                        <td className="text-[11px] text-muted-foreground">
                          {formatDate(scan.started_at)}
                        </td>
                        <td>
                          <TextLink href={`/scans/${scan.id}`}>
                            View results
                          </TextLink>
                        </td>
                      </tr>
                    ),
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 text-[10px] text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <Globe2 size={12} />
          Your data, from actual crawl and execution records.
        </span>
        <TextLink href="/docs">How to read your results</TextLink>
      </div>
    </div>
  );
}
