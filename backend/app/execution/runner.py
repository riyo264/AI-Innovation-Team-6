"""Runs the approved suite in a pytest subprocess and streams its output.

Why a subprocess: Playwright's sync API and pytest both want to own the process, the
demo shows real pytest terminal output, and a crash can't take the API server down.
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import Settings
from app.db.models import Execution, TaskAssignmentRow, TestCaseRow
from app.services.event_bus import EventBus

BACKEND_DIR = Path(__file__).resolve().parents[2]
HARNESS_DIR = Path(__file__).resolve().parent / "harness"
RESULT_PREFIX = "@@RESULT "


class ExecutionService:
    def __init__(self, settings: Settings, sessions: async_sessionmaker[AsyncSession], bus: EventBus):
        self.settings = settings
        self.sessions = sessions
        self.bus = bus

    async def _load_cases(self, run_id: str) -> list[dict]:
        async with self.sessions() as s:
            rows = (await s.execute(
                select(TestCaseRow, TaskAssignmentRow.final_assignee)
                .join(TaskAssignmentRow, (TaskAssignmentRow.run_id == TestCaseRow.run_id)
                      & (TaskAssignmentRow.case_key == TestCaseRow.case_key))
                .where(TestCaseRow.run_id == run_id)
                .order_by(TestCaseRow.case_key)
            )).all()
        return [{**tc.payload, "assignee": assignee} for tc, assignee in rows]

    async def run(self, run_id: str) -> None:
        cases = await self._load_cases(run_id)
        now = datetime.now(timezone.utc)
        async with self.sessions() as s:
            await s.execute(delete(Execution).where(Execution.run_id == run_id))
            s.add_all(Execution(run_id=run_id, case_key=c["id"], status="running", started_at=now)
                      for c in cases)
            await s.commit()
        for c in cases:
            self.bus.publish(run_id, "result", test_case_id=c["id"], status="running")

        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cases, f)
            cases_file = f.name

        env = {
            **os.environ,
            "PYTHONPATH": str(BACKEND_DIR),
            "HARNESS_CASES_FILE": cases_file,
            "TARGET_API_URL": self.settings.target_api_url,
            "TARGET_UI_URL": self.settings.target_ui_url,
        }
        cmd = [sys.executable, "-m", "pytest", str(HARNESS_DIR), "-v", "-s", "--no-header",
               "-p", "no:cacheprovider", "-o", "asyncio_mode=strict", "--color=no"]
        self.bus.publish(run_id, "log", line="$ " + " ".join(cmd[2:]))

        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=BACKEND_DIR, env=env,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT,
        )
        try:
            assert proc.stdout is not None
            async for raw in proc.stdout:
                line = raw.decode(errors="replace").rstrip()
                if RESULT_PREFIX in line:
                    before, _, payload = line.partition(RESULT_PREFIX)
                    if before.strip():
                        self.bus.publish(run_id, "log", line=before)
                    await self._record(run_id, json.loads(payload))
                elif line:
                    self.bus.publish(run_id, "log", line=line)
            code = await proc.wait()
        finally:
            os.unlink(cases_file)
        self.bus.publish(run_id, "log", line=f"pytest exited with code {code}")

    async def _record(self, run_id: str, result: dict) -> None:
        status = result["status"]
        async with self.sessions() as s:
            await s.execute(
                update(Execution)
                .where(Execution.run_id == run_id, Execution.case_key == result["test_case_id"])
                .values(status=status, duration_ms=result["duration_ms"], message=result["message"],
                        finished_at=datetime.now(timezone.utc))
            )
            await s.execute(
                update(TaskAssignmentRow)
                .where(TaskAssignmentRow.run_id == run_id,
                       TaskAssignmentRow.case_key == result["test_case_id"])
                .values(task_status="passed" if status == "passed" else "failed")
            )
            await s.commit()
        self.bus.publish(run_id, "result", **result)
