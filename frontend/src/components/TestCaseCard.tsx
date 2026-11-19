import type { Assignment, ExecutionStatus, TestCase } from "../api/types";
import { StatusBadge } from "./StatusBadge";

interface Props {
  testCase: TestCase;
  assignment?: Assignment;
  execution?: ExecutionStatus;
  executionMessage?: string | null;
  draggable?: boolean;
  overridden?: boolean;
}

export function TestCaseCard({ testCase, assignment, execution, executionMessage, draggable, overridden }: Props) {
  const spec = testCase.spec;
  return (
    <article
      className={`card ${assignment?.needs_manager_review ? "card-flag" : ""}`}
      draggable={draggable}
      onDragStart={(e) => e.dataTransfer.setData("text/plain", testCase.id)}
    >
      <header>
        <strong>{testCase.id}</strong>
        <span className={`type type-${testCase.test_type}`}>{testCase.test_type}</span>
        <span className="muted">↳ {testCase.source_requirement_id}</span>
        {execution && <StatusBadge status={execution} />}
      </header>
      <p className="title">{testCase.title}</p>
      <p className="muted small">
        {spec.kind === "api"
          ? `${spec.method} ${spec.path}${spec.repeat > 1 ? ` ×${spec.repeat}` : ""} → ${spec.expected_status}`
          : `UI · ${spec.steps.length} steps`}
      </p>
      <div className="tags">
        {testCase.tags.map((t) => (
          <span key={t} className="tag">{t}</span>
        ))}
      </div>
      {assignment && (
        <details>
          <summary>
            AI reasoning · confidence {Math.round(assignment.confidence * 100)}%
            {assignment.needs_manager_review && <span className="flag"> ⚑ review</span>}
            {overridden && <span className="flag"> ✎ overridden</span>}
          </summary>
          <p className="small">{assignment.reasoning}</p>
        </details>
      )}
      {executionMessage && <p className="small bad-text">{executionMessage}</p>}
    </article>
  );
}
