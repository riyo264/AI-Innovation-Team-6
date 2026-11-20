// Mirrors backend/app/schemas. Keep in sync (or generate from /openapi.json later).

export type RunStatus =
  | "generating"
  | "awaiting_approval"
  | "approved"
  | "executing"
  | "completed"
  | "failed";
export type TaskStatus = "todo" | "in_progress" | "passed" | "failed";
export type ExecutionStatus = "queued" | "running" | "passed" | "failed" | "error";
export type TestType = "positive" | "negative" | "boundary" | "security";

export const UNASSIGNED = "unassigned";

export interface AcceptanceCriterion {
  id: string;             // e.g. "AC-006.1"
  text: string;
  source_quote: string | null;
  ambiguous: boolean;
  ambiguity_note: string | null;
}

export interface Requirement {
  id: string;
  title: string;
  description: string;
  tags: string[];
  acceptance_criteria: AcceptanceCriterion[];
  ambiguous: boolean;
  ambiguity_note: string | null;
}

export interface ApiSpec {
  kind: "api";
  method: string;
  path: string;
  json_body: Record<string, unknown> | null;
  repeat: number;
  expected_status: number;
  expected_body_contains: string[];
}

export interface UiSpec {
  kind: "ui";
  steps: { action: string; selector: string | null; value: string | null }[];
}

export interface TestCase {
  id: string;
  title: string;
  source_requirement_id: string;
  test_type: TestType;
  tags: string[];
  preconditions: string[];
  steps_description: string[];
  expected_result: string;
  confidence: number;
  covers_criteria: string[];
  spec: ApiSpec | UiSpec;
}

export interface Member {
  id: string;
  name: string;
  role: string;
  skills: string[];
}

export interface Assignment {
  test_case_id: string;
  ai_assignee_id: string;
  final_assignee_id: string;
  reasoning: string;
  matched_skills: string[];
  confidence: number;
  needs_manager_review: boolean;
  overridden: boolean;
  task_status: TaskStatus;
}

export interface ExecutionView {
  test_case_id: string;
  status: ExecutionStatus;
  duration_ms: number | null;
  message: string | null;
}

export interface ValidationFailure {
  attempt: number;
  error_type: "json_decode" | "schema" | "traceability" | "coverage";
  message: string;
  item_index: number | null;
  requirement_id: string | null;
  raw_excerpt: string | null;
}

export interface RunSummary {
  id: string;
  status: RunStatus;
  prd_filename: string | null;
  created_at: string;
  error: string | null;
}

export interface RunDetail extends RunSummary {
  requirements: Requirement[];
  team: Member[];
  test_cases: TestCase[];
  assignments: Assignment[];
  validation_failures: ValidationFailure[];
  executions: ExecutionView[];
}

export interface DeveloperTask {
  test_case: TestCase;
  assignment: Assignment;
  execution: ExecutionView | null;
}

export interface Telemetry {
  runs: number;
  test_cases_total: number;
  requirements_total: number;
  ambiguous_requirements: number;
  developers_with_tasks: number;
  unassigned_total: number;
  validation_failures_total: number;
  self_corrected_runs: number;
  retry_loops_total: number;
  llm_calls: number;
  avg_llm_latency_ms: number;
  prompt_tokens: number;
  completion_tokens: number;
  overrides: number;
  override_rate: number;
  executions_passed: number;
  executions_failed: number;
}

// Server-Sent Events
export type RunEvent =
  | { type: "node"; ts: string; node: string; accepted?: number; failures?: string[]; retry_count?: number }
  | { type: "status"; ts: string; status: RunStatus; error: string | null }
  | { type: "log"; ts: string; line: string }
  | { type: "result"; ts: string; test_case_id: string; status: ExecutionStatus; duration_ms?: number; message?: string | null }
  | { type: "task"; ts: string; test_case_id: string; task_status: TaskStatus };
