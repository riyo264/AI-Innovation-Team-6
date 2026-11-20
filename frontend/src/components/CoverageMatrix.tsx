import { useMemo, useState } from "react";
import type { ExecutionStatus, RunDetail, TestCase, TestCaseUpdate } from "../api/types";
import {
  TEST_TYPES,
  buildCoverage,
  executionStatus,
  specLabel,
  type CriterionView,
  type MatrixRow,
} from "../coverage/matrix";
import { StatusBadge } from "./StatusBadge";
import { TestCaseEditor } from "./TestCaseEditor";

interface Props {
  run: RunDetail;
  liveResults: Record<string, ExecutionStatus>;
  editable: boolean;
  onSaveTestCase: (caseId: string, update: TestCaseUpdate) => Promise<void>;
}

type Selection = { kind: "test"; id: string } | { kind: "requirement"; id: string };

export function CoverageMatrix({ run, liveResults, editable, onSaveTestCase }: Props) {
  const model = useMemo(
    () => buildCoverage(run.requirements, run.test_cases),
    [run.requirements, run.test_cases],
  );
  const [selection, setSelection] = useState<Selection | null>(null);

  const selected = useMemo(() => {
    if (!selection) return null;
    const row = model.rows.find((item) =>
      selection.kind === "requirement"
        ? item.requirement.id === selection.id
        : Object.values(item.byType).some((tests) => tests.some((test) => test.id === selection.id)),
    );
    if (!row) return null;
    if (selection.kind === "requirement") return { row, test: null as TestCase | null };
    const test = Object.values(row.byType).flat().find((item) => item.id === selection.id) ?? null;
    return test ? { row, test } : null;
  }, [model.rows, selection]);

  return (
    <div>
      <p className="small muted matrix-lead">
        Each row is a requirement. Select a test to read its steps, expected result, automation spec,
        and the criteria it proves. Amber marks a gap: a missing required type, an uncovered
        criterion, or an ambiguous line the PRD must clarify.
      </p>
      {model.gaps.length > 0 ? (
        <ul className="gap-list">
          {model.gaps.map((gap) => (
            <li key={gap.id}>
              <button className="link" onClick={() => setSelection({ kind: "requirement", id: gap.requirementId })}>
                {gap.message}
              </button>
            </li>
          ))}
        </ul>
      ) : (
        <p className="ok-text">Every required type and measurable criterion has a test.</p>
      )}

      <div className="matrix-scroll">
        <table className="matrix">
          <thead>
            <tr>
              <th>Requirement</th>
              <th>Criteria</th>
              {TEST_TYPES.map((type) => (
                <th key={type}>{type}</th>
              ))}
              <th>Spec</th>
              <th>Result</th>
            </tr>
          </thead>
          <tbody>
            {model.rows.map((row) => (
              <MatrixTableRow
                key={row.requirement.id}
                row={row}
                run={run}
                liveResults={liveResults}
                selectedId={selection?.kind === "test" ? selection.id : null}
                onSelectTest={(id) => setSelection({ kind: "test", id })}
                onSelectRequirement={() => setSelection({ kind: "requirement", id: row.requirement.id })}
              />
            ))}
          </tbody>
        </table>
      </div>

      {selected && (
        <CoverageDetail
          key={selected.test?.id ?? selected.row.requirement.id}
          row={selected.row}
          test={selected.test}
          status={
            selected.test
              ? executionStatus(selected.test.id, liveResults, run.executions)
              : null
          }
          editable={editable}
          onSaveTestCase={onSaveTestCase}
          onClose={() => setSelection(null)}
        />
      )}
    </div>
  );
}

