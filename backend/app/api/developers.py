from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import MOCK_TOKENS, get_bus, get_session
from app.db.models import AuditLog, TaskAssignmentRow
from app.schemas.api import DeveloperTask, TaskStatusUpdate
from app.services import queries
from app.services.event_bus import EventBus

router = APIRouter(prefix="/api/runs/{run_id}", tags=["developers"])

Session = Annotated[AsyncSession, Depends(get_session)]


@router.get("/developers/{member_id}/tasks", response_model=list[DeveloperTask])
async def developer_tasks(run_id: str, member_id: str, session: Session,
                          x_token: str = Header(default="")):
    """Developer View: the test cases delegated to one person.
    Developers can only fetch their own tasks; managers can fetch any."""
    user = MOCK_TOKENS.get(x_token, {})
    if user.get("role") == "developer" and user.get("member_key") != member_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only view your own tasks")
    return await queries.developer_tasks(session, run_id, member_id)


@router.patch("/tasks/{case_key}")
async def move_task(
    run_id: str,
    case_key: str,
    body: TaskStatusUpdate,
    session: Session,
    bus: Annotated[EventBus, Depends(get_bus)],
    x_token: str = Header(default=""),
):
    """Kanban move by a developer."""
    user = MOCK_TOKENS.get(x_token, {})
    result = await session.execute(
        update(TaskAssignmentRow)
        .where(TaskAssignmentRow.run_id == run_id, TaskAssignmentRow.case_key == case_key)
        .values(task_status=body.status)
    )
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "task not found")
    session.add(AuditLog(
        run_id=run_id,
        actor=user.get("id", "unknown"),          # real identity now, not hardcoded "developer"
        event="task_moved",
        details={"test_case_id": case_key, "status": body.status},
    ))
    await session.commit()
    bus.publish(run_id, "task", test_case_id=case_key, task_status=body.status)
    return {"ok": True}
