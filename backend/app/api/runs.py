from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_pipeline, get_session, require_role
from app.schemas.api import RunCreated, RunDetail, RunSummary
from app.schemas.delegation import ManagerApproval
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
