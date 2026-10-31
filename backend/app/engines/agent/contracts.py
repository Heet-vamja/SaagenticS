"""Shared execution results; model claims and verification remain separate."""

from typing import Any, Literal

from pydantic import BaseModel, Field

FailureCategory = Literal[
    "element_not_found",
    "blocked_by_captcha_or_bot_protection",
    "content_requires_js",
    "ambiguous_navigation",
    "step_limit",
    "loop",
    "malformed_output",
    "infra_error",
    "other",
]
Outcome = Literal["SUCCEEDED", "FAILED", "INCONCLUSIVE", "UNAVAILABLE"]
VerificationMethod = Literal["rules", "judged", "unverified"]


class TaskJudgment(BaseModel):
    success: bool | None
    reason: str = Field(max_length=400)


class SuccessCheck(BaseModel):
    success: bool | None
    reason: str = Field(max_length=400)
    evidence: dict[str, Any] = Field(default_factory=dict)
    failure_category: FailureCategory | None = None


class RunResult(BaseModel):
    outcome: Outcome
    verification_method: VerificationMethod = "unverified"
    verification_evidence: dict[str, Any] = Field(default_factory=dict)
    failure_category: FailureCategory | None = None
    failure_reason: str | None = None
    agent_declared_outcome: str | None = None
    steps_completed: int = 0
    final_url: str | None = None
    execution_duration: float = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    model_identifier: str = ""
