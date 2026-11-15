"use client";

import Image from "next/image";
import Link from "next/link";
import { useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Eye,
  ShieldAlert,
} from "lucide-react";
import type {
  AgentTaskRunSummary,
  AgentTaskStepSummary,
  AgentTaskSummary,
} from "@/lib/types";
import { taskName } from "./agent-testing";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./ui/dialog";

const outcomeClass: Record<string, string> = {
  SUCCEEDED: "border-success/25 bg-success/5 text-success",
  FAILED: "border-danger/25 bg-danger/5 text-danger",
  INCONCLUSIVE: "border-warning/30 bg-warning/5 text-warning",
  UNAVAILABLE: "border-border bg-muted text-muted-foreground",
};
const verificationName: Record<string, string> = {
  rules: "Rule verified",
  judged: "LLM judged · lower assurance",
  unverified: "Unverified",
};
const failureName: Record<string, string> = {
  infra_error: "Inference or execution service issue",
  element_not_found: "Element not found",
  blocked_by_captcha_or_bot_protection: "Bot protection or CAPTCHA",
  content_requires_js: "Content requires JavaScript",
  ambiguous_navigation: "Ambiguous navigation",
  step_limit: "Step limit reached",
  loop: "Repeated action loop",
  malformed_output: "Malformed model output",
  other: "Other failure",
};

