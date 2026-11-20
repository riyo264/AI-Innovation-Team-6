from typing import Literal

from pydantic import BaseModel

FailureType = Literal[
    "json_decode",
    "schema",
    "traceability",
    "coverage",
    "criterion_id_unknown",
    "criterion_uncovered",
]


class ValidationFailure(BaseModel):
    """One problem the Validator found. Fed back verbatim to the Generator on retry."""

    attempt: int
    error_type: FailureType
    message: str
    item_index: int | None = None
    requirement_id: str | None = None
    criterion_id: str | None = None
    raw_excerpt: str | None = None

    def as_feedback(self) -> str:
        where = f"item[{self.item_index}]" if self.item_index is not None else "output"
        if self.requirement_id and self.item_index is None:
            where = self.requirement_id
        if self.criterion_id and self.item_index is None:
            where = self.criterion_id
        line = f"- {where} ({self.error_type}): {self.message}"
        if self.raw_excerpt:
            line += f"\n  offending JSON: {self.raw_excerpt}"
        return line

