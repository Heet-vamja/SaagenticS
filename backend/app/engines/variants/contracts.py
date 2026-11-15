"""Typed contracts for variant generation. Model output is untrusted until validated."""

from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict, Field


@dataclass
class EvidencePage:
    """One rendered page: what a JavaScript-capable visitor actually sees."""

    path: str
    title: str
    text: str
    status: int


@dataclass
class EvidenceData:
    """A same-origin JSON response the page loaded while rendering."""

    path: str
    body: object


@dataclass
class Evidence:
    origin: str
    pages: list[EvidencePage] = field(default_factory=list)
    data: list[EvidenceData] = field(default_factory=list)
    limited: bool = False


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SizeStock(_Strict):
    size: str = Field(min_length=1, max_length=20)
    in_stock: bool | None = Field(
        description="True or false only when the evidence states it; otherwise null."
    )


class Product(_Strict):
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9][a-z0-9-]*$")
    name: str = Field(min_length=1, max_length=200)
    path: str = Field(
        min_length=1, max_length=300, description="Same-origin page path, starting with /."
    )
    price: float = Field(ge=0, description="Exact price as shown, in the store currency.")
    category: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=600)
    sizes: list[SizeStock] = Field(default_factory=list, max_length=40)


class Policy(_Strict):
    topic: str = Field(min_length=1, max_length=60)
    text: str = Field(min_length=1, max_length=1200)
    path: str | None = Field(default=None, max_length=300)


class KeyTask(_Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=400)


class Catalog(_Strict):
    """Facts extracted from the site. Every value must come from the evidence."""

    store_name: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=400)
    currency: str = Field(min_length=3, max_length=3, description="ISO 4217 code, e.g. INR.")
    products: list[Product] = Field(default_factory=list, max_length=500)
    policies: list[Policy] = Field(default_factory=list, max_length=30)
    key_tasks: list[KeyTask] = Field(default_factory=list, max_length=20)
