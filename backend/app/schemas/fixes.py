from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FixAction = Literal[
    "PROMPT_COPIED",
    "ASSET_DOWNLOADED",
    "FIX_APPLIED",
    "USEFUL",
    "NOT_USEFUL",
    "PRICE_INTERESTED",
    "PRICE_NOT_INTERESTED",
    "PACK_DOWNLOADED",
]


class FixEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_type: FixAction
    fix_key: str = Field(default="", max_length=64, pattern=r"^[a-zA-Z0-9_.-]*$")


class CustomerFix(BaseModel):
    key: str
    title: str
    category: str
    severity: str
    url: str | None
    evidence: str
    recommendation: str
    template_version: str
    prompts: dict[str, str]
    status: Literal["OPEN", "PROMPT_COPIED", "FIX_APPLIED", "STILL_FAILING"]


class CustomerAsset(BaseModel):
    key: str
    filename: str
    content: str
    media_type: str
    placement: str
    provenance: str
    validated: bool
    version: str


class FixVerification(BaseModel):
    key: str
    title: str
    url: str | None
    status: Literal["VERIFIED_FIXED", "STILL_FAILING", "NOT_RETESTED"]


class FixComparison(BaseModel):
    available: bool
    reason: str | None = None
    confirmed: int = 0
    total: int = 0
    results: list[FixVerification] = Field(default_factory=list)
    score_before: float | None = None
    score_after: float | None = None
    score_delta: float | None = None


class FixCenterRead(BaseModel):
    version: str
    fixes: list[CustomerFix]
    truncated: bool
    assets: list[CustomerAsset]
    missing_information: list[str]
    comparison: FixComparison
    events: list[str]
    agent_status: Literal["NOT_RUN"] = "NOT_RUN"
    agent_message: str = (
        "No agent task was run in this free static scan. Task success has not been measured."
    )


class FreeFixPreview(BaseModel):
    fixes: list[CustomerFix] = Field(default_factory=list, max_length=3)
    assets: list[CustomerAsset] = Field(default_factory=list, max_length=3)
    remaining_fixes: int
    remaining_assets: int
    truncated: bool = False
