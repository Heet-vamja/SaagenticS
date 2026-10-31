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
    )
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    status: Mapped[ScanStatus] = mapped_column(
        enum_type(ScanStatus, "scan_status"), default=ScanStatus.PENDING, server_default="PENDING"
    )
    overall_score: Mapped[float | None] = mapped_column(Float)
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
    scan: Mapped[Scan] = relationship(back_populates="workflow_tests")
