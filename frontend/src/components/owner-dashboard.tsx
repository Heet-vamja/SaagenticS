"use client";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import {
  Bot,
  Check,
  Clock,
  Footprints,
  KeyRound,
  LoaderCircle,
  LogOut,
  Minus,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  X,
} from "lucide-react";
import { api, ApiError } from "@/lib/api";
import type {
  DashboardOverview,
  DashboardSite,
  DashboardVariant,
  QATargetSummary,
  SiteJob,
  SiteJobKind,
} from "@/lib/types";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import {
  AddSiteForm,
  isActive,
  JobButton,
  JobStatus,
  LanePanel,
} from "./owner-dashboard-lane";
import styles from "./owner-dashboard.module.css";

const TOKEN_KEY = "al-dashboard-token";
const WINDOWS = [7, 30, 90];
// Brand marks for known agent families; anything else falls back to an icon.
const AGENT_LOGOS: { match: string; logo: string; color: string }[] = [
  { match: "chatgpt", logo: "/agent-logos/chatgpt.svg", color: "#10a37f" },
  { match: "claude", logo: "/agent-logos/claude.svg", color: "#d97757" },
  {
    match: "perplexity",
    logo: "/agent-logos/perplexity.svg",
    color: "#20808d",
  },
];

type Outcome = "PASSED" | "FAILED" | "ERROR" | undefined;

