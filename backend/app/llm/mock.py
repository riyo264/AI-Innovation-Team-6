"""Deterministic stand-in for the LLM, tuned to samples/prd_password_reset.md.

Use it for unit tests, offline development and the fallback demo. The first generator
call returns two deliberately broken items (one schema error, one traceability error)
so the Validator's retry loop is exercised every run.
"""

import asyncio
import json
import random

from app.llm.base import LLMResult

REQUIREMENTS = [
    {
        "id": "REQ-001",
        "title": "Login with email and password",
        "description": "Correct credentials return 200 and a token; wrong ones return 401 "
        "'Invalid credentials' without revealing whether the email exists.",
        "tags": ["api", "auth"],
        "acceptance_criteria": ["200 + token on success", "401 'Invalid credentials' on failure"],
    },
    {
        "id": "REQ-002",
        "title": "Reset request does not enumerate users",
        "description": "Reset request always returns 200 with a generic message, registered "
        "or not.",
        "tags": ["api", "security"],
        "acceptance_criteria": ["200 + 'If an account exists' for any email"],
    },
    {
        "id": "REQ-003",
        "title": "Rate limit reset requests",
        "description": "At most 5 reset requests per email per hour; the 6th returns 429.",
        "tags": ["rate-limiting", "security"],
        "acceptance_criteria": ["5th request 200", "6th request 429"],
    },
    {
        "id": "REQ-004",
        "title": "Reset tokens expire after 15 minutes",
        "description": "Confirming with an expired token returns 400 'Token expired'.",
        "tags": ["auth", "security"],
        "acceptance_criteria": ["expired token -> 400 'Token expired'"],
    },
    {
        "id": "REQ-005",
        "title": "Reset tokens are single use",
        "description": "A reset token can be used once; reuse returns 400.",
        "tags": ["auth", "security"],
        "acceptance_criteria": ["second use -> 400"],
    },
    {
        "id": "REQ-006",
        "title": "Minimum password length",
        "description": "New passwords must be at least 8 characters; shorter returns 422.",
        "tags": ["api", "validation"],
        "acceptance_criteria": ["7 chars -> 422", "8 chars -> 200"],
    },
    {
        "id": "REQ-007",
        "title": "Forgot-password UI confirmation",
        "description": "The forgot-password page shows a confirmation after submit. Reset "
        "emails should be sent promptly.",
        "tags": ["email", "ui"],
        "acceptance_criteria": ["confirmation message visible after submit"],
        "ambiguous": True,
        "ambiguity_note": "'Promptly' has no measurable threshold (seconds? minutes?).",
    },
]

ALICE = {"email": "alice@example.com", "password": "CorrectHorse1!"}


def _api(method, path, body, status, contains=(), repeat=1):
    return {
        "kind": "api",
        "method": method,
        "path": path,
        "json_body": body,
        "repeat": repeat,
        "expected_status": status,
        "expected_body_contains": list(contains),
    }


def _tc(title, req, ttype, tags, steps, expected, conf, spec):
    return {
        "title": title,
        "source_requirement_id": req,
        "test_type": ttype,
        "tags": tags,
        "preconditions": ["Demo target reset to seed state", "alice@example.com is registered"],
        "steps_description": steps,
        "expected_result": expected,
        "confidence": conf,
        "spec": spec,
    }


_WEAK_PW = _tc(
    "Reject 7-character password on reset",
    "REQ-006", "boundary", ["api", "validation"],
    ["Issue a reset token", "Confirm with a 7-character password"],
    "HTTP 422", 0.9,
    _api("POST", "/api/password-reset/confirm",
         {"token": "{{RESET_TOKEN}}", "new_password": "Short7!"}, 422),
)

_UI_CONFIRM = _tc(
    "Forgot-password page shows confirmation",
    "REQ-007", "positive", ["ui"],
    ["Open /forgot-password", "Enter email", "Submit"],
    "Generic confirmation message is visible", 0.8,
    {"kind": "ui", "steps": [
        {"action": "goto", "value": "/forgot-password"},
        {"action": "fill", "selector": "#email", "value": ALICE["email"]},
        {"action": "click", "selector": "#submit"},
        {"action": "expect_text", "value": "If an account exists"},
    ]},
)

