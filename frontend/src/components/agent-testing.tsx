"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  Bot,
  CreditCard,
  FileText,
  FormInput,
  LoaderCircle,
  Mail,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentConfig, AgentTaskType, AgentTest } from "@/lib/types";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import { duration, Status, TextLink } from "./product-ui";

const builtinTypes: AgentTaskType[] = [
  "FIND_PRICING",
  "FIND_CONTACT",
  "FIND_SIGNUP_FORM",
];
const taskIcons = {
  FIND_PRICING: CreditCard,
  FIND_CONTACT: Mail,
  FIND_SIGNUP_FORM: FormInput,
  FIND_DOCUMENTATION: FileText,
} as const;
const legacyNames: Record<AgentTaskType, string> = {
  FIND_PRICING: "Find Pricing",
  FIND_CONTACT: "Find Contact Information",
  FIND_SIGNUP_FORM: "Find Signup or Demo Form",
  FIND_DOCUMENTATION: "Find Documentation",
};

export function taskName(type: AgentTaskType | string) {
  return legacyNames[type as AgentTaskType] ?? type;
}

function RunLimits({ config }: { config: AgentConfig }) {
  const runMax = Math.max(1, Math.min(config.max_runs, config.runs_limit));
  return (
    <div className="mt-5 flex flex-wrap items-end justify-between gap-4 border-t pt-5">
      <div className="space-y-1 text-[10px] leading-5 text-muted-foreground">
        <p>
          {config.max_steps} steps maximum · {duration(config.duration_seconds)}
          execution limit
        </p>
        <p>
          Model:{" "}
          <span className="mono text-foreground">
            {config.model_identifier}
          </span>
        </p>
        <p>
          Token budget: {config.token_budget.toLocaleString()} ·{" "}
          {config.action_delay}s between actions
        </p>
      </div>
      <label className="grid gap-1 text-[10px] text-muted-foreground">
        Runs per task
        <select
          name="runs"
          className="field min-w-28 py-2 text-xs text-foreground"
          defaultValue={Math.max(1, Math.min(config.default_runs, runMax))}
        >
          {Array.from({ length: runMax }, (_, index) => index + 1).map(
            (count) => (
              <option key={count} value={count}>
                {count} {count === 1 ? "run" : "runs"}
                {count === Math.min(config.default_runs, runMax)
                  ? " · default"
                  : ""}
              </option>
            ),
          )}
        </select>
      </label>
    </div>
  );
}

