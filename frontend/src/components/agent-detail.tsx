"use client";
import Image from "next/image";
import Link from "next/link";
import { useCallback, useState } from "react";
import {
  AlertTriangle,
  ArrowDown,
  Bot,
  Check,
  CheckCircle2,
  ChevronRight,
  Clock3,
  CornerUpLeft,
  Eye,
  FileText,
  FormInput,
  Globe2,
  ImageOff,
  Layers,
  LoaderCircle,
  Maximize2,
  MousePointer2,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { api } from "@/lib/api";
import { useResource } from "@/lib/use-resource";
import type { AgentStep, AgentTest } from "@/lib/types";
import { cn } from "@/lib/utils";
import { taskName } from "./agent-testing";
import {
  CopyButton,
  domainOf,
  duration,
  PageHeading,
  Status,
  VerificationNotice,
} from "./product-ui";
import { EmptyState, ErrorState, LoadingState } from "./states";
import { Button } from "./ui/button";
const actions: Record<string, { label: string; icon: LucideIcon }> = {
  navigate: { label: "Navigate to page", icon: Globe2 },
  click: { label: "Click an element", icon: MousePointer2 },
  fill: { label: "Fill a permitted field", icon: FormInput },
  select_option: { label: "Select an option", icon: Layers },
  scroll: { label: "Scroll the page", icon: ArrowDown },
  get_page_snapshot: { label: "Observe the page", icon: Eye },
  go_back: { label: "Go back", icon: CornerUpLeft },
  finish: { label: "Agent declared completion", icon: CheckCircle2 },
  inference_error: { label: "Model request failed", icon: Bot },
  invalid: { label: "Action rejected", icon: AlertTriangle },
  interrupted: { label: "Execution interrupted", icon: Clock3 },
};
type Data = { test: AgentTest; steps: AgentStep[] };
const active = (d: Data) =>
  d.test.status === "PENDING" || d.test.status === "RUNNING";
function FailureMessage({ message }: { message: string }) {
  const billing = message.includes("402");
  return (
    <div className="rounded-lg border border-danger/15 bg-danger/5 p-4">
      <div className="flex items-center gap-2 text-xs font-medium text-danger">
        <AlertTriangle size={14} />
        {billing
          ? "Model inference is unavailable"
          : "This execution needs attention"}
      </div>
      <p className="mt-2 break-words text-[11px] leading-6 text-muted-foreground">
        {billing
          ? "The inference endpoint requires credits or billing. Configure a funded Hugging Face endpoint or a working local model server, then start a new test."
          : message}
      </p>
      {billing && (
        <details className="mt-2 text-[10px] text-muted-foreground">
          <summary>Technical details</summary>
          <p className="mt-2 break-words leading-5">{message}</p>
        </details>
      )}
      <Link
        href="/docs#agent"
        className="mt-3 inline-flex items-center gap-1 text-[10px] font-medium text-danger"
      >
        Inference setup guide
        <ChevronRight size={11} />
      </Link>
    </div>
  );
}
function BrowserEvidence({
  step,
  test,
}: {
  step: AgentStep | null;
  test: AgentTest;
}) {
  const [failedSrc, setFailedSrc] = useState("");
  const src = step?.has_screenshot
    ? `/api/v1/agent-tests/${test.id}/steps/${step.id}/screenshot`
    : "";
  const title =
    typeof step?.observation_summary.title === "string"
      ? step.observation_summary.title
      : "Browser observation";
  const text =
    typeof step?.observation_summary.visible_text === "string"
      ? step.observation_summary.visible_text
      : null;
  const elements = Array.isArray(step?.observation_summary.elements)
    ? step.observation_summary.elements
    : [];
  return (
    <div className="min-w-0 space-y-4 lg:sticky lg:top-[85px]">
      <section className="evidence-browser surface overflow-hidden">
        <div className="flex items-center justify-between border-b px-5 py-4">
          <h2 className="section-title flex items-center gap-2">
            <Eye size={16} className="text-muted-foreground" />
            Browser evidence
          </h2>
          {step && (
            <span className="mono text-[9px] text-muted-foreground">
              STEP {String(step.step_number).padStart(2, "0")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-3 border-b bg-background/70 px-4 py-3">
          <div className="hidden gap-1 sm:flex">
            {[1, 2, 3].map((n) => (
              <span key={n} className="size-1.5 rounded-full border bg-muted" />
            ))}
          </div>
          <div className="mono flex min-w-0 flex-1 items-center gap-2 rounded-md border bg-card px-2.5 py-1.5 text-[9px] text-muted-foreground">
            <ShieldCheck size={10} className="shrink-0" />
            <span
              className="truncate"
              title={step?.page_url ?? test.final_url ?? test.starting_url}
            >
              {step?.page_url ?? test.final_url ?? test.starting_url}
            </span>
          </div>
          {src && src !== failedSrc && (
            <a
              href={src}
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Open full screenshot"
              className="rounded p-1.5 text-muted-foreground hover:bg-muted"
            >
              <Maximize2 size={13} />
            </a>
          )}
        </div>
        {src && src !== failedSrc ? (
          <div className="bg-muted/30 p-3">
            <Image
              src={src}
              width={1280}
              height={800}
              unoptimized
              alt={`Captured browser screenshot at step ${step?.step_number}`}
              className="h-auto w-full rounded-lg border bg-white"
              onError={() => setFailedSrc(src)}
            />
          </div>
        ) : (
          <div className="flex min-h-[260px] flex-col items-center justify-center bg-background/50 p-8 text-center">
            <span className="mb-4 grid size-12 place-items-center rounded-xl border bg-card text-muted-foreground">
              <ImageOff size={21} strokeWidth={1.4} />
            </span>
            <p className="text-xs font-medium">
              {src === failedSrc && src
                ? "Screenshot could not be loaded"
                : "No screenshot for this step"}
            </p>
            <p className="mt-2 max-w-[260px] text-[11px] leading-6 text-muted-foreground">
              {test.status === "PENDING"
                ? "Evidence appears as the agent begins its journey."
                : "A screenshot was not captured here. The recorded page observation is available below."}
            </p>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-between gap-2 border-t px-4 py-3 text-[9px] text-muted-foreground">
          <span className="inline-flex items-center gap-1.5">
            <ShieldCheck size={11} />
            Captured evidence · inputs masked
          </span>
          <span>
            {src && src !== failedSrc
              ? "Actual browser screenshot"
              : "No illustrative imagery"}
          </span>
        </div>
      </section>
      <section className="surface p-5">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="section-title flex items-center gap-2">
            <FileText size={15} className="text-muted-foreground" />
            Page observation
          </h3>
          <span className="text-[9px] text-muted-foreground">
            Recorded at this step
          </span>
        </div>
        <p className="text-xs font-medium">{title || "Untitled page"}</p>
        {text ? (
          <p
            tabIndex={0}
            aria-label="Observed visible page text"
            className="mt-3 max-h-[220px] overflow-y-auto whitespace-pre-wrap text-[11px] leading-6 text-muted-foreground"
          >
            {text}
          </p>
        ) : (
          <p className="mt-3 text-[11px] leading-6 text-muted-foreground">
            {step
              ? "No visible text was recorded for this step."
              : "Select a step to inspect what the agent observed."}
          </p>
        )}
        {elements.length > 0 && (
          <details className="mt-4 border-t pt-4 text-[11px]">
            <summary className="text-muted-foreground">
              {elements.length} observed interactive elements
            </summary>
            <div className="mt-3 space-y-2">
              {elements.slice(0, 20).map((element, index) => {
                const item = element as Record<string, unknown>;
                return (
                  <div
                    key={index}
                    className="flex min-w-0 items-start gap-2 rounded-md bg-background px-3 py-2 text-[10px]"
                  >
                    <span className="mono shrink-0 text-muted-foreground">
                      {String(item.role ?? item.tag ?? "element")}
                    </span>
                    <span className="min-w-0 break-words">
                      {String(item.name ?? "Unnamed element")}
                    </span>
                    {item.required === true && (
                      <span className="ml-auto shrink-0 text-warning">
                        Required
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </details>
        )}
        {step && (
          <details className="mt-4 border-t pt-4 text-[10px] text-muted-foreground">
            <summary>Raw observation data</summary>
            <pre tabIndex={0} className="code-panel mt-3">
              {JSON.stringify(step.observation_summary, null, 2)}
            </pre>
          </details>
        )}
      </section>
    </div>
  );
}
export function AgentDetail({ id }: { id: string }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [follow, setFollow] = useState(true);
  const load = useCallback(async () => {
    const [test, steps] = await Promise.all([
      api.agentTest(id),
      api.agentSteps(id),
    ]);
    return { test, steps };
  }, [id]);
  const { data, error, retry } = useResource(load, active);
  if (error) return <ErrorState message={error.message} retry={retry} />;
  if (!data) return <LoadingState />;
  const { test, steps } = data;
  const current = active(data);
  const selected =
    (follow ? steps.at(-1) : steps.find((s) => s.id === selectedId)) ??
    steps.at(-1) ??
    null;
  const timedOut =
    Boolean(test.metrics.timeouts) ||
    /time limit|timed out|deadline/i.test(test.failure_reason ?? "");
  return (
    <div className="fade-in">
      <PageHeading
        back={{
          href: `/scans/${test.scan_id}?tab=agents`,
          label: "Back to scan",
        }}
        eyebrow="Agent execution"
        title={taskName(test.task_type)}
        description={test.task_description}
        action={
          <>
            <Status value={test.status} timeout={timedOut} />
            <Button variant="outline" asChild>
              <Link href={`/scans/${test.scan_id}?tab=agents`}>
                <Bot size={14} />
                New agent test
              </Link>
            </Button>
          </>
        }
      />
      <div className="-mt-4 mb-6 flex items-center gap-1 text-muted-foreground">
        <span className="mono break-all text-[9px]">{test.id}</span>
        <CopyButton value={test.id} />
      </div>
      <section className="surface mb-6 overflow-hidden">
        <div className="grid grid-cols-2 gap-px bg-border md:grid-cols-[1.5fr_1fr_.65fr_.65fr]">
          <div className="min-w-0 bg-card p-4 sm:px-5">
            <p className="eyebrow text-[8px]">Model used</p>
            <p
              className="mono mt-2 truncate text-[10px]"
              title={test.model_identifier}
            >
              {test.model_identifier}
            </p>
          </div>
          <div className="min-w-0 bg-card p-4 sm:px-5">
            <p className="eyebrow text-[8px]">Website</p>
            <p className="mono mt-2 truncate text-[10px]">
              {domainOf(test.starting_url)}
            </p>
          </div>
          <div className="bg-card p-4 sm:px-5">
            <p className="eyebrow text-[8px]">Steps executed</p>
            <p className="mt-1 text-lg font-medium tabular-nums">
              {test.steps_completed}
              <span className="ml-1 text-[10px] text-muted-foreground">
                / 15 max
              </span>
            </p>
          </div>
          <div className="bg-card p-4 sm:px-5">
            <p className="eyebrow text-[8px]">Duration</p>
            <p className="mono mt-2 text-sm">
              {duration(test.execution_duration)}
            </p>
          </div>
        </div>
        <div className="border-t px-5 py-3">
          <div className="mb-2 flex items-center gap-2 text-[9px] font-medium text-muted-foreground">
            <Workflow size={13} />
            Agent-reported outcome
          </div>
          {test.agent_declared_outcome ? (
            <p className="mb-2 whitespace-pre-wrap text-xs leading-6">
              {test.agent_declared_outcome}
            </p>
          ) : (
            <p className="mb-2 text-xs text-muted-foreground">
              {current
                ? "The agent has not declared an outcome yet."
                : "No completion outcome was reported."}
            </p>
          )}
          <VerificationNotice />
        </div>
      </section>
      {test.failure_reason && (
        <div className="mb-6">
          <FailureMessage message={test.failure_reason} />
        </div>
      )}
      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,.9fr)_minmax(0,1.1fr)]">
        <section className="execution-timeline surface min-w-0 overflow-hidden">
          <div className="flex items-center justify-between gap-2 border-b px-5 py-4">
            <h2 className="section-title flex items-center gap-2">
              <Workflow size={16} className="text-muted-foreground" />
              Execution timeline
            </h2>
            <button
              className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[9px] ${follow ? "border-primary/20 bg-accent-soft text-primary" : "text-muted-foreground"}`}
              aria-pressed={follow}
              onClick={() => setFollow((v) => !v)}
            >
              {current ? (
                <LoaderCircle
                  size={10}
                  className={follow ? "animate-spin" : ""}
                />
              ) : (
                <Check size={10} />
              )}
              Follow latest
            </button>
          </div>
          <div className="max-h-[750px] overflow-y-auto px-4 py-5 lg:max-h-[calc(100vh-180px)]">
            {steps.length === 0 ? (
              <EmptyState
                title={
                  current ? "The agent is getting ready" : "No steps recorded"
                }
                description={
                  current
                    ? "The browser is opening. Actions and observations appear here as the execution progresses."
                    : "This run ended before an action could be recorded. Review the error above."
                }
              />
            ) : (
              <ol>
                {steps.map((step, index) => {
                  const info = actions[step.action_type] ?? {
                    label: step.action_type.replaceAll("_", " "),
                    icon: Bot,
                  };
                  const Icon = step.error_message ? AlertTriangle : info.icon;
                  const chosen = selected?.id === step.id;
                  return (
                    <li className="relative pb-3 pl-10 last:pb-0" key={step.id}>
                      {index < steps.length - 1 && (
                        <span className="absolute bottom-0 left-[14px] top-8 border-l" />
                      )}
                      <span
                        className={cn(
                          "absolute left-0 top-3 grid size-7 place-items-center rounded-full border bg-card",
                          step.error_message
                            ? "border-danger/25 text-danger"
                            : step.action_type === "finish"
                              ? "border-primary/25 text-primary"
                              : "text-muted-foreground",
                        )}
                      >
                        <Icon size={12} />
                      </span>
                      <div
                        className={cn(
                          "rounded-xl border transition-colors",
                          chosen
                            ? "border-primary/30 bg-accent-soft/30"
                            : "border-transparent hover:border-border hover:bg-background",
                        )}
                      >
                        <button
                          className="w-full rounded-xl p-3 text-left"
                          aria-pressed={chosen}
                          onClick={() => {
                            setSelectedId(step.id);
                            setFollow(false);
                          }}
                        >
                          <span className="mb-2 flex items-center justify-between gap-2">
                            <span className="mono text-[8px] uppercase tracking-wide text-muted-foreground">
                              Step {String(step.step_number).padStart(2, "0")}
                            </span>
                            <span className="mono text-[8px] text-muted-foreground">
                              {step.duration_ms < 1000
                                ? `${step.duration_ms} ms`
                                : `${(step.duration_ms / 1000).toFixed(1)}s`}
                            </span>
                          </span>
                          <span className="block text-[11px] font-semibold">
                            {info.label}
                          </span>
                          <span className="mt-1.5 block text-[10px] leading-5 text-muted-foreground">
                            {step.reasoning_summary}
                          </span>
                          <span className="mono mt-2 block truncate text-[8px] text-muted-foreground">
                            {step.page_url}
                          </span>
                          {step.error_message && (
                            <span className="mt-2 block text-[10px] font-medium text-danger">
                              {step.error_message.includes("402")
                                ? "Inference unavailable · HTTP 402"
                                : step.error_message}
                            </span>
                          )}
                        </button>
                        <details className="mx-3 mb-3 border-t border-border/70 pt-2 text-[9px] text-muted-foreground">
                          <summary>Action & execution result</summary>
                          <pre tabIndex={0} className="code-panel mt-2">
                            {JSON.stringify(
                              {
                                arguments: step.action_arguments,
                                result: step.action_result,
                              },
                              null,
                              2,
                            )}
                          </pre>
                        </details>
                      </div>
                    </li>
                  );
                })}
                {current && (
                  <li className="mt-3 flex items-center gap-3 pl-10 text-[10px] text-muted-foreground">
                    <LoaderCircle
                      className="animate-spin text-primary"
                      size={13}
                    />
                    Waiting for the next observation…
                  </li>
                )}
              </ol>
            )}
          </div>
          <div className="border-t bg-background/40 px-5 py-3 text-[9px] text-muted-foreground">
            {current
              ? "Live updates every 2 seconds"
              : "Execution finished · showing recorded evidence"}
          </div>
        </section>
        <BrowserEvidence step={selected} test={test} />
      </div>
      <details className="surface mt-6 p-5 text-xs">
        <summary className="text-muted-foreground">
          Execution diagnostics
        </summary>
        <pre tabIndex={0} className="code-panel mt-4">
          {JSON.stringify(test.metrics, null, 2)}
        </pre>
        <p className="mono mt-4 break-all text-[9px] text-muted-foreground">
          Final URL: {test.final_url ?? "Not recorded"}
        </p>
      </details>
    </div>
  );
}
