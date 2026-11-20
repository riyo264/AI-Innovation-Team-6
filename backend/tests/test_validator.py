import json

from app.graph.nodes.validator import route_after_validation, validate_generation
from app.llm.mock import FIRST_ATTEMPT, REQUIREMENTS, RETRY_ATTEMPT

# validate_generation now takes the full requirements list (not just IDs)


def test_first_attempt_keeps_valid_items_and_reports_failures():
    valid, failures = validate_generation(json.dumps(FIRST_ATTEMPT), REQUIREMENTS, [], attempt=0)
    assert len(valid) == 12
    assert [v["id"] for v in valid[:2]] == ["TC-001", "TC-002"]
    failure_types = sorted(f.error_type for f in failures)
    assert "schema" in failure_types
    assert "traceability" in failure_types
    assert any("REQ-099" in f.message for f in failures)


def test_retry_fixes_failures_and_continues_numbering():
    valid, _ = validate_generation(json.dumps(FIRST_ATTEMPT), REQUIREMENTS, [], attempt=0)
    fixed, failures = validate_generation(json.dumps(RETRY_ATTEMPT), REQUIREMENTS, valid, attempt=1)
    assert failures == []
    assert [f["id"] for f in fixed] == ["TC-013", "TC-014"]


def test_garbage_output_is_json_decode_failure_plus_coverage():
    valid, failures = validate_generation("Sure! Here are your tests:", REQUIREMENTS, [], attempt=0)
    assert valid == []
    types = [f.error_type for f in failures]
    assert types[0] == "json_decode"
    assert types.count("coverage") == len(REQUIREMENTS)


def test_llm_supplied_ids_are_ignored():
    # Build a minimal single-item requirements list that matches the test case
    req = next(r for r in REQUIREMENTS if r["id"] == "REQ-006")
    item = {**RETRY_ATTEMPT["test_cases"][0], "id": "TC-999"}  # _WEAK_PW is REQ-006
    valid, _ = validate_generation(json.dumps({"test_cases": [item]}), [req], [], 0)
    assert valid[0]["id"] == "TC-001"


def test_criterion_id_unknown_is_rejected():
    """A test that lists a non-existent AC ID in covers_criteria must be rejected."""
    req = next(r for r in REQUIREMENTS if r["id"] == "REQ-006")
    bad_item = {
        **RETRY_ATTEMPT["test_cases"][0],  # _WEAK_PW -> REQ-006
        "covers_criteria": ["AC-006.99"],  # doesn't exist
    }
    valid, failures = validate_generation(json.dumps({"test_cases": [bad_item]}), [req], [], 0)
    assert valid == []
    assert any(f.error_type == "criterion_id_unknown" for f in failures)


def test_criterion_uncovered_fires_when_no_test_covers_ac():
    """A criterion with no test pointing to it must produce criterion_uncovered."""
    req = next(r for r in REQUIREMENTS if r["id"] == "REQ-006")
    # Only covers AC-006.1; AC-006.2 is left uncovered
    item = {**RETRY_ATTEMPT["test_cases"][0], "covers_criteria": ["AC-006.1"]}
    _, failures = validate_generation(json.dumps({"test_cases": [item]}), [req], [], 0)
    uncovered = [f for f in failures if f.error_type == "criterion_uncovered"]
    assert any("AC-006.2" in f.message for f in uncovered)


def test_retry_loop_is_bounded():
    failing = {"pending_failures": [{"x": 1}]}
    assert route_after_validation({**failing, "retry_count": 3}, max_retries=3) == "generator"
    assert route_after_validation({**failing, "retry_count": 4}, max_retries=3) == "delegator"
    assert route_after_validation({"pending_failures": [], "retry_count": 1}, 3) == "delegator"
