"""Pytest plumbing for the generated suite.

Each result is printed as a machine-readable line:
    @@RESULT {"test_case_id": "TC-001", "status": "passed", ...}
The ExecutionService parses those lines; every other line is streamed to the UI as log.
"""

import json
import os
import sys

import httpx
import pytest

CASES_FILE = os.environ.get("HARNESS_CASES_FILE", "")
TARGET_API_URL = os.environ.get("TARGET_API_URL", "http://localhost:9000")
TARGET_UI_URL = os.environ.get("TARGET_UI_URL", "http://localhost:9000")


def load_cases() -> list[dict]:
    if not CASES_FILE:
        return []
    with open(CASES_FILE) as f:
        return json.load(f)


@pytest.fixture(autouse=True)
def reset_target():
    """Every test starts from the demo target's seed state (users, rate limits, tokens)."""
    httpx.post(f"{TARGET_API_URL}/__debug/reset", timeout=5)
    yield


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()


def pytest_runtest_logreport(report):
    failed_setup = report.when == "setup" and report.failed
    if report.when != "call" and not failed_setup:
        return
    case_id = report.nodeid.split("[")[-1].rstrip("]")
    if report.passed:
        status, message = "passed", None
    else:
        status = "failed" if report.when == "call" else "error"
        message = str(report.longrepr.reprcrash.message) if hasattr(report.longrepr, "reprcrash") \
            else str(report.longrepr)[-500:]
    line = json.dumps({
        "test_case_id": case_id,
        "status": status,
        "duration_ms": int(report.duration * 1000),
        "message": message,
    })
    sys.__stdout__.write(f"\n@@RESULT {line}\n")
    sys.__stdout__.flush()
