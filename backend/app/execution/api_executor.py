"""Interprets an ApiSpec against the demo target. Sync, because it runs inside pytest."""

import json

import httpx

from app.schemas.test_case import ApiSpec

DEFAULT_EMAIL = "alice@example.com"


def resolve_placeholders(body: dict | None, client: httpx.Client) -> dict | None:
    """Swap {{RESET_TOKEN}} / {{EXPIRED_RESET_TOKEN}} for real tokens from the target's
    debug endpoints. Resolved once per test, so `repeat` reuses the same token."""
    if body is None:
        return None
    raw = json.dumps(body)
    if "{{RESET_TOKEN}}" in raw:
        token = client.post("/__debug/issue-token", json={"email": DEFAULT_EMAIL}).json()["token"]
        raw = raw.replace("{{RESET_TOKEN}}", token)
    if "{{EXPIRED_RESET_TOKEN}}" in raw:
        token = client.post("/__debug/expired-token", json={"email": DEFAULT_EMAIL}).json()["token"]
        raw = raw.replace("{{EXPIRED_RESET_TOKEN}}", token)
    return json.loads(raw)


def run_api_spec(spec: dict, base_url: str) -> str:
    s = ApiSpec.model_validate(spec)
    with httpx.Client(base_url=base_url, timeout=10) as client:
        body = resolve_placeholders(s.json_body, client)
        resp = None
        for _ in range(s.repeat):
            resp = client.request(s.method, s.path, json=body, headers=s.headers)

    assert resp is not None
    detail = f"{s.method} {s.path} x{s.repeat} -> {resp.status_code} {resp.text[:200]}"
    assert resp.status_code == s.expected_status, (
        f"expected HTTP {s.expected_status}, got {resp.status_code}. {detail}"
    )
    for needle in s.expected_body_contains:
        assert needle in resp.text, f"response body missing '{needle}'. {detail}"
    return detail