export function AgentTesting({ scanId }: { scanId: string }) {
  const router = useRouter();
  const [config, setConfig] = useState<AgentConfig | null>(null);
  const [task, setTask] = useState<AgentTaskType>("FIND_PRICING");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [configError, setConfigError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api.agentConfig().then(
      (value) => {
        if (cancelled) return;
        setConfig(value);
        const allowed = value.tasks.find((item) =>
          builtinTypes.includes(item.task_type),
        );
        if (allowed) setTask(allowed.task_type);
      },
      (cause: unknown) => {
        if (!cancelled) {
          setConfigError(
            cause instanceof Error
              ? cause.message
              : "Could not load agent configuration.",
          );
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, []);

  const tasks = (config?.tasks ?? []).filter((item) =>
    builtinTypes.includes(item.task_type),
  );
  const configured = Boolean(config?.configured);

  return (
    <section className="surface overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-5">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Bot size={17} className="text-primary" />
            Give your agent a task
          </h2>
          <p className="mt-2 text-xs leading-6 text-muted-foreground">
            The model chooses a path through this scanned website. Review its
            actions and evidence afterward.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-[9px] text-muted-foreground">
          <ShieldCheck size={11} />
          Read-only execution
        </span>
      </div>
      <form
        className="p-5"
        onSubmit={async (event) => {
          event.preventDefault();
          if (!config || !configured) return;
          setBusy(true);
          setError("");
          try {
            const form = new FormData(event.currentTarget);
            const runs = Number(form.get("runs")) || undefined;
            const created = await api.createAgentTask(scanId, task, runs);
            const runList = await api.agentTaskRuns(created.id);
            if (runList[0]?.id) {
              router.push(`/agent-tests/${runList[0].id}`);
            } else {
              router.push(`/scans/${scanId}?tab=agents`);
            }
          } catch (cause) {
            setError(
              cause instanceof Error
                ? cause.message
                : "Could not start the agent task.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        {configError ? (
          <InlineError>{configError}</InlineError>
        ) : !config ? (
          <div className="flex items-center gap-2 py-8 text-xs text-muted-foreground">
            <LoaderCircle className="animate-spin" size={14} />
            Loading model and task limits…
          </div>
        ) : tasks.length === 0 ? (
          <p className="rounded-lg border p-4 text-xs text-muted-foreground">
            No built-in agent tasks are available for this installation.
          </p>
        ) : (
          <>
            {!configured && (
              <div className="mb-4 rounded-lg border border-warning/30 bg-warning/5 p-3 text-[11px] leading-5 text-muted-foreground">
                Agent inference is not configured. Add a supported model
                credential or endpoint before starting a task.
                <Link
                  href="/docs#agent"
                  className="ml-1 font-medium text-primary underline"
                >
                  Setup guide
                </Link>
              </div>
            )}
            <fieldset disabled={!configured || busy}>
              <legend className="sr-only">Choose an agent task</legend>
              <div className="grid gap-3 md:grid-cols-3">
                {tasks.map((item) => {
                  const Icon = taskIcons[item.task_type];
                  return (
                    <label
                      key={item.task_type}
                      className={`relative cursor-pointer rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-ring ${item.task_type === task ? "border-primary/60 bg-accent-soft/60" : "bg-card hover:bg-muted/40"}`}
                    >
                      <input
                        className="sr-only"
                        type="radio"
                        name="agent-task"
                        value={item.task_type}
                        checked={task === item.task_type}
                        onChange={() => setTask(item.task_type)}
                      />
                      <span className="mb-4 grid size-8 place-items-center rounded-lg border bg-background text-primary">
                        <Icon size={16} />
                      </span>
                      <span className="block text-xs font-semibold">
                        {item.name}
                      </span>
                      <span className="mt-2 block text-[11px] leading-5 text-muted-foreground">
                        {item.goal}
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>
            <RunLimits config={config} />
            {error && (
              <div className="mt-4">
                <InlineError>{error}</InlineError>
              </div>
            )}
            <div className="mt-5 flex justify-end">
              <Button disabled={!configured || busy || tasks.length === 0}>
                {busy ? (
                  <LoaderCircle className="animate-spin" size={14} />
                ) : (
                  <Bot size={14} />
                )}
                Run Agent Task
                <ArrowRight size={13} />
              </Button>
            </div>
          </>
        )}
      </form>
    </section>
  );
}

export function AgentHistory({ tests }: { tests: AgentTest[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-[650px]">
        <thead className="table-head">
          <tr>
            <th>Task / execution</th>
            <th>Model</th>
            <th>Status</th>
            <th>Steps</th>
            <th>Duration</th>
            <th>
              <span className="sr-only">View execution</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {tests.map((test) => (
            <tr key={test.id} className="table-row">
              <td>
                <Link
                  className="font-medium hover:text-primary"
                  href={`/agent-tests/${test.id}`}
                >
                  {taskName(test.task_type)}
                </Link>
                <p className="mono mt-1 text-[9px] text-muted-foreground">
                  {test.id.slice(0, 8)} · run {test.run_number ?? 1}
                </p>
              </td>
              <td>
                <span
                  title={test.model_identifier}
                  className="mono block max-w-[210px] truncate text-[10px] text-muted-foreground"
                >
                  {test.model_identifier}
                </span>
              </td>
              <td>
                <Status
                  value={test.status}
                  timeout={Boolean(test.metrics.timeouts)}
                />
              </td>
              <td className="tabular-nums">{test.steps_completed}</td>
              <td className="mono text-[10px] text-muted-foreground">
                {duration(test.execution_duration)}
              </td>
              <td>
                <TextLink href={`/agent-tests/${test.id}`}>
                  Inspect run
                </TextLink>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
