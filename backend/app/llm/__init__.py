from app.config import Settings
from app.llm.base import LLMClient, LLMResult


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise RuntimeError("LLM_PROVIDER=groq but GROQ_API_KEY is not set")
        from app.llm.groq import GroqLLM

        return GroqLLM(settings.groq_api_key, settings.groq_model, settings.llm_temperature)

    from app.llm.mock import MockLLM

    return MockLLM()


__all__ = ["LLMClient", "LLMResult", "build_llm"]
