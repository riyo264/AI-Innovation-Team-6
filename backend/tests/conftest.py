import json
from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parents[2] / "samples"


@pytest.fixture
def team_members() -> list[dict]:
    return json.loads((SAMPLES / "team.json").read_text())["members"]


@pytest.fixture
def prd_text() -> str:
    return (SAMPLES / "prd_password_reset.md").read_text()
