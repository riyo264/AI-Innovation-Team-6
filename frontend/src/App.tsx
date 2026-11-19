import { useEffect, useState } from "react";
import { useSession } from "./auth/MockAuth";
import { Header } from "./components/Header";
import { useRun } from "./hooks/useRun";
import { useRunEvents } from "./hooks/useRunEvents";
import { DeveloperView } from "./views/DeveloperView";
import { IngestionView } from "./views/IngestionView";
import { ManagerDashboard } from "./views/ManagerDashboard";
import { PitchDashboard } from "./views/PitchDashboard";

type Tab = "ingest" | "review" | "pitch";

export default function App() {
  const { viewer, runId } = useSession();
  const { run, error, refresh } = useRun(runId);
  const [tab, setTab] = useState<Tab>("ingest");
  const [refreshKey, setRefreshKey] = useState(0);

  const { logs, nodes, results } = useRunEvents(runId, (e) => {
    // Refetch persisted state when something meaningful changes.
    if (e.type === "status" || e.type === "task" || (e.type === "result" && e.status !== "running")) {
      void refresh();
      setRefreshKey((k) => k + 1);
    }
  });

  useEffect(() => {
    if (!runId) setTab("ingest");
  }, [runId]);

  const team = run?.team ?? [];
  const member = viewer.kind === "developer" ? team.find((m) => m.id === viewer.memberId) : undefined;

  return (
    <>
      <Header team={team} runStatus={run?.status} />
      <main>
        {error && <p className="bad-text">{error}</p>}

        {viewer.kind === "manager" && (
          <>
            <nav className="tabs">
              <button className={tab === "ingest" ? "active" : ""} onClick={() => setTab("ingest")}>
                1 · Ingest
              </button>
              <button className={tab === "review" ? "active" : ""} onClick={() => setTab("review")} disabled={!run}>
                2 · Review & approve
              </button>
              <button className={tab === "pitch" ? "active" : ""} onClick={() => setTab("pitch")}>
                3 · Pitch dashboard
              </button>
            </nav>
            {tab === "ingest" && <IngestionView run={run} nodes={nodes} onReview={() => setTab("review")} />}
            {tab === "review" && run && (
              <ManagerDashboard run={run} logs={logs} liveResults={results} onChanged={refresh} />
            )}
            {tab === "pitch" && <PitchDashboard run={run} refreshKey={refreshKey} />}
          </>
        )}

        {viewer.kind === "developer" &&
          (run && member ? (
            <DeveloperView runId={run.id} member={member} logs={logs} liveResults={results} refreshKey={refreshKey} />
          ) : (
            <p className="muted">Select a run to see your tasks.</p>
          ))}
      </main>
    </>
  );
}
