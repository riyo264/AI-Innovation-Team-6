# AI Test Harness (Team 6)

A Manager uploads a PRD and a team structure. A LangGraph pipeline extracts requirements,
generates test cases, **validates them against strict Pydantic schemas with bounded retries**,
and delegates each one to a developer with written reasoning. The graph then **pauses for the
manager**, who drags cards to reassign and clicks *Approve & Distribute*. The approved suite runs
against a deliberately buggy demo app with pytest + Playwright, and results stream live over SSE.

## Quick start

```bash
cp .env.example .env          # LLM_PROVIDER=mock works offline; set groq + GROQ_API_KEY for the real model
docker compose up --build
```

| Service      | URL                        |
|--------------|----------------------------|
| Frontend     | http://localhost:5173      |
| Backend docs | http://localhost:8000/docs |
| Demo target  | http://localhost:9000/login |
| Postgres     | localhost:5432 (harness / harness) |

Demo flow: **1 · Ingest** → upload `samples/prd_password_reset.md` (team JSON is prefilled) →
**2 · Review & approve** → drag the Unassigned card to someone → *Approve & Distribute* → watch
the console → **3 · Pitch dashboard**. Switch *Viewing as* to a developer to see their Kanban.

With the mock LLM the sample run gives: 7 requirements (1 flagged ambiguous), 2 schema errors
self-corrected in 1 retry loop, 14 test cases, 1 Unassigned, and **5 failing tests that match the
5 planted bugs** in `demo-target/FLAWS.md`.

Backend tests (no Docker needed: SQLite + in-memory checkpointer + mock LLM):

```bash
cd backend && pip install -r requirements.txt && python -m pytest
```

## Architecture

```
React (Vite/TS) ──HTTP/SSE──► FastAPI ──► LangGraph thread (thread_id = run_id)
                                 │          extractor → generator ⇄ validator → delegator ║ distributor
                                 │                         (≤3 retries)        interrupt_after ║ resume
                                 │          checkpoints ──► PostgreSQL (AsyncPostgresSaver)
                                 ├──► PostgreSQL tables (runs, requirements, test_cases, team_members,
                                 │     task_assignments, executions, audit_logs, llm_calls, validation_failures)
                                 └──► pytest subprocess ──httpx / Playwright──► demo-target (FastAPI)
                                        └─ @@RESULT lines parsed → DB + SSE
```

Design choices that matter for the pitch:

- **The LLM never writes code.** It emits a declarative `ApiSpec` / `UiSpec`; the executor
  interprets it. No `exec`, nothing to sandbox, and every run is reproducible.
- **The harness owns IDs.** The Validator assigns `TC-###`, so the model can't produce
  duplicate or colliding IDs. Valid items are kept; only the failures (with the exact Pydantic
  error and the offending JSON) go back to the Generator.
- **Delegation is deterministic.** Skill/tag overlap + load balancing, no LLM. Same input →
  same plan, and every assignment has a `reasoning` string. Low confidence, ambiguous
  requirements or no skill match → `needs_manager_review` / Unassigned bucket.
- **Override rate is computed in the graph** (distributor node) by diffing the AI plan against
  the manager's approved plan, and stored for the dashboard.

## File map (and which stream owns it)

