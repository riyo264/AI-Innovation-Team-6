"""Request/response models for the HTTP API (what the React app consumes)."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

RunStatus = Literal[
    "generating", "awaiting_approval", "approved", "executing", "completed", "failed"
]
TaskStatus = Literal["todo", "in_progress", "passed", "failed"]
ExecutionStatus = Literal["queued", "running", "passed", "failed", "error"]


class RunCreated(BaseModel):
    run_id: str


class RunSummary(BaseModel):
    id: str
    status: RunStatus
    prd_filename: str | None
    created_at: datetime
    error: str | None = None


class AssignmentView(BaseModel):
    test_case_id: str
    ai_assignee_id: str
    final_assignee_id: str
    reasoning: str
    matched_skills: list[str]
    confidence: float
    needs_manager_review: bool
    overridden: bool
    task_status: TaskStatus


class ExecutionView(BaseModel):
    test_case_id: str
    status: ExecutionStatus
    duration_ms: int | None
    message: str | None


class RunDetail(RunSummary):
    requirements: list[dict]
    team: list[dict]
    test_cases: list[dict]
    assignments: list[AssignmentView]
    validation_failures: list[dict]
    executions: list[ExecutionView]


class DeveloperTask(BaseModel):
    test_case: dict
    assignment: AssignmentView
    execution: ExecutionView | None


class TaskStatusUpdate(BaseModel):
    status: TaskStatus


class TelemetrySummary(BaseModel):
    runs: int
    test_cases_total: int
    requirements_total: int
    ambiguous_requirements: int
    developers_with_tasks: int
    unassigned_total: int
    validation_failures_total: int
    self_corrected_runs: int
    retry_loops_total: int
    llm_calls: int
    avg_llm_latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    overrides: int
    override_rate: float
    executions_passed: int
    executions_failed: int
