from typing import AsyncIterator

from fastapi import Depends, Header, HTTPException, Request, status
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


# ---------------------------------------------------------------------------
# Mock RBAC — swap this dict for a real JWT decoder before going to production.
# Each key is a static token the frontend sends in the X-Token header.
# ---------------------------------------------------------------------------
MOCK_TOKENS: dict[str, dict] = {
    "manager-token": {"role": "manager",   "id": "manager"},
    "alice-token":   {"role": "developer", "id": "alice",  "member_key": "alice"},
    "bob-token":     {"role": "developer", "id": "bob",    "member_key": "bob"},
    "carol-token":   {"role": "developer", "id": "carol",  "member_key": "carol"},
}


def get_current_user(x_token: str = Header(default="")) -> dict:
    """Return the user dict for the token, or raise 401."""
    user = MOCK_TOKENS.get(x_token)
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid X-Token header")
    return user


def require_role(*roles: str):
    """FastAPI dependency factory. Usage: _=Depends(require_role('manager'))"""
    def _dep(x_token: str = Header(default="")) -> dict:
        user = MOCK_TOKENS.get(x_token)
        if not user or user["role"] not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"This action requires one of these roles: {list(roles)}",
            )
        return user
    return Depends(_dep)
