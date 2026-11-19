"""Interprets a UiSpec with Playwright (sync API, Chromium headless)."""

from app.schemas.test_case import UiSpec

TIMEOUT_MS = 5000


def run_ui_spec(spec: dict, base_url: str, page) -> str:
    from playwright.sync_api import expect

    s = UiSpec.model_validate(spec)
    trail = []
    for step in s.steps:
        trail.append(f"{step.action}({step.selector or ''}{', ' if step.selector and step.value else ''}{step.value or ''})")
        match step.action:
            case "goto":
                page.goto(base_url.rstrip("/") + step.value, timeout=TIMEOUT_MS)
            case "fill":
                page.fill(step.selector, step.value, timeout=TIMEOUT_MS)
            case "click":
                page.click(step.selector, timeout=TIMEOUT_MS)
            case "expect_text":
                target = page.locator(step.selector) if step.selector else page.locator("body")
                expect(target).to_contain_text(step.value, timeout=TIMEOUT_MS)
            case "expect_url":
                expect(page).to_have_url(f"{base_url.rstrip('/')}{step.value}", timeout=TIMEOUT_MS)
    return " -> ".join(trail)
