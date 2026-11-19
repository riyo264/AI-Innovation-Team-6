import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { UNASSIGNED, type ExecutionStatus, type RunDetail } from "../api/types";
import { LiveConsole } from "../components/LiveConsole";
import { StatusBadge } from "../components/StatusBadge";
import { TestCaseCard } from "../components/TestCaseCard";

interface Props {
  run: RunDetail;
  logs: string[];
  liveResults: Record<string, ExecutionStatus>;
  onChanged: () => void;
}

/** Manager Approval Dashboard: test cases grouped by assignee, drag to reassign, approve. */
export function ManagerDashboard({ run, logs, liveResults, onChanged }: Props) {
  const editable = run.status === "awaiting_approval";
  const [decisions, setDecisions] = useState<Record<string, string>>({});
  const [dragOver, setDragOver] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setDecisions(Object.fromEntries(run.assignments.map((a) => [a.test_case_id, a.final_assignee_id])));
  }, [run.id, run.assignments]);

  const assignmentById = useMemo(
    () => Object.fromEntries(run.assignments.map((a) => [a.test_case_id, a])),
    [run.assignments],
  );
  const executionById = useMemo(
    () => Object.fromEntries(run.executions.map((e) => [e.test_case_id, e])),
    [run.executions],
  );
  const columns = [
    ...run.team.map((m) => ({ id: m.id, title: `${m.name} · ${m.role}` })),
    { id: UNASSIGNED, title: "Unassigned (needs a decision)" },
  ];
  const overrides = run.assignments.filter((a) => decisions[a.test_case_id] !== a.ai_assignee_id).length;

  function drop(columnId: string, e: React.DragEvent) {
    e.preventDefault();
    setDragOver(null);
    if (!editable) return;
    const caseId = e.dataTransfer.getData("text/plain");
    if (caseId) setDecisions((d) => ({ ...d, [caseId]: columnId }));
  }

  async function approve() {
    setBusy(true);
    setError(null);
    try {
      await api.approve(
        run.id,
        Object.entries(decisions).map(([test_case_id, assignee_id]) => ({ test_case_id, assignee_id })),
      );
      onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const exhausted = run.validation_failures.some((f) => f.attempt >= 3);

  return (
    <div>
      <section className="panel toolbar">
        <h2>
          2 · Review & approve <StatusBadge status={run.status} />
        </h2>
        <span>
          {run.test_cases.length} test cases · {run.requirements.length} requirements ·{" "}
          {run.validation_failures.length} schema errors self-corrected · {overrides} manual override
          {overrides === 1 ? "" : "s"}
        </span>
        {editable && (
          <button className="primary" onClick={approve} disabled={busy}>
            {busy ? "Approving…" : "Approve & Distribute"}
          </button>
        )}
        {run.status === "completed" && (
          <button onClick={() => api.rerun(run.id).then(onChanged)}>Re-run suite</button>
        )}
        {error && <p className="bad-text">{error}</p>}
        {exhausted && <p className="warn-text">Retry budget exhausted; some requirements may be uncovered.</p>}
      </section>

      <div className="board">
        {columns.map((col) => {
          const cases = run.test_cases.filter((tc) => (decisions[tc.id] ?? UNASSIGNED) === col.id);
          return (
            <section
              key={col.id}
              className={`column ${dragOver === col.id ? "drag-over" : ""} ${col.id === UNASSIGNED ? "column-unassigned" : ""}`}
              onDragOver={(e) => {
                if (!editable) return;
                e.preventDefault();
                setDragOver(col.id);
              }}
              onDragLeave={() => setDragOver(null)}
              onDrop={(e) => drop(col.id, e)}
            >
              <h3>
                {col.title} <span className="muted">({cases.length})</span>
              </h3>
              {cases.map((tc) => (
                <TestCaseCard
                  key={tc.id}
                  testCase={tc}
                  assignment={assignmentById[tc.id]}
                  draggable={editable}
                  overridden={assignmentById[tc.id] && decisions[tc.id] !== assignmentById[tc.id].ai_assignee_id}
                  execution={liveResults[tc.id] ?? executionById[tc.id]?.status}
                  executionMessage={executionById[tc.id]?.message}
                />
              ))}
            </section>
          );
        })}
      </div>

      {run.status !== "awaiting_approval" && <LiveConsole lines={logs} />}
    </div>
  );
}
