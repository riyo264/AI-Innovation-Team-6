from fastapi import APIRouter

from app.api import developers, events, runs, telemetry

api_router = APIRouter()
api_router.include_router(runs.router)
api_router.include_router(developers.router)
api_router.include_router(events.router)
api_router.include_router(telemetry.router)