function readToken() {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function plural(n: number, word: string) {
  return `${n.toLocaleString()} ${word}${n === 1 ? "" : "s"}`;
}

function rate(summary: QATargetSummary) {
  return summary.eligible
    ? Math.round((summary.passed / summary.eligible) * 100)
    : null;
}

function Ring({ value, label }: { value: number | null; label: string }) {
  const pct = value === null ? 0 : Math.max(0, Math.min(100, value));
  return (
    <div
      className={styles.ring}
      role="img"
      aria-label={value === null ? `${label}: no data` : `${pct}% ${label}`}
    >
      <svg viewBox="0 0 136 136" aria-hidden="true">
        <circle
          cx="68"
          cy="68"
          r="58"
          fill="none"
          stroke="var(--muted)"
          strokeWidth="12"
        />
        {pct > 0 && (
          <circle
            cx="68"
            cy="68"
            r="58"
            fill="none"
            stroke="var(--signal)"
            strokeWidth="12"
            strokeLinecap="round"
            pathLength="100"
            strokeDasharray="100"
            strokeDashoffset={100 - pct}
            transform="rotate(-90 68 68)"
          />
        )}
      </svg>
      <span aria-hidden="true">
        <strong>{value === null ? "—" : `${pct}%`}</strong>
        <small>{label}</small>
      </span>
    </div>
  );
}

function AgentMark({ agent, kind }: { agent: string; kind: string }) {
  const brand = AGENT_LOGOS.find((item) =>
    agent.toLowerCase().includes(item.match),
  );
  return (
    <span className={styles.logo} aria-hidden="true">
      {brand ? (
        <span
          style={{
            background: brand.color,
            maskImage: `url(${brand.logo})`,
            WebkitMaskImage: `url(${brand.logo})`,
          }}
        />
      ) : kind === "agent" ? (
        <Bot size={17} />
      ) : (
        <Search size={17} />
      )}
    </span>
  );
}

function OutcomeMark({ value }: { value: Outcome }) {
  const text =
    value === "PASSED"
      ? "Passed"
      : value === "FAILED"
        ? "Failed"
        : value === "ERROR"
          ? "Error, excluded"
          : "Not run";
  return (
    <span className={styles.outcome} data-v={value} title={text}>
      {value === "PASSED" ? (
        <Check size={12} strokeWidth={3} aria-hidden="true" />
      ) : value === "FAILED" ? (
        <X size={12} strokeWidth={3} aria-hidden="true" />
      ) : (
        <Minus size={12} strokeWidth={3} aria-hidden="true" />
      )}
      <span className="sr-only">{text}</span>
    </span>
  );
}

function QASide({
  lane,
  label,
  host,
  summary,
  tasks,
}: {
  lane?: boolean;
  label: string;
  host: string;
  summary: QATargetSummary;
  tasks: { key: string; prompt: string; outcome: Outcome; steps?: number }[];
}) {
  const avgSeconds = summary.eligible
    ? summary.duration_ms / summary.eligible / 1000
    : null;
  const avgSteps = summary.eligible ? summary.steps / summary.eligible : null;
  const pct = rate(summary);
  return (
    <section
      className={`${styles.card} ${styles.side} ${lane ? styles.lane : ""}`}
      aria-label={label}
    >
      <div className={styles.sideTop}>
        <div className="min-w-0">
          <p className={styles.sideLabel}>{label}</p>
          <p className={styles.sideHost}>{host}</p>
        </div>
        {avgSeconds !== null && avgSteps !== null && (
          <div className={styles.pills}>
            <span className={styles.pill}>
              <Clock size={12} aria-hidden="true" />
              {avgSeconds.toFixed(1)}s avg
            </span>
            <span className={styles.pill}>
              <Footprints size={12} aria-hidden="true" />
              {avgSteps.toFixed(1)} steps avg
            </span>
          </div>
        )}
      </div>
      <p className={styles.score}>
        <strong>
          {summary.passed}/{summary.eligible}
        </strong>
        <span>
          {pct === null ? "no eligible runs" : `tasks passed · ${pct}%`}
        </span>
      </p>
      <ul className={styles.steps}>
        {tasks.map((task) => (
          <li key={task.key}>
            <OutcomeMark value={task.outcome} />
            <span>{task.prompt}</span>
            <code>
              {task.outcome && task.outcome !== "ERROR" && task.steps
                ? plural(task.steps, "step")
                : ""}
            </code>
          </li>
        ))}
      </ul>
    </section>
  );
}

function GhostSide({ lane, label }: { lane?: boolean; label: string }) {
  return (
    <div className={`${styles.card} ${styles.side} ${lane ? styles.lane : ""}`}>
      <p className={styles.sideLabel}>{label}</p>
      <div className={styles.ghost} aria-hidden="true">
        <p className={styles.score}>
          <strong>–/10</strong>
        </p>
        <ul className={styles.steps}>
          {[72, 58, 80, 46, 64].map((width) => (
            <li key={width}>
              <OutcomeMark value={undefined} />
              <span className={styles.skel} style={{ width: `${width}%` }} />
              <code />
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

const noSubscription = () => () => {};

export function OwnerDashboard() {
  // Hydration-safe read of the saved token; `override` holds sign-in/sign-out changes.
  const stored = useSyncExternalStore(noSubscription, readToken, () => "");
  const [override, setToken] = useState<string | null>(null);
  const token = override ?? stored;
  const [draft, setDraft] = useState("");
  const [sites, setSites] = useState<DashboardSite[]>([]);
  const [host, setHost] = useState("");
  const [days, setDays] = useState(7);
  const [data, setData] = useState<DashboardOverview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [sitesLoaded, setSitesLoaded] = useState(false);
  const [adding, setAdding] = useState(false);
  const [jobs, setJobs] = useState<SiteJob[]>([]);
  const [variants, setVariants] = useState<DashboardVariant[]>([]);
  const wasActive = useRef(false);

  const fail = useCallback((e: unknown) => {
    if (e instanceof ApiError && e.status === 401) {
      try {
        sessionStorage.removeItem(TOKEN_KEY);
      } catch {}
      setToken("");
    }
    setError(e instanceof Error ? e.message : "Something went wrong.");
  }, []);

  useEffect(() => {
    if (!token) return;
    api
      .dashboardSites(token)
      .then(({ sites }) => {
        setSites(sites);
        setSitesLoaded(true);
        setHost((current) => current || sites[0]?.host || "");
      })
      .catch(fail);
  }, [token, fail]);

  const load = useCallback(
    () =>
      token && host
        ? api
            .dashboardOverview(token, host, days)
            .then((overview) => {
              setData(overview);
              setError("");
            })
            .catch(fail)
        : Promise.resolve(),
    [token, host, days, fail],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const loadLane = useCallback(
    () =>
      token && host
        ? Promise.all([
            api.siteJobs(token, host),
            api.siteVariants(token, host),
          ])
            .then(([jobList, variantList]) => {
              const active = jobList.jobs.some(isActive);
              // A job just finished: its results (variant, labels, QA) change the overview.
              if (wasActive.current && !active) void load();
              wasActive.current = active;
              setJobs(jobList.jobs);
              setVariants(variantList.variants);
            })
            .catch(fail)
        : Promise.resolve(),
    [token, host, load, fail],
  );

  useEffect(() => {
    void loadLane();
  }, [loadLane]);

  const anyActive = jobs.some(isActive);
  useEffect(() => {
    if (!anyActive) return;
    const timer = setInterval(() => void loadLane(), 4000);
    return () => clearInterval(timer);
  }, [anyActive, loadLane]);

  const latest = (kind: SiteJobKind) => jobs.find((job) => job.kind === kind);
  const start = (kind: SiteJobKind) =>
    api
      .startJob(token, host, kind)
      .then((job) => {
        wasActive.current = true;
        setJobs((current) => [job, ...current]);
        setError("");
      })
      .catch(fail);

  if (!token) {
    return (
      <div className={styles.gate}>
        <div className={styles.shell}>
          <div className={`${styles.card} ${styles.cardBody}`}>
            <span className={styles.avatar} aria-hidden="true">
              <KeyRound size={24} />
            </span>
            <h1>Sign in to your dashboard</h1>
            <p className="mt-2 text-[14.5px] leading-6 text-muted-foreground">
              Enter the operator token configured as{" "}
              <code className="font-mono">EDGE_DASHBOARD_TOKEN</code>. It is
              kept only for this browser tab.
            </p>
            <form
              className="mt-6 space-y-3"
              onSubmit={(event) => {
                event.preventDefault();
                const value = draft.trim();
                if (!value) return;
                try {
                  sessionStorage.setItem(TOKEN_KEY, value);
                } catch {}
                setError("");
                setToken(value);
              }}
            >
              <label className="block text-[14px] font-semibold">
                Dashboard token
                <input
                  className="field mt-2"
                  type="password"
                  autoComplete="off"
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  required
                />
              </label>
              <Button size="lg" className="w-full">
                Open dashboard
              </Button>
            </form>
            {error && (
              <div className="mt-4">
                <InlineError>{error}</InlineError>
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }

  const qa = data?.qa;
  const tokenRatio =
    qa && qa.original.tokens > 0 && qa.variant.tokens > 0
      ? qa.original.tokens / qa.variant.tokens
      : null;
  const labeled = data?.tasks.reduce(
    (sum, task) => ({
      sessions: sum.sessions + task.sessions,
      succeeded: sum.succeeded + task.succeeded,
    }),
    { sessions: 0, succeeded: 0 },
  );
  const agentCount = data?.agents.filter((row) => row.kind === "agent").length;
  const crawlerCount = data ? data.agents.length - (agentCount ?? 0) : 0;
  const siteName = data?.site.name ?? (host || "Dashboard");

  return (
    <div className={styles.page}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <span className={styles.avatar} aria-hidden="true">
            {host ? siteName.charAt(0).toUpperCase() : <Plus size={24} />}
          </span>
          <div className="min-w-0">
            <p className="eyebrow">Agent lane dashboard</p>
            <h1 className="mt-1">
              {data?.site.name ??
                (sitesLoaded && !sites.length
                  ? "Add your first site"
                  : "Loading…")}
            </h1>
            <p className={styles.meta}>
              <span className={styles.host}>{host}</span>
              {data &&
                (data.variant ? (
                  <span className={styles.status} data-live="">
                    <i aria-hidden="true" /> Agent lane v{data.variant.version}{" "}
                    live · {plural(data.variant.products, "product")}
                  </span>
                ) : (
                  <span className={styles.status}>
                    <i aria-hidden="true" /> No published agent lane yet
                  </span>
                ))}
            </p>
          </div>
        </div>
        <div className={styles.controls}>
          {sites.length > 1 && (
            <select
              className="field w-auto py-2"
              aria-label="Site"
              value={host}
              onChange={(event) => setHost(event.target.value)}
            >
              {sites.map((site) => (
                <option key={site.host} value={site.host}>
                  {site.name}
                </option>
              ))}
            </select>
          )}
          {host && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setAdding((value) => !value)}
                aria-expanded={adding}
              >
                <Plus size={14} aria-hidden="true" /> Add site
              </Button>
              <div
                className={styles.segmented}
                role="group"
                aria-label="Time window"
              >
                {WINDOWS.map((value) => (
                  <button
                    key={value}
                    type="button"
                    aria-pressed={days === value}
                    aria-label={`Last ${value} days`}
                    onClick={() => setDays(value)}
                  >
                    {value}d
                  </button>
                ))}
              </div>
              <Button
                variant="outline"
                size="sm"
                disabled={busy || !host}
                onClick={async () => {
                  setBusy(true);
                  try {
                    await api.refreshSessions(token, host);
                    await load();
                  } catch (e) {
                    fail(e);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {busy ? (
                  <LoaderCircle
                    size={14}
                    className="animate-spin"
                    aria-hidden="true"
                  />
                ) : (
                  <RefreshCw size={14} aria-hidden="true" />
                )}
                Refresh sessions
              </Button>
            </>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              try {
                sessionStorage.removeItem(TOKEN_KEY);
              } catch {}
              setToken("");
              setData(null);
            }}
          >
            <LogOut size={14} aria-hidden="true" /> Sign out
          </Button>
        </div>
      </header>

      {error && (
        <div className="mb-6">
          <InlineError>{error}</InlineError>
        </div>
      )}
      {(adding || (sitesLoaded && sites.length === 0)) && (
        <div className="mb-5">
          <AddSiteForm
            token={token}
            onCancel={sites.length ? () => setAdding(false) : undefined}
            onCreated={(site) => {
              setSites((current) => [...current, site]);
              setHost(site.host);
              setData(null);
              setAdding(false);
            }}
          />
        </div>
      )}

      {data && (
        <>
          <div className={styles.shell}>
            <dl className={`${styles.card} ${styles.stats}`}>
              <div className={styles.stat}>
                <dt>Agent requests</dt>
                <dd>
                  <span className={styles.figure}>
                    {data.totals.agent_requests.toLocaleString()}
                  </span>
                  <span className={styles.caption}>
                    From user-initiated AI agents, last {data.window_days} days
                  </span>
                </dd>
              </div>
              <div className={styles.stat}>
                <dt>Sessions</dt>
                <dd>
                  <span className={styles.figure}>
                    {data.totals.sessions.toLocaleString()}
                  </span>
                  <span className={styles.caption}>
                    {data.totals.unlabeled_sessions
                      ? `${data.totals.unlabeled_sessions} not labeled yet`
                      : "All labeled"}
                  </span>
                </dd>
              </div>
              <div className={styles.stat} data-accent="">
                <dt>Served from the agent lane</dt>
                <dd>
                  <span className={styles.figure}>
                    {data.totals.variant_requests.toLocaleString()}
                  </span>
                  <span className={styles.caption}>
                    {data.totals.agent_requests
                      ? `${Math.round((data.totals.variant_requests / data.totals.agent_requests) * 100)}% of agent requests`
                      : "No agent requests yet"}
                  </span>
                </dd>
              </div>
              <div className={styles.stat}>
                <dt>Crawler requests</dt>
                <dd>
                  <span className={styles.figure}>
                    {data.totals.crawler_requests.toLocaleString()}
                  </span>
                  <span className={styles.caption}>
                    Never routed; always your original site
                  </span>
                </dd>
              </div>
            </dl>
          </div>

          <LanePanel
            variants={variants}
            job={latest("build_variant")}
            onBuild={() => void start("build_variant")}
            onPublish={(version) =>
              void api
                .publishVariant(token, host, version)
                .then(() => Promise.all([load(), loadLane()]))
                .catch(fail)
            }
          />

          <div className={styles.grid}>
            <div className={styles.shell}>
              <section
                className={`${styles.card} ${styles.cardBody} h-full`}
                aria-labelledby="agents-title"
              >
                <div className={styles.cardHead}>
                  <h2 id="agents-title">Agents visiting</h2>
                  <span className={styles.kicker}>
                    Last {data.window_days} days
                  </span>
                </div>
                {data.agents.length ? (
                  <>
                    <ul className={styles.agents}>
                      {data.agents.map((row) => (
                        <li key={row.agent}>
                          <AgentMark agent={row.agent} kind={row.kind} />
                          <span className="min-w-0">
                            <span className={styles.agentName}>
                              {row.agent}
                            </span>
                            <span className={styles.agentSub}>
                              {row.kind === "agent"
                                ? `AI agent · ${plural(row.sessions, "session")}`
                                : "Crawler · never routed"}
                              {row.errors > 0 &&
                                ` · ${plural(row.errors, "error")}`}
                            </span>
                          </span>
                          <span className={styles.agentCount}>
                            <strong>{plural(row.requests, "request")}</strong>
                            {row.kind === "agent" ? (
                              row.variant_requests > 0 ? (
                                <span className={styles.badge}>
                                  <Check size={12} aria-hidden="true" />
                                  {row.variant_requests} from lane
                                </span>
                              ) : (
                                <span
                                  className={styles.badge}
                                  data-tone="muted"
                                >
                                  Original site
                                </span>
                              )
                            ) : (
                              <span className={styles.badge} data-tone="muted">
                                Passed through
                              </span>
                            )}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <p className={styles.footerBar}>
                      {plural(agentCount ?? 0, "AI agent")} ·{" "}
                      {plural(crawlerCount, "crawler")} seen
                    </p>
                  </>
                ) : (
                  <div className={styles.emptyInline}>
                    <p>
                      No agent traffic in this window yet. Requests appear here
                      as soon as an AI agent fetches a page through the router.
                    </p>
                  </div>
                )}
              </section>
            </div>

            <div className={styles.shell}>
              <section
                className={`${styles.card} ${styles.cardBody} h-full`}
                aria-labelledby="tasks-title"
              >
                <div className={styles.cardHead}>
                  <h2 id="tasks-title">Task success</h2>
                  <span className={styles.badge}>
                    <Sparkles size={12} aria-hidden="true" />
                    Model-judged from request logs
                  </span>
                </div>
                {data.tasks.length && labeled ? (
                  <>
                    {data.totals.unlabeled_sessions > 0 && (
                      <div className={styles.labelMore}>
                        <JobButton
                          variant="outline"
                          job={latest("label_sessions")}
                          label={`Label ${data.totals.unlabeled_sessions} new`}
                          onStart={() => void start("label_sessions")}
                        />
                        <JobStatus job={latest("label_sessions")} />
                      </div>
                    )}
                    <div className={styles.success}>
                      <Ring
                        value={
                          labeled.sessions
                            ? Math.round(
                                (labeled.succeeded / labeled.sessions) * 100,
                              )
                            : null
                        }
                        label="succeeded"
                      />
                      <ul className={styles.bars}>
                        {data.tasks.map((task) => {
                          const pct = (n: number) =>
                            `${(n / task.sessions) * 100}%`;
                          return (
                            <li key={task.task}>
                              <div className={styles.barLabel}>
                                <span className="font-semibold">
                                  {task.task}
                                </span>
                                <span>
                                  {task.succeeded}/{task.sessions}
                                </span>
                              </div>
                              <div
                                className={styles.bar}
                                role="img"
                                aria-label={`${task.succeeded} succeeded, ${task.failed} failed, ${task.unknown} unknown`}
                              >
                                <span
                                  className="bg-success"
                                  style={{ width: pct(task.succeeded) }}
                                />
                                <span
                                  className="bg-danger"
                                  style={{ width: pct(task.failed) }}
                                />
                                <span
                                  className="bg-border"
                                  style={{ width: pct(task.unknown) }}
                                />
                              </div>
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                    <p className={styles.legend} aria-hidden="true">
                      <span>
                        <i className="bg-success" /> Succeeded
                      </span>
                      <span>
                        <i className="bg-danger" /> Failed
                      </span>
                      <span>
                        <i className="bg-border" /> Unknown
                      </span>
                    </p>
                  </>
                ) : (
                  <div className={styles.preview}>
                    <div
                      className={`${styles.success} ${styles.ghost}`}
                      aria-hidden="true"
                    >
                      <Ring value={null} label="succeeded" />
                      <div className={styles.bars}>
                        {[80, 55, 68].map((width) => (
                          <div key={width}>
                            <span
                              className={styles.skel}
                              style={{ width: `${width / 2}%` }}
                            />
                            <span className={`${styles.bar}`} />
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className={styles.emptyNote}>
                      <div
                        className={`${styles.card} ${styles.cardBody} grid justify-items-center gap-2.5`}
                      >
                        <strong>No labeled sessions yet</strong>
                        <p>
                          Gemini reads each session and judges what the agent
                          was trying to do. These are model judgments, not
                          verified results.
                        </p>
                        <JobButton
                          job={latest("label_sessions")}
                          label="Label sessions with Gemini"
                          onStart={() => void start("label_sessions")}
                          disabled={!data.totals.sessions}
                        />
                        {!data.totals.sessions && (
                          <p className={styles.hint}>
                            Sessions appear once AI agents visit through the
                            router.
                          </p>
                        )}
                        <JobStatus job={latest("label_sessions")} />
                      </div>
                    </div>
                  </div>
                )}
              </section>
            </div>
          </div>

          <section
            className={`${styles.shell} ${styles.section}`}
            aria-labelledby="compare-title"
          >
            <div className={styles.compareHead}>
              <div>
                <h2 id="compare-title">Before and after</h2>
                <p>
                  The same tasks, run by an AI agent on your original site and
                  on the agent lane.
                </p>
              </div>
              <div className={styles.pills}>
                {tokenRatio && (
                  <span className={styles.tokens}>
                    {tokenRatio.toFixed(1)}× fewer tokens
                  </span>
                )}
                <span className={styles.badge}>
                  <Check size={12} aria-hidden="true" />
                  Rule-verified agent QA
                </span>
                {qa && (
                  <JobButton
                    variant="outline"
                    job={latest("run_qa")}
                    label="Run again"
                    onStart={() => void start("run_qa")}
                    disabled={!data.variant}
                  />
                )}
              </div>
            </div>
            {qa ? (
              <>
                <div className={styles.compare}>
                  <QASide
                    label="Original site"
                    host={host}
                    summary={qa.original}
                    tasks={qa.tasks.map((task) => ({
                      key: task.task,
                      prompt: task.prompt,
                      outcome: task.original,
                      steps: task.original_steps,
                    }))}
                  />
                  <QASide
                    lane
                    label={
                      data.variant
                        ? `Agent lane · v${data.variant.version}`
                        : "Agent lane"
                    }
                    host={host}
                    summary={qa.variant}
                    tasks={qa.tasks.map((task) => ({
                      key: task.task,
                      prompt: task.prompt,
                      outcome: task.variant,
                      steps: task.variant_steps,
                    }))}
                  />
                </div>
                <p className={styles.compareNote}>
                  Answers are checked by rules against the site’s known facts,
                  never taken from the agent’s own claim. Runs with
                  infrastructure errors (
                  {qa.original.errors + qa.variant.errors}) are excluded from
                  the rates.{" "}
                  {tokenRatio &&
                    `Tokens: ${qa.variant.tokens.toLocaleString()} on the lane vs ${qa.original.tokens.toLocaleString()} on the original. `}
                  Batch run {new Date(qa.created_at).toLocaleString()}.
                </p>
                <div className="px-3.5 pb-2">
                  <JobStatus job={latest("run_qa")} />
                </div>
              </>
            ) : (
              <div className={styles.preview}>
                <div className={styles.compare}>
                  <GhostSide label="Original site" />
                  <GhostSide lane label="Agent lane" />
                </div>
                <div className={styles.emptyNote}>
                  <div
                    className={`${styles.card} ${styles.cardBody} grid justify-items-center gap-2.5`}
                  >
                    <strong>No QA batch yet</strong>
                    <p>
                      QA runs the same ten tasks with Gemini Computer Use on
                      both versions and checks every answer by rules.
                    </p>
                    <JobButton
                      job={latest("run_qa")}
                      label="Run agent QA"
                      onStart={() => void start("run_qa")}
                      disabled={!data.variant}
                    />
                    {!data.variant && (
                      <p className={styles.hint}>
                        Publish an agent lane first; QA compares it with your
                        original site.
                      </p>
                    )}
                    <JobStatus job={latest("run_qa")} />
                  </div>
                </div>
              </div>
            )}
          </section>

          <section
            className={`${styles.shell} ${styles.section}`}
            aria-labelledby="failures-title"
          >
            <div className={styles.compareHead}>
              <div>
                <h2 id="failures-title">Top failures</h2>
                <p>Where agents got stuck, and what would help.</p>
              </div>
              <span className={styles.badge} data-tone="muted">
                Suggestions, not applied automatically
              </span>
            </div>
            {data.failures.length ? (
              <ul className={styles.failures}>
                {data.failures.map((failure) => (
                  <li
                    key={`${failure.task}-${failure.failed_step}`}
                    className={`${styles.card} ${styles.failure}`}
                  >
                    <h3>{failure.task}</h3>
                    <code className={styles.stepChip}>
                      {failure.failed_step}
                    </code>
                    {failure.explanation && <p>{failure.explanation}</p>}
                    {failure.suggested_fix && (
                      <p className={styles.fix}>
                        <b>Suggested fix</b>
                        {failure.suggested_fix}
                      </p>
                    )}
                    <p className={styles.seen}>
                      {plural(failure.sessions, "session")} · seen from{" "}
                      {failure.agents.join(", ")}
                    </p>
                  </li>
                ))}
              </ul>
            ) : (
              <div className={`${styles.card} ${styles.cardBody}`}>
                <p className="text-[14px] text-muted-foreground">
                  No failed sessions have been labeled in this window.
                </p>
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}
