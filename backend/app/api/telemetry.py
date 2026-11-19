from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_session
from app.schemas.api import TelemetrySummary
from app.services.telemetry import summarize

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


@router.get("", response_model=TelemetrySummary)
async def telemetry(
    session: Annotated[AsyncSession, Depends(get_session)], run_id: str | None = None
):
    """Pitch dashboard numbers. Pass run_id for one run, omit for all runs."""
    return await summarize(session, run_id)
