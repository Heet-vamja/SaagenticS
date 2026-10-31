import type { Finding, Project, Scan } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    signal: init?.signal ?? AbortSignal.timeout(15000),
  });
  const body = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = body?.error?.details
      ?.map((d: { message: string }) => d.message)
      .join(". ");
    throw new Error(
      detail ||
        body?.error?.message ||
        "We couldn’t reach the service. Please try again.",
    );
  }
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
  projects: () => all<Project>("/projects"),
  scans: () => all<Scan>("/scans"),
  createProject: (name: string, website_url: string) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, website_url }),
    }),
  createScan: (project_id: string) =>
    request<Scan>("/scans", {
      method: "POST",
      body: JSON.stringify({ project_id }),
    }),
  scan: (id: string) => request<Scan>(`/scans/${encodeURIComponent(id)}`),
  findings: (id: string) =>
    all<Finding>(`/scans/${encodeURIComponent(id)}/findings`),
};
