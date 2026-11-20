import { useState } from "react";
import type { TestCase, TestCaseUpdate } from "../api/types";

interface Props {
  testCase: TestCase;
  onSave: (update: TestCaseUpdate) => Promise<void>;
  onCancel: () => void;
}

function lines(value: string): string[] {
  return value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
}

export function TestCaseEditor({ testCase, onSave, onCancel }: Props) {
  const [title, setTitle] = useState(testCase.title);
  const [preconditions, setPreconditions] = useState(testCase.preconditions.join("\n"));
  const [steps, setSteps] = useState(testCase.steps_description.join("\n"));
  const [expectedResult, setExpectedResult] = useState(testCase.expected_result);
  const [spec, setSpec] = useState(JSON.stringify(testCase.spec, null, 2));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const parsedSpec: unknown = JSON.parse(spec);
      await onSave({
        title: title.trim(),
        preconditions: lines(preconditions),
        steps_description: lines(steps),
        expected_result: expectedResult.trim(),
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
        Title
        <input value={title} onChange={(event) => setTitle(event.target.value)} />
      </label>
      <label className="field">
        Preconditions (one per line)
        <textarea rows={3} value={preconditions} onChange={(event) => setPreconditions(event.target.value)} />
      </label>
      <label className="field">
        Steps (one per line)
        <textarea rows={4} value={steps} onChange={(event) => setSteps(event.target.value)} />
      </label>
      <label className="field">
        Expected result
        <textarea rows={3} value={expectedResult} onChange={(event) => setExpectedResult(event.target.value)} />
      </label>
      <label className="field">
        Automation spec (JSON)
        <textarea
          className="mono"
          rows={10}
          value={spec}
          onChange={(event) => setSpec(event.target.value)}
          spellCheck={false}
        />
      </label>
      {error && <p className="bad-text">{error}</p>}
      <div className="toolbar">
        <button className="primary" type="submit" disabled={saving}>
          {saving ? "Saving…" : "Save changes"}
        </button>
        <button type="button" onClick={onCancel} disabled={saving}>Cancel</button>
      </div>
    </form>
  );
}
