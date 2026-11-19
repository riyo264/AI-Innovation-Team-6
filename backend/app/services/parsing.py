"""Turn uploaded PRD / team files into text and a validated TeamStructure."""

import csv
import io
import json

from pypdf import PdfReader

from app.schemas.team import TeamStructure


class InputError(ValueError):
    pass


def prd_to_text(filename: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    else:
        text = data.decode("utf-8", errors="replace")
    text = text.strip()
    if len(text) < 50:
        raise InputError("PRD is empty or too short to extract requirements from")
    return text


def parse_team(raw: str, filename: str | None = None) -> TeamStructure:
    """Accepts {"members": [...]}, a bare JSON list, or CSV (id,name,role,skills with ';')."""
    raw = raw.strip()
    if not raw:
        raise InputError("Team structure is empty")

    if (filename or "").lower().endswith(".csv") or not raw.startswith(("{", "[")):
        rows = list(csv.DictReader(io.StringIO(raw)))
        members = [
            {
                "id": r["id"].strip(),
                "name": r["name"].strip(),
                "role": r["role"].strip(),
                "skills": [s for s in (r.get("skills") or "").split(";") if s.strip()],
            }
            for r in rows
        ]
        return TeamStructure(members=members)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise InputError(f"Team JSON is invalid: {exc}") from exc
    if isinstance(data, list):
        data = {"members": data}
    return TeamStructure.model_validate(data)
