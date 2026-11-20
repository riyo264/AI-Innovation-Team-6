import { useState } from "react";
import type { Requirement, TestCaseCreate, TestType } from "../api/types";

interface Props {
  requirements: Requirement[];
  onCreate: (draft: TestCaseCreate) => Promise<void>;
  onCancel: () => void;
}

const TEST_TYPES: TestType[] = ["positive", "negative", "boundary", "security"];
const API_SPEC = {
  kind: "api",
  method: "GET",
  path: "/replace-with-your-endpoint",
  repeat: 1,
  expected_status: 200,
  expected_body_contains: [],
};
const UI_SPEC = {
  kind: "ui",
  steps: [{ action: "goto", selector: null, value: "http://localhost:9000/replace-with-your-page" }],
};

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

export function TestCaseCreateForm({ requirements, onCreate, onCancel }: Props) {
  const [requirementId, setRequirementId] = useState(requirements[0]?.id ?? "");
  const [testType, setTestType] = useState<TestType>("positive");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("manager-added");
  const [preconditions, setPreconditions] = useState("");
  const [steps, setSteps] = useState("");
  const [expectedResult, setExpectedResult] = useState("");
  const [specKind, setSpecKind] = useState<"api" | "ui">("api");
  const [spec, setSpec] = useState(JSON.stringify(API_SPEC, null, 2));
  const [coversCriteria, setCoversCriteria] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedRequirement = requirements.find((requirement) => requirement.id === requirementId);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const parsedSpec: unknown = JSON.parse(spec);
      await onCreate({
        source_requirement_id: requirementId,
        test_type: testType,
        title: title.trim(),
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
        preconditions: lines(preconditions),
        steps_description: lines(steps),
        expected_result: expectedResult.trim(),
        confidence: 1,
        covers_criteria: coversCriteria,
        spec: parsedSpec,
      });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form className="test-case-editor" onSubmit={submit}>
      <label className="field">
        Source requirement
        <select value={requirementId} onChange={(event) => {
          setRequirementId(event.target.value);
          setCoversCriteria([]);
        }}>
          {requirements.map((requirement) => (
            <option key={requirement.id} value={requirement.id}>
              {requirement.id} · {requirement.title}
            </option>
          ))}
        </select>
      </label>
      <label className="field">
        Test type
        <select value={testType} onChange={(event) => setTestType(event.target.value as TestType)}>
          {TEST_TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
      </label>
      <label className="field">
        Title
        <input required minLength={5} value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="field">
        Tags (comma-separated)
        <input required value={tags} onChange={(event) => setTags(event.target.value)} />
      </label>
      {selectedRequirement && selectedRequirement.acceptance_criteria.length > 0 && (
        <fieldset className="field">
          <legend>Acceptance criteria covered</legend>
          {selectedRequirement.acceptance_criteria.map((criterion) => (
            <label key={criterion.id}>
              <input
                type="checkbox"
                checked={coversCriteria.includes(criterion.id)}
                onChange={(event) => setCoversCriteria((current) =>
                  event.target.checked
                    ? [...current, criterion.id]
                    : current.filter((id) => id !== criterion.id))}
              />
              <span className="mono">{criterion.id}</span> {criterion.text}
            </label>
          ))}
        </fieldset>
      )}
      <label className="field">
        Preconditions (one per line)
        <textarea rows={3} value={preconditions} onChange={(event) => setPreconditions(event.target.value)} />
      </label>
      <label className="field">
        Steps (one per line)
        <textarea
          required
          rows={4}
          value={steps}
          onChange={(event) => setSteps(event.target.value)}
        />
      </label>
      <label className="field">
        Expected result
        <textarea
          required
          minLength={5}
          rows={3}
          value={expectedResult}
          onChange={(event) => setExpectedResult(event.target.value)}
        />
      </label>
      <label className="field">
        Spec type
        <select
          value={specKind}
          onChange={(event) => {
            const kind = event.target.value as "api" | "ui";
            setSpecKind(kind);
            setSpec(JSON.stringify(kind === "api" ? API_SPEC : UI_SPEC, null, 2));
          }}
        >
          <option value="api">API</option>
          <option value="ui">UI</option>
        </select>
      </label>
      <label className="field">
        Automation spec (JSON; replace the sample path/URL)
        <textarea
          required
          className="mono"
          rows={10}
          value={spec}
          onChange={(event) => setSpec(event.target.value)}
          spellCheck={false}
        />
      </label>
      {error && <p className="bad-text">{error}</p>}
      <div className="toolbar">
        <button className="primary" type="submit" disabled={saving || !requirementId}>
          {saving ? "Adding…" : "Add test case"}
        </button>
        <button type="button" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </form>
  );
}
