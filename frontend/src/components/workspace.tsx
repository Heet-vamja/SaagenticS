"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Check,
  ChevronRight,
  Circle,
  Globe2,
  Layers3,
  Plus,
  ScanLine,
  Search,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { api } from "@/lib/api";
import type { Project, Scan } from "@/lib/types";
import { Button } from "./ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "./ui/dialog";
import { EmptyState, ErrorState, LoadingState } from "./states";

export function ProjectDialog({
  onCreated,
}: {
  onCreated: (project: Project) => void;
}) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button onClick={() => setError("")}>
          <Plus size={16} />
          New project
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle className="text-xl font-semibold tracking-tight">
          A new perspective on your website.
        </DialogTitle>
        <DialogDescription className="mb-6 mt-2 text-sm leading-6 text-muted-foreground">
          Add a website to your workspace. You can create a scan record once
          your project is saved.
        </DialogDescription>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = new FormData(e.currentTarget);
            setBusy(true);
            setError("");
            try {
              const project = await api.createProject(
                String(form.get("name")),
                String(form.get("url")),
              );
              onCreated(project);
              setOpen(false);
            } catch (e) {
              setError(
                e instanceof Error ? e.message : "Could not create project",
              );
            } finally {
              setBusy(false);
            }
          }}
          className="space-y-4"
        >
          <label className="block text-sm font-medium">
            Project name
            <input
              name="name"
              placeholder="My website"
              maxLength={200}
              required
              className="field mt-2"
            />
          </label>
          <label className="block text-sm font-medium">
            Website URL
            <input
              name="url"
              type="url"
              placeholder="https://example.com"
              maxLength={2048}
              required
              className="field mt-2"
            />
          </label>
          {error && (
            <p role="alert" className="text-sm text-red-700">
              {error}
            </p>
          )}
          <Button className="w-full" disabled={busy} type="submit">
            {busy ? "Creating…" : "Create project"}
            <ArrowRight size={16} />
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            Adding a project does not crawl your website.
          </p>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function Status({ value }: { value: Scan["status"] }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-md border bg-background px-2 py-1 text-[11px] font-medium">
      <span
        className={`size-1.5 rounded-full ${value === "COMPLETED" ? "bg-green-600" : value === "FAILED" ? "bg-red-500" : "bg-amber-500"}`}
      />
      {value.toLowerCase()}
    </span>
  );
}

