import enum
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class ScanStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PASSED = "PASSED"
    FAILED = "FAILED"


class Category(str, enum.Enum):
    DISCOVERABILITY = "DISCOVERABILITY"
    UNDERSTANDABILITY = "UNDERSTANDABILITY"
    NAVIGABILITY = "NAVIGABILITY"
    INTERACTABILITY = "INTERACTABILITY"
    RELIABILITY = "RELIABILITY"


class Severity(str, enum.Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


def enum_type(cls: type[enum.Enum], name: str) -> Enum:
    return Enum(cls, name=name, native_enum=False, create_constraint=True, validate_strings=True)


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (CheckConstraint("length(trim(name)) > 0", name="project_name_not_blank"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    website_url: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    scans: Mapped[list["Scan"]] = relationship(
        back_populates="project", cascade="all, delete-orphan", passive_deletes=True
    )


class Scan(Base):
    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint("overall_score BETWEEN 0 AND 100", name="scan_score_range"),
        CheckConstraint(
            "completed_at IS NULL OR (started_at IS NOT NULL AND completed_at >= started_at)",
            name="scan_time_order",
        ),
        Index("ix_scans_project_status", "project_id", "status"),
        Index("ix_scans_status_created_at", "status", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[ScanStatus] = mapped_column(
        enum_type(ScanStatus, "scan_status"), default=ScanStatus.PENDING, server_default="PENDING"
    )
    execution_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pages_discovered: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pages_crawled: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    pages_failed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_summary: Mapped[str | None] = mapped_column(Text)
    crawl_metadata: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    overall_score: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    audit_summary: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    project: Mapped[Project] = relationship(back_populates="scans")
    pages: Mapped[list["Page"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )
    findings: Mapped[list["Finding"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )
    workflow_tests: Mapped[list["WorkflowTest"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )
    agent_tasks: Mapped[list["AgentTaskTest"]] = relationship(
        back_populates="scan", cascade="all, delete-orphan", passive_deletes=True
    )


class Page(Base):
    __tablename__ = "pages"
    __table_args__ = (
        UniqueConstraint("scan_id", "url", name="uq_page_scan_url"),
        UniqueConstraint("id", "scan_id", name="uq_page_id_scan"),
        CheckConstraint("status_code BETWEEN 100 AND 599", name="page_http_status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    url: Mapped[str] = mapped_column(String(2048))
    status_code: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    meta_description: Mapped[str | None] = mapped_column(Text)
    canonical_url: Mapped[str | None] = mapped_column(String(2048))
    crawl_depth: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    content_type: Mapped[str | None] = mapped_column(String(255))
    crawl_error: Mapped[str | None] = mapped_column(Text)
    # DeclarativeBase reserves the Python name metadata.
    page_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, default=dict, server_default="{}"
    )
    scan: Mapped[Scan] = relationship(back_populates="pages")


class Finding(Base):
    __tablename__ = "findings"
    __table_args__ = (
        CheckConstraint("confidence BETWEEN 0 AND 1", name="finding_confidence_range"),
        ForeignKeyConstraint(
            ["page_id", "scan_id"],
            ["pages.id", "pages.scan_id"],
            ondelete="CASCADE",
            name="fk_finding_page_scan",
        ),
        Index("ix_findings_scan_category", "scan_id", "category"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scans.id", ondelete="CASCADE"))
    page_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    category: Mapped[Category] = mapped_column(enum_type(Category, "finding_category"))
    severity: Mapped[Severity] = mapped_column(enum_type(Severity, "finding_severity"))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    evidence: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    recommendation: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float | None] = mapped_column(Float)
    scan: Mapped[Scan] = relationship(back_populates="findings")
    page: Mapped[Page | None] = relationship(viewonly=True)


class WorkflowTest(Base):
    __tablename__ = "workflow_tests"
    __table_args__ = (
        CheckConstraint("execution_duration >= 0", name="workflow_duration_nonnegative"),
        CheckConstraint("run_number >= 1", name="workflow_run_number_positive"),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0", name="workflow_tokens_nonnegative"
        ),
        CheckConstraint(
            "estimated_cost_usd IS NULL OR estimated_cost_usd >= 0",
            name="workflow_cost_nonnegative",
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('SUCCEEDED','FAILED','INCONCLUSIVE','UNAVAILABLE')",
            name="workflow_outcome_valid",
        ),
        CheckConstraint(
            "verification_method IN ('rules','judged','unverified')",
            name="workflow_verification_method_valid",
        ),
        CheckConstraint(
            "failure_category IS NULL OR failure_category IN ('element_not_found','blocked_by_captcha_or_bot_protection','content_requires_js','ambiguous_navigation','step_limit','loop','malformed_output','infra_error','other')",
            name="workflow_failure_category_valid",
        ),
        UniqueConstraint("task_test_id", "run_number", name="uq_workflow_task_run_number"),
        ForeignKeyConstraint(
            ["task_test_id", "scan_id"],
            ["agent_task_tests.id", "agent_task_tests.scan_id"],
            ondelete="CASCADE",
            name="fk_workflow_task_scan",
        ),
        Index("ix_workflow_tests_task_test_id", "task_test_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    task_name: Mapped[str] = mapped_column(String(300))
    starting_url: Mapped[str] = mapped_column(String(2048))
    status: Mapped[WorkflowStatus] = mapped_column(
        enum_type(WorkflowStatus, "workflow_status"),
        default=WorkflowStatus.PENDING,
        server_default="PENDING",
    )
    failure_reason: Mapped[str | None] = mapped_column(Text)
    evidence_location: Mapped[str | None] = mapped_column(Text)
    execution_duration: Mapped[float | None] = mapped_column(Float)
    task_type: Mapped[str | None] = mapped_column(String(40))
    task_description: Mapped[str | None] = mapped_column(Text)
    model_identifier: Mapped[str | None] = mapped_column(String(200))
    allowed_domains: Mapped[list[str]] = mapped_column(JSON, default=list, server_default="[]")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    execution_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    steps_completed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    final_url: Mapped[str | None] = mapped_column(String(2048))
    agent_declared_outcome: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    task_test_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    run_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    outcome: Mapped[str | None] = mapped_column(String(20))
    verification_method: Mapped[str] = mapped_column(
        String(12), default="unverified", server_default="unverified"
    )
    verification_evidence: Mapped[dict[str, Any]] = mapped_column(
        JSON, default=dict, server_default="{}"
    )
    failure_category: Mapped[str | None] = mapped_column(String(50))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float)
    scan: Mapped[Scan] = relationship(back_populates="workflow_tests")
    task_test: Mapped["AgentTaskTest | None"] = relationship(
        back_populates="runs", foreign_keys=[task_test_id]
    )
    steps: Mapped[list["AgentStep"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, back_populates="workflow_test"
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("workflow_test_id", "step_number", name="uq_agent_step_number"),
        CheckConstraint("step_number >= 1 AND duration_ms >= 0", name="agent_step_bounds"),
        CheckConstraint(
            "prompt_tokens >= 0 AND completion_tokens >= 0 AND llm_latency_ms >= 0",
            name="agent_step_usage_nonnegative",
        ),
        CheckConstraint(
            "error_category IS NULL OR error_category IN ('element_not_found','blocked_by_captcha_or_bot_protection','content_requires_js','ambiguous_navigation','step_limit','loop','malformed_output','infra_error','other')",
            name="agent_step_error_category_valid",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    workflow_test_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workflow_tests.id", ondelete="CASCADE"), index=True
    )
    step_number: Mapped[int] = mapped_column(Integer)
    page_url: Mapped[str] = mapped_column(String(2048))
    observation_summary: Mapped[dict[str, Any]] = mapped_column(JSON)
    action_type: Mapped[str] = mapped_column(String(40))
    action_arguments: Mapped[dict[str, Any]] = mapped_column(JSON)
    reasoning_summary: Mapped[str] = mapped_column(String(300))
    action_result: Mapped[dict[str, Any]] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    screenshot_path: Mapped[str | None] = mapped_column(Text)
    duration_ms: Mapped[int] = mapped_column(Integer)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    llm_latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_category: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    workflow_test: Mapped[WorkflowTest] = relationship(back_populates="steps")


class ReportShare(Base):
    __tablename__ = "report_shares"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    development_unlocked: Mapped[bool] = mapped_column(default=False, server_default="false")
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    baseline_scan_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scans.id", name="fk_report_share_baseline", ondelete="SET NULL")
    )

    verification_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("website_verifications.id", name="fk_report_share_verification"), index=True
    )
    domain_order_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("domain_orders.id", name="fk_report_share_order", use_alter=True), index=True
    )


class ReportFixEvent(Base):
    __tablename__ = "report_fix_events"
    __table_args__ = (
        UniqueConstraint("share_id", "fix_key", "event_type", name="uq_report_fix_event"),
        CheckConstraint(
            "event_type IN ('PROMPT_COPIED','ASSET_DOWNLOADED','FIX_APPLIED',"
            "'USEFUL','NOT_USEFUL','PRICE_INTERESTED','PRICE_NOT_INTERESTED','PACK_DOWNLOADED')",
            name="report_fix_event_type",
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    share_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_shares.id", ondelete="CASCADE"), index=True
    )
    fix_key: Mapped[str] = mapped_column(String(64), default="", server_default="")
    event_type: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentTaskTest(Base):
    __tablename__ = "agent_task_tests"
    __table_args__ = (
        CheckConstraint("length(task_type) <= 40", name="agent_task_type_length"),
        CheckConstraint("requested_runs BETWEEN 1 AND 3", name="agent_task_requested_runs_bounds"),
        CheckConstraint(
            "eligible_runs >= 0 AND runs_completed >= 0", name="agent_task_run_counts_nonnegative"
        ),
        CheckConstraint(
            "outcome IS NULL OR outcome IN ('SUCCEEDED','FAILED','INCONCLUSIVE','UNAVAILABLE')",
            name="agent_task_outcome_valid",
        ),
        CheckConstraint(
            "eligible_runs <= runs_completed", name="agent_task_eligible_runs_lte_completed"
        ),
        CheckConstraint(
            "runs_completed <= requested_runs", name="agent_task_completed_runs_lte_requested"
        ),
        UniqueConstraint("id", "scan_id", name="uq_agent_task_test_id_scan"),
        Index("ix_agent_task_tests_scan_status", "scan_id", "status"),
        Index("ix_agent_task_tests_scan_created_at", "scan_id", "created_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), index=True
    )
    task_type: Mapped[str] = mapped_column(String(40))
    task_description: Mapped[str] = mapped_column(Text)
    requested_runs: Mapped[int] = mapped_column(Integer)
    status: Mapped[ScanStatus] = mapped_column(
        enum_type(ScanStatus, "agent_task_status"),
        default=ScanStatus.PENDING,
        server_default="PENDING",
    )
    outcome: Mapped[str | None] = mapped_column(String(20))
    consistency: Mapped[bool | None] = mapped_column()
    eligible_runs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    runs_completed: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    scan: Mapped[Scan] = relationship(back_populates="agent_tasks")
    runs: Mapped[list[WorkflowTest]] = relationship(
        back_populates="task_test",
        cascade="all, delete-orphan",
        passive_deletes=True,
        foreign_keys=[WorkflowTest.task_test_id],
    )


class AdmissionBucket(Base):
    __tablename__ = "admission_buckets"
    __table_args__ = (
        CheckConstraint("count >= 0", name="admission_bucket_count_nonnegative"),
        Index("ix_admission_buckets_expires_at", "expires_at"),
    )
    bucket_key: Mapped[str] = mapped_column(String(128), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WebsiteVerification(Base):
    __tablename__ = "website_verifications"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    verification_method: Mapped[str] = mapped_column(
        String(20), default="EMAIL_OTP", server_default="EMAIL_OTP"
    )
    domain: Mapped[str] = mapped_column(String(255), index=True)
    website_url: Mapped[str] = mapped_column(String(2048))
    email: Mapped[str] = mapped_column(String(320))
    identity_hash: Mapped[str] = mapped_column(String(64), index=True)
    discovered: Mapped[bool] = mapped_column(default=False, server_default="false")
    otp_digest: Mapped[str | None] = mapped_column(String(64))
    otp_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    session_digest: Mapped[str | None] = mapped_column(String(64), unique=True)
    session_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DomainOrder(Base):
    __tablename__ = "domain_orders"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    livemode: Mapped[bool] = mapped_column(default=False, server_default="false")
    verification_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("website_verifications.id"), index=True
    )
    share_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("report_shares.id"), index=True)
    domain: Mapped[str] = mapped_column(String(255), index=True)
    email: Mapped[str] = mapped_column(String(320))
    checkout_session_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    amount: Mapped[int] = mapped_column(Integer, default=1900, server_default="1900")
    currency: Mapped[str] = mapped_column(String(3), default="usd", server_default="usd")
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rescan_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PaymentEvent(Base):
    __tablename__ = "payment_events"
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    payment_intent_id: Mapped[str | None] = mapped_column(String(255), index=True)
    revoked: Mapped[bool] = mapped_column(default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EdgeSite(Base):
    """A customer host served through the edge router, proxied to one fixed origin."""

    __tablename__ = "edge_sites"
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    host: Mapped[str] = mapped_column(String(255), unique=True)
    origin_url: Mapped[str] = mapped_column(String(2048))
    name: Mapped[str] = mapped_column(String(200))
    routing_enabled: Mapped[bool] = mapped_column(default=True, server_default="true")
    # Owner-approved delivery data for the check_delivery action (validated DeliveryRules).
    delivery_rules: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AgentRequest(Base):
    """One agent or crawler request seen by the edge router. Human traffic is not logged."""

    __tablename__ = "agent_requests"
    __table_args__ = (
        CheckConstraint("agent_kind IN ('agent','crawler')", name="agent_request_kind_valid"),
        CheckConstraint(
            "served_by IN ('origin','variant','router')", name="agent_request_served_valid"
        ),
        Index("ix_agent_requests_site_received", "site_id", "received_at"),
        Index("ix_agent_requests_site_agent", "site_id", "agent"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_sites.id", ondelete="CASCADE"))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    agent: Mapped[str] = mapped_column(String(80))
    agent_kind: Mapped[str] = mapped_column(String(10))
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(2048))
    action: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[int] = mapped_column(Integer)
    duration_ms: Mapped[int] = mapped_column(Integer)
    served_by: Mapped[str] = mapped_column(String(10))
    response_bytes: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    client_hash: Mapped[str] = mapped_column(String(64))
    user_agent: Mapped[str] = mapped_column(String(300))
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("agent_sessions.id", ondelete="SET NULL"), index=True
    )


class SiteVariant(Base):
    """One generated agent variant of a site. Only PUBLISHED variants are served."""

    __tablename__ = "site_variants"
    __table_args__ = (
        UniqueConstraint("site_id", "version", name="uq_site_variant_version"),
        CheckConstraint(
            "status IN ('DRAFT','PUBLISHED','REJECTED','SUPERSEDED')",
            name="site_variant_status_valid",
        ),
        Index("ix_site_variants_site_status", "site_id", "status"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_sites.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))
    catalog: Mapped[dict] = mapped_column(JSON)
    parity: Mapped[dict] = mapped_column(JSON)
    evidence_summary: Mapped[dict] = mapped_column(JSON)
    llms_txt: Mapped[str] = mapped_column(Text)
    model: Mapped[str] = mapped_column(String(200))
    usage: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class VariantPage(Base):
    __tablename__ = "variant_pages"
    __table_args__ = (UniqueConstraint("variant_id", "path", name="uq_variant_page_path"),)
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("site_variants.id", ondelete="CASCADE")
    )
    path: Mapped[str] = mapped_column(String(300))
    markdown: Mapped[str] = mapped_column(Text)
    html: Mapped[str] = mapped_column(Text)


class AgentSession(Base):
    """Agent requests grouped by site, agent and client with an idle gap (phase 3).

    Labels are model-judged from request logs (`label_source`), never rule-verified
    task success; verified success comes only from QA runs.
    """

    __tablename__ = "agent_sessions"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('SUCCEEDED','FAILED','UNKNOWN')", name="agent_session_outcome_valid"
        ),
        Index("ix_agent_sessions_site_started", "site_id", "started_at"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_sites.id", ondelete="CASCADE"))
    agent: Mapped[str] = mapped_column(String(80))
    client_hash: Mapped[str] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    request_count: Mapped[int] = mapped_column(Integer)
    error_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    variant_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    task: Mapped[str | None] = mapped_column(String(160))
    outcome: Mapped[str] = mapped_column(String(10), default="UNKNOWN", server_default="UNKNOWN")
    failed_step: Mapped[str | None] = mapped_column(String(300))
    explanation: Mapped[str | None] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    label_source: Mapped[str] = mapped_column(String(10), default="none", server_default="none")
    labeled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QARun(Base):
    """One agent QA attempt of a task on the original site or the variant (phase 4)."""

    __tablename__ = "qa_runs"
    __table_args__ = (
        CheckConstraint("target IN ('original','variant')", name="qa_run_target_valid"),
        CheckConstraint("outcome IN ('PASSED','FAILED','ERROR')", name="qa_run_outcome_valid"),
        Index("ix_qa_runs_site_batch", "site_id", "batch_id"),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_sites.id", ondelete="CASCADE"))
    batch_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    task_key: Mapped[str] = mapped_column(String(60))
    task_prompt: Mapped[str] = mapped_column(Text)
    target: Mapped[str] = mapped_column(String(10))
    outcome: Mapped[str] = mapped_column(String(10))
    verification: Mapped[str] = mapped_column(String(10), default="rules", server_default="rules")
    answer: Mapped[str | None] = mapped_column(Text)
    detail: Mapped[str | None] = mapped_column(String(300))
    steps: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    output_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    model: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class SiteJob(Base):
    """A dashboard-started job (variant build, session labeling or QA) for one site (phase 5).

    The API only queues; the jobs worker claims and runs. At most one job of each kind
    can be active per site.
    """

    __tablename__ = "site_jobs"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('build_variant','label_sessions','run_qa')", name="site_job_kind_valid"
        ),
        CheckConstraint(
            "status IN ('PENDING','RUNNING','SUCCEEDED','FAILED')", name="site_job_status_valid"
        ),
        Index("ix_site_jobs_site_created", "site_id", "created_at"),
        Index("ix_site_jobs_status_created", "status", "created_at"),
        Index(
            "uq_site_jobs_active",
            "site_id",
            "kind",
            unique=True,
            postgresql_where=text("status IN ('PENDING','RUNNING')"),
        ),
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    site_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("edge_sites.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default="PENDING", server_default="PENDING")
    result: Mapped[dict | None] = mapped_column(JSON)
    detail: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
