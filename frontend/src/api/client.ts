import type { DeveloperTask, RunDetail, RunSummary, TaskStatus, Telemetry } from "./types";

const TOKEN_KEY = "harness.token";

/** Read the active token that Header saves whenever the role changes. */
function getToken(): string {
  try {
    return localStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

/** Save a token so all subsequent requests pick it up automatically. */
export function saveToken(token: string) {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable */
  }
}

/** Every request automatically carries the X-Token header. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { ...init?.headers, "X-Token": getToken() },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  createRun(input: { prdFile?: File | null; prdText?: string; teamJson: string }) {
    const form = new FormData();
    if (input.prdFile) form.append("prd_file", input.prdFile);
    else if (input.prdText) form.append("prd_text", input.prdText);
    form.append("team_json", input.teamJson);
    return request<{ run_id: string }>("/api/runs", { method: "POST", body: form });
  },
  listRuns: () => request<RunSummary[]>("/api/runs"),
  getRun: (id: string) => request<RunDetail>(`/api/runs/${id}`),
  approve: (id: string, assignments: { test_case_id: string; assignee_id: string }[]) =>
    request<{ overrides: unknown[] }>(
      `/api/runs/${id}/approve`,
      json({ approved_by: "manager", assignments }),
    ),
  rerun: (id: string) => request<{ status: string }>(`/api/runs/${id}/execute`, { method: "POST" }),
  developerTasks: (runId: string, memberId: string) =>
    request<DeveloperTask[]>(`/api/runs/${runId}/developers/${memberId}/tasks`),
  moveTask: (runId: string, caseId: string, status: TaskStatus) =>
    request<{ ok: boolean }>(`/api/runs/${runId}/tasks/${caseId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    }),
  telemetry: (runId?: string) =>
    request<Telemetry>(`/api/telemetry${runId ? `?run_id=${runId}` : ""}`),
  eventsUrl: (runId: string) => `/api/runs/${runId}/events`,
};
