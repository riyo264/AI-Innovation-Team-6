from contextlib import asynccontextmanager
from typing import AsyncIterator

from app.config import Settings


@asynccontextmanager
async def open_checkpointer(settings: Settings) -> AsyncIterator[object]:
    """Postgres checkpointer in docker/prod; in-memory for SQLite-backed tests."""
    if not settings.uses_postgres:
        from langgraph.checkpoint.memory import InMemorySaver

        yield InMemorySaver()
        return

    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import AsyncConnectionPool

    async with AsyncConnectionPool(
        settings.checkpointer_conninfo,
        max_size=10,
        open=False,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
    ) as pool:
        saver = AsyncPostgresSaver(pool)
        await saver.setup()  # creates checkpoint tables if missing
        yield saver
