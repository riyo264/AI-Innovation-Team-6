import { useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import type { ExecutionStatus, RunEvent } from "../api/types";

const EVENT_TYPES = ["node", "status", "log", "result", "task"] as const;
const MAX_LOG_LINES = 2000;

/**
 * Subscribes to the run's SSE stream.
 * `onChange` fires on events that change persisted state (status, task moves, results),
 * so views can refetch. Logs and per-test results are also kept locally for live display.
 */
export function useRunEvents(runId: string | null, onChange?: (e: RunEvent) => void) {
  const [logs, setLogs] = useState<string[]>([]);
  const [nodes, setNodes] = useState<Extract<RunEvent, { type: "node" }>[]>([]);
  const [results, setResults] = useState<Record<string, ExecutionStatus>>({});
  const [connected, setConnected] = useState(false);
  const onChangeRef = useRef(onChange);
  onChangeRef.current = onChange;

  useEffect(() => {
    setLogs([]);
    setNodes([]);
    setResults({});
    if (!runId) return;

    const source = new EventSource(api.eventsUrl(runId));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    const handle = (msg: MessageEvent) => {
      const event = JSON.parse(msg.data) as RunEvent;
      switch (event.type) {
        case "log":
          setLogs((l) => [...l.slice(-MAX_LOG_LINES), event.line]);
          break;
        case "node":
          setNodes((n) => [...n, event]);
          break;
        case "result":
          setResults((r) => ({ ...r, [event.test_case_id]: event.status }));
          break;
      }
      if (event.type !== "log") onChangeRef.current?.(event);
    };
    EVENT_TYPES.forEach((t) => source.addEventListener(t, handle));
    return () => source.close();
  }, [runId]);

  return { logs, nodes, results, connected };
}
