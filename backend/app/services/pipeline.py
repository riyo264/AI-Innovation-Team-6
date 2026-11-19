r"""Glue between FastAPI, the LangGraph thread, Postgres and the event bus.

run lifecycle:  generating -> awaiting_approval -> approved -> executing -> completed
                         \-> failed (any stage)
"""

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from langgraph.graph.state import CompiledStateGraph
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import (
    AuditLog,
    LlmCall,
    RequirementRow,
    Run,
    TaskAssignmentRow,
    TeamMember,
    TestCaseRow,
    ValidationFailureRow,
)
from app.schemas.delegation import UNASSIGNED, ManagerApproval
from app.schemas.team import TeamStructure
from app.services.event_bus import EventBus

log = logging.getLogger(__name__)


class PipelineError(Exception):
    pass


def _thread(run_id: str) -> dict:
    return {"configurable": {"thread_id": run_id}}


class PipelineService:
    def __init__(
        self,
        graph: CompiledStateGraph,
        sessions: async_sessionmaker[AsyncSession],
        bus: EventBus,
        executor=None,  # ExecutionService | None
    ):
        self.graph = graph
        self.sessions = sessions
        self.bus = bus
        self.executor = executor
        self._tasks: set[asyncio.Task] = set()

    # ---- helpers -------------------------------------------------------------------

    def _spawn(self, coro) -> asyncio.Task:
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task

    async def _set_status(self, run_id: str, status: str, error: str | None = None) -> None:
        async with self.sessions() as s:
            await s.execute(update(Run).where(Run.id == run_id).values(status=status, error=error))
            await s.commit()
        self.bus.publish(run_id, "status", status=status, error=error)

    async def _stream(self, run_id: str, graph_input) -> None:
        """Run the graph until it pauses or ends, emitting one SSE event per node."""
        async for update_ in self.graph.astream(graph_input, _thread(run_id), stream_mode="updates"):
            for node, delta in update_.items():
                if node == "__interrupt__":
                    continue
                summary: dict = {}
                if node == "validator" and delta:
                    summary = {
                        "accepted": len(delta.get("valid_test_cases", [])),
                        "failures": [f["error_type"] for f in delta.get("pending_failures", [])],
                        "retry_count": delta.get("retry_count"),
                    }
                self.bus.publish(run_id, "node", node=node, **summary)

    # ---- stage 1+2: ingest and generate ----------------------------------------------

    async def start_run(self, prd_text: str, prd_filename: str | None, team: TeamStructure) -> str:
        run_id = str(uuid.uuid4())
        async with self.sessions() as s:
            s.add(Run(id=run_id, prd_text=prd_text, prd_filename=prd_filename, status="generating"))
            s.add_all(
                TeamMember(
                    run_id=run_id, member_key=m.id, name=m.name, role=m.role, skills=m.skills
                )
                for m in team.members
            )
            s.add(AuditLog(run_id=run_id, actor="manager", event="run_created",
                           details={"prd_filename": prd_filename, "team_size": len(team.members)}))
            await s.commit()

        initial = {
            "run_id": run_id,
            "prd_text": prd_text,
            "team": [m.model_dump() for m in team.members],
            "retry_count": 0,
        }
        self._spawn(self._generate(run_id, initial))
        return run_id

    async def _generate(self, run_id: str, initial: dict) -> None:
        try:
            await self._stream(run_id, initial)
            snapshot = await self.graph.aget_state(_thread(run_id))
            await self._persist_generation(run_id, snapshot.values)
            await self._set_status(run_id, "awaiting_approval")
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            log.exception("generation failed for run %s", run_id)
            await self._set_status(run_id, "failed", error=str(exc))

    async def _persist_generation(self, run_id: str, values: dict) -> None:
        cases = values.get("valid_test_cases", [])
        plan = values.get("delegation_plan", {"assignments": []})
        log_ = values.get("validation_log", [])
        exhausted = bool(values.get("pending_failures"))

        async with self.sessions() as s:
            s.add_all(
                RequirementRow(run_id=run_id, req_key=r["id"], title=r["title"], payload=r,
                               ambiguous=r.get("ambiguous", False))
                for r in values.get("requirements", [])
            )
            s.add_all(
                TestCaseRow(
                    run_id=run_id, case_key=tc["id"], source_requirement_key=tc["source_requirement_id"],
                    title=tc["title"], test_type=tc["test_type"], kind=tc["spec"]["kind"],
                    confidence=tc["confidence"], payload=tc,
                )
                for tc in cases
            )
            s.add_all(
                TaskAssignmentRow(
                    run_id=run_id, case_key=a["test_case_id"], ai_assignee=a["assignee_id"],
                    final_assignee=a["assignee_id"], reasoning=a["reasoning"],
                    matched_skills=a["matched_skills"], confidence=a["confidence"],
                    needs_manager_review=a["needs_manager_review"],
                )
                for a in plan["assignments"]
            )
            s.add_all(
                ValidationFailureRow(run_id=run_id, attempt=f["attempt"], error_type=f["error_type"],
                                     message=f["message"], payload=f)
                for f in log_
            )
            s.add_all(
                LlmCall(run_id=run_id, node=c["node"], attempt=c["attempt"], model=c["model"],
                        latency_ms=c["latency_ms"], prompt_tokens=c["prompt_tokens"],
                        completion_tokens=c["completion_tokens"])
                for c in values.get("llm_calls", [])
            )
            s.add(AuditLog(run_id=run_id, actor="ai", event="delegation_proposed", details={
                "test_cases": len(cases),
                "retry_count": values.get("retry_count", 0),
                "validation_failures": len(log_),
                "retries_exhausted": exhausted,
            }))
            await s.commit()

    # ---- stage 3+4: manager approval resumes the graph --------------------------------

    async def approve(self, run_id: str, approval: ManagerApproval) -> dict:
        async with self.sessions() as s:
            run = await s.get(Run, run_id)
            if run is None:
                raise PipelineError("run not found")
            if run.status != "awaiting_approval":
                raise PipelineError(f"run is '{run.status}', not awaiting approval")
            valid_cases = set((await s.scalars(
                select(TestCaseRow.case_key).where(TestCaseRow.run_id == run_id))).all())
            valid_members = set((await s.scalars(
                select(TeamMember.member_key).where(TeamMember.run_id == run_id))).all())

        for d in approval.assignments:
            if d.test_case_id not in valid_cases:
                raise PipelineError(f"unknown test case {d.test_case_id}")
            if d.assignee_id not in valid_members | {UNASSIGNED}:
                raise PipelineError(f"unknown assignee {d.assignee_id}")

        snapshot = await self.graph.aget_state(_thread(run_id))
        if snapshot.next != ("distributor",):
            raise PipelineError(f"graph is not paused at the approval breakpoint ({snapshot.next})")

        # Inject the manager's decision into the checkpointed state, then resume.
        await self.graph.aupdate_state(_thread(run_id), {"approved_plan": approval.model_dump()})
        await self._stream(run_id, None)
        values = (await self.graph.aget_state(_thread(run_id))).values

        overrides = values.get("overrides", [])
        async with self.sessions() as s:
            for fa in values.get("final_assignments", []):
                await s.execute(
                    update(TaskAssignmentRow)
                    .where(TaskAssignmentRow.run_id == run_id,
                           TaskAssignmentRow.case_key == fa["test_case_id"])
                    .values(final_assignee=fa["final_assignee_id"],
                            overridden=fa["final_assignee_id"] != fa["assignee_id"])
                )
            await s.execute(update(Run).where(Run.id == run_id).values(
                approved_by=approval.approved_by, approved_at=datetime.now(timezone.utc)))
            s.add(AuditLog(run_id=run_id, actor=approval.approved_by, event="plan_approved",
                           details={"overrides": overrides}))
            await s.commit()
        await self._set_status(run_id, "approved")

        if self.executor is not None:
            self._spawn(self.execute(run_id))
        return {"overrides": overrides}

    # ---- stage 5: execution ----------------------------------------------------------

    async def execute(self, run_id: str) -> None:
        if self.executor is None:
            raise PipelineError("execution engine is disabled")
        await self._set_status(run_id, "executing")
        try:
            await self.executor.run(run_id)
            await self._set_status(run_id, "completed")
        except Exception as exc:  # noqa: BLE001
            log.exception("execution failed for run %s", run_id)
            await self._set_status(run_id, "failed", error=f"execution: {exc}")

    async def shutdown(self) -> None:
        for t in list(self._tasks):
            t.cancel()
