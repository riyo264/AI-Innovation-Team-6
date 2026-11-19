import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.config import Settings, get_settings
from app.db.session import create_tables, make_engine, make_session_factory
from app.execution.runner import ExecutionService
from app.graph.builder import build_graph
from app.graph.checkpointer import open_checkpointer
from app.llm import build_llm
from app.services.event_bus import EventBus
from app.services.pipeline import PipelineService

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        engine = make_engine(settings.database_url)
        await create_tables(engine)
        sessions = make_session_factory(engine)
        bus = EventBus()

        async with open_checkpointer(settings) as checkpointer:
            graph = build_graph(build_llm(settings), checkpointer, settings.max_validation_retries)
            executor = ExecutionService(settings, sessions, bus) if settings.execute_on_approval else None
            pipeline = PipelineService(graph, sessions, bus, executor)

            app.state.settings = settings
            app.state.sessions = sessions
            app.state.bus = bus
            app.state.pipeline = pipeline
            yield
            await pipeline.shutdown()
        await engine.dispose()

    app = FastAPI(title="AI Test Harness", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)

    @app.get("/api/health", tags=["meta"])
    async def health():
        return {"ok": True, "llm_provider": settings.llm_provider}

    return app


app = create_app()
