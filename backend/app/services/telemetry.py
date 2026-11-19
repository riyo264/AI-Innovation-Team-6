"""Aggregates the numbers for the pitch dashboard."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Execution,
    LlmCall,
    RequirementRow,
    Run,
    TaskAssignmentRow,
    TestCaseRow,
    ValidationFailureRow,
)
from app.schemas.api import TelemetrySummary
from app.schemas.delegation import UNASSIGNED


async def summarize(session: AsyncSession, run_id: str | None = None) -> TelemetrySummary:
    def scoped(stmt, model):
        return stmt.where(model.run_id == run_id) if run_id else stmt

    async def scalar(stmt) -> int | float:
        return (await session.scalar(stmt)) or 0

    runs = await scalar(select(func.count(Run.id)).where(Run.id == run_id) if run_id
                        else select(func.count(Run.id)))
    cases = await scalar(scoped(select(func.count(TestCaseRow.id)), TestCaseRow))
    reqs = await scalar(scoped(select(func.count(RequirementRow.id)), RequirementRow))
    ambiguous = await scalar(scoped(
        select(func.count(RequirementRow.id)).where(RequirementRow.ambiguous.is_(True)), RequirementRow))

    devs = await scalar(scoped(
        select(func.count(func.distinct(TaskAssignmentRow.final_assignee)))
        .where(TaskAssignmentRow.final_assignee != UNASSIGNED), TaskAssignmentRow))
    unassigned = await scalar(scoped(
        select(func.count(TaskAssignmentRow.id)).where(TaskAssignmentRow.final_assignee == UNASSIGNED),
        TaskAssignmentRow))

    vfail = await scalar(scoped(select(func.count(ValidationFailureRow.id)), ValidationFailureRow))
    self_corrected = await scalar(scoped(
        select(func.count(func.distinct(ValidationFailureRow.run_id))), ValidationFailureRow))
    retry_loops = await scalar(scoped(
        select(func.count(LlmCall.id)).where(LlmCall.node == "generator", LlmCall.attempt > 0), LlmCall))

    calls = await scalar(scoped(select(func.count(LlmCall.id)), LlmCall))
    latency = await scalar(scoped(select(func.avg(LlmCall.latency_ms)), LlmCall))
    ptok = await scalar(scoped(select(func.sum(LlmCall.prompt_tokens)), LlmCall))
    ctok = await scalar(scoped(select(func.sum(LlmCall.completion_tokens)), LlmCall))

    overrides = await scalar(scoped(
        select(func.count(TaskAssignmentRow.id)).where(TaskAssignmentRow.overridden.is_(True)),
        TaskAssignmentRow))
    reviewed = await scalar(scoped(
        select(func.count(TaskAssignmentRow.id))
        .join(Run, Run.id == TaskAssignmentRow.run_id).where(Run.approved_at.is_not(None)),
        TaskAssignmentRow))

    passed = await scalar(scoped(select(func.count(Execution.id)).where(Execution.status == "passed"), Execution))
    failed = await scalar(scoped(
        select(func.count(Execution.id)).where(Execution.status.in_(["failed", "error"])), Execution))

    return TelemetrySummary(
        runs=runs, test_cases_total=cases, requirements_total=reqs, ambiguous_requirements=ambiguous,
        developers_with_tasks=devs, unassigned_total=unassigned,
        validation_failures_total=vfail, self_corrected_runs=self_corrected, retry_loops_total=retry_loops,
        llm_calls=calls, avg_llm_latency_ms=round(float(latency), 1),
        prompt_tokens=int(ptok), completion_tokens=int(ctok),
        overrides=overrides, override_rate=round(overrides / reviewed, 3) if reviewed else 0.0,
        executions_passed=passed, executions_failed=failed,
    )
