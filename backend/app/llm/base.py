from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass
class LLMResult:
    text: str
    model: str
    latency_ms: int
    prompt_tokens: int = 0
    completion_tokens: int = 0

    def telemetry(self, node: str, attempt: int = 0) -> dict:
        """Shape stored in graph state and later persisted to the llm_calls table."""
        data = asdict(self)
        data.pop("text")
        return {"node": node, "attempt": attempt, **data}


class LLMClient(Protocol):
    async def complete(self, *, node: str, system: str, user: str) -> LLMResult: ...
