"""Future pipeline boundaries. No engine is wired to scan creation.

Concrete implementations should live in separate crawling, auditing, workflows,
scoring, recommendations and reports modules when those features are built.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.models.domain import Category, Severity


@dataclass(frozen=True)
class CrawlPolicy:
    allowed_host: str
    max_pages: int = 50
    max_redirects: int = 5
    timeout_seconds: float = 15
    max_response_bytes: int = 5_000_000


@dataclass(frozen=True)
class PageSnapshot:
    url: str
    html: str
    status_code: int


@dataclass(frozen=True)
class AuditObservation:
    category: Category
    severity: Severity
    title: str
    description: str
    evidence: dict[str, Any]


class Crawler(Protocol):
    def crawl(self, url: str, policy: CrawlPolicy) -> Sequence[PageSnapshot]: ...


class AuditCheck(Protocol):
    def evaluate(self, page: PageSnapshot) -> Sequence[AuditObservation]: ...


@dataclass(frozen=True)
class WorkflowResult:
    task_name: str
    passed: bool
    failure_reason: str | None
    evidence_location: str | None
    duration_seconds: float


class WorkflowRunner(Protocol):
    def run(self, task_name: str, starting_url: str, policy: CrawlPolicy) -> WorkflowResult: ...


class ScoringEngine(Protocol):
    def score(self, findings: Sequence[AuditObservation]) -> dict[Category, float]: ...


class RecommendationProvider(Protocol):
    def recommend(self, findings: Sequence[AuditObservation]) -> Sequence[str]: ...


class ReportGenerator(Protocol):
    def generate(self, scan_id: UUID) -> bytes: ...
