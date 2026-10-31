from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.urls import validate_website_url
from app.models.domain import Category, ScanStatus, Severity, WorkflowStatus


class ProjectCreate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    website_url: str = Field(max_length=2048)

    @field_validator("website_url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        normalized = validate_website_url(value)
        if len(normalized) > 2048:
            raise ValueError("Website URL must be at most 2048 characters")
        return normalized


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectRead(ReadModel):
    id: UUID
    name: str
    website_url: str
    created_at: datetime
    updated_at: datetime


class ScanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: UUID


class ScanRead(ReadModel):
    id: UUID
    project_id: UUID
    status: ScanStatus
    pages_discovered: int
    pages_crawled: int
    pages_failed: int
    error_summary: str | None
    crawl_metadata: dict[str, Any]
    overall_score: float | None
    created_at: datetime
    audit_summary: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None


class FindingRead(ReadModel):
    id: UUID
    scan_id: UUID
    page_id: UUID | None
    category: Category
    severity: Severity
    title: str
    description: str
    evidence: dict[str, Any]
    recommendation: str | None
    confidence: float | None


class WorkflowRead(ReadModel):
    id: UUID
    scan_id: UUID
    task_name: str
    starting_url: str
    status: WorkflowStatus
    failure_reason: str | None
    evidence_location: str | None
    execution_duration: float | None


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class PageRead(ReadModel):
    id: UUID
    scan_id: UUID
    url: str
    status_code: int | None
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    crawl_depth: int
    content_type: str | None
    crawl_error: str | None
    page_metadata: dict[str, Any]
