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
  overall_score: number | null;
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