function Outcome({ value }: { value?: string | null }) {
  if (!value) {
    return (
      <span className="inline-flex items-center gap-1 text-[12px] text-muted-foreground">
        <CircleHelp size={12} />
        Pending
      </span>
    );
  }
  const Icon =
    value === "SUCCEEDED"
      ? CheckCircle2
      : value === "UNAVAILABLE"
        ? ShieldAlert
        : value === "FAILED"
          ? AlertTriangle
          : CircleHelp;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[12px] font-medium ${outcomeClass[value] ?? "border-border bg-muted text-muted-foreground"}`}
    >
      <Icon size={11} />
      {value.toLowerCase().replaceAll("_", " ")}
    </span>
  );
}

function money(value?: number | null) {
  return value == null
    ? "Not reported"
    : `$${value.toFixed(value < 0.01 ? 5 : 3)}`;
}

function ReplayDialog({ run }: { run: AgentTaskRunSummary }) {
  const [open, setOpen] = useState(false);
  const [index, setIndex] = useState(0);
  const steps = run.steps ?? [];
  if (steps.length === 0) return null;
  const step = steps[Math.min(index, steps.length - 1)];
  const screenshot =
    step.screenshot_url ??
    (step.has_screenshot && run.id && step.id
      ? `/api/v1/agent-tests/${encodeURIComponent(run.id)}/steps/${encodeURIComponent(step.id)}/screenshot`
      : undefined);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex items-center gap-1 text-[12px] font-medium text-signal hover:underline"
      >
        <Eye size={12} /> Replay {steps.length}{" "}
        {steps.length === 1 ? "step" : "steps"}
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[90vh] max-w-4xl overflow-y-auto p-5 sm:p-7">
          <DialogTitle className="pr-8 text-base">
            Run {run.run_number} replay
          </DialogTitle>
          <DialogDescription className="text-xs text-muted-foreground">
            Recorded page and action evidence for this run.
          </DialogDescription>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-y py-3">
            <button
              type="button"
              disabled={index === 0}
              onClick={() => setIndex((value) => Math.max(0, value - 1))}
              className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-xs disabled:opacity-40"
            >
              <ArrowLeft size={13} /> Previous
            </button>
            <span className="mono text-[12px] text-muted-foreground">
              Step {index + 1} of {steps.length}
            </span>
            <button
              type="button"
              disabled={index === steps.length - 1}
              onClick={() =>
                setIndex((value) => Math.min(steps.length - 1, value + 1))
              }
              className="inline-flex items-center gap-1 rounded-md border px-3 py-2 text-xs disabled:opacity-40"
            >
              Next <ArrowRight size={13} />
            </button>
          </div>
          <StepEvidence step={step} screenshot={screenshot} />
        </DialogContent>
      </Dialog>
    </>
  );
}

function StepEvidence({
  step,
  screenshot,
}: {
  step: AgentTaskStepSummary;
  screenshot?: string;
}) {
  return (
    <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1.5fr)_minmax(220px,.8fr)]">
      <div className="min-w-0">
        {screenshot ? (
          <a
            href={screenshot}
            target="_blank"
            rel="noopener noreferrer"
            className="block overflow-hidden rounded-lg border bg-muted/30"
          >
            <Image
              src={screenshot}
              alt={`Browser screenshot at step ${step.step_number}`}
              width={1280}
              height={800}
              unoptimized
              className="h-auto max-h-[60vh] w-full object-contain"
            />
          </a>
        ) : (
          <div className="grid min-h-48 place-items-center rounded-lg border bg-muted/20 text-center text-xs text-muted-foreground">
            No screenshot was captured for this step.
          </div>
        )}
      </div>
      <div className="min-w-0 space-y-3 text-xs">
        <div>
          <p className="eyebrow text-[12px]">Action</p>
          <p className="mt-1 font-medium">
            {step.action_type.replaceAll("_", " ")}
          </p>
          <p className="mt-1 leading-5 text-muted-foreground">
            {step.reason ??
              step.reasoning_summary ??
              "No action reason recorded."}
          </p>
        </div>
        <div>
          <p className="eyebrow text-[12px]">Page</p>
          <p className="mono mt-1 break-all text-[12px] text-muted-foreground">
            {step.page_url}
          </p>
        </div>
        {step.error_message && (
          <p className="rounded-md border border-danger/20 bg-danger/5 p-3 text-[12px] leading-5 text-danger">
            {step.error_message}
          </p>
        )}
        <p className="text-[12px] text-muted-foreground">
          {step.duration_ms.toLocaleString()} ms
        </p>
      </div>
    </div>
  );
}

function RunRow({
  run,
  excluded,
}: {
  run: AgentTaskRunSummary;
  excluded: boolean;
}) {
  const category = run.failure_category
    ? (failureName[run.failure_category] ??
      run.failure_category.replaceAll("_", " "))
    : null;
  return (
    <article className="rounded-lg border bg-background/70 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="mono text-[12px] text-muted-foreground">
            RUN {String(run.run_number).padStart(2, "0")}
          </span>
          <Outcome value={run.outcome} />
        </div>
        {run.id && (
          <Link
            href={`/agent-tests/${run.id}`}
            className="text-[12px] font-medium text-signal hover:underline"
          >
            Open workspace replay
          </Link>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
        <span>{verificationName[run.verification_method ?? "unverified"]}</span>
        {run.model_identifier && (
          <span
            className="mono max-w-[220px] truncate"
            title={run.model_identifier}
          >
            {run.model_identifier}
          </span>
        )}
        <span>{run.steps_completed ?? 0} steps</span>
        <span>
          {run.execution_duration == null
            ? "Duration unavailable"
            : `${run.execution_duration.toFixed(1)}s`}
        </span>
        <span>
          {(run.prompt_tokens ?? 0).toLocaleString()} prompt ·{" "}
          {(run.completion_tokens ?? 0).toLocaleString()} completion tokens
        </span>
        <span>Estimated cost: {money(run.estimated_cost_usd)}</span>
      </div>
      {category && (
        <p className="mt-2 text-[12px] text-muted-foreground">{category}</p>
      )}
      {run.failure_reason && (
        <p className="mt-2 text-[12px] leading-5 text-muted-foreground">
          {run.failure_reason}
        </p>
      )}
      {excluded && (
        <p className="mt-2 rounded-md border border-border bg-muted/60 px-2.5 py-2 text-[12px] text-muted-foreground">
          Infrastructure unavailable; excluded from site scoring.
        </p>
      )}
      {run.steps && run.steps.length > 0 && (
        <div className="mt-3">
          <ReplayDialog run={run} />
        </div>
      )}
    </article>
  );
}

export function AgentTaskCards({ tasks }: { tasks: AgentTaskSummary[] }) {
  if (tasks.length === 0) {
    return (
      <p className="rounded-xl border bg-card p-5 text-xs text-muted-foreground">
        No agent task results are available.
      </p>
    );
  }
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {tasks.map((task, taskIndex) => (
        <section
          key={task.id ?? `${task.task_type}-${taskIndex}`}
          className="surface min-w-0 overflow-hidden"
        >
          <div className="flex flex-wrap items-start justify-between gap-3 border-b p-4 sm:p-5">
            <div className="min-w-0">
              <h3 className="text-sm font-semibold">
                {taskName(task.task_type)}
              </h3>
              <p className="mt-1 text-[12px] leading-5 text-muted-foreground">
                {task.runs_completed ?? task.runs.length} of{" "}
                {task.requested_runs ?? task.runs.length} runs completed
                {task.eligible_runs != null
                  ? ` · ${task.eligible_runs} eligible`
                  : ""}
                {task.consistency === null || task.consistency === undefined
                  ? ""
                  : task.consistency
                    ? " · consistent"
                    : " · mixed outcomes"}
              </p>
            </div>
            <Outcome value={task.outcome} />
          </div>
          {task.failure_reason && (
            <p className="border-b px-4 py-3 text-[12px] leading-5 text-muted-foreground sm:px-5">
              {task.failure_reason}
            </p>
          )}
          {task.outcome === "UNAVAILABLE" && (
            <p className="border-b px-4 py-3 text-[12px] leading-5 text-muted-foreground sm:px-5">
              Agent infrastructure was unavailable. These runs are excluded from
              site scoring.
            </p>
          )}
          <div className="space-y-2 p-4 sm:p-5">
            {task.runs.length === 0 ? (
              <p className="text-[12px] text-muted-foreground">
                Run details are not available.
              </p>
            ) : (
              task.runs.map((run, runIndex) => (
                <RunRow
                  key={run.id ?? `${run.run_number}-${runIndex}`}
                  run={run}
                  excluded={
                    run.outcome === "UNAVAILABLE" ||
                    run.failure_category === "infra_error"
                  }
                />
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
