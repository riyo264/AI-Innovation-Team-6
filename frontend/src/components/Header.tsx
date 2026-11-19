import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { Member, RunSummary } from "../api/types";
import { useSession } from "../auth/MockAuth";

export function Header({ team, runStatus }: { team: Member[]; runStatus?: string }) {
  const { viewer, setViewer, runId, setRunId } = useSession();
  const [runs, setRuns] = useState<RunSummary[]>([]);

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
  }, [runId, runStatus]); // refresh labels when the current run changes status

  const value = viewer.kind === "manager" ? "manager" : viewer.memberId;

  return (
    <header className="topbar">
      <h1>AI Test Harness</h1>
      <label>
        Run{" "}
        <select value={runId ?? ""} onChange={(e) => setRunId(e.target.value || null)}>
          <option value="">— new run —</option>
          {runs.map((r) => (
            <option key={r.id} value={r.id}>
              {r.prd_filename ?? "pasted PRD"} · {r.status} · {new Date(r.created_at).toLocaleTimeString()}
            </option>
          ))}
        </select>
      </label>
      <label>
        Viewing as{" "}
        <select
          value={value}
          onChange={(e) =>
            setViewer(e.target.value === "manager" ? { kind: "manager" } : { kind: "developer", memberId: e.target.value })
          }
        >
          <option value="manager">Manager View</option>
          {team.map((m) => (
            <option key={m.id} value={m.id}>
              Developer: {m.name} ({m.role})
            </option>
          ))}
        </select>
      </label>
    </header>
  );
}
