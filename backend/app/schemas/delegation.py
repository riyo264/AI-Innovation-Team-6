from pydantic import BaseModel, Field

UNASSIGNED = "unassigned"


class TaskAssignment(BaseModel):
    """Node 4 output: one test case mapped to one developer, with an explanation."""

    test_case_id: str
    assignee_id: str = Field(description=f"Team member id, or '{UNASSIGNED}'")
    reasoning: str = Field(min_length=10)
    matched_skills: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    needs_manager_review: bool = False


class DelegationPlan(BaseModel):
    assignments: list[TaskAssignment]

    @property
    def unassigned(self) -> list[TaskAssignment]:
        return [a for a in self.assignments if a.assignee_id == UNASSIGNED]


class AssignmentDecision(BaseModel):
    test_case_id: str
    assignee_id: str


class ManagerApproval(BaseModel):
    """Payload the manager sends to resume the paused LangGraph thread."""

    approved_by: str = "manager"
    assignments: list[AssignmentDecision]


class Override(BaseModel):
    test_case_id: str
    ai_assignee_id: str
    final_assignee_id: str
