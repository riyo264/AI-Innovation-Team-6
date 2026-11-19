const COLORS: Record<string, string> = {
  generating: "info",
  awaiting_approval: "warn",
  approved: "info",
  executing: "info",
  running: "info",
  queued: "muted",
  completed: "ok",
  passed: "ok",
  failed: "bad",
  error: "bad",
  todo: "muted",
  in_progress: "info",
};

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${COLORS[status] ?? "muted"}`}>{status.replace("_", " ")}</span>;
}
