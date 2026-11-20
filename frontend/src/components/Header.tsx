import { useEffect, useState } from "react";
import { api, saveToken } from "../api/client";
import type { Member, RunSummary } from "../api/types";
import { useSession } from "../auth/MockAuth";

/**
 * Maps each viewer selection to the static backend token for that identity.
 * Managers get "manager-token"; each developer gets their own "<id>-token".
 * These must match the MOCK_TOKENS dict in backend/app/api/deps.py.
 */
function tokenFor(value: string): string {
  if (value === "manager") return "manager-token";
  return `${value}-token`;          // e.g. "alice" → "alice-token"
}

export function Header({ team, runStatus }: { team: Member[]; runStatus?: string }) {
  const { viewer, setViewer, runId, setRunId } = useSession();
  const [runs, setRuns] = useState<RunSummary[]>([]);

  useEffect(() => {
    api.listRuns().then(setRuns).catch(() => setRuns([]));
  }, [runId, runStatus]); // refresh labels when the current run changes status

  const value = viewer.kind === "manager" ? "manager" : viewer.memberId;

  function handleViewerChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const selected = e.target.value;
    // 1. Update the token so the very next API call uses the right identity.
    saveToken(tokenFor(selected));
    // 2. Update the UI so the correct view renders with changes.
    setViewer(selected === "manager"
      ? { kind: "manager" }
      : { kind: "developer", memberId: selected });
  }

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
        <select value={value} onChange={handleViewerChange}>
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
