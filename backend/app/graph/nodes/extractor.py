"""Node 1: PRD -> list[Requirement]."""

import json

from pydantic import ValidationError

from app.graph.prompts import EXTRACTOR_SYSTEM, EXTRACTOR_USER
from app.graph.state import PipelineState
from app.llm.base import LLMClient
from app.llm.json_utils import extract_json
from app.schemas.requirement import RequirementSet


def _parse(text: str) -> RequirementSet:
    return RequirementSet.model_validate(extract_json(text))


async def extractor(state: PipelineState, *, llm: LLMClient) -> dict:
    user = EXTRACTOR_USER.format(prd=state["prd_text"])
    result = await llm.complete(node="extractor", system=EXTRACTOR_SYSTEM, user=user)
    calls = [result.telemetry("extractor", 0)]

    try:
        parsed = _parse(result.text)
    except (json.JSONDecodeError, ValidationError) as exc:
        # One corrective retry; if that also fails the run is marked failed upstream.
        retry_user = f"{user}\n\nYour previous output was invalid:\n{exc}\nReturn corrected JSON."
        result = await llm.complete(node="extractor", system=EXTRACTOR_SYSTEM, user=retry_user)
        calls.append(result.telemetry("extractor", 1))
        parsed = _parse(result.text)

    return {
        "requirements": [r.model_dump() for r in parsed.requirements],
        "llm_calls": calls,
    }
