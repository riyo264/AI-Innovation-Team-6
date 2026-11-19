.PHONY: up down logs reset test-backend test-target fmt

up:            ## Build and start everything
	cp -n .env.example .env || true
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f backend

reset:         ## Wipe the database volume
	docker compose down -v

test-backend:  ## Unit + graph tests (mock LLM, SQLite, in-memory checkpointer)
	cd backend && python -m pytest tests -q

demo-run:      ## Kick off a pipeline run with the sample PRD + team
	curl -s -X POST http://localhost:8000/api/runs \
	  -F prd_file=@samples/prd_password_reset.md \
	  -F team_file=@samples/team.json | python -m json.tool
