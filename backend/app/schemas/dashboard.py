from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SiteCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host: str = Field(min_length=1, max_length=253)
    origin: str = Field(min_length=1, max_length=2048)
    name: str = Field(min_length=1, max_length=200)


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["build_variant", "label_sessions", "run_qa"]


class SiteUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=200)
    origin: str | None = Field(default=None, min_length=1, max_length=2048)
    routing_enabled: bool | None = None
