"""Node 3: the Harness.

Checks, per item:
  1. JSON decodes                          -> json_decode
  2. Pydantic TestCaseDraft schema         -> schema
  3. source_requirement_id is a known REQ  -> traceability
  4. covers_criteria refs valid AC IDs     -> criterion_id_unknown
Then across the whole suite:
  5. every requirement has >= 1 test case  -> coverage
  6. every criterion has >= 1 test         -> criterion_uncovered

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


def _ac_ids_for_requirement(requirements: list[dict], req_id: str) -> set[str]:
    """Return the set of AC IDs declared on a requirement."""
    for req in requirements:
        if req["id"] == req_id:
            return {ac["id"] for ac in req.get("acceptance_criteria", [])}
    return set()


def validate_generation(
    raw: str,
    requirements: list[dict],
    already_valid: list[dict],
    attempt: int,
) -> tuple[list[dict], list[ValidationFailure]]:
    requirement_ids = {r["id"] for r in requirements}
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

        # Check 3: source_requirement_id must be a known REQ
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

        # Check 4: every AC ID in covers_criteria must belong to source_requirement_id
        if draft.covers_criteria:
            valid_ac_ids = _ac_ids_for_requirement(requirements, draft.source_requirement_id)
            unknown = [ac for ac in draft.covers_criteria if ac not in valid_ac_ids]
            if unknown:
                failures.append(
                    ValidationFailure(
                        attempt=attempt,
                        error_type="criterion_id_unknown",
                        item_index=idx,
                        message=(
                            f"covers_criteria contains unknown AC IDs {unknown} for "
                            f"{draft.source_requirement_id}. "
                            f"Valid AC IDs: {sorted(valid_ac_ids) or 'none (no criteria defined)'}"
                        ),
                        raw_excerpt=excerpt(item),
                    )
                )
                continue

        case = TestCase(id=f"TC-{next_number:03d}", **draft.model_dump())
        new_valid.append(case.model_dump(mode="json"))
        next_number += 1

    # Check 5: every requirement has at least one test
    covered_reqs = {tc["source_requirement_id"] for tc in already_valid + new_valid}
    for req_id in sorted(requirement_ids - covered_reqs):
        failures.append(
            ValidationFailure(
                attempt=attempt,
                error_type="coverage",
                requirement_id=req_id,
                message=f"{req_id} has no valid test case. Generate at least one.",
            )
        )

    # Check 6: every criterion has at least one test pointing to it
    # Build a map: criterion_id -> list of test case IDs that cover it
    all_valid = already_valid + new_valid
    covered_criteria: dict[str, list[str]] = {}
    for tc in all_valid:
        for ac_id in tc.get("covers_criteria", []):
            covered_criteria.setdefault(ac_id, []).append(tc["id"])

    for req in requirements:
        for ac in req.get("acceptance_criteria", []):
            if ac.get("ambiguous"):
                continue  # ambiguous criteria can't be tested; skip
            ac_id = ac["id"]
            req_id = req["id"]
            if ac_id not in covered_criteria:
                failures.append(
                    ValidationFailure(
                        attempt=attempt,
                        error_type="criterion_uncovered",
                        requirement_id=req_id,
                        criterion_id=ac_id,
                        message=(
                            f"{ac_id} on {req_id} has no test. "
                            f"Generate a test with covers_criteria containing \"{ac_id}\". "
                            f"Criterion text: \"{ac['text']}\""
                        ),
                    )
                )

    return new_valid, failures


async def validator(state: PipelineState) -> dict:
    attempt = state.get("retry_count", 0)
    new_valid, failures = validate_generation(
        state.get("raw_generation", ""),
        state["requirements"],
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