```
docker-compose.yml, Makefile, .env.example          QA & Infra
samples/                                            All (demo PRD + team JSON/CSV)

backend/                                            Backend & AI
  app/main.py                 app factory, lifespan (DB, checkpointer, graph, services)
  app/config.py               env settings
  app/schemas/                Pydantic contracts: Requirement, TestCase(Draft), Api/UiSpec,
                              Employee/TeamStructure, TaskAssignment/DelegationPlan,
                              ManagerApproval, ValidationFailure, API views
  app/graph/state.py          PipelineState (plain JSON for the checkpointer)
  app/graph/prompts.py        system/user prompts (JSON Schema embedded from Pydantic)
  app/graph/nodes/            extractor, generator, validator (+ bounded router), delegator, distributor
  app/graph/builder.py        StateGraph wiring, interrupt_after=["delegator"]
  app/graph/checkpointer.py   AsyncPostgresSaver (InMemorySaver for SQLite tests)
  app/llm/                    Groq client (JSON mode, token + latency capture), MockLLM, JSON utils
  app/services/pipeline.py    start run → pause → persist; approve → update_state → resume → execute
  app/services/event_bus.py   in-process pub/sub with replay for SSE
  app/services/queries.py     read models for the API
  app/services/telemetry.py   pitch-dashboard aggregates
  app/services/parsing.py     PRD (.md/.txt/.pdf) and team (JSON/CSV) parsing
  app/api/                    runs (ingest, detail, approve, re-run), developers (tasks, kanban move),
                              events (SSE), telemetry
  app/db/                     SQLAlchemy models + session                      QA & Infra
  app/execution/              runner (pytest subprocess + streaming),          QA & Infra
                              api_executor (httpx), ui_executor (Playwright),
                              harness/ (conftest with @@RESULT reporter, parametrised test)
  tests/                      schemas, validator, delegator, graph (pause/resume/retry cap), API flow

demo-target/                                        QA & Infra
  app/main.py                 login + password reset with 5 planted bugs, /__debug hooks for tests
  app/pages/                  /login, /forgot-password, /reset-password
  FLAWS.md                    answer key (keep it out of the LLM's context)

frontend/                                           Frontend
  src/auth/MockAuth.tsx       Manager / Developer dropdown (no real auth), selected run
  src/api/                    typed client + types mirroring backend schemas
  src/hooks/                  useRun (fetch), useRunEvents (SSE)
  src/views/IngestionView     upload PRD + paste team, live pipeline progress
  src/views/ManagerDashboard  columns per developer + Unassigned, native drag-and-drop, Approve
  src/views/DeveloperView     personal Kanban (todo / in progress / passed / failed) + live output
  src/views/PitchDashboard    telemetry tiles + harness log
  src/components/             Header, TestCaseCard, LiveConsole, PipelineProgress, StatusBadge
```

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/runs` | multipart: `prd_file` or `prd_text`, plus `team_file` or `team_json` → `{run_id}` |
| GET | `/api/runs`, `/api/runs/{id}` | list / full detail (requirements, cases, assignments, failures, executions) |
| POST | `/api/runs/{id}/approve` | `{approved_by, assignments:[{test_case_id, assignee_id}]}` resumes the graph |
| POST | `/api/runs/{id}/execute` | re-run the approved suite |
| GET | `/api/runs/{id}/developers/{member}/tasks` | developer view |
| PATCH | `/api/runs/{id}/tasks/{case}` | `{status}`: Kanban move |
| GET | `/api/runs/{id}/events` | SSE: `node`, `status`, `log`, `result`, `task` |
| GET | `/api/telemetry?run_id=` | dashboard numbers |

## Next steps, by plan phase

- **Hours 8–20:** switch to `LLM_PROVIDER=groq` and tune `graph/prompts.py` on the sample PRD.
  Check `GROQ_MODEL` against Groq's current model list. Watch the validator log to see which
  schema errors the real model makes.
- **Hours 20–32:** extend `SKILL_ALIASES` in `delegator.py` for your real team JSON; add UI specs
  for `/reset-password`.
- **Hours 32–44:** SSE, confidence scores, ambiguity flags and the Unassigned bucket already
  work. Remaining polish: an LLM tie-breaker in the delegator (keep the reasoning field), and
  a per-node latency chart on the pitch dashboard.
- **Before freeze:** move `create_all` to Alembic if the schema changed; record the fallback
  video using `LLM_PROVIDER=mock` (fully offline and deterministic).

Known limits: the event bus is in-process (one backend replica); `/api/runs` has no auth by design.
