"""Read-side queries that assemble API views from the relational tables."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Execution,
    RequirementRow,
    Run,
    TaskAssignmentRow,
    TeamMember,
    TestCaseRow,
    ValidationFailureRow,
)
from app.schemas.api import AssignmentView, DeveloperTask, ExecutionView, RunDetail, RunSummary


def _assignment(a: TaskAssignmentRow) -> AssignmentView:
    return AssignmentView(
        test_case_id=a.case_key, ai_assignee_id=a.ai_assignee, final_assignee_id=a.final_assignee,
        reasoning=a.reasoning, matched_skills=a.matched_skills, confidence=a.confidence,
        needs_manager_review=a.needs_manager_review, overridden=a.overridden,
        task_status=a.task_status,
    )


def _execution(e: Execution) -> ExecutionView:
    return ExecutionView(test_case_id=e.case_key, status=e.status, duration_ms=e.duration_ms,
                         message=e.message)


def summary(run: Run) -> RunSummary:
    return RunSummary(id=run.id, status=run.status, prd_filename=run.prd_filename,
                      created_at=run.created_at, error=run.error)


async def list_runs(s: AsyncSession) -> list[RunSummary]:
    runs = (await s.scalars(select(Run).order_by(Run.created_at.desc()).limit(50))).all()
    return [summary(r) for r in runs]


async def run_detail(s: AsyncSession, run_id: str) -> RunDetail | None:
    run = await s.get(Run, run_id)
    if run is None:
        return None

    async def rows(model, order):
        return (await s.scalars(select(model).where(model.run_id == run_id).order_by(order))).all()

    reqs = await rows(RequirementRow, RequirementRow.req_key)
    team = await rows(TeamMember, TeamMember.id)
    cases = await rows(TestCaseRow, TestCaseRow.case_key)
    assignments = await rows(TaskAssignmentRow, TaskAssignmentRow.case_key)
    failures = await rows(ValidationFailureRow, ValidationFailureRow.id)
    executions = await rows(Execution, Execution.case_key)

    return RunDetail(
        **summary(run).model_dump(),
        requirements=[r.payload for r in reqs],
        team=[{"id": m.member_key, "name": m.name, "role": m.role, "skills": m.skills} for m in team],
        test_cases=[c.payload for c in cases],
        assignments=[_assignment(a) for a in assignments],
        validation_failures=[f.payload for f in failures],
        executions=[_execution(e) for e in executions],
    )


async def developer_tasks(s: AsyncSession, run_id: str, member_id: str) -> list[DeveloperTask]:
    assignments = (await s.scalars(
        select(TaskAssignmentRow)
        .where(TaskAssignmentRow.run_id == run_id, TaskAssignmentRow.final_assignee == member_id)
        .order_by(TaskAssignmentRow.case_key)
    )).all()
    keys = [a.case_key for a in assignments]
    cases = {c.case_key: c.payload for c in (await s.scalars(
        select(TestCaseRow).where(TestCaseRow.run_id == run_id, TestCaseRow.case_key.in_(keys))))}
    execs = {e.case_key: e for e in (await s.scalars(
        select(Execution).where(Execution.run_id == run_id, Execution.case_key.in_(keys))))}
    return [
        DeveloperTask(
            test_case=cases[a.case_key],
            assignment=_assignment(a),
            execution=_execution(execs[a.case_key]) if a.case_key in execs else None,
        )
        for a in assignments
    ]
