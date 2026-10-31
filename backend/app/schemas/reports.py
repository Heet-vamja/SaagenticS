from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


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
    score_kind: Literal["STATIC_READINESS"]
    rubric: str | None
    audited: bool
    findings: list[ReportFinding]
    priority_fixes: list[ReportFinding]
    verification: Literal["AGENT_TASK_SUCCESS_NOT_EVALUATED"]
    sharing: Literal["WORKSPACE", "ANYONE_WITH_LINK"]


class ComparisonRead(BaseModel):
    available: bool
    reason: str | None = None
    before: UUID | None
    after: UUID
    score_delta: float | None = None
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
