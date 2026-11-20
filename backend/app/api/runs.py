import json
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from pydantic import ValidationError
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_pipeline, get_session, require_role
from app.db.models import AuditLog, Execution, RequirementRow, Run, TaskAssignmentRow, TestCaseRow
from app.schemas.api import RunCreated, RunDetail, RunSummary
from app.schemas.delegation import ManagerApproval, UNASSIGNED
from app.schemas.test_case import TestCase, TestCaseDraft, TestCaseUpdate
from app.services import queries
from app.services.parsing import InputError, parse_team, prd_to_text
from app.services.pipeline import PipelineError, PipelineService

router = APIRouter(prefix="/api/runs", tags=["runs"])

Session = Annotated[AsyncSession, Depends(get_session)]
Pipeline = Annotated[PipelineService, Depends(get_pipeline)]


@router.post("", response_model=RunCreated, status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    pipeline: Pipeline,
    _: dict = require_role("manager"),
    prd_file: UploadFile | None = File(None),
    prd_text: str | None = Form(None),
    team_file: UploadFile | None = File(None),
    team_json: str | None = Form(None),
):
    """Stage 1 (Ingestion). Accepts a PRD (file or text) and a team (file or JSON/CSV text).
    Returns immediately; follow progress on GET /api/runs/{id}/events."""
    try:
        if prd_file is not None:
            prd = prd_to_text(prd_file.filename, await prd_file.read())
            prd_name = prd_file.filename
        elif prd_text:
            prd, prd_name = prd_to_text("prd.txt", prd_text.encode()), None
        else:
            raise InputError("Provide prd_file or prd_text")

        if team_file is not None:
            team = parse_team((await team_file.read()).decode(), team_file.filename)
        elif team_json:
            team = parse_team(team_json)
        else:
            raise InputError("Provide team_file or team_json")
    except (InputError, ValidationError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    run_id = await pipeline.start_run(prd, prd_name, team)
    return RunCreated(run_id=run_id)


@router.get("", response_model=list[RunSummary])
async def list_runs(session: Session):
    return await queries.list_runs(session)


@router.get("/{run_id}", response_model=RunDetail)
async def get_run(run_id: str, session: Session):
    detail = await queries.run_detail(session, run_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return detail


@router.get("/{run_id}/export", response_class=Response)
async def export_run(run_id: str, session: Session, _: dict = require_role("manager")):
    detail = await queries.run_detail(session, run_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    return Response(
        content=json.dumps(detail.model_dump(mode="json"), indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="test-plan-{run_id}.json"'},
    )


@router.patch("/{run_id}/test-cases/{case_id}", response_model=TestCase)
async def update_test_case(
    run_id: str,
    case_id: str,
    update: TestCaseUpdate,
    session: Session,
    user: dict = require_role("manager"),
):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, "test cases can only be edited before approval")

    case = await session.scalar(
        select(TestCaseRow).where(TestCaseRow.run_id == run_id, TestCaseRow.case_key == case_id)
    )
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "test case not found")

    updated = TestCase.model_validate({**case.payload, **update.model_dump()})
    case.payload = updated.model_dump(mode="json")
    case.title = updated.title
    case.test_type = updated.test_type.value
    case.kind = updated.spec.kind
    session.add(AuditLog(
        run_id=run_id,
        actor=user["id"],
        event="test_case_edited",
        details={"test_case_id": case_id},
    ))
    await session.commit()
    return updated


@router.post("/{run_id}/test-cases", response_model=TestCase, status_code=status.HTTP_201_CREATED)
async def add_test_case(
    run_id: str,
    draft: TestCaseDraft,
    session: Session,
    user: dict = require_role("manager"),
):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, "test cases can only be added before approval")

    requirement = await session.scalar(
        select(RequirementRow).where(
            RequirementRow.run_id == run_id,
            RequirementRow.req_key == draft.source_requirement_id,
        )
    )
    if requirement is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "source requirement does not exist")
    valid_criteria = {criterion["id"] for criterion in requirement.payload["acceptance_criteria"]}
    unknown_criteria = sorted(set(draft.covers_criteria) - valid_criteria)
    if unknown_criteria:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown acceptance criteria for {draft.source_requirement_id}: {unknown_criteria}",
        )

    case_keys = (await session.scalars(
        select(TestCaseRow.case_key).where(TestCaseRow.run_id == run_id)
    )).all()
    next_number = max((int(key.removeprefix("TC-")) for key in case_keys), default=0) + 1
    if next_number > 999:
        raise HTTPException(status.HTTP_409_CONFLICT, "this run has reached the 999 test-case limit")

    case = TestCase(id=f"TC-{next_number:03d}", **draft.model_dump())
    session.add(TestCaseRow(
        run_id=run_id,
        case_key=case.id,
        source_requirement_key=case.source_requirement_id,
        title=case.title,
        test_type=case.test_type.value,
        kind=case.spec.kind,
        confidence=case.confidence,
        payload=case.model_dump(mode="json"),
    ))
    session.add(TaskAssignmentRow(
        run_id=run_id,
        case_key=case.id,
        ai_assignee=UNASSIGNED,
        final_assignee=UNASSIGNED,
        reasoning="Added by manager; assign before approval.",
        matched_skills=[],
        confidence=0.0,
        needs_manager_review=True,
    ))
    session.add(AuditLog(
        run_id=run_id,
        actor=user["id"],
        event="test_case_added",
        details={"test_case_id": case.id},
    ))
    await session.commit()
    return case


@router.delete("/{run_id}/test-cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_test_case(
    run_id: str,
    case_id: str,
    session: Session,
    user: dict = require_role("manager"),
):
    run = await session.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status.HTTP_409_CONFLICT, "test cases can only be deleted before approval")

    case = await session.scalar(
        select(TestCaseRow).where(TestCaseRow.run_id == run_id, TestCaseRow.case_key == case_id)
    )
    if case is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "test case not found")

    await session.execute(delete(TaskAssignmentRow).where(
        TaskAssignmentRow.run_id == run_id,
        TaskAssignmentRow.case_key == case_id,
    ))
    await session.execute(delete(Execution).where(
        Execution.run_id == run_id,
        Execution.case_key == case_id,
    ))
    await session.delete(case)
    session.add(AuditLog(
        run_id=run_id,
        actor=user["id"],
        event="test_case_deleted",
        details={"test_case_id": case_id},
    ))
    await session.commit()


@router.post("/{run_id}/approve")
async def approve_run(run_id: str, approval: ManagerApproval, pipeline: Pipeline,
                      _: dict = require_role("manager")):
    """Stage 4. Manager's final assignments; resumes the paused LangGraph thread."""
    try:
        return await pipeline.approve(run_id, approval)
    except PipelineError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc


@router.post("/{run_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def rerun_execution(run_id: str, pipeline: Pipeline,
                          _: dict = require_role("manager")):
    """Re-run the approved suite (e.g. after fixing the demo target live on stage)."""
    if pipeline.executor is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "execution engine is disabled")
    pipeline._spawn(pipeline.execute(run_id))
    return {"status": "executing"}
