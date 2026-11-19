import json
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_bus
from app.services.event_bus import EventBus

router = APIRouter(prefix="/api/runs/{run_id}", tags=["events"])


@router.get("/events")
async def run_events(run_id: str, request: Request, bus: Annotated[EventBus, Depends(get_bus)]):
    """Server-Sent Events: node progress, run status, live pytest output, per-test results.

    Event names: node | status | log | result | task
    """

    async def stream():
        async for event in bus.subscribe(run_id):
            if await request.is_disconnected():
                break
            yield {"event": event["type"], "data": json.dumps(event)}

    return EventSourceResponse(stream(), ping=15)
