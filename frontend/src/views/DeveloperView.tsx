import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { DeveloperTask, ExecutionStatus, Member, TaskStatus } from "../api/types";
import { LiveConsole } from "../components/LiveConsole";
import { TestCaseCard } from "../components/TestCaseCard";

const LANES: { id: TaskStatus; title: string }[] = [
  { id: "todo", title: "To do" },
  { id: "in_progress", title: "In progress" },
  { id: "passed", title: "Passed" },
  { id: "failed", title: "Failed" },
];

interface Props {
  runId: string;
  member: Member;
  logs: string[];
  liveResults: Record<string, ExecutionStatus>;
  refreshKey: number;
}

/** Developer View: Kanban of the test cases delegated to this developer. */
export function DeveloperView({ runId, member, logs, liveResults, refreshKey }: Props) {
  const [tasks, setTasks] = useState<DeveloperTask[]>([]);

  const load = useCallback(() => {
    api.developerTasks(runId, member.id).then(setTasks).catch(() => setTasks([]));
  }, [runId, member.id]);

  useEffect(load, [load, refreshKey]);

  async function drop(lane: TaskStatus, e: React.DragEvent) {
    e.preventDefault();
    const caseId = e.dataTransfer.getData("text/plain");
    if (!caseId) return;
    setTasks((ts) =>
      ts.map((t) => (t.test_case.id === caseId ? { ...t, assignment: { ...t.assignment, task_status: lane } } : t)),
    );
    await api.moveTask(runId, caseId, lane).catch(load);
  }

  const mine = new Set(tasks.map((t) => t.test_case.id));
  const myLogs = logs.filter((l) => !/\[TC-\d{3}\]/.test(l) || [...mine].some((id) => l.includes(id)));

  return (
    <div>
      <section className="panel">
        <h2>
          {member.name}'s tasks <span className="muted">({tasks.length})</span>
        </h2>
        <p className="muted">
          {member.role} · skills: {member.skills.join(", ")}
        </p>
      </section>
      <div className="board">
        {LANES.map((lane) => (
          <section key={lane.id} className="column" onDragOver={(e) => e.preventDefault()} onDrop={(e) => drop(lane.id, e)}>
            <h3>{lane.title}</h3>
            {tasks
              .filter((t) => t.assignment.task_status === lane.id)
              .map((t) => (
                <TestCaseCard
                  key={t.test_case.id}
                  testCase={t.test_case}
                  assignment={t.assignment}
                  execution={liveResults[t.test_case.id] ?? t.execution?.status}
                  executionMessage={t.execution?.message}
                  draggable
                />
              ))}
          </section>
        ))}
      </div>
      <LiveConsole lines={myLogs} title="Live output (your tests)" />
    </div>
  );
}
