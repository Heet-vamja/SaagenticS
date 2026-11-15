from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.urls import validate_website_url
from app.schemas.standards import StandardsCoverage


class CheckRead(BaseModel):
    rule: str
    bucket: str
    status: Literal["PASS", "FAIL", "UNKNOWN", "INFO", "NOT_APPLICABLE"]
    title: str
    description: str
    recommendation: str
    severity: str
    url: str | None
    evidence: dict[str, Any]
    weight: int


class ReportProject(BaseModel):
    id: UUID | None = None
    name: str
    website_url: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ReportScan(BaseModel):
    id: UUID | None = None
    project_id: UUID | None = None
    status: str
    overall_score: float | None = Field(ge=0, le=100)
    pages_discovered: int
    pages_crawled: int
    pages_failed: int
    started_at: datetime | None
    completed_at: datetime | None
    audit_summary: dict[str, Any]
    created_at: datetime | None = None
    error_summary: str | None = None
    crawl_metadata: dict[str, Any] | None = None


class ReportFinding(BaseModel):
    id: str
    scan_id: UUID | None = None
    page_id: UUID | None = None
    category: str
    severity: str
    title: str
    description: str
    evidence: dict[str, Any]
    recommendation: str | None
    confidence: float | None


class ReportRead(BaseModel):
    project: ReportProject
    scan: ReportScan
    score_kind: Literal["STATIC_READINESS", "AGENT_READINESS", "COMBINED_READINESS"]
    score_components: dict[str, Any] = Field(default_factory=dict)
    agent_tasks: list[dict[str, Any]] = Field(default_factory=list)
    rubric: str | None
    audited: bool
    findings: list[ReportFinding]
    priority_fixes: list[ReportFinding]
    verification: Literal["AGENT_TASK_SUCCESS_NOT_EVALUATED", "AGENT_RESULTS_REPORTED"]
    sharing: Literal["WORKSPACE", "ANYONE_WITH_LINK"]


class ComparisonRead(BaseModel):
    available: bool
    reason: str | None = None
    before: UUID | None
    after: UUID
    score_delta: float | None = None
    score_components: dict[str, Any] | None = None
    agent_coverage_changed: bool | None = None
    agent_task_changes: list[dict[str, Any]] = Field(default_factory=list)
    added: list[CheckRead] | None = None
    resolved: list[CheckRead] | None = None
    unchanged: list[CheckRead] | None = None
    not_retested: list[CheckRead] | None = None
    coverage_changed: bool | None = None
    note: str | None = None


class ShareRead(BaseModel):
    id: UUID
    path: str
    expires_at: datetime
    visibility: Literal["ANYONE_WITH_LINK"]


class FreeScanCreate(BaseModel):
    website_url: str = Field(min_length=1, max_length=2048)

    @field_validator("website_url")
    @classmethod
    def valid_website_url(cls, value: str) -> str:
        normalized = validate_website_url(value)
        if len(normalized) > 2048:
            raise ValueError("Website URL must be at most 2048 characters")
        return normalized


class FreeScanAccepted(BaseModel):
    report_path: str
    status: str
    expires_at: datetime


class FreeCategoryScore(BaseModel):
    name: str
    score: float | None
    weight: int
    tested: bool
    evaluated: int
    total: int


class FreeCoverage(BaseModel):
    evaluated: int
    total: int
    passed: int
    problems: int
    untested: int
    checks_total: int
    checks_passed: int
    checks_failed: int
    checks_inconclusive: int
    checks_informational: int
    checks_not_applicable: int


class FreeCheck(BaseModel):
    category: str
    status: Literal["PASS", "FAIL", "UNKNOWN", "INFO", "NOT_APPLICABLE"]
    title: str
    description: str
    url: str | None
    evidence_summary: str | None
    recommendation: str | None


class FreeInsight(BaseModel):
    category: str
    severity: str
    title: str
    description: str
    evidence_url: str | None
    evidence_summary: str | None
    recommendation: str | None


class FreeAccessPolicy(BaseModel):
    user_agent: str
    kind: Literal["SCANNER", "AI_BOT"]
    policy: Literal["ALLOWED", "DISALLOWED", "UNKNOWN"]
    sampled_url: str
    source_url: str
    http_status: int | None


class FreeReportRead(BaseModel):
    standards_coverage: StandardsCoverage | None = None
    full_report_unlocked: bool = False
    development_access: bool = False
    development_skip_available: bool = False
    development_payment_skipped: bool = False
    rescan_until: datetime | None = None
    status: str
    website: str
    phase: str
    progress_message: str
    score_version: str
    score: float | None
    score_status: Literal["PRELIMINARY", "UNAVAILABLE"]
    access_policies: list[FreeAccessPolicy] = Field(default_factory=list)
    score_explanation: str
    category_scores: list[FreeCategoryScore]
    coverage: FreeCoverage
    checks: list[FreeCheck]
    checks_truncated: bool
    insights: list[FreeInsight]
    pages_crawled: int
    pages_discovered: int
    pages_failed: int
    failure_message: str | None
