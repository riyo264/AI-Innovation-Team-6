"""End-to-end LangGraph behaviour with the mock LLM and an in-memory checkpointer."""

from langgraph.checkpoint.memory import InMemorySaver

from app.graph.builder import build_graph
from app.llm.base import LLMResult
from app.llm.mock import MockLLM


async def test_pauses_after_delegator_then_resumes_with_overrides(prd_text, team_members):
    graph = build_graph(MockLLM(), InMemorySaver())
    cfg = {"configurable": {"thread_id": "run-1"}}

    await graph.ainvoke({"run_id": "run-1", "prd_text": prd_text, "team": team_members,
                         "retry_count": 0}, cfg)
    snap = await graph.aget_state(cfg)

    assert snap.next == ("distributor",)  # interrupt_after=["delegator"]
    assert snap.values["retry_count"] == 1  # self-corrected once
    assert len(snap.values["valid_test_cases"]) == 14
    assert {f["error_type"] for f in snap.values["validation_log"]} == {"schema", "traceability"}
    assert all(tc["source_requirement_id"].startswith("REQ-") for tc in snap.values["valid_test_cases"])

    plan = snap.values["delegation_plan"]["assignments"]
    first = plan[0]
    new_owner = "carol" if first["assignee_id"] != "carol" else "bob"
    await graph.aupdate_state(cfg, {"approved_plan": {
        "approved_by": "manager",
        "assignments": [{"test_case_id": first["test_case_id"], "assignee_id": new_owner}],
    }})
    await graph.ainvoke(None, cfg)
    done = await graph.aget_state(cfg)

    assert done.next == ()
    assert done.values["overrides"] == [{
        "test_case_id": first["test_case_id"],
        "ai_assignee_id": first["assignee_id"],
        "final_assignee_id": new_owner,
    }]


class AlwaysBrokenLLM(MockLLM):
    async def complete(self, *, node, system, user):
        if node == "generator":
            return LLMResult(text="not json at all", model="broken", latency_ms=1)
        return await super().complete(node=node, system=system, user=user)


async def test_retries_are_capped(prd_text, team_members):
    graph = build_graph(AlwaysBrokenLLM(), InMemorySaver(), max_retries=3)
    cfg = {"configurable": {"thread_id": "run-2"}}
    await graph.ainvoke({"run_id": "run-2", "prd_text": prd_text, "team": team_members,
                         "retry_count": 0}, cfg)
    snap = await graph.aget_state(cfg)

    generator_calls = [c for c in snap.values["llm_calls"] if c["node"] == "generator"]
    assert len(generator_calls) == 4  # 1 initial + 3 retries
    assert snap.next == ("distributor",)  # still reaches the manager, with failures surfaced
    assert snap.values["pending_failures"]
