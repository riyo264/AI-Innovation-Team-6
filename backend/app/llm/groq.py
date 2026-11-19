import time

from app.llm.base import LLMResult


class GroqLLM:
    """Open-weight model via Groq (default: Llama 3.3 70B) in JSON mode."""

    def __init__(self, api_key: str, model: str, temperature: float = 0.0):
        from langchain_groq import ChatGroq

        self.model = model
        self._chat = ChatGroq(
            api_key=api_key, model=model, temperature=temperature, max_retries=2
        ).bind(response_format={"type": "json_object"})

    async def complete(self, *, node: str, system: str, user: str) -> LLMResult:
        start = time.perf_counter()
        msg = await self._chat.ainvoke([("system", system), ("human", user)])
        latency_ms = int((time.perf_counter() - start) * 1000)
        usage = getattr(msg, "usage_metadata", None) or {}
        return LLMResult(
            text=str(msg.content),
            model=self.model,
            latency_ms=latency_ms,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
        )
