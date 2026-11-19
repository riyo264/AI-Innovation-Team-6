"""Node 3: the Harness.

Checks, per item:
  1. JSON decodes                          -> json_decode
  2. Pydantic TestCaseDraft schema         -> schema
  3. source_requirement_id is a known REQ  -> traceability
Then across the whole suite:
  4. every requirement has >= 1 test case  -> coverage

Valid items are kept (and given harness IDs); only failures are sent back to the Generator.
"""

import json

from pydantic import ValidationError

from app.graph.state import PipelineState
from app.llm.json_utils import excerpt, extract_json
from app.schemas.test_case import TestCase, TestCaseDraft
from app.schemas.validation import ValidationFailure


def _format_pydantic(exc: ValidationError) -> str:
    return "; ".join(
        f"{'.'.join(str(p) for p in e['loc']) or '<root>'}: {e['msg']}" for e in exc.errors()
    )


def validate_generation(
    raw: str,
    requirement_ids: set[str],
    already_valid: list[dict],
    attempt: int,
) -> tuple[list[dict], list[ValidationFailure]]:
    failures: list[ValidationFailure] = []
    new_valid: list[dict] = []

    try:
        payload = extract_json(raw)
        items = payload["test_cases"] if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise TypeError("'test_cases' must be a list")
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        failures.append(
            ValidationFailure(
                attempt=attempt,
                error_type="json_decode",
                message=f"Output is not {{'test_cases': [...]}}: {exc}",
                raw_excerpt=excerpt(raw),
            )
        )
        items = []

    next_number = len(already_valid) + 1
    for idx, item in enumerate(items):
        if isinstance(item, dict):
            item = {k: v for k, v in item.items() if k != "id"}  # harness owns IDs
        try:
            draft = TestCaseDraft.model_validate(item)
        except ValidationError as exc:
            failures.append(
                ValidationFailure(
                    attempt=attempt,
                    error_type="schema",
                    item_index=idx,
                    message=_format_pydantic(exc),
                    raw_excerpt=excerpt(item),
                )
            )
            continue

        if draft.source_requirement_id not in requirement_ids:
            failures.append(
                ValidationFailure(
                    attempt=attempt,
                    error_type="traceability",
                    item_index=idx,
                    message=(
                        f"source_requirement_id '{draft.source_requirement_id}' does not exist. "
                        f"Valid IDs: {sorted(requirement_ids)}"
                    ),
                    raw_excerpt=excerpt(item),
                )
            )
            continue

        case = TestCase(id=f"TC-{next_number:03d}", **draft.model_dump())
        new_valid.append(case.model_dump(mode="json"))
        next_number += 1

    covered = {tc["source_requirement_id"] for tc in already_valid + new_valid}
    for req_id in sorted(requirement_ids - covered):
        failures.append(
            ValidationFailure(
                attempt=attempt,
                error_type="coverage",
                requirement_id=req_id,
                message=f"{req_id} has no valid test case. Generate at least one.",
            )
        )

    return new_valid, failures


async def validator(state: PipelineState) -> dict:
    attempt = state.get("retry_count", 0)
    requirement_ids = {r["id"] for r in state["requirements"]}
    new_valid, failures = validate_generation(
        state.get("raw_generation", ""),
        requirement_ids,
        state.get("valid_test_cases", []),
        attempt,
    )
    dumped = [f.model_dump() for f in failures]
    return {
        "valid_test_cases": new_valid,
        "pending_failures": dumped,
        "validation_log": dumped,
        "retry_count": attempt + (1 if failures else 0),
    }


def route_after_validation(state: PipelineState, max_retries: int) -> str:
    """Bounded retry: back to the Generator at most `max_retries` times."""
    if state.get("pending_failures") and state.get("retry_count", 0) <= max_retries:
        return "generator"
    return "delegator"
