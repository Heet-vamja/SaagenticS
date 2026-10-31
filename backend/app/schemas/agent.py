from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.engines.agent.actions import TaskType
from app.engines.agent.contracts import FailureCategory
from app.models.domain import ScanStatus, WorkflowStatus
from app.schemas.api import ReadModel


class AgentTestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: TaskType
    allowed_domains: list[str] = Field(default_factory=list, max_length=5)


class AgentTestRead(ReadModel):
    id: UUID
    scan_id: UUID
    task_type: str
    task_description: str
    starting_url: str
    allowed_domains: list[str]
    model_identifier: str
    status: WorkflowStatus
    steps_completed: int
    final_url: str | None
    agent_declared_outcome: str | None
    failure_reason: str | None
    execution_duration: float | None
    started_at: datetime | None
    completed_at: datetime | None
    metrics: dict[str, Any]
    task_test_id: UUID | None = None
    run_number: int = 1
    outcome: Literal["SUCCEEDED", "FAILED", "INCONCLUSIVE", "UNAVAILABLE"] | None = None
    verification_method: Literal["rules", "judged", "unverified"] = "unverified"
    verification_evidence: dict[str, Any] = Field(default_factory=dict)
    failure_category: FailureCategory | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float | None = None
    verification: Literal["NOT_INDEPENDENTLY_VERIFIED", "RULE_VERIFIED", "LLM_JUDGED"] = (
        "NOT_INDEPENDENTLY_VERIFIED"
    )

    @model_validator(mode="after")
    def set_verification_label(self):
        self.verification = {
            "rules": "RULE_VERIFIED",
            "judged": "LLM_JUDGED",
            "unverified": "NOT_INDEPENDENTLY_VERIFIED",
        }[self.verification_method]
        return self


class AgentTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_type: Literal["FIND_PRICING", "FIND_CONTACT", "FIND_SIGNUP_FORM", "FIND_DOCUMENTATION"]
    runs: int | None = Field(default=None, ge=1, le=3)


class AgentTaskRead(ReadModel):
    id: UUID
    scan_id: UUID
    task_type: str
    task_description: str
    requested_runs: int
    status: ScanStatus
    outcome: Literal["SUCCEEDED", "FAILED", "INCONCLUSIVE", "UNAVAILABLE"] | None
    consistency: bool | None
    eligible_runs: int
    runs_completed: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    deadline: datetime | None
    policy_snapshot: dict[str, Any]
    failure_reason: str | None


class AgentStepRead(ReadModel):
    id: UUID
    workflow_test_id: UUID
    step_number: int
    page_url: str
    observation_summary: dict[str, Any]
    action_type: str
    action_arguments: dict[str, Any]
    reasoning_summary: str
    action_result: dict[str, Any]
    error_message: str | None
    duration_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0
    llm_latency_ms: int = 0
    error_category: FailureCategory | None = None
    created_at: datetime
    has_screenshot: bool = False
