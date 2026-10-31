import type {
  AgentTest,
  AgentStep,
  AgentTaskType,
  AgentTask,
  AgentConfig,
  CrawledPage,
  Finding,
  Project,
  Scan,
  StaticReport,
  ScanComparison,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
      signal: init?.signal ?? AbortSignal.timeout(15000),
    });
  } catch (error) {
    const timeout =
      error instanceof DOMException &&
      ["TimeoutError", "AbortError"].includes(error.name);
    throw new ApiError(
      timeout
        ? "The request timed out. Please try again."
        : "We couldn’t connect to the service. Please try again.",
      0,
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.error?.details
      ?.map((d: { message: string }) => d.message)
      .join(". ");
    throw new ApiError(
      detail ||
        body?.error?.message ||
        "We couldn’t reach the service. Please try again.",
      response.status,
    );
  }
  if (body === null)
    throw new ApiError(
      "The service returned an unreadable response. Please try again.",
      response.status,
    );
  return body as T;
}

// Fetch bounded pages so dashboard counts reflect all records, not just the first page.
async function all<T>(path: string): Promise<T[]> {
  const records: T[] = [];
  for (let offset = 0; ; offset += 100) {
    const page = await request<T[]>(`${path}?limit=100&offset=${offset}`);
    records.push(...page);
    if (page.length < 100) return records;
  }
}

export const api = {
  report: (id: string) =>
    request<StaticReport>(`/scans/${encodeURIComponent(id)}/report`),
  sharedReport: (token: string) =>
    request<StaticReport>(`/shares/${encodeURIComponent(token)}`),
  comparison: (id: string, before?: string) =>
    request<ScanComparison>(
      `/scans/${encodeURIComponent(id)}/comparison${before ? `?before=${encodeURIComponent(before)}` : ""}`,
    ),
  history: (id: string) =>
    all<Scan>(`/projects/${encodeURIComponent(id)}/history`),
  shareReport: (id: string) =>
    request<{
      id: string;
      path: string;
      expires_at: string;
      visibility: string;
    }>(`/scans/${encodeURIComponent(id)}/shares`, { method: "POST" }),
  revokeShares: (id: string) =>
    request<{ revoked: boolean }>(
      `/scans/${encodeURIComponent(id)}/shares/revoke`,
      { method: "POST" },
    ),
  exportReport: async (
    id: string,
    format: "json" | "csv" | "pdf",
    shared = false,
  ) => {
    let response: Response;
    try {
      response = await fetch(
        `/api/v1/${shared ? "shares" : "scans"}/${encodeURIComponent(id)}/export?format=${format}`,
        { signal: AbortSignal.timeout(30000) },
      );
    } catch {
      throw new Error(
        "Export timed out or the service is unavailable. Please retry.",
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(body?.error?.message ?? "Could not export this report.");
    }
    return response.blob();
  },
  agentTestsForScans: async (scans: Scan[]) => {
    const tests: AgentTest[] = [];
    for (let index = 0; index < scans.length; index += 6) {
      const group = await Promise.all(
        scans
          .slice(index, index + 6)
          .map((scan) =>
            all<AgentTest>(`/scans/${encodeURIComponent(scan.id)}/agent-tests`),
          ),
      );
      tests.push(...group.flat());
    }
    return tests.sort((a, b) =>
      (b.started_at ?? "9999").localeCompare(a.started_at ?? "9999"),
    );
  },
  agentTests: (scan: string) =>
    all<AgentTest>(`/scans/${encodeURIComponent(scan)}/agent-tests`),
  agentConfig: () => request<AgentConfig>("/agent-config"),
  agentTasks: (scan: string) =>
    all<AgentTask>(`/scans/${encodeURIComponent(scan)}/agent-tasks`),
  createAgentTask: (scan: string, task_type: AgentTaskType, runs?: number) =>
    request<AgentTask>(`/scans/${encodeURIComponent(scan)}/agent-tasks`, {
      method: "POST",
      body: JSON.stringify({ task_type, ...(runs ? { runs } : {}) }),
    }),
  agentTask: (id: string) =>
    request<AgentTask>(`/agent-tasks/${encodeURIComponent(id)}`),
  agentTaskRuns: (id: string) =>
    request<AgentTest[]>(`/agent-tasks/${encodeURIComponent(id)}/runs`),
  createAgentTest: (
    scan: string,
    task_type: AgentTaskType,
    allowed_domains: string[],
  ) =>
    request<AgentTest>(`/scans/${encodeURIComponent(scan)}/agent-tests`, {
      method: "POST",
      body: JSON.stringify({ task_type, allowed_domains }),
    }),
  agentTest: (id: string) =>
    request<AgentTest>(`/agent-tests/${encodeURIComponent(id)}`),
  agentSteps: (id: string) =>
    all<AgentStep>(`/agent-tests/${encodeURIComponent(id)}/steps`),
  projects: () => all<Project>("/projects"),
  scans: () => all<Scan>("/scans"),
  createProject: (name: string, website_url: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, website_url }),
    }),
  createScan: (project_id: string) =>
    request<Scan>(`/projects/${encodeURIComponent(project_id)}/scans`, {
      method: "POST",
    }),
  project: (id: string) =>
    request<Project>(`/projects/${encodeURIComponent(id)}`),
  pages: (id: string, offset = 0) =>
    request<CrawledPage[]>(
      `/scans/${encodeURIComponent(id)}/pages?limit=30&offset=${offset}`,
    ),
  page: (scan: string, id: string) =>
    request<CrawledPage>(
      `/scans/${encodeURIComponent(scan)}/pages/${encodeURIComponent(id)}`,
    ),
  scan: (id: string) => request<Scan>(`/scans/${encodeURIComponent(id)}`),
  findings: (id: string) =>
    all<Finding>(`/scans/${encodeURIComponent(id)}/findings`),
};
