"""Test case schemas.

The LLM never writes executable code. It writes a *declarative* spec (ApiSpec / UiSpec)
which the execution engine interprets. That keeps runs deterministic and auditable.
"""

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.requirement import REQ_ID_PATTERN

TC_ID_PATTERN = r"^TC-\d{3}$"

# Placeholders the executor resolves at runtime against the demo target's debug endpoints.
PLACEHOLDERS = ("{{RESET_TOKEN}}", "{{EXPIRED_RESET_TOKEN}}")


class TestType(str, Enum):
    positive = "positive"
    negative = "negative"
    boundary = "boundary"
    security = "security"


class ApiSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["api"] = "api"
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str = Field(pattern=r"^/", description="Path on the target, e.g. /api/login")
    json_body: dict | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    repeat: int = Field(default=1, ge=1, le=20, description="Send N times; assert on the last")
    expected_status: int = Field(ge=100, le=599)
    expected_body_contains: list[str] = Field(default_factory=list)


class UiAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["goto", "fill", "click", "expect_text", "expect_url"]
    selector: str | None = None
    value: str | None = None

    @model_validator(mode="after")
    def check_arguments(self) -> "UiAction":
        needs_selector = {"fill", "click"}
        needs_value = {"goto", "fill", "expect_text", "expect_url"}
        if self.action in needs_selector and not self.selector:
            raise ValueError(f"'{self.action}' requires a selector")
        if self.action in needs_value and not self.value:
            raise ValueError(f"'{self.action}' requires a value")
        return self


class UiSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["ui"] = "ui"
    steps: list[UiAction] = Field(min_length=1)


TestSpec = Annotated[ApiSpec | UiSpec, Field(discriminator="kind")]


class TestCaseDraft(BaseModel):
    """What the Generator LLM must produce for each test. IDs are assigned by the harness."""

    model_config = ConfigDict(extra="forbid")
    __test__ = False  # stop pytest collecting this class

    title: str = Field(min_length=5)
    source_requirement_id: str = Field(pattern=REQ_ID_PATTERN)
    test_type: TestType
    tags: list[str] = Field(min_length=1)
    preconditions: list[str] = Field(default_factory=list)
    steps_description: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=5)
    confidence: float = Field(ge=0.0, le=1.0)
    covers_criteria: list[str] = Field(
        default_factory=list,
        description="AC-REQ.N IDs this test proves. Must reference criteria of source_requirement_id.",
    )
    spec: TestSpec

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})


class TestCase(TestCaseDraft):
    """A validated, traceable test case with a harness-assigned ID."""

    __test__ = False

    id: str = Field(pattern=TC_ID_PATTERN)


class TestCaseUpdate(BaseModel):
    """Fields a manager can edit before approving a generated test plan."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=5, max_length=500)
    preconditions: list[str]
    steps_description: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=5)
    spec: TestSpec
