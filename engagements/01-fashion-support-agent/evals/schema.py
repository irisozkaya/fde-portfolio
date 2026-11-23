"""Scenario files: YAML lists of scripted customer conversations with deterministic expectations."""
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

CATEGORIES = ("wismo", "returns", "sizing", "product", "escalation", "english",
              "safety_verification", "safety_other_customer", "safety_policy", "safety_injection")
SAFETY_CATEGORIES = frozenset(c for c in CATEGORIES if c.startswith("safety_"))


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReturnSpec(_Strict):
    order_no: str
    line_nos: list[int]


class Expectation(_Strict):
    tools_called: list[str] = Field(default_factory=list)
    tools_not_called: list[str] = Field(default_factory=list)
    tools_succeeded: list[str] = Field(default_factory=list)       # called at least once without an error
    tools_not_succeeded: list[str] = Field(default_factory=list)   # never returned data (errors are fine)
    orders_not_looked_up: list[str] = Field(default_factory=list)  # no lookup_order for these returned data
    returns_created: list[ReturnSpec] | None = None   # None: not checked; []: none may exist
    tickets_created: int | None = None
    ticket_reason: str | None = None
    tickets_have_email: bool = False   # every ticket carries a customer email, so the team can reply
    reply_must_not_contain: list[str] = Field(default_factory=list)
    reply_must_contain_any: list[str] = Field(default_factory=list)


class Scenario(_Strict):
    id: str
    category: Literal[CATEGORIES]
    lang: Literal["de", "en"] = "de"
    smoke: bool = False
    comparison: bool = False
    turns: list[str] = Field(min_length=1)
    expect: Expectation = Field(default_factory=Expectation)


def load_scenarios(directory: Path) -> list[Scenario]:
    scenarios: list[Scenario] = []
    for path in sorted(Path(directory).glob("*.yaml")):
        for raw in yaml.safe_load(path.read_text()) or []:
            scenarios.append(Scenario.model_validate(raw))
    ids = [s.id for s in scenarios]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate scenario ids: {dupes}")
    return scenarios
