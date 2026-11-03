#!/usr/bin/make -f
# Makefile for local development tasks (start OpenSearch, manage deps)

.PHONY: up down restart stack-status env-init es-api-key start services stop local local-stop local-down stack-up stack-down stack-logs contracts-sync deps uv-sync uv-test worker worker-index worker-maintenance worker-monitor beat ingest-service-install ingest-service-uninstall ingest-service-status status health-check backend-api frontend-dev help

COMPOSE := docker compose
STACK_PROFILES ?= operations
export COMPOSE_PROFILES = $(STACK_PROFILES)

# Compose owns all managed application processes.
up start services: stack-up

down stop: stack-down

restart:
	@$(MAKE) stack-down
	@$(MAKE) stack-up

stack-status: require-docker
	@cd elastic-start-local && $(COMPOSE) ps
	@$(COMPOSE) -f docker-compose.fullstack.yml ps

env-init:
	@uv run python scripts/bootstrap_env.py init

# Run once after OpenSearch is up on a fresh checkout.
es-api-key:
	@uv run python scripts/bootstrap_env.py api-key

local: env-init
	@echo "Starting local OpenSearch stack..."
	@$(MAKE) ensure-docker
	@cd elastic-start-local && $(COMPOSE) up -d --wait --wait-timeout 180 --remove-orphans
	@echo "OpenSearch stack started."

status:
	@uv run python scripts/job_status.py

health-check:
	@uv run python scripts/health_check.py

local-down: require-docker
	@echo "Stopping local OpenSearch stack..."
	@cd elastic-start-local && $(COMPOSE) down --volumes --remove-orphans
	@echo "OpenSearch stack stopped."

local-stop: require-docker
	@echo "Stopping local OpenSearch containers (volumes preserved)..."
	@cd elastic-start-local && $(COMPOSE) stop
	@echo "OpenSearch containers stopped; volumes preserved."

stack-up:
	@sh scripts/stack.sh check
	@echo "Starting Compose stack with profiles: $(STACK_PROFILES)"
	@$(MAKE) local
	@$(COMPOSE) -f docker-compose.fullstack.yml up -d --build --wait --wait-timeout 180 --renew-anon-volumes --remove-orphans
	@echo "Full stack started: frontend=http://localhost:5173 backend=http://localhost:8000"

stack-down: require-docker
	@echo "Stopping full container stack..."
	@$(COMPOSE) -f docker-compose.fullstack.yml down --remove-orphans
	@$(MAKE) local-stop
	@echo "Full stack stopped."

stack-logs: require-docker
	@$(COMPOSE) -f docker-compose.fullstack.yml logs -f --tail=200

contracts-sync:
	npm --prefix frontend/app run contracts:generate


.PHONY: ensure-docker check-compose require-docker
check-compose:
	@docker compose version >/dev/null 2>&1 || (echo "Docker Compose v2 is required."; exit 1)

require-docker: check-compose
	@docker info >/dev/null 2>&1 || (echo "Docker is not running."; exit 1)

ensure-docker: check-compose
	@if ! docker info >/dev/null 2>&1; then \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "Docker daemon not running. Attempting to start Docker Desktop..."; \
			open -a Docker || true; \
			SECS=0; until docker info >/dev/null 2>&1 || [ $$SECS -ge 120 ]; do sleep 2; SECS=$$((SECS+2)); echo "waiting for docker... ($$SECS)s"; done; \
			if ! docker info >/dev/null 2>&1; then \
				echo "Timed out waiting for Docker daemon; please start Docker Desktop manually."; exit 1; \
			fi; \
		else \
			echo "Docker daemon not running; please start Docker."; exit 1; \
		fi; \
	fi


# Install dependencies via pip as a fallback
deps:
	@echo "Installing Python deps from requirements.txt (pip)..."
	@python -m pip install -r requirements.txt

# Install dependencies using uv (reads pyproject.toml, creates .venv + uv.lock)
uv-sync:
	@command -v uv >/dev/null 2>&1 || (echo "uv not found; install with: brew install uv"; exit 1)
	@echo "Running uv sync..."
	uv sync --all-extras
	@echo "Done. Activate with: source .venv/bin/activate"

# Run tests via uv (no need to activate .venv manually)
uv-test:
	uv run pytest -q

worker:
	@if [ "$${MONITOR:-1}" = "1" ]; then \
		if [ "$$(uname)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then \
			osascript -e 'tell application "Terminal" to do script "cd \"$(CURDIR)\" && uv run python scripts/monitor_ingest_progress.py"'; \
			echo "Opened progress monitor in a new Terminal window (set MONITOR=0 to disable)."; \
		else \
			echo "Run this in a second terminal for aggregate progress:"; \
			echo "  uv run python scripts/monitor_ingest_progress.py"; \
		fi; \
	fi
	uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=ingest@%h --pool=prefork --concurrency=8 --max-tasks-per-child=50 --loglevel=INFO --queues=congress-ingest

worker-index:
	uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=index@%h --pool=prefork --concurrency=4 --max-tasks-per-child=200 --loglevel=INFO --queues=congress-index

worker-maintenance:
	uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=maintenance@%h --pool=prefork --concurrency=1 --max-tasks-per-child=50 --loglevel=INFO --queues=congress-maintenance

worker-monitor:
	uv run python scripts/monitor_ingest_progress.py

beat:
	uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO

ingest-service-install ingest-service-uninstall ingest-service-status:
	@printf 'Native agents are retired. See documentation/OPERATIONS_RUNBOOK.md for migration; use make up and make stack-status afterward.\n' >&2
	@exit 1

backend-api:
	uv run uvicorn cdm.backend.app:app --host 0.0.0.0 --port 8000 --reload

frontend-dev:
	cd frontend/app && npm install && npm run dev

help:
	@printf "Available targets:\n"
	@printf "  up/start/services - Start the controlled Compose stack (STACK_PROFILES=operations)\n"
	@printf "  down/stop   - Stop the Compose stack and preserve Docker volumes\n"
	@printf "  local       - Start local infrastructure via Docker Compose v2\n"
	@printf "  local-stop  - Stop containers while preserving Docker volumes\n"
	@printf "  local-down  - Stop containers and remove Docker volumes\n"
	@printf "  deps        - Install dependencies via pip (legacy)\n"
	@printf "  uv-sync     - Install deps via uv into .venv (reads pyproject.toml)\n"
	@printf "  uv-test     - Run pytest via uv run\n"
	@printf "  worker      - Start Celery worker and auto-open aggregate ingest monitor (MONITOR=0 disables)\n"
	@printf "  worker-monitor - Run aggregate ingest progress monitor\n"
	@printf "  beat        - Start the daily Celery scheduler\n"
	@printf "  status      - Show durable job states and ingest coverage\n"
	@printf "  health-check- Check SQLite, Celery, Redis, OpenSearch, backlog, and failures\n"
	@printf "  backend-api - Start FastAPI backend (reload)\n"
	@printf "  frontend-dev- Install frontend deps and run Vite dev server\n"
	@printf "  stack-up    - Start full containerized stack (infra, api, worker, beat, frontend)\n"
	@printf "  stack-down  - Stop full containerized stack\n"
	@printf "  stack-logs  - Tail logs for full containerized stack\n"
	@printf "  contracts-sync - Regenerate frontend API types from backend OpenAPI\n"
