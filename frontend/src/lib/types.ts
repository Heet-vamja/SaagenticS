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
  "FIND_PRICING" | "FIND_CONTACT" | "FIND_DOCUMENTATION" | "FIND_SIGNUP_FORM";
export type AgentOutcome =
  "SUCCEEDED" | "FAILED" | "INCONCLUSIVE" | "UNAVAILABLE";
export type AgentVerificationMethod = "rules" | "judged" | "unverified";
export type AgentFailureCategory =
  | "element_not_found"
  | "blocked_by_captcha_or_bot_protection"
  | "content_requires_js"
  | "ambiguous_navigation"
  | "step_limit"
  | "loop"
  | "malformed_output"
  | "infra_error"
  | "other";
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
  verification: "NOT_INDEPENDENTLY_VERIFIED" | "RULE_VERIFIED" | "LLM_JUDGED";
  task_test_id?: string | null;
  run_number?: number;
  outcome?: AgentOutcome | null;
  verification_method?: AgentVerificationMethod;
  verification_evidence?: Record<string, unknown>;
  failure_category?: AgentFailureCategory | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  estimated_cost_usd?: number | null;
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
  prompt_tokens?: number;
  completion_tokens?: number;
  llm_latency_ms?: number;
  error_category?: AgentFailureCategory | null;
  screenshot_url?: string;
};
export type AgentConfig = {
  model_identifier: string;
  configured: boolean;
  max_steps: number;
  duration_seconds: number;
  token_budget: number;
  action_delay: number;
  default_runs: number;
  max_runs: number;
  free_limits_enabled: boolean;
  task_limit: number;
  runs_limit: number;
  tasks: { task_type: AgentTaskType; name: string; goal: string }[];
};
export type AgentTask = {
  id: string;
  scan_id: string;
  task_type: AgentTaskType;
  task_description: string;
  requested_runs: number;
  status: "PENDING" | "RUNNING" | "COMPLETED" | "FAILED";
  outcome: AgentOutcome | null;
  consistency: boolean | null;
  eligible_runs: number;
  runs_completed: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  deadline: string | null;
  policy_snapshot: Record<string, unknown>;
  failure_reason: string | null;
};
export type AgentTaskRunSummary = {
  id?: string;
  run_number: number;
  status?: string;
  outcome?: AgentOutcome | null;
  verification_method?: AgentVerificationMethod;
  failure_category?: AgentFailureCategory | null;
  failure_reason?: string | null;
  steps_completed?: number;
  execution_duration?: number | null;
  prompt_tokens?: number;
  completion_tokens?: number;
  estimated_cost_usd?: number | null;
  model_identifier?: string;
  final_url?: string | null;
  steps?: AgentTaskStepSummary[];
};
export type AgentTaskStepSummary = {
  id?: string;
  step_number: number;
  page_url: string;
  action_type: string;
  reason?: string;
  reasoning_summary?: string;
  duration_ms: number;
  error_message?: string | null;
  has_screenshot?: boolean;
  screenshot_url?: string;
};
/** Aggregate task summary used by workspace cards and redacted shared reports. */
export type AgentTaskSummary = {
  id?: string;
  scan_id?: string;
  task_type: AgentTaskType;
  task_description?: string;
  requested_runs?: number;
  status?: string;
  outcome?: AgentOutcome | null;
  consistency?: boolean | null;
  eligible_runs?: number;
  runs_completed?: number;
  failure_reason?: string | null;
  runs: AgentTaskRunSummary[];
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
  static_score?: number | null;
  agent?: {
    agent_score?: number | null;
    eligible_runs?: number;
    eligible_tasks?: number;
    excluded_infra_runs?: number;
    inconclusive_runs?: number;
    incomplete_tasks?: number;
    fallback_reason?: string | null;
  };
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
  score_components?: {
    before?: Record<string, unknown>;
    after?: Record<string, unknown>;
    static_delta?: number | null;
    agent_delta?: number | null;
    score_comparable?: boolean;
  };
  agent_coverage_changed?: boolean;
  agent_task_changes?: {
    task_type: AgentTaskType;
    before: AgentOutcome | null;
    after: AgentOutcome | null;
    changed: boolean;
    before_eligible_runs: number;
    after_eligible_runs: number;
  }[];
  coverage_changed?: boolean;
  note?: string;
  added?: StaticCheck[];
  resolved?: StaticCheck[];
  unchanged?: StaticCheck[];
  not_retested?: StaticCheck[];
};
