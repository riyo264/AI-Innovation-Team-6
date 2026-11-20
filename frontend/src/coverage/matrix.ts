import type { AcceptanceCriterion, ExecutionStatus, ExecutionView, Requirement, TestCase, TestType } from "../api/types";

/** Same threshold the delegator uses to flag a case for the manager. */
export const LOW_CONFIDENCE = 0.5;

export const TEST_TYPES: TestType[] = ["positive", "negative", "boundary", "security"];

const EXPECTED_BY_TAG: { tag: string; type: TestType }[] = [
  { tag: "ui", type: "positive" },
  { tag: "frontend", type: "positive" },
  { tag: "accessibility", type: "positive" },
  { tag: "validation", type: "boundary" },
  { tag: "rate-limiting", type: "boundary" },
  { tag: "security", type: "security" },
];

export interface CriterionView {
  criterion: AcceptanceCriterion;
  /** Test case IDs that explicitly cover this criterion (via covers_criteria). */
  coveredBy: string[];
}

export interface Gap {
  id: string;
  requirementId: string;
  message: string;
}

export interface MatrixRow {
  requirement: Requirement;
  criteria: CriterionView[];
  byType: Record<TestType, TestCase[]>;
  expected: TestType[];
  gaps: Gap[];
}

export interface CoverageModel {
  rows: MatrixRow[];
  gaps: Gap[];
}

/** Types this requirement must exercise. Tags drive the rule; everything else still renders. */
export function expectedTypes(requirement: Requirement): TestType[] {
  const tags = new Set(requirement.tags.map((tag) => tag.toLowerCase()));
  const expected = new Set<TestType>();
  for (const rule of EXPECTED_BY_TAG) {
    if (tags.has(rule.tag)) expected.add(rule.type);
  }
  if (tags.has("auth") && !expected.has("security")) expected.add("negative");
  if (expected.size === 0) expected.add("positive");
  return TEST_TYPES.filter((type) => expected.has(type));
}

export function specLabel(testCase: TestCase): string {
  const spec = testCase.spec;
  if (spec.kind === "api") {
    const times = spec.repeat > 1 ? ` ×${spec.repeat}` : "";
    return `${spec.method} ${spec.path}${times} → ${spec.expected_status}`;
  }
  const page = spec.steps.find((step) => step.action === "goto")?.value ?? "page";
  return `UI ${page} · ${spec.steps.length} steps`;
}

export function executionStatus(
  testId: string,
  live: Record<string, ExecutionStatus>,
  executions: ExecutionView[],
): ExecutionStatus | null {
  return live[testId] ?? executions.find((item) => item.test_case_id === testId)?.status ?? null;
}

function emptyByType(): Record<TestType, TestCase[]> {
  return { positive: [], negative: [], boundary: [], security: [] };
}

export function buildCoverage(requirements: Requirement[], testCases: TestCase[]): CoverageModel {
  const testsFor = new Map<string, TestCase[]>();
  for (const testCase of testCases) {
    const list = testsFor.get(testCase.source_requirement_id) ?? [];
    list.push(testCase);
    testsFor.set(testCase.source_requirement_id, list);
  }

  const rows = [...requirements]
    .sort((a, b) => a.id.localeCompare(b.id))
    .map((requirement) => {
      // Guard: acceptance_criteria may be missing or malformed in old/mock runs
      const acceptance_criteria: AcceptanceCriterion[] = Array.isArray(requirement.acceptance_criteria)
        ? requirement.acceptance_criteria.filter(
            (c): c is AcceptanceCriterion =>
              c != null && typeof c === "object" && typeof c.id === "string" && typeof c.text === "string",
          )
        : [];

      const tests = testsFor.get(requirement.id) ?? [];
      const byType = emptyByType();
      for (const testCase of tests) byType[testCase.test_type].push(testCase);

      // Build criteria views using explicit covers_criteria linkage (no heuristics)
      const criteria: CriterionView[] = acceptance_criteria.map((criterion) => {
        const coveredBy = tests
          .filter((tc) => tc.covers_criteria?.includes(criterion.id))
          .map((tc) => tc.id);
        return { criterion, coveredBy };
      });

      const gaps: Gap[] = [];
      const push = (suffix: string, message: string) =>
        gaps.push({ id: `${requirement.id}:${suffix}`, requirementId: requirement.id, message });

      if (acceptance_criteria.length === 0) {
        push("criteria", `${requirement.id} has no acceptance criteria.`);
      }
      if (requirement.ambiguous) {
        push(
          "ambiguous",
          `${requirement.id} is ambiguous. ${requirement.ambiguity_note ?? "No measurable threshold."}`,
        );
      }

      // Gap: a non-ambiguous criterion with no test covering it
      for (const { criterion, coveredBy } of criteria) {
        if (!criterion.ambiguous && coveredBy.length === 0) {
          push(
            criterion.id,
            `${criterion.id} has no test. "${criterion.text}"`,
          );
        }
        // Ambiguous criteria with no test: informational only (not a gap we can fix)
        if (criterion.ambiguous) {
          push(
            `${criterion.id}-ambiguous`,
            `${criterion.id} is ambiguous. ${criterion.ambiguity_note ?? "No measurable threshold."} No test can be written until the PRD is clarified.`,
          );
        }
      }

      const expected = expectedTypes(requirement);
      for (const type of expected) {
        if (byType[type].length === 0) {
          push(type, `${requirement.id} ${requirement.title} has no ${type} test.`);
        }
      }
      for (const testCase of tests) {
        if (testCase.confidence < LOW_CONFIDENCE) {
          push(
            testCase.id,
            `${testCase.id} on ${requirement.id} is ${Math.round(testCase.confidence * 100)}% confident. "${testCase.title}" does not assert a measurable threshold.`,
          );
        }
      }

      return { requirement: { ...requirement, acceptance_criteria }, criteria, byType, expected, gaps };
    });

  return { rows, gaps: rows.flatMap((row) => row.gaps) };
}
