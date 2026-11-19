import json

from app.schemas.requirement import RequirementSet
from app.schemas.test_case import TestCaseDraft


def _schema(model) -> str:
    return json.dumps(model.model_json_schema(), indent=None)


EXTRACTOR_SYSTEM = f"""You are a senior QA analyst. Extract every testable functional
constraint from the Product Requirement Document.

Rules:
- Return ONLY a JSON object matching this JSON Schema: {_schema(RequirementSet)}
- IDs are sequential: REQ-001, REQ-002, ...
- tags: short lowercase labels drawn from: security, auth, rate-limiting, api, validation,
  ui, frontend, accessibility, performance, email, notifications.
- If a requirement is vague or has no measurable threshold, set "ambiguous": true and explain
  why in "ambiguity_note". Do not invent thresholds.
"""

EXTRACTOR_USER = """PRD:
---
{prd}
---
Return the JSON object now."""


GENERATOR_SYSTEM = f"""You are a test designer. For each requirement write test cases that
cover positive, negative, boundary and security behaviour where relevant.

Each test case MUST match this JSON Schema: {_schema(TestCaseDraft)}

Rules:
- Return ONLY {{"test_cases": [ ... ]}}.
- source_requirement_id MUST be one of the requirement IDs given. Every requirement needs at
  least one test case.
- Do NOT include an "id" field; the harness assigns IDs.
- spec.kind="api" sends HTTP requests to the target. Use "repeat" for rate-limit tests
  (the assertion applies to the last response).
- spec.kind="ui" drives a browser. Pages: /login, /forgot-password, /reset-password.
  Inputs: #email, #password, #token, #new_password. Button: #submit. Result text: #message.
- Placeholders available in json_body: "{{{{RESET_TOKEN}}}}" (fresh valid token for
  alice@example.com) and "{{{{EXPIRED_RESET_TOKEN}}}}" (token issued 16 minutes ago).
- Seed user: alice@example.com / CorrectHorse1!
- confidence: your certainty (0-1) that the test faithfully encodes the requirement.
"""

GENERATOR_USER = """Requirements:
{requirements}

Return the JSON object now."""

GENERATOR_RETRY_USER = """Requirements:
{requirements}

Your previous output was rejected by the schema validator.
Test cases already accepted (do NOT repeat them): {accepted}

VALIDATION ERRORS (fix each one exactly):
{failures}

Return ONLY the corrected or missing test cases as {{"test_cases": [...]}}."""
