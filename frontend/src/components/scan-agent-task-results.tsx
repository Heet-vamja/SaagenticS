"use client";

import { useCallback } from "react";
import { api } from "@/lib/api";
import type {
  AgentTaskRunSummary,
  AgentTaskSummary,
  AgentTest,
} from "@/lib/types";
import { useResource } from "@/lib/use-resource";
import { AgentTaskCards } from "./agent-task-cards";
import { InlineError, LoadingState } from "./states";

function hasActiveTask(tasks: Awaited<ReturnType<typeof loadTasks>>) {
  return tasks.some(
    (task) => task.status === "PENDING" || task.status === "RUNNING",
  );
}

export function AgentTaskStatusList({ tasks }: { tasks: AgentTaskSummary[] }) {
  if (tasks.length === 0) return null;
  return (
    <div className="mb-4 space-y-2 rounded-lg border bg-card p-4">
      {tasks.map((task, index) => (
        <div
          key={task.id ?? `${task.task_type}-${index}`}
          className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[10px]"
        >
          <span className="font-medium">
            {task.task_type.replaceAll("_", " ")}
          </span>
          <span className="text-muted-foreground">
            Task {task.status?.toLowerCase() ?? "status unavailable"}
            {task.runs.map((run) => (
              <span key={run.id ?? run.run_number}>
                {` · run ${run.run_number}: ${run.status?.toLowerCase() ?? run.outcome?.toLowerCase() ?? "pending"}`}
                {run.verification_method
                  ? `, ${run.verification_method === "rules" ? "rule verified" : run.verification_method === "judged" ? "LLM judged, lower assurance" : "unverified"}`
                  : ", verification pending"}
              </span>
            ))}
          </span>
        </div>
      ))}
    </div>
  );
}

async function loadTasks(scanId: string): Promise<AgentTaskSummary[]> {
  const tasks = await api.agentTasks(scanId);
  return Promise.all(
    tasks.map(async (task) => {
      const tests = await api.agentTaskRuns(task.id);
      const runs: AgentTaskRunSummary[] = await Promise.all(
        tests.map(async (test: AgentTest) => {
          const steps = await api.agentSteps(test.id);
          return {
            id: test.id,
            run_number: test.run_number ?? 1,
            status: test.status,
            outcome: test.outcome,
            verification_method: test.verification_method,
            failure_category: test.failure_category,
            failure_reason: test.failure_reason,
            steps_completed: test.steps_completed,
            execution_duration: test.execution_duration,
            prompt_tokens: test.prompt_tokens,
            completion_tokens: test.completion_tokens,
            estimated_cost_usd: test.estimated_cost_usd,
            model_identifier: test.model_identifier,
            final_url: test.final_url,
            steps: steps.map((step) => ({
              id: step.id,
              step_number: step.step_number,
              page_url: step.page_url,
              action_type: step.action_type,
              reason: step.reasoning_summary,
              reasoning_summary: step.reasoning_summary,
              duration_ms: step.duration_ms,
              error_message: step.error_message,
              has_screenshot: step.has_screenshot,
              screenshot_url: step.screenshot_url,
            })),
          };
        }),
      );
      return {
        id: task.id,
        scan_id: task.scan_id,
        task_type: task.task_type,
        task_description: task.task_description,
        requested_runs: task.requested_runs,
        status: task.status,
        outcome: task.outcome,
        consistency: task.consistency,
        eligible_runs: task.eligible_runs,
        runs_completed: task.runs_completed,
        failure_reason: task.failure_reason,
        runs,
      };
    }),
  );
}

export function ScanAgentTaskResults({ scanId }: { scanId: string }) {
  const load = useCallback(() => loadTasks(scanId), [scanId]);
  const { data, error, retry } = useResource(load, hasActiveTask);
  if (error) {
    return (
      <div className="space-y-3">
        <InlineError>{error.message}</InlineError>
        <button
          type="button"
          className="text-xs text-primary hover:underline"
          onClick={retry}
        >
          Retry loading agent task results
        </button>
      </div>
    );
  }
  if (!data) return <LoadingState />;
  return (
    <>
      <AgentTaskStatusList tasks={data} />
      <AgentTaskCards tasks={data} />
    </>
  );
}
