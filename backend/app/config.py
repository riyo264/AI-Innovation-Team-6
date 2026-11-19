from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://harness:harness@localhost:5432/harness"

    llm_provider: Literal["groq", "mock"] = "mock"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    llm_temperature: float = 0.0

    max_validation_retries: int = 3

    target_api_url: str = "http://localhost:9000"
    target_ui_url: str = "http://localhost:9000"
    execute_on_approval: bool = True

    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def uses_postgres(self) -> bool:
        return self.database_url.startswith("postgresql")

    @property
    def checkpointer_conninfo(self) -> str:
        """psycopg conninfo for the LangGraph checkpointer (no SQLAlchemy driver suffix)."""
        return self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)


@lru_cache
def get_settings() -> Settings:
    return Settings()
