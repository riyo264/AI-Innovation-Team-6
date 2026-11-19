"""Graph state. Everything is plain JSON (dicts/lists) so the Postgres checkpointer can
serialise it without custom serde. Pydantic models are re-hydrated inside nodes."""

import operator
from typing import Annotated, TypedDict


class PipelineState(TypedDict, total=False):
    run_id: str
    prd_text: str
    team: list[dict]  # Employee dumps

    # Node 1
    requirements: list[dict]  # Requirement dumps

    # Node 2 <-> Node 3 loop
    raw_generation: str  # last raw generator output
    valid_test_cases: Annotated[list[dict], operator.add]  # TestCase dumps, accumulated
    pending_failures: list[dict]  # failures from the latest validation pass
    validation_log: Annotated[list[dict], operator.add]  # every failure, every attempt
    retry_count: int
    retries_exhausted: bool

    # Node 4 (graph pauses after this)
    delegation_plan: dict  # DelegationPlan dump

    # Injected by the manager via update_state before resuming
    approved_plan: dict  # ManagerApproval dump

    # Distributor
    final_assignments: list[dict]
    overrides: list[dict]

    # Observability
    llm_calls: Annotated[list[dict], operator.add]
