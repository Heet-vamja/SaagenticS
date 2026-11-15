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
  FreeScanAccepted,
  FreeReport,
  FixCenter,
  FreeFixPreview,
  FixAction,
  RobotsPreset,
  DashboardOverview,
  DashboardSite,
  DashboardVariant,
  DeliveryRules,
  SiteJob,
  SiteSettings,
  SiteJobKind,
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
  if (response.status === 204) return undefined as T;
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

async function fetchDownload(path: string) {
  let response: Response;
  try {
    response = await fetch(`/api/v1${path}`, {
      signal: AbortSignal.timeout(30000),
    });
  } catch {
    throw new Error(
      "Download timed out or the service is unavailable. Please retry.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.error?.message ?? "Could not download this file.");
  }
  return response.blob();
}

const bearer = (token: string) => ({ Authorization: `Bearer ${token}` });

export const api = {
  dashboardSites: (token: string) =>
    request<{ sites: DashboardSite[] }>("/dashboard/sites", {
      headers: bearer(token),
    }),
  dashboardOverview: (token: string, host: string, days: number) =>
    request<DashboardOverview>(
      `/dashboard/sites/${encodeURIComponent(host)}/overview?days=${days}`,
      { headers: bearer(token) },
    ),
  createSite: (
    token: string,
    body: { host: string; origin: string; name: string },
  ) =>
    request<DashboardSite>("/dashboard/sites", {
      method: "POST",
      headers: bearer(token),
      body: JSON.stringify(body),
    }),
  siteSettings: (token: string, host: string) =>
    request<SiteSettings>(
      `/dashboard/sites/${encodeURIComponent(host)}/settings`,
      { headers: bearer(token) },
    ),
  updateSite: (
    token: string,
    host: string,
    body: Partial<Pick<SiteSettings, "name" | "origin" | "routing_enabled">>,
  ) =>
    request<SiteSettings>(`/dashboard/sites/${encodeURIComponent(host)}`, {
      method: "PATCH",
      headers: bearer(token),
      body: JSON.stringify(body),
    }),
  setDelivery: (token: string, host: string, rules: DeliveryRules | null) =>
    request<SiteSettings>(
      `/dashboard/sites/${encodeURIComponent(host)}/delivery`,
      rules
        ? { method: "PUT", headers: bearer(token), body: JSON.stringify(rules) }
        : { method: "DELETE", headers: bearer(token) },
    ),
  removeSite: (token: string, host: string) =>
    request<void>(`/dashboard/sites/${encodeURIComponent(host)}`, {
      method: "DELETE",
      headers: bearer(token),
    }),
  siteVariants: (token: string, host: string) =>
    request<{ variants: DashboardVariant[] }>(
      `/dashboard/sites/${encodeURIComponent(host)}/variants`,
      { headers: bearer(token) },
    ),
  publishVariant: (token: string, host: string, version: number) =>
    request<{ published: number }>(
      `/dashboard/sites/${encodeURIComponent(host)}/variants/${version}/publish`,
      { method: "POST", headers: bearer(token) },
    ),
  siteJobs: (token: string, host: string) =>
    request<{ jobs: SiteJob[] }>(
      `/dashboard/sites/${encodeURIComponent(host)}/jobs`,
      { headers: bearer(token) },
    ),
  startJob: (token: string, host: string, kind: SiteJobKind) =>
    request<SiteJob>(`/dashboard/sites/${encodeURIComponent(host)}/jobs`, {
      method: "POST",
      headers: bearer(token),
      body: JSON.stringify({ kind }),
    }),
  refreshSessions: (token: string, host: string) =>
    request<{ requests: number; created: number; extended: number }>(
      `/dashboard/sites/${encodeURIComponent(host)}/sessions`,
      { method: "POST", headers: bearer(token) },
    ),
  verificationStatus: (website_url: string) =>
    request<{
      verified: boolean;
      domain: string;
      email_hint?: string;
      development_email?: string | null;
      development_access?: boolean;
      development_skip_available?: boolean;
    }>(`/verification/status?website_url=${encodeURIComponent(website_url)}`),
  requestCode: (website_url: string, email?: string, candidate_id?: string) =>
    request<{ challenge_id: string; email_hint: string; expires_in: number }>(
      "/verification/request",
      {
        method: "POST",
        body: JSON.stringify({ website_url, email, candidate_id }),
      },
    ),
  skipVerification: (
    website_url: string,
    email?: string,
    candidate_id?: string,
  ) =>
    request<{ verified: boolean }>("/verification/skip", {
      method: "POST",
      body: JSON.stringify({ website_url, email, candidate_id }),
    }),
  skipPayment: (token: string) =>
    request<{ development_payment_skipped: boolean }>(
      `/free-reports/${encodeURIComponent(token)}/skip-payment`,
      { method: "POST" },
    ),
  verifyCode: (challenge_id: string, code: string) =>
    request<{ verified: boolean }>("/verification/verify", {
      method: "POST",
      body: JSON.stringify({ challenge_id, code }),
    }),
  discoverEmails: (website_url: string) =>
    request<{
      candidates: { id: string; email_hint: string }[];
      message: string;
    }>("/verification/discover", {
      method: "POST",
      body: JSON.stringify({ website_url }),
      signal: AbortSignal.timeout(25000),
    }),
  reportTarget: (token: string) =>
    request<{ website_url: string }>(
      `/free-reports/${encodeURIComponent(token)}/verification-target`,
    ),
  checkout: (token: string) =>
    request<{ url: string }>(
      `/free-reports/${encodeURIComponent(token)}/checkout`,
      { method: "POST" },
    ),
  startFreeScan: (website_url: string) =>
    request<FreeScanAccepted>("/free-scans", {
      method: "POST",
      body: JSON.stringify({ website_url }),
    }),
  freeReport: (token: string) =>
    request<FreeReport>(`/free-reports/${encodeURIComponent(token)}`),
  fixPreview: (token: string) =>
    request<FreeFixPreview>(
      `/free-reports/${encodeURIComponent(token)}/fix-preview`,
    ),
  fixCenter: (token: string, preset: RobotsPreset) =>
    request<FixCenter>(
      `/free-reports/${encodeURIComponent(token)}/fix-center?robots_preset=${preset}`,
    ),
  fixEvent: (token: string, event_type: FixAction, fix_key = "") =>
    request<{ recorded: boolean }>(
      `/free-reports/${encodeURIComponent(token)}/fix-events`,
      {
        method: "POST",
        body: JSON.stringify({ event_type, fix_key }),
      },
    ),
  rescanFreeReport: (token: string) =>
    request<FreeScanAccepted>(
      `/free-reports/${encodeURIComponent(token)}/rescan`,
      { method: "POST" },
    ),
  downloadFixPack: (token: string, preset: RobotsPreset) =>
    fetchDownload(
      `/free-reports/${encodeURIComponent(token)}/fix-pack.zip?robots_preset=${preset}`,
    ),
  downloadFixAsset: (token: string, filename: string, preset: RobotsPreset) =>
    fetchDownload(
      `/free-reports/${encodeURIComponent(token)}/assets/${encodeURIComponent(filename)}?robots_preset=${preset}`,
    ),
  exportFreeReport: async (token: string) => {
    let response: Response;
    try {
      response = await fetch(
        `/api/v1/free-reports/${encodeURIComponent(token)}/export.pdf`,
        { signal: AbortSignal.timeout(30000) },
      );
    } catch {
      throw new Error(
        "PDF export timed out or the service is unavailable. Please retry.",
      );
    }
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      throw new Error(
        body?.error?.message ?? "Could not download this report.",
      );
    }
    return response.blob();
  },
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
