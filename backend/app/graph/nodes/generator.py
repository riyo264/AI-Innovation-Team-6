"""Node 2: requirements -> raw test case JSON. On retry, receives the exact error trace."""

import json

from app.graph.prompts import GENERATOR_RETRY_USER, GENERATOR_SYSTEM, GENERATOR_USER
from app.graph.state import PipelineState
from app.llm.base import LLMClient
from app.schemas.validation import ValidationFailure


async def generator(state: PipelineState, *, llm: LLMClient) -> dict:
    requirements = json.dumps(state["requirements"], indent=1)
    failures = [ValidationFailure.model_validate(f) for f in state.get("pending_failures") or []]
    attempt = state.get("retry_count", 0)

    if failures:
        accepted = [
            {"source_requirement_id": tc["source_requirement_id"], "title": tc["title"]}
            for tc in state.get("valid_test_cases", [])
        ]
        user = GENERATOR_RETRY_USER.format(
            requirements=requirements,
            accepted=json.dumps(accepted),
            failures="\n".join(f.as_feedback() for f in failures),
        )
    else:
        user = GENERATOR_USER.format(requirements=requirements)

    result = await llm.complete(node="generator", system=GENERATOR_SYSTEM, user=user)
    return {"raw_generation": result.text, "llm_calls": [result.telemetry("generator", attempt)]}
