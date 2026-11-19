"""One parametrised test per approved, AI-generated test case."""

import pytest

from app.execution.api_executor import run_api_spec
from app.execution.harness.conftest import TARGET_API_URL, TARGET_UI_URL, load_cases

CASES = load_cases()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_case(case, request):
    spec = case["spec"]
    print(f"\n[{case['id']}] {case['title']}  (assignee: {case.get('assignee', '-')})")
    if spec["kind"] == "api":
        print("  " + run_api_spec(spec, TARGET_API_URL))
    else:
        from app.execution.ui_executor import run_ui_spec

        page = request.getfixturevalue("page")  # only start a browser for UI cases
        print("  " + run_ui_spec(spec, TARGET_UI_URL, page))
