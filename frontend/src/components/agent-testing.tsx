"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Bot,
  CreditCard,
  FormInput,
  LoaderCircle,
  ShieldCheck,
} from "lucide-react";
import { api } from "@/lib/api";
import type { AgentTaskType, AgentTest } from "@/lib/types";
import { Button } from "./ui/button";
import { InlineError } from "./states";
import { duration, Status, TextLink } from "./product-ui";
export const agentTasks = [
  {
    type: "FIND_PRICING" as AgentTaskType,
    name: "Find Pricing",
    icon: CreditCard,
    description:
      "Find the pricing page and read available plans and displayed prices.",
    expectation: "Navigation + content discovery",
  },
  {
    type: "FIND_DOCUMENTATION" as AgentTaskType,
    name: "Find Documentation",
    icon: BookOpen,
    description: "Discover and navigate to product or developer documentation.",
    expectation: "Navigation + destination discovery",
  },
  {
    type: "FIND_SIGNUP_FORM" as AgentTaskType,
    name: "Find Signup or Demo Form",
    icon: FormInput,
    description:
      "Locate a signup, trial, or demo form and identify its required fields.",
    expectation: "Form inspection · no submission",
  },
];
export function taskName(type: AgentTaskType) {
  return agentTasks.find((t) => t.type === type)?.name ?? type;
}
export function AgentTesting({ scanId }: { scanId: string }) {
  const router = useRouter();
  const [task, setTask] = useState<AgentTaskType>("FIND_PRICING");
  const [domains, setDomains] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <section className="surface overflow-hidden">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b px-5 py-5">
        <div>
          <h2 className="section-title flex items-center gap-2">
            <Bot size={17} className="text-primary" />
            Give your agent a task
          </h2>
          <p className="mt-2 text-xs leading-6 text-muted-foreground">
            The model chooses its own path. You get an observation and action
            trace.
          </p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full border bg-background px-2.5 py-1 text-[9px] text-muted-foreground">
          <ShieldCheck size={11} />
          Read-only execution
        </span>
      </div>
      <form
        className="p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const test = await api.createAgentTest(
              scanId,
              task,
              domains
                .split(",")
                .map((d) => d.trim())
                .filter(Boolean),
            );
            router.push(`/agent-tests/${test.id}`);
          } catch (e) {
            setError(
              e instanceof Error
                ? e.message
                : "Could not start the agent test.",
            );
          } finally {
            setBusy(false);
          }
        }}
      >
        <fieldset>
          <legend className="sr-only">Choose an agent task</legend>
          <div className="grid gap-3 lg:grid-cols-3">
            {agentTasks.map(
              ({ type, name, icon: Icon, description, expectation }) => (
                <label
                  key={type}
                  className={`relative cursor-pointer rounded-xl border p-4 transition-colors focus-within:ring-2 focus-within:ring-ring ${type === task ? "border-primary/60 bg-accent-soft/60" : "bg-card hover:bg-muted/40"}`}
                >
                  <input
                    className="sr-only"
                    type="radio"
                    name="agent-task"
                    value={type}
                    checked={task === type}
                    onChange={() => setTask(type)}
                  />
                  <div className="mb-4 flex items-center justify-between">
                    <span
                      className={`grid size-8 place-items-center rounded-lg border ${type === task ? "border-primary/20 bg-card text-primary" : "bg-background text-muted-foreground"}`}
                    >
                      <Icon size={16} />
                    </span>
                    <span
                      className={`grid size-3.5 place-items-center rounded-full border ${type === task ? "border-primary" : "border-border"}`}
                    >
                      {type === task && (
                        <span className="size-1.5 rounded-full bg-primary" />
                      )}
                    </span>
                  </div>
                  <span className="block text-xs font-semibold">{name}</span>
                  <span className="mt-2 block text-[11px] leading-5 text-muted-foreground">
                    {description}
                  </span>
                  <span className="mt-4 block text-[9px] text-muted-foreground">
                    {expectation}
                  </span>
                </label>
              ),
            )}
          </div>
        </fieldset>
        <details className="mt-5 text-xs">
          <summary className="text-muted-foreground">
            Additional authorized domains
          </summary>
          <p className="mt-3 text-[11px] leading-6 text-muted-foreground">
            By default, the agent stays on your project’s hostname. Add exact
            domains only when your task needs them.
          </p>
          <input
            aria-label="Additional authorized domains"
            className="field mt-2 max-w-md"
            value={domains}
            onChange={(e) => setDomains(e.target.value)}
            maxLength={1000}
            placeholder="docs.example.com, app.example.com"
          />
        </details>
        {error && (
          <div className="mt-4">
            <InlineError>{error}</InlineError>
          </div>
        )}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t pt-5">
          <p className="text-[10px] leading-5 text-muted-foreground">
            15 steps maximum · 120 second limit
            <br />
            The model used is recorded when execution starts.
          </p>
          <Button disabled={busy}>
            {busy ? (
              <LoaderCircle className="animate-spin" size={14} />
            ) : (
              <Bot size={14} />
            )}
            Run Agent Test
            <ArrowRight size={13} />
          </Button>
        </div>
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
                  {test.id.slice(0, 8)}
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
