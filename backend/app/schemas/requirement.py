from pydantic import BaseModel, ConfigDict, Field, field_validator

REQ_ID_PATTERN = r"^REQ-\d{3}$"
AC_ID_PATTERN = r"^AC-\d{3}\.\d+$"


class AcceptanceCriterion(BaseModel):
    """A single measurable acceptance criterion attached to a Requirement."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        pattern=AC_ID_PATTERN,
        description="Stable ID, e.g. AC-006.1 (derived from parent REQ-006)",
    )
    text: str = Field(min_length=5, description="Given/When/Then or plain statement")
    source_quote: str | None = Field(
        default=None, description="Verbatim phrase from the PRD that this criterion encodes"
    )
    ambiguous: bool = Field(
        default=False,
        description="True when the PRD gives no measurable threshold for this criterion",
    )
    ambiguity_note: str | None = Field(
        default=None, description="Why this criterion is ambiguous and what is missing"
    )


class Requirement(BaseModel):
    """A single functional constraint extracted from the PRD (Node 1 output)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=REQ_ID_PATTERN, description="Stable ID, e.g. REQ-001")
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)
    tags: list[str] = Field(min_length=1, description="e.g. security, api, ui, validation")
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    ambiguous: bool = False
    ambiguity_note: str | None = None

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})


class RequirementSet(BaseModel):
    """Envelope the extractor LLM must return."""

    requirements: list[Requirement] = Field(min_length=1)