export function Workspace({
  view = "overview",
}: {
  view?: "overview" | "projects" | "scans";
}) {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [scans, setScans] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    Promise.all([api.projects(), api.scans()])
      .then(([p, s]) => {
        if (active) {
          setProjects(p);
          setScans(s);
          setError("");
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [attempt]);
  const filtered = projects.filter((p) =>
    `${p.name} ${p.website_url}`.toLowerCase().includes(search.toLowerCase()),
  );
  const completed = scans.filter((s) => s.status === "COMPLETED");
  const title =
    view === "overview"
      ? "Your agent-ready journey starts here."
      : view === "projects"
        ? "A home for every website."
        : "Every scan. One clear view.";
  const create = (
    <ProjectDialog
      onCreated={(p) => setProjects((previous) => [p, ...previous])}
    />
  );
  return (
    <>
      <div className="mb-8 flex flex-wrap items-start justify-between gap-5">
        <div>
          <div className="mb-2.5 text-[10px] font-semibold uppercase tracking-[.2em] text-primary">
            {view === "overview"
              ? "See your website differently"
              : "Your workspace"}
          </div>
          <h1 className="text-[28px] font-semibold leading-tight tracking-[-.04em] sm:text-[32px]">
            {title}
          </h1>
          <p className="mt-3 text-sm text-muted-foreground">
            {view === "scans"
              ? "Track scan records and explore findings as your auditing engine takes shape."
              : "Understand how AI agents discover, navigate, and interact with your website."}
          </p>
        </div>
        {create}
      </div>
      {view === "overview" && (
        <section className="relative mb-7 overflow-hidden rounded-2xl border border-[#dce2d3] bg-[#edf1e6] p-7 sm:p-8">
          <div className="relative z-10 max-w-lg">
            <span className="mb-5 inline-flex items-center gap-1.5 rounded-full border border-[#cfdac3] px-2.5 py-1 text-[10px] font-medium text-[#536847]">
              <Sparkles size={12} />A new kind of website readiness
            </span>
            <h2 className="max-w-sm text-[27px] font-medium leading-[1.2] tracking-[-.04em]">
              The next visitor to your
              <br />
              website might be an agent.
            </h2>
            <p className="mb-6 mt-4 max-w-sm text-sm leading-6 text-[#67715f]">
              Make space for the next wave of the web. Start with a project,
              then build a clearer picture with every scan.
            </p>
            <Button
              asChild
              variant="outline"
              className="border-[#cfdac3] bg-white/60"
            >
              <Link href="/projects">
                Explore your projects
                <ArrowUpRight size={15} />
              </Link>
            </Button>
          </div>
          <div
            aria-hidden="true"
            className="absolute -right-10 top-8 hidden h-64 w-96 sm:block"
          >
            <div className="orbit orbit-one" />
            <div className="orbit orbit-two" />
            <div className="orbit orbit-three" />
            <div className="absolute left-40 top-20 grid size-20 rotate-[-12deg] place-items-center rounded-2xl border border-[#b6c4a5] bg-[#e1e8d5] shadow-[0_14px_30px_#53684718]">
              <ScanLine size={40} strokeWidth={1} className="text-[#687f50]" />
            </div>
            <span className="absolute left-16 top-5 size-3 rounded-full bg-[#b6c79f]" />
            <span className="absolute right-16 top-44 size-4 rounded-full border-4 border-[#d1ddbf] bg-[#849b6e]" />
          </div>
        </section>
      )}
      {loading ? (
        <LoadingState />
      ) : error ? (
        <ErrorState
          message={error}
          retry={() => {
            setLoading(true);
            setAttempt((n) => n + 1);
          }}
        />
      ) : (
        <>
          {view === "overview" && (
            <div className="mb-9 grid gap-4 sm:grid-cols-3">
              {[
                {
                  label: "Total projects",
                  value: projects.length,
                  sub: "Websites in your workspace",
                  icon: Boxes,
                },
                {
                  label: "Scan records",
                  value: scans.length,
                  sub: "A record of your readiness journey",
                  icon: ScanLine,
                },
                {
                  label: "Completed scans",
                  value: completed.length,
                  sub: "Ready for review when available",
                  icon: ShieldCheck,
                },
              ].map(({ label, value, sub, icon: Icon }) => (
                <div key={label} className="rounded-xl border bg-card p-5">
                  <div className="flex items-center justify-between text-xs text-muted-foreground">
                    {label}
                    <Icon size={17} strokeWidth={1.5} />
                  </div>
                  <div className="my-3 text-3xl font-medium tracking-tight">
                    {value}
                  </div>
                  <p className="text-[11px] text-muted-foreground">{sub}</p>
                </div>
              ))}
            </div>
          )}
          <section className="overflow-hidden rounded-xl border bg-card">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b px-5 py-4">
              <div className="flex items-center gap-2.5">
                <h2 className="text-sm font-semibold">
                  {view === "scans" ? "Scan history" : "Your projects"}
                </h2>
                <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] text-muted-foreground">
                  {view === "scans" ? scans.length : projects.length}
                </span>
              </div>
              {view !== "scans" && (
                <label className="flex items-center gap-2 text-muted-foreground">
                  <Search size={14} />
                  <input
                    aria-label="Search projects"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search projects…"
                    className="w-36 bg-transparent text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  />
                </label>
              )}
            </div>
            {view === "scans" ? (
              scans.length === 0 ? (
                <EmptyState
                  title="A fresh start for your scan history."
                  description="Create a project, then add your first scan record. Website crawling and testing will arrive in a future release."
                  action={
                    <Button asChild variant="outline">
                      <Link href="/projects">
                        View projects
                        <ArrowRight size={15} />
                      </Link>
                    </Button>
                  }
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="table-head">
                      <tr>
                        <th>Project</th>
                        <th>Status</th>
                        <th>Score</th>
                        <th>
                          <span className="sr-only">Details</span>
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {scans.map((s) => (
                        <tr key={s.id} className="table-row">
                          <td>
                            {projects.find((p) => p.id === s.project_id)
                              ?.name ?? s.project_id}
                          </td>
                          <td>
                            <Status value={s.status} />
                          </td>
                          <td>{s.overall_score ?? "—"}</td>
                          <td>
                            <Link
                              aria-label={`View scan ${s.id}`}
                              href={`/scans/${s.id}`}
                              className="inline-flex items-center gap-1 text-xs text-primary"
                            >
                              View scan
                              <ChevronRight size={14} />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )
            ) : filtered.length === 0 ? (
              <EmptyState
                title={
                  search
                    ? "No matching projects."
                    : "Your first project is a possibility."
                }
                description={
                  search
                    ? "Try another name or website address."
                    : "Add a website to give your readiness journey a home. Everything starts with a URL."
                }
                action={
                  search ? (
                    <Button variant="outline" onClick={() => setSearch("")}>
                      Clear search
                    </Button>
                  ) : (
                    create
                  )
                }
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="table-head">
                    <tr>
                      <th>Project</th>
                      <th>Website</th>
                      <th>Scans</th>
                      <th>
                        <span className="sr-only">Actions</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filtered.map((p) => (
                      <tr key={p.id} className="table-row">
                        <td>
                          <span className="flex items-center gap-3">
                            <span className="grid size-8 shrink-0 place-items-center rounded-lg border bg-background text-muted-foreground">
                              <Globe2 size={16} />
                            </span>
                            <span className="font-medium">{p.name}</span>
                          </span>
                        </td>
                        <td>
                          <a
                            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-primary"
                            href={p.website_url}
                            target="_blank"
                            rel="noopener noreferrer"
                          >
                            {new URL(p.website_url).hostname}
                            <ArrowUpRight size={12} />
                          </a>
                        </td>
                        <td>
                          {scans.filter((s) => s.project_id === p.id).length}
                        </td>
                        <td className="text-right">
                          <Button
                            variant="outline"
                            disabled={busy !== null}
                            onClick={async () => {
                              setBusy(p.id);
                              try {
                                const s = await api.createScan(p.id);
                                setScans((prev) => [...prev, s]);
                                router.push(`/scans/${s.id}`);
                              } catch (e) {
                                setError(
                                  e instanceof Error
                                    ? e.message
                                    : "Could not create scan",
                                );
                              } finally {
                                setBusy(null);
                              }
                            }}
                          >
                            <Plus size={14} />
                            {busy === p.id ? "Creating…" : "Create scan"}
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      )}
      {view === "overview" && (
        <section className="mt-9">
          <div className="mb-4 flex items-center gap-2">
            <Layers3 size={16} className="text-muted-foreground" />
            <h2 className="text-sm font-semibold">
              A foundation for agent readiness
            </h2>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {[
              {
                title: "01 / Connect your website",
                text: "Create a project with your website URL. Keep your websites organized in one workspace.",
                ready: true,
              },
              {
                title: "02 / Understand the experience",
                text: "Future audits will examine five dimensions, from discovery to reliable interaction.",
                ready: false,
              },
              {
                title: "03 / Turn insight into action",
                text: "Evidence-based findings and recommendations will help you decide what to improve.",
                ready: false,
              },
            ].map((x) => (
              <div
                key={x.title}
                className="rounded-xl border border-dashed p-5"
              >
                <p className="mb-2 text-xs font-medium">{x.title}</p>
                <p className="text-xs leading-5 text-muted-foreground">
                  {x.text}
                </p>
                <span className="mt-4 inline-flex items-center gap-1.5 text-[10px] text-muted-foreground">
                  {x.ready ? <Check size={12} /> : <Circle size={10} />}
                  {x.ready ? "Available now" : "Coming next"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
      <footer className="mt-9 flex flex-wrap items-center justify-between gap-2 border-t pt-5 text-[10px] text-muted-foreground">
        <span>
          AgentReadiness · A thoughtful foundation for an agentic web.
        </span>
        <span>
          Auditing, workflow testing, and scoring are not enabled yet.
        </span>
      </footer>
    </>
  );
}
