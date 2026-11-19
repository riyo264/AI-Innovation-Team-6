import json
import re
from typing import Any

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Parse model output into JSON, tolerating code fences and leading prose.

    Raises json.JSONDecodeError if nothing parseable is found; the Validator turns that
    into a `json_decode` ValidationFailure.
    """
    cleaned = _FENCE.sub("", text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def excerpt(obj: Any, limit: int = 400) -> str:
    raw = obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False)
    return raw if len(raw) <= limit else raw[:limit] + "…"
