"""Demo Target App: a deliberately flawed login + password-reset service.

Generated tests run against this. Known bugs are listed in ../FLAWS.md. Don't show that
file to the LLM, the point is that the harness finds them on its own.
"""

import secrets
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

app = FastAPI(title="Demo Target (intentionally flawed)")
PAGES = Path(__file__).parent / "pages"

TOKEN_TTL_SECONDS = 15 * 60
SEED_USERS = {"alice@example.com": "CorrectHorse1!", "bob@example.com": "Hunter2Hunter2"}

USERS: dict[str, str] = {}
TOKENS: dict[str, dict] = {}  # token -> {email, issued_at, used}
RESET_REQUESTS: dict[str, list[float]] = {}


def reset_state() -> None:
    USERS.clear()
    USERS.update(SEED_USERS)
    TOKENS.clear()
    RESET_REQUESTS.clear()


reset_state()


class LoginBody(BaseModel):
    email: str
    password: str


class ResetRequestBody(BaseModel):
    email: str


class ResetConfirmBody(BaseModel):
    token: str
    new_password: str


def issue_token(email: str, age_seconds: int = 0) -> str:
    token = secrets.token_urlsafe(16)
    TOKENS[token] = {"email": email, "issued_at": time.time() - age_seconds, "used": False}
    return token


# --- API ---------------------------------------------------------------------------


@app.post("/api/login")
def login(body: LoginBody):
    if USERS.get(body.email) == body.password:
        return {"token": secrets.token_hex(16), "email": body.email}
    return JSONResponse({"detail": "Invalid credentials"}, status_code=401)


@app.post("/api/password-reset/request")
def request_reset(body: ResetRequestBody):
    # FLAW 1: no rate limiting. Requests are recorded but never checked.
    RESET_REQUESTS.setdefault(body.email, []).append(time.time())

    # FLAW 2: user enumeration. Unknown emails get a distinct 404.
    if body.email not in USERS:
        return JSONResponse({"detail": "No account with that email"}, status_code=404)

    issue_token(body.email)
    return {"message": "If an account exists, a reset link has been sent"}


@app.post("/api/password-reset/confirm")
def confirm_reset(body: ResetConfirmBody):
    record = TOKENS.get(body.token)
    if record is None:
        return JSONResponse({"detail": "Invalid token"}, status_code=400)

    # FLAW 3: expiry is never checked (should reject after TOKEN_TTL_SECONDS).
    # FLAW 4: tokens are never marked used, so they can be replayed.

    # FLAW 5: off-by-two password policy (PRD says >= 8).
    if len(body.new_password) < 6:
        return JSONResponse({"detail": "Password too short"}, status_code=422)

    USERS[record["email"]] = body.new_password
    return {"message": "Password updated"}


# --- UI pages ----------------------------------------------------------------------


@app.get("/login")
def login_page():
    return FileResponse(PAGES / "login.html")


@app.get("/forgot-password")
def forgot_page():
    return FileResponse(PAGES / "forgot-password.html")


@app.get("/reset-password")
def reset_page():
    return FileResponse(PAGES / "reset-password.html")


# --- Test hooks (would not exist in a real app) -------------------------------------


@app.post("/__debug/reset")
def debug_reset():
    reset_state()
    return {"ok": True}


@app.post("/__debug/issue-token")
def debug_issue_token(body: ResetRequestBody):
    return {"token": issue_token(body.email)}


@app.post("/__debug/expired-token")
def debug_expired_token(body: ResetRequestBody):
    return {"token": issue_token(body.email, age_seconds=TOKEN_TTL_SECONDS + 60)}
