import pytest
from pydantic import ValidationError

from app.schemas import TeamStructure, TestCaseDraft
from app.services.parsing import parse_team

BASE = {
    "title": "Valid login returns token",
    "source_requirement_id": "REQ-001",
    "test_type": "positive",
    "tags": ["API", " auth "],
    "steps_description": ["POST /api/login"],
    "expected_result": "HTTP 200",
    "confidence": 0.9,
}


def test_api_spec_is_accepted_and_tags_normalised():
    tc = TestCaseDraft.model_validate(
        {**BASE, "spec": {"kind": "api", "method": "POST", "path": "/api/login", "expected_status": 200}}
    )
    assert tc.tags == ["api", "auth"]
    assert tc.spec.kind == "api"


def test_ui_fill_without_selector_is_rejected():
    with pytest.raises(ValidationError, match="requires a selector"):
        TestCaseDraft.model_validate(
            {**BASE, "spec": {"kind": "ui", "steps": [{"action": "fill", "value": "x"}]}}
        )


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        TestCaseDraft.model_validate({**BASE, "spec": {"kind": "api", "method": "POST",
                                                       "path": "/x", "expected_status": 200},
                                      "python_code": "import os"})


def test_bad_requirement_id_pattern():
    with pytest.raises(ValidationError):
        TestCaseDraft.model_validate({**BASE, "source_requirement_id": "R1", "spec": {
            "kind": "api", "method": "GET", "path": "/", "expected_status": 200}})


def test_team_duplicate_ids_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        TeamStructure.model_validate({"members": [
            {"id": "a", "name": "A", "role": "Security"},
            {"id": "a", "name": "B", "role": "Frontend UI"},
        ]})


def test_team_csv_parsing():
    team = parse_team("id,name,role,skills\nalice,Alice,Security,security;auth\n", "team.csv")
    assert team.members[0].skills == ["auth", "security"]
