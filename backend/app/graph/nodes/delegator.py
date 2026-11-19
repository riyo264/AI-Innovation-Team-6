"""Node 4: map validated test cases to developers.

Deliberately deterministic (no LLM): skill/tag overlap + load balancing. The same inputs
always give the same plan, and every assignment carries a human-readable `reasoning`.
Swap `score_member` for an LLM tie-breaker later if you want, but keep the reasoning field.
"""

from collections import Counter

from app.graph.state import PipelineState
from app.schemas.delegation import UNASSIGNED, DelegationPlan, TaskAssignment
from app.schemas.team import Employee
from app.schemas.test_case import TestCase

# Skill -> extra tags it should match. Extend as your Org JSON grows.
SKILL_ALIASES: dict[str, set[str]] = {
    "security": {"security", "auth", "rate-limiting", "injection", "xss"},
    "auth": {"auth", "login", "session"},
    "frontend": {"ui", "frontend", "accessibility"},
    "frontend ui": {"ui", "frontend"},
    "ui": {"ui", "frontend"},
    "backend": {"api", "backend", "validation"},
    "api": {"api"},
    "api integration": {"api", "integration"},
}

LOW_CONFIDENCE = 0.5


def expand_skills(member: Employee) -> set[str]:
    skills = set(member.skills) | {member.role.strip().lower()}
    expanded = set(skills)
    for s in skills:
        expanded |= SKILL_ALIASES.get(s, set())
    return expanded


def case_signals(tc: TestCase) -> set[str]:
    signals = set(tc.tags)
    if tc.test_type.value == "security":
        signals.add("security")
    return signals


def delegate(
    test_cases: list[TestCase], team: list[Employee], ambiguous_reqs: set[str]
) -> DelegationPlan:
    load: Counter[str] = Counter()
    member_skills = {m.id: expand_skills(m) for m in team}
    by_id = {m.id: m for m in team}
    assignments: list[TaskAssignment] = []

    for tc in test_cases:
        signals = case_signals(tc)
        candidates = []
        for m in team:
            matched = sorted(signals & member_skills[m.id])
            if matched and load[m.id] < m.max_load:
                score = len(matched)
                # A security-type test should go to a security specialist on ties.
                if tc.test_type.value == "security" and "security" in matched:
                    score += 1
                candidates.append((score, -load[m.id], m.id, matched))

        flags: list[str] = []
        if tc.source_requirement_id in ambiguous_reqs:
            flags.append(f"{tc.source_requirement_id} is flagged ambiguous")
        if tc.confidence < LOW_CONFIDENCE:
            flags.append(f"generator confidence is low ({tc.confidence:.2f})")

        if not candidates:
            assignments.append(
                TaskAssignment(
                    test_case_id=tc.id,
                    assignee_id=UNASSIGNED,
                    reasoning=(
                        f"No team member has a skill matching tags {sorted(signals)}. "
                        "Needs a manager decision."
                    ),
                    confidence=0.0,
                    needs_manager_review=True,
                )
            )
            continue

        candidates.sort(reverse=True)
        score, _, member_id, matched = candidates[0]
        load[member_id] += 1
        member = by_id[member_id]
        match_ratio = len(matched) / max(len(signals), 1)
        # Generator confidence, discounted (at most 40%) by how partial the skill match is.
        confidence = round(tc.confidence * (0.6 + 0.4 * min(1.0, match_ratio)), 2)

        reasoning = (
            f"Assigned to {member.name} ({member.role}) because their skills match "
            f"{', '.join(matched)} and this is a {tc.test_type.value} test for "
            f"{tc.source_requirement_id}."
        )
        if len(candidates) > 1 and candidates[1][0] == score:
            reasoning += f" Tie with {by_id[candidates[1][2]].name}; broken by lower workload."
        if flags:
            reasoning += " Review: " + "; ".join(flags) + "."

        assignments.append(
            TaskAssignment(
                test_case_id=tc.id,
                assignee_id=member_id,
                reasoning=reasoning,
                matched_skills=matched,
                confidence=confidence,
                needs_manager_review=bool(flags) or confidence < LOW_CONFIDENCE,
            )
        )

    return DelegationPlan(assignments=assignments)


async def delegator(state: PipelineState) -> dict:
    cases = [TestCase.model_validate(tc) for tc in state.get("valid_test_cases", [])]
    team = [Employee.model_validate(m) for m in state["team"]]
    ambiguous = {r["id"] for r in state["requirements"] if r.get("ambiguous")}
    plan = delegate(cases, team, ambiguous)
    return {"delegation_plan": plan.model_dump()}
