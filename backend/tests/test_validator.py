import json

from app.graph.nodes.validator import route_after_validation, validate_generation
from app.llm.mock import FIRST_ATTEMPT, REQUIREMENTS, RETRY_ATTEMPT

REQ_IDS = {r["id"] for r in REQUIREMENTS}


def test_first_attempt_keeps_valid_items_and_reports_failures():
    valid, failures = validate_generation(json.dumps(FIRST_ATTEMPT), REQ_IDS, [], attempt=0)
    assert len(valid) == 12
    assert [v["id"] for v in valid[:2]] == ["TC-001", "TC-002"]
    assert sorted(f.error_type for f in failures) == ["schema", "traceability"]
    assert any("REQ-099" in f.message for f in failures)


def test_retry_fixes_failures_and_continues_numbering():
    valid, _ = validate_generation(json.dumps(FIRST_ATTEMPT), REQ_IDS, [], attempt=0)
    fixed, failures = validate_generation(json.dumps(RETRY_ATTEMPT), REQ_IDS, valid, attempt=1)
    assert failures == []
    assert [f["id"] for f in fixed] == ["TC-013", "TC-014"]


def test_garbage_output_is_json_decode_failure_plus_coverage():
    valid, failures = validate_generation("Sure! Here are your tests:", REQ_IDS, [], attempt=0)
    assert valid == []
    types = [f.error_type for f in failures]
    assert types[0] == "json_decode"
    assert types.count("coverage") == len(REQ_IDS)


def test_llm_supplied_ids_are_ignored():
    item = {**RETRY_ATTEMPT["test_cases"][0], "id": "TC-999"}
    valid, _ = validate_generation(json.dumps({"test_cases": [item]}), {"REQ-006"}, [], 0)
    assert valid[0]["id"] == "TC-001"


def test_retry_loop_is_bounded():
    failing = {"pending_failures": [{"x": 1}]}
    assert route_after_validation({**failing, "retry_count": 3}, max_retries=3) == "generator"
    assert route_after_validation({**failing, "retry_count": 4}, max_retries=3) == "delegator"
    assert route_after_validation({"pending_failures": [], "retry_count": 1}, 3) == "delegator"