function MatrixTableRow({
  row,
  run,
  liveResults,
  selectedId,
  onSelectTest,
  onSelectRequirement,
}: {
  row: MatrixRow;
  run: RunDetail;
  liveResults: Record<string, ExecutionStatus>;
  selectedId: string | null;
  onSelectTest: (id: string) => void;
  onSelectRequirement: () => void;
}) {
  const { requirement } = row;
  const tests = TEST_TYPES.flatMap((type) => row.byType[type]);
  const hasUncoveredCriterion = row.criteria.some(
    (cv) => !cv.criterion.ambiguous && cv.coveredBy.length === 0,
  );

  return (
    <tr className={row.gaps.length > 0 ? "row-gap" : undefined}>
      <td>
        <button className="cell-btn" onClick={onSelectRequirement}>
          <strong>{requirement.id}</strong>
          <span className="title">{requirement.title}</span>
        </button>
        {requirement.ambiguous && <span className="badge badge-warn">ambiguous</span>}
      </td>
      <td
        className={
          requirement.ambiguous || requirement.acceptance_criteria.length === 0 || hasUncoveredCriterion
            ? "cell-gap"
            : undefined
        }
      >
        {row.criteria.length === 0 && <span className="gap-text">No acceptance criteria</span>}
        <ul className="criterion-list">
          {row.criteria.map(({ criterion, coveredBy }) => (
            <li
              key={criterion.id}
              className={
                criterion.ambiguous
                  ? "muted"
                  : coveredBy.length === 0
                  ? "gap-text"
                  : undefined
              }
            >
              <span className="mono">{criterion.id}</span> {criterion.text}
              {criterion.ambiguous && (
                <span className="badge badge-warn" title={criterion.ambiguity_note ?? undefined}>
                  ambiguous
                </span>
              )}
              {!criterion.ambiguous && coveredBy.length > 0 && (
                <span className="muted"> · {coveredBy.join(", ")}</span>
              )}
            </li>
          ))}
        </ul>
        {requirement.ambiguous && <p className="gap-text small">{requirement.ambiguity_note}</p>}
      </td>
      {TEST_TYPES.map((type) => {
        const cases = row.byType[type];
        const missing = cases.length === 0 && row.expected.includes(type);
        return (
          <td key={type} className={missing ? "cell-gap" : undefined}>
            {cases.map((testCase) => (
              <TestChip
                key={testCase.id}
                testCase={testCase}
                active={selectedId === testCase.id}
                onSelect={onSelectTest}
              />
            ))}
            {missing && <span className="gap-text">No {type} test</span>}
            {cases.length === 0 && !missing && <span className="muted">—</span>}
          </td>
        );
      })}
      <td>
        {tests.map((testCase) => (
          <button
            key={testCase.id}
            className={`link spec-line ${selectedId === testCase.id ? "active" : ""}`}
            onClick={() => onSelectTest(testCase.id)}
          >
            <span className="mono">{testCase.id}</span> {specLabel(testCase)}
          </button>
        ))}
        {tests.length === 0 && <span className="muted">—</span>}
      </td>
      <td>
        {tests.map((testCase) => {
          const status = executionStatus(testCase.id, liveResults, run.executions);
          return (
            <button key={testCase.id} className="cell-btn" onClick={() => onSelectTest(testCase.id)}>
              <span className="mono">{testCase.id}</span>{" "}
              {status ? <StatusBadge status={status} /> : <span className="muted">Not run</span>}
            </button>
          );
        })}
        {tests.length === 0 && <span className="muted">Not run</span>}
      </td>
    </tr>
  );
}

function TestChip({
  testCase,
  active,
  onSelect,
}: {
  testCase: TestCase;
  active: boolean;
  onSelect: (id: string) => void;
}) {
  const low = testCase.confidence < 0.5;
  return (
    <button
      className={`cell-btn ${active ? "active" : ""} ${low ? "low" : ""}`}
      onClick={() => onSelect(testCase.id)}
    >
      <strong>{testCase.id}</strong>
      <span className="title">{testCase.title}</span>
    </button>
  );
}

