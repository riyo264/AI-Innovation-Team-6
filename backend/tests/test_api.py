"""HTTP flow: ingest -> wait for pause -> approve. SQLite + in-memory checkpointer, no execution."""

import time

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        llm_provider="mock",
        execute_on_approval=False,
    )
    with TestClient(create_app(settings), headers={"X-Token": "manager-token"}) as c:
        yield c


def wait_for(client, run_id, status, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        run = client.get(f"/api/runs/{run_id}").json()
        if run["status"] in (status, "failed"):
            return run
        time.sleep(0.1)
    raise AssertionError(f"run never reached {status}")


def test_full_approval_flow(client, prd_text, team_members):
    import json

    resp = client.post("/api/runs", data={"prd_text": prd_text,
                                          "team_json": json.dumps({"members": team_members})})
    assert resp.status_code == 202
    run_id = resp.json()["run_id"]

    run = wait_for(client, run_id, "awaiting_approval")
    assert run["status"] == "awaiting_approval", run.get("error")
    assert len(run["test_cases"]) == 14
    assert len(run["validation_failures"]) == 4
    test_case = run["test_cases"][0]
    edit = {
        "title": "Manager-edited case title",
        "preconditions": test_case["preconditions"],
        "steps_description": ["Manager-edited step"],
        "expected_result": "The edited expected result is shown.",
        "spec": test_case["spec"],
    }
    edit_response = client.patch(
        f"/api/runs/{run_id}/test-cases/{test_case['id']}",
        json=edit,
    )
    assert edit_response.status_code == 200, edit_response.text
    assert client.get(f"/api/runs/{run_id}").json()["test_cases"][0]["title"] == edit["title"]

    unassigned = [a for a in run["assignments"] if a["ai_assignee_id"] == "unassigned"]
    assert unassigned, "the 'email' test should land in the Unassigned bucket"

    draft = {
        "title": "Manager-added test case",
        "source_requirement_id": run["requirements"][0]["id"],
        "test_type": "positive",
        "tags": ["manager-added"],
        "preconditions": [],
        "steps_description": ["Call the endpoint with a valid request"],
        "expected_result": "The endpoint responds successfully.",
        "confidence": 1.0,
        "covers_criteria": [],
        "spec": {
            "kind": "api",
            "method": "GET",
            "path": "/api/health",
            "repeat": 1,
            "expected_status": 200,
            "expected_body_contains": [],
        },
    }
    added_response = client.post(f"/api/runs/{run_id}/test-cases", json=draft)
    assert added_response.status_code == 201, added_response.text
    added_case = added_response.json()

    deleted_case_id = next(
        case["id"]
        for case in run["test_cases"]
        if case["id"] != test_case["id"] and case["id"] != unassigned[0]["test_case_id"]
    )
    delete_response = client.delete(f"/api/runs/{run_id}/test-cases/{deleted_case_id}")
    assert delete_response.status_code == 204

    run = client.get(f"/api/runs/{run_id}").json()
    assert len(run["test_cases"]) == 14
    assert added_case["id"] in {case["id"] for case in run["test_cases"]}
    assert deleted_case_id not in {case["id"] for case in run["test_cases"]}
    assert run["test_cases"][0]["title"] == edit["title"]

    decisions = [{"test_case_id": a["test_case_id"], "assignee_id": a["final_assignee_id"]}
                 for a in run["assignments"]]
    decisions = [{**d, "assignee_id": "bob"} if d["test_case_id"] == unassigned[0]["test_case_id"]
                 else d for d in decisions]
    resp = client.post(f"/api/runs/{run_id}/approve",
                       json={"approved_by": "manager", "assignments": decisions})
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["overrides"]) == 1

    run = client.get(f"/api/runs/{run_id}").json()
    assert run["status"] == "approved"
    assert client.patch(
        f"/api/runs/{run_id}/test-cases/{test_case['id']}",
        json=edit,
    ).status_code == 409
    assert client.post(f"/api/runs/{run_id}/test-cases", json=draft).status_code == 409
    assert client.delete(
        f"/api/runs/{run_id}/test-cases/{test_case['id']}"
    ).status_code == 409

    exported = client.get(f"/api/runs/{run_id}/export")
    assert exported.status_code == 200
    assert exported.headers["content-disposition"].endswith(f'"test-plan-{run_id}.json"')
    exported_cases = exported.json()["test_cases"]
    assert exported_cases[0]["title"] == edit["title"]
    assert added_case["id"] in {case["id"] for case in exported_cases}
    assert deleted_case_id not in {case["id"] for case in exported_cases}

    tasks = client.get(f"/api/runs/{run_id}/developers/bob/tasks").json()
    assert unassigned[0]["test_case_id"] in {t["test_case"]["id"] for t in tasks}

    telemetry = client.get("/api/telemetry", params={"run_id": run_id}).json()
    assert telemetry["overrides"] == 1
    assert telemetry["retry_loops_total"] == 1
    assert telemetry["validation_failures_total"] == 4



def test_approve_twice_conflicts(client, prd_text, team_members):
    import json

    run_id = client.post("/api/runs", data={"prd_text": prd_text,
                                            "team_json": json.dumps(team_members)}).json()["run_id"]
    wait_for(client, run_id, "awaiting_approval")
    body = {"assignments": []}
    assert client.post(f"/api/runs/{run_id}/approve", json=body).status_code == 200
    assert client.post(f"/api/runs/{run_id}/approve", json=body).status_code == 409


def test_bad_team_json_is_422(client, prd_text):
    resp = client.post("/api/runs", data={"prd_text": prd_text, "team_json": "{not json"})
    assert resp.status_code == 422
