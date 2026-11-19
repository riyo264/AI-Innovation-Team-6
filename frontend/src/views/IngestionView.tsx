import { useState } from "react";
import { api } from "../api/client";
import type { RunDetail, RunEvent } from "../api/types";
import { useSession } from "../auth/MockAuth";
import { PipelineProgress } from "../components/PipelineProgress";
import { StatusBadge } from "../components/StatusBadge";

const SAMPLE_TEAM = JSON.stringify(
  {
    members: [
      { id: "alice", name: "Alice", role: "Security", skills: ["security", "auth", "rate-limiting"] },
      { id: "bob", name: "Bob", role: "API Integration", skills: ["api", "backend", "validation"] },
      { id: "carol", name: "Carol", role: "Frontend UI", skills: ["ui", "frontend", "accessibility"] },
    ],
  },
  null,
  2,
);

interface Props {
  run: RunDetail | null;
  nodes: Extract<RunEvent, { type: "node" }>[];
  onReview: () => void;
}

export function IngestionView({ run, nodes, onReview }: Props) {
  const { setRunId } = useSession();
  const [prdFile, setPrdFile] = useState<File | null>(null);
  const [prdText, setPrdText] = useState("");
  const [teamJson, setTeamJson] = useState(SAMPLE_TEAM);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const { run_id } = await api.createRun({ prdFile, prdText, teamJson });
      setRunId(run_id);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid-2">
      <form className="panel" onSubmit={submit}>
        <h2>1 · Ingest</h2>
        <label className="field">
          Product Requirement Document (.md, .txt, .pdf)
          <input type="file" accept=".md,.txt,.pdf" onChange={(e) => setPrdFile(e.target.files?.[0] ?? null)} />
        </label>
        <label className="field">
          …or paste PRD text
          <textarea rows={8} value={prdText} onChange={(e) => setPrdText(e.target.value)} disabled={!!prdFile} />
        </label>
        <label className="field">
          Team structure (JSON, or CSV: id,name,role,skills)
          <textarea rows={12} className="mono" value={teamJson} onChange={(e) => setTeamJson(e.target.value)} />
        </label>
        {error && <p className="bad-text">{error}</p>}
        <button className="primary" disabled={busy || (!prdFile && !prdText.trim())}>
          {busy ? "Uploading…" : "Generate test plan"}
        </button>
      </form>

      <div>
        {run ? (
          <>
            <section className="panel">
              <h3>
                Current run <StatusBadge status={run.status} />
              </h3>
              {run.error && <p className="bad-text">{run.error}</p>}
              {run.status === "awaiting_approval" && (
                <button className="primary" onClick={onReview}>
                  Review {run.test_cases.length} test cases →
                </button>
              )}
            </section>
            <PipelineProgress nodes={nodes} />
          </>
        ) : (
          <section className="panel muted">Upload a PRD and a team to start a run.</section>
        )}
      </div>
    </div>
  );
}
