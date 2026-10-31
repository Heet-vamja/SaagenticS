export type Project = {
  id: string;
  name: string;
  website_url: string;
  created_at: string;
  updated_at: string;
};
export type Scan = {
  id: string;
  project_id: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  pages_discovered: number;
  pages_crawled: number;
  pages_failed: number;
  error_summary: string | null;
  crawl_metadata: Record<string, unknown>;
  overall_score: number | null;
  audit_summary?: AuditSummary;
  created_at?: string;
  started_at: string | null;
  completed_at: string | null;
};
export type Finding = {
  id: string;
  title: string;
  description: string;
  category: string;
  severity: string;
  recommendation: string | null;
  evidence: Record<string, unknown>;
  confidence: number | null;
};

export type CrawledPage = {
  id: string;
  scan_id: string;
  url: string;
  status_code: number | null;
  title: string | null;
  meta_description: string | null;
  canonical_url: string | null;
  crawl_depth: number;
  content_type: string | null;
  crawl_error: string | null;
  page_metadata: Record<string, unknown>;
};

export type AgentTaskType =
  "FIND_PRICING" | "FIND_DOCUMENTATION" | "FIND_SIGNUP_FORM";
export type AgentTest = {
  id: string;
  scan_id: string;
  task_type: AgentTaskType;
  task_description: string;
  model_identifier: string;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED" | "PASSED";
  starting_url: string;
  allowed_domains: string[];
  steps_completed: number;
  final_url: string | null;
  agent_declared_outcome: string | null;
  failure_reason: string | null;
  execution_duration: number | null;
  started_at: string | null;
  completed_at: string | null;
  metrics: Record<string, unknown>;
  verification: "NOT_INDEPENDENTLY_VERIFIED";
};
export type AgentStep = {
  id: string;
  step_number: number;
  page_url: string;
  action_type: string;
  reasoning_summary: string;
  action_arguments: Record<string, unknown>;
  action_result: Record<string, unknown>;
  observation_summary: Record<string, unknown>;
  error_message: string | null;
  duration_ms: number;
  has_screenshot: boolean;
};

export type StaticCheck = {
  rule: string;
  bucket: string;
  status: "PASS" | "FAIL" | "UNKNOWN" | "INFO" | "NOT_APPLICABLE";
  title: string;
  description: string;
  recommendation: string;
  severity: string;
  url: string | null;
  evidence: Record<string, unknown>;
  weight: number;
};
export type AuditSummary = {
  version?: string;
  phase?: string;
  score_kind?: string;
  score?: number | null;
  category_scores?: Record<string, number | null>;
  weights?: Record<string, number>;
  coverage?: Record<string, { evaluated: number; total: number }>;
  counts?: Record<string, number>;
  provisional?: boolean;
  checks?: StaticCheck[];
  limitations?: string[];
  browser_pages_done?: number;
  browser_pages_total?: number;
};
export type StaticReport = {
  project: { id?: string; name: string; website_url: string };
  scan: {
    id?: string;
    status: string;
    overall_score: number | null;
    pages_discovered: number;
    pages_crawled: number;
    pages_failed: number;
    started_at: string | null;
    completed_at: string | null;
    audit_summary: AuditSummary;
  };
  score_kind: string;
  rubric: string | null;
  audited: boolean;
  findings: Finding[];
  priority_fixes: Finding[];
  verification: string;
  sharing: string;
};
export type ScanComparison = {
  available: boolean;
  reason?: string;
  before: string | null;
  after: string;
  score_delta?: number | null;
  coverage_changed?: boolean;
  note?: string;
  added?: StaticCheck[];
  resolved?: StaticCheck[];
  unchanged?: StaticCheck[];
  not_retested?: StaticCheck[];
};
