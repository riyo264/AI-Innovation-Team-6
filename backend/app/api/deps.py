from typing import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.event_bus import EventBus
from app.services.pipeline import PipelineService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessions() as session:
        yield session


def get_pipeline(request: Request) -> PipelineService:
    return request.app.state.pipeline


def get_bus(request: Request) -> EventBus:
    return request.app.state.bus
