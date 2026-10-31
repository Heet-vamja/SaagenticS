"""The model can select only these bounded operations; never executable code."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

TASKS = {
    "FIND_PRICING": "Navigate through this website and find the pricing page. Identify the available plans and their displayed prices. Do not submit any forms.",
    "FIND_DOCUMENTATION": "Find the product documentation or developer documentation and navigate to it.",
    "FIND_SIGNUP_FORM": "Find the signup, free trial, or demo booking form. Navigate to it and identify the required fields. Do not submit the form.",
}
TaskType = Literal["FIND_PRICING", "FIND_DOCUMENTATION", "FIND_SIGNUP_FORM"]


class AgentAction(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action: Literal[
        "navigate",
        "click",
        "fill",
        "select_option",
        "scroll",
        "get_page_snapshot",
        "go_back",
        "finish",
    ]
    element_id: str | None = Field(None, max_length=40)
    url: str | None = Field(None, max_length=2048)
    value: str | None = Field(None, max_length=200)
    direction: Literal["up", "down"] | None = None
    result: str | None = Field(None, max_length=2000)
    reason: str = Field(
        max_length=300, description="Brief observable action purpose, never hidden reasoning"
    )

    @model_validator(mode="after")
    def arguments(self):
        required = {
            "navigate": "url",
            "click": "element_id",
            "fill": "element_id",
            "select_option": "element_id",
            "scroll": "direction",
            "finish": "result",
        }
        if self.action in required and not getattr(self, required[self.action]):
            raise ValueError("Missing required action argument")
        if self.action in ("fill", "select_option") and self.value is None:
            raise ValueError("Missing value")
        allowed = {
            "navigate": {"url"},
            "click": {"element_id"},
            "fill": {"element_id", "value"},
            "select_option": {"element_id", "value"},
            "scroll": {"direction"},
            "finish": {"result"},
        }.get(self.action, set())
        for field in ("url", "element_id", "value", "direction", "result"):
            if field not in allowed and getattr(self, field) is not None:
                raise ValueError("Unexpected action argument")
        return self
