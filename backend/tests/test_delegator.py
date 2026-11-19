from app.graph.nodes.delegator import delegate
from app.schemas import UNASSIGNED, Employee, TestCase

SPEC = {"kind": "api", "method": "POST", "path": "/x", "expected_status": 200}


def make_case(n: int, tags: list[str], test_type="positive", confidence=0.9, req="REQ-001"):
    return TestCase(id=f"TC-{n:03d}", title=f"Case {n} title", source_requirement_id=req,
                    test_type=test_type, tags=tags, steps_description=["do it"],
                    expected_result="it works", confidence=confidence, spec=SPEC)


def team(members):
    return [Employee.model_validate(m) for m in members]


def test_security_case_goes_to_security_dev_with_reasoning(team_members):
    plan = delegate([make_case(1, ["rate-limiting", "security"], "security")], team(team_members), set())
    a = plan.assignments[0]
    assert a.assignee_id == "alice"
    assert "Alice" in a.reasoning and "rate-limiting" in a.reasoning


def test_security_type_wins_tie_against_api_dev(team_members):
    plan = delegate([make_case(1, ["api", "security"], "security")], team(team_members), set())
    assert plan.assignments[0].assignee_id == "alice"


def test_ui_maps_to_frontend(team_members):
    plan = delegate([make_case(1, ["ui"])], team(team_members), set())
    assert plan.assignments[0].assignee_id == "carol"


def test_no_matching_skill_goes_to_unassigned_bucket(team_members):
    plan = delegate([make_case(1, ["email"])], team(team_members), set())
    a = plan.assignments[0]
    assert a.assignee_id == UNASSIGNED and a.needs_manager_review


def test_ambiguous_requirement_is_flagged(team_members):
    plan = delegate([make_case(1, ["ui"], req="REQ-007")], team(team_members), {"REQ-007"})
    assert plan.assignments[0].needs_manager_review
    assert "ambiguous" in plan.assignments[0].reasoning


def test_load_balances_on_ties():
    devs = team([
        {"id": "a", "name": "A", "role": "QA", "skills": ["api"]},
        {"id": "b", "name": "B", "role": "QA", "skills": ["api"]},
    ])
    plan = delegate([make_case(i, ["api"]) for i in range(1, 5)], devs, set())
    owners = [a.assignee_id for a in plan.assignments]
    assert owners.count("a") == owners.count("b") == 2


def test_is_deterministic(team_members):
    cases = [make_case(i, ["api", "auth"]) for i in range(1, 6)]
    assert delegate(cases, team(team_members), set()) == delegate(cases, team(team_members), set())
