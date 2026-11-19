from pydantic import BaseModel, ConfigDict, Field, field_validator

REQ_ID_PATTERN = r"^REQ-\d{3}$"


class Requirement(BaseModel):
    """A single functional constraint extracted from the PRD (Node 1 output)."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=REQ_ID_PATTERN, description="Stable ID, e.g. REQ-001")
    title: str = Field(min_length=3)
    description: str = Field(min_length=10)
    tags: list[str] = Field(min_length=1, description="e.g. security, api, ui, validation")
    acceptance_criteria: list[str] = Field(default_factory=list)
    ambiguous: bool = False
    ambiguity_note: str | None = None

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})


class RequirementSet(BaseModel):
    """Envelope the extractor LLM must return."""

    requirements: list[Requirement] = Field(min_length=1)
