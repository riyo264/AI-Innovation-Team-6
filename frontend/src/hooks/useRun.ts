import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { RunDetail } from "../api/types";

export function useRun(runId: string | null) {
  const [run, setRun] = useState<RunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!runId) return;
    try {
      setRun(await api.getRun(runId));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [runId]);

  useEffect(() => {
    setRun(null);
    void refresh();
  }, [refresh]);

  return { run, error, refresh };
}
