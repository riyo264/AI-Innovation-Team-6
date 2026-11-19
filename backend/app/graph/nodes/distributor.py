"""Runs after the manager resumes the graph. Merges the manager's decisions with the AI
plan and records every override (feeds the 'manager override rate' metric)."""

from app.graph.state import PipelineState
from app.schemas.delegation import DelegationPlan, ManagerApproval, Override


async def distributor(state: PipelineState) -> dict:
    plan = DelegationPlan.model_validate(state["delegation_plan"])
    approval = ManagerApproval.model_validate(
        state.get("approved_plan") or {"assignments": []}
    )
    decided = {d.test_case_id: d.assignee_id for d in approval.assignments}

    final, overrides = [], []
    for a in plan.assignments:
        final_assignee = decided.get(a.test_case_id, a.assignee_id)
        final.append({**a.model_dump(), "final_assignee_id": final_assignee})
        if final_assignee != a.assignee_id:
            overrides.append(
                Override(
                    test_case_id=a.test_case_id,
                    ai_assignee_id=a.assignee_id,
                    final_assignee_id=final_assignee,
                ).model_dump()
            )

    return {"final_assignments": final, "overrides": overrides}
