from typing import Literal

from pydantic import BaseModel, Field


class SignalCounts(BaseModel):
    passed: int = Field(default=0, ge=0)
    issues: int = Field(default=0, ge=0)
    inconclusive: int = Field(default=0, ge=0)
    informational: int = Field(default=0, ge=0)
    not_applicable: int = Field(default=0, ge=0)


class RequirementCoverage(BaseModel):
    id: str
    stage: Literal["FIND", "READ", "ACT"]
    level: Literal["MUST", "SHOULD", "MAY"]
    title: str
    implementation: Literal["PARTIAL", "NOT_IMPLEMENTED"]
    assessment: Literal["PARTIAL_EVIDENCE", "INCONCLUSIVE", "NOT_TESTED"]
    observations: SignalCounts
    limitations: str


class StandardsCoverage(BaseModel):
    mapping_version: str
    spec_version: str
    reviewed_on: str
    source_url: str
    conformance: Literal["NOT_ASSESSED"] = "NOT_ASSESSED"
    checks_truncated: bool = False
    requirements: list[RequirementCoverage]