GOOD_CASES = [
    _tc("Valid login returns token", "REQ-001", "positive", ["api", "auth"],
        ["POST valid credentials"], "200 with token", 0.95,
        _api("POST", "/api/login", ALICE, 200, ["token"])),
    _tc("Wrong password returns 401", "REQ-001", "negative", ["api", "auth"],
        ["POST wrong password"], "401 Invalid credentials", 0.95,
        _api("POST", "/api/login", {**ALICE, "password": "nope"}, 401, ["Invalid credentials"])),
    _tc("Login error does not reveal unknown email", "REQ-001", "security", ["auth", "security"],
        ["POST unknown email"], "Same 401 message as wrong password", 0.85,
        _api("POST", "/api/login", {"email": "ghost@example.com", "password": "x"}, 401,
             ["Invalid credentials"])),
    _tc("Login page signs user in", "REQ-001", "positive", ["ui"],
        ["Open /login", "Fill credentials", "Submit"], "Welcome message shown", 0.8,
        {"kind": "ui", "steps": [
            {"action": "goto", "value": "/login"},
            {"action": "fill", "selector": "#email", "value": ALICE["email"]},
            {"action": "fill", "selector": "#password", "value": ALICE["password"]},
            {"action": "click", "selector": "#submit"},
            {"action": "expect_text", "value": "Welcome"},
        ]}),
    _tc("Reset request for registered email", "REQ-002", "positive", ["api"],
        ["POST registered email"], "200 generic message", 0.95,
        _api("POST", "/api/password-reset/request", {"email": ALICE["email"]}, 200,
             ["If an account exists"])),
    _tc("Reset request for unknown email is indistinguishable", "REQ-002", "security",
        ["security", "api"], ["POST unknown email"], "200 generic message", 0.9,
        _api("POST", "/api/password-reset/request", {"email": "ghost@example.com"}, 200,
             ["If an account exists"])),
    _tc("6th reset request in an hour is rate limited", "REQ-003", "security",
        ["rate-limiting", "security"], ["POST reset request 6 times"], "Last response 429", 0.9,
        _api("POST", "/api/password-reset/request", {"email": ALICE["email"]}, 429, repeat=6)),
    _tc("5 reset requests are allowed", "REQ-003", "boundary", ["rate-limiting", "api"],
        ["POST reset request 5 times"], "Last response 200", 0.85,
        _api("POST", "/api/password-reset/request", {"email": ALICE["email"]}, 200, repeat=5)),
    _tc("Expired token is rejected", "REQ-004", "security", ["auth", "security"],
        ["Obtain a token issued 16 minutes ago", "Confirm with it"], "400 Token expired", 0.9,
        _api("POST", "/api/password-reset/confirm",
             {"token": "{{EXPIRED_RESET_TOKEN}}", "new_password": "NewPassword9!"}, 400,
             ["Token expired"])),
    _tc("Reset token cannot be reused", "REQ-005", "security", ["auth", "security"],
        ["Issue token", "Confirm twice with same token"], "Second attempt 400", 0.9,
        _api("POST", "/api/password-reset/confirm",
             {"token": "{{RESET_TOKEN}}", "new_password": "NewPassword9!"}, 400, repeat=2)),
    _tc("Accept 8-character password", "REQ-006", "boundary", ["api", "validation"],
        ["Issue token", "Confirm with 8-char password"], "HTTP 200, password updated", 0.9,
        _api("POST", "/api/password-reset/confirm",
             {"token": "{{RESET_TOKEN}}", "new_password": "Exactly8"}, 200)),
    _tc("Reset email is delivered promptly", "REQ-007", "positive", ["email", "notifications"],
        ["Request reset", "Check outbound mail queue"], "Email queued within threshold", 0.4,
        _api("POST", "/api/password-reset/request", {"email": ALICE["email"]}, 200)),
]

# First attempt: two broken items appended.
_broken_schema = {k: v for k, v in _WEAK_PW.items() if k != "source_requirement_id"}
_broken_trace = {**_UI_CONFIRM, "source_requirement_id": "REQ-099"}
FIRST_ATTEMPT = {"test_cases": GOOD_CASES + [_broken_schema, _broken_trace]}
RETRY_ATTEMPT = {"test_cases": [_WEAK_PW, _UI_CONFIRM]}


class MockLLM:
    model = "mock-llm"

    async def complete(self, *, node: str, system: str, user: str) -> LLMResult:
        await asyncio.sleep(0.05)
        if node == "extractor":
            payload = {"requirements": REQUIREMENTS}
        elif node == "generator":
            payload = RETRY_ATTEMPT if "VALIDATION ERRORS" in user else FIRST_ATTEMPT
        else:
            raise ValueError(f"MockLLM has no canned response for node '{node}'")
        text = json.dumps(payload)
        return LLMResult(
            text=text,
            model=self.model,
            latency_ms=random.randint(300, 900),
            prompt_tokens=len(system + user) // 4,
            completion_tokens=len(text) // 4,
        )