function CoverageDetail({
  row,
  test,
  status,
  editable,
  onSaveTestCase,
  onClose,
}: {
  row: MatrixRow;
  test: TestCase | null;
  status: ExecutionStatus | null;
  editable: boolean;
  onSaveTestCase: (caseId: string, update: TestCaseUpdate) => Promise<void>;
  onClose: () => void;
}) {
  const { requirement } = row;
  const [editing, setEditing] = useState(false);

  // When a test is selected, show only the criteria it explicitly covers.
  // When a requirement is selected, show all criteria.
  const tracedCriteria: CriterionView[] = test
    ? row.criteria.filter((cv) => cv.coveredBy.includes(test.id))
    : row.criteria;

  return (
    <section className="panel detail-panel">
      <div className="toolbar">
        <h2>{test ? test.id : requirement.id}</h2>
        {test && <span className={`type type-${test.test_type}`}>{test.test_type}</span>}
        {status && <StatusBadge status={status} />}
        {test && editable && !editing && (
          <button onClick={() => setEditing(true)}>Edit test case</button>
        )}
        <button onClick={onClose}>Close</button>
      </div>
      {editing && test ? (
        <TestCaseEditor
          testCase={test}
          onSave={async (update) => {
            await onSaveTestCase(test.id, update);
            setEditing(false);
          }}
          onCancel={() => setEditing(false)}
        />
      ) : <div className="detail-grid">
        <div>
          {test ? (
            <>
              <p className="title">{test.title}</p>
              <h3>Steps</h3>
              <ol className="detail-list">
                {test.steps_description.map((step) => (
                  <li key={step}>{step}</li>
                ))}
              </ol>
              <h3>Expected result</h3>
              <p>{test.expected_result}</p>
              {test.preconditions.length > 0 && (
                <>
                  <h3>Preconditions</h3>
                  <ul className="detail-list">
                    {test.preconditions.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </>
              )}
            </>
          ) : (
            <>
              <p className="title">{requirement.title}</p>
              {row.gaps.length > 0 && (
                <ul className="gap-list">
                  {row.gaps.map((gap) => (
                    <li key={gap.id}>{gap.message}</li>
                  ))}
                </ul>
              )}
            </>
          )}
          <h3>Requirement text</h3>
          <blockquote className="trace-quote">{requirement.description}</blockquote>
          <h3>Acceptance criteria</h3>
          {tracedCriteria.length === 0 && requirement.acceptance_criteria.length === 0 && (
            <li>None extracted.</li>
          )}
          {tracedCriteria.length === 0 && test && requirement.acceptance_criteria.length > 0 && (
            <p className="muted small">This test does not explicitly cover any criterion.</p>
          )}
          <ul className="criterion-list">
            {tracedCriteria.map(({ criterion, coveredBy }) => (
              <li key={criterion.id}>
                <span className="mono">{criterion.id}</span>{" "}
                {criterion.text}
                {criterion.ambiguous && (
                  <span className="badge badge-warn" title={criterion.ambiguity_note ?? undefined}>
                    ambiguous
                  </span>
                )}
                {criterion.source_quote && (
                  <blockquote className="trace-quote small">"{criterion.source_quote}"</blockquote>
                )}
                {test && coveredBy.includes(test.id) && (
                  <span className="muted"> · explicitly covered</span>
                )}
              </li>
            ))}
          </ul>
          {requirement.ambiguous && <p className="warn-text">{requirement.ambiguity_note}</p>}
        </div>
        <div>
          <h3>Automation spec</h3>
          {test ? <SpecBlock testCase={test} /> : <p className="muted">Select a test to see its spec.</p>}
          {test && (
            <p className="small muted">
              Generator confidence {Math.round(test.confidence * 100)}%. Traces to {requirement.id}.
              {test.covers_criteria.length > 0 && (
                <> Covers: {test.covers_criteria.join(", ")}.</>
              )}
            </p>
          )}
        </div>
      </div>}
    </section>
  );
}

function SpecBlock({ testCase }: { testCase: TestCase }) {
  const spec = testCase.spec;
  if (spec.kind === "api") {
    return (
      <pre className="spec-block">
        {`${spec.method} ${spec.path}${spec.repeat > 1 ? ` ×${spec.repeat}` : ""}\nexpect ${spec.expected_status}`}
        {spec.expected_body_contains.length > 0 ? `\nbody contains ${spec.expected_body_contains.join(", ")}` : ""}
        {spec.json_body ? `\n${JSON.stringify(spec.json_body, null, 2)}` : ""}
      </pre>
    );
  }
  return (
    <ol className="detail-list">
      {spec.steps.map((step, index) => (
        <li key={`${step.action}-${index}`}>
          {step.action}
          {step.selector ? ` ${step.selector}` : ""}
          {step.value ? ` "${step.value}"` : ""}
        </li>
      ))}
    </ol>
  );
}
