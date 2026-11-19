// Hackathon rule: no real auth. A dropdown switches between Manager and a developer.
import { createContext, useContext, useState, type ReactNode } from "react";

export type Viewer = { kind: "manager" } | { kind: "developer"; memberId: string };

interface Session {
  viewer: Viewer;
  setViewer: (v: Viewer) => void;
  runId: string | null;
  setRunId: (id: string | null) => void;
}

const Ctx = createContext<Session | null>(null);
const RUN_KEY = "harness.runId";

function readStoredRun(): string | null {
  try {
    return localStorage.getItem(RUN_KEY);
  } catch {
    return null;
  }
}

export function MockAuthProvider({ children }: { children: ReactNode }) {
  const [viewer, setViewer] = useState<Viewer>({ kind: "manager" });
  const [runId, setRunIdState] = useState<string | null>(readStoredRun);

  const setRunId = (id: string | null) => {
    setRunIdState(id);
    try {
      if (id) localStorage.setItem(RUN_KEY, id);
      else localStorage.removeItem(RUN_KEY);
    } catch {
      /* storage unavailable */
    }
  };

  return <Ctx.Provider value={{ viewer, setViewer, runId, setRunId }}>{children}</Ctx.Provider>;
}

export function useSession(): Session {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSession must be used inside MockAuthProvider");
  return ctx;
}
