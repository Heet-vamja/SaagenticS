from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.engines.agent.actions import TaskType
from app.models.domain import WorkflowStatus
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
    verification: Literal["NOT_INDEPENDENTLY_VERIFIED"] = "NOT_INDEPENDENTLY_VERIFIED"


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
    created_at: datetime
    has_screenshot: bool = False
