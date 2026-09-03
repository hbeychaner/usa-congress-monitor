#!/usr/bin/make -f
# Makefile for local development tasks (start OpenSearch, manage deps)

.PHONY: start services stop local local-stop local-down stack-up stack-down stack-logs contracts-sync deps uv-sync uv-test worker worker-index worker-monitor beat status health-check backend-api frontend-dev help

# Detect docker compose command at make-parse time (prefer `docker compose`)
DOCKER_COMPOSE_CMD_DETECTED := $(if $(shell docker compose version >/dev/null 2>&1 && echo ok),docker compose,$(if $(shell command -v docker-compose >/dev/null 2>&1 && echo ok),docker-compose,))

# Start the local OpenSearch stack (uses elastic-start-local/docker-compose.yml)
start: services

local:
	@echo "Starting local OpenSearch stack..."
	@$(MAKE) ensure-docker
	@cd elastic-start-local && . ../.make_docker_env && eval "$$DOCKER_COMPOSE_CMD up -d --remove-orphans"
	@echo "OpenSearch stack started."

services: local
	@echo "Starting Celery worker and 24-hour coverage scheduler..."
	@if [ "$$(uname)" = "Darwin" ] && command -v osascript >/dev/null 2>&1; then \
		osascript -e 'tell application "Terminal" to do script "cd \"$(CURDIR)\" && MONITOR=0 uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=ingest@%h --pool=prefork --concurrency=8 --max-tasks-per-child=50 --loglevel=INFO --queues=congress-ingest"'; \
		osascript -e 'tell application "Terminal" to do script "cd \"$(CURDIR)\" && uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=index@%h --pool=prefork --concurrency=4 --max-tasks-per-child=1 --loglevel=INFO --queues=congress-index"'; \
		osascript -e 'tell application "Terminal" to do script "cd \"$(CURDIR)\" && uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO"'; \
		echo "Worker and beat started in separate Terminal windows."; \
	else \
		mkdir -p logs; nohup uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=ingest@%h --pool=prefork --concurrency=8 --max-tasks-per-child=50 --loglevel=INFO --queues=congress-ingest > logs/worker-ingest.log 2>&1 & \
		nohup uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=index@%h --pool=prefork --concurrency=4 --max-tasks-per-child=1 --loglevel=INFO --queues=congress-index > logs/worker-index.log 2>&1 & \
		nohup uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO > logs/beat.log 2>&1 & \
		echo "Worker and beat started; logs are in logs/worker.log and logs/beat.log."; \
	fi

status:
	@uv run python scripts/job_status.py

health-check:
	@uv run python scripts/health_check.py

local-down:
	@echo "Stopping local OpenSearch stack..."
	@cd elastic-start-local && . ../.make_docker_env && eval "$$DOCKER_COMPOSE_CMD down --volumes --remove-orphans"
	@echo "OpenSearch stack stopped."

local-stop:
	@echo "Stopping local OpenSearch containers (volumes preserved)..."
	@cd elastic-start-local && . ../.make_docker_env && eval "$$DOCKER_COMPOSE_CMD stop"
	@echo "OpenSearch containers stopped; volumes preserved."

stop: local-stop

stack-up:
	@echo "Starting full container stack (infra + backend + worker + beat + frontend)..."
	@$(MAKE) ensure-docker
	@$(MAKE) local
	@. .make_docker_env && eval "$$DOCKER_COMPOSE_CMD -f docker-compose.fullstack.yml up -d --build --remove-orphans"
	@echo "Full stack started: frontend=http://localhost:5173 backend=http://localhost:8000"

stack-down:
	@echo "Stopping full container stack..."
	@$(MAKE) ensure-docker
	@. .make_docker_env && eval "$$DOCKER_COMPOSE_CMD -f docker-compose.fullstack.yml down --remove-orphans"
	@$(MAKE) local-stop
	@echo "Full stack stopped."

stack-logs:
	@$(MAKE) ensure-docker
	@. .make_docker_env && eval "$$DOCKER_COMPOSE_CMD -f docker-compose.fullstack.yml logs -f --tail=200"

contracts-sync:
	@$(MAKE) ensure-docker
	@. .make_docker_env && eval "$$DOCKER_COMPOSE_CMD -f docker-compose.fullstack.yml exec -T frontend sh -lc 'OPENAPI_URL=http://backend:8000/openapi.json npm run contracts:generate'"


.PHONY: ensure-docker
ensure-docker:
	# detect compose command at parse time and write to .make_docker_env
	@if [ -z "$(DOCKER_COMPOSE_CMD_DETECTED)" ]; then \
		echo "No docker compose command detected; please install Docker or docker-compose."; rm -f .make_docker_env; exit 1; \
	fi; \
	# Quick check if Docker daemon is responsive; try to start Docker on macOS
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
	fi; \
	echo "Using compose command: $(DOCKER_COMPOSE_CMD_DETECTED)"
	echo "DOCKER_COMPOSE_CMD='$(DOCKER_COMPOSE_CMD_DETECTED)'" > .make_docker_env


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
	uv run celery -A cdm.workers.celery_app:celery_app worker --hostname=index@%h --pool=prefork --concurrency=4 --max-tasks-per-child=1 --loglevel=INFO --queues=congress-index

worker-monitor:
	uv run python scripts/monitor_ingest_progress.py

beat:
	uv run celery -A cdm.workers.celery_app:celery_app beat --loglevel=INFO

backend-api:
	uv run uvicorn cdm.backend.app:app --host 0.0.0.0 --port 8000 --reload

frontend-dev:
	cd frontend/app && npm install && npm run dev

help:
	@printf "Available targets:\n"
	@printf "  start       - Start the local OpenSearch stack\n"
	@printf "  stop        - Stop local containers and preserve Docker volumes\n"
	@printf "  local       - Start local OpenSearch stack via docker-compose\n"
	@printf "  local-stop  - Stop containers while preserving Docker volumes\n"
	@printf "  local-down  - Stop containers and remove Docker volumes\n"
	@printf "  deps        - Install dependencies via pip (legacy)\n"
	@printf "  uv-sync     - Install deps via uv into .venv (reads pyproject.toml)\n"
	@printf "  uv-test     - Run pytest via uv run\n"
	@printf "  worker      - Start Celery worker and auto-open aggregate ingest monitor (MONITOR=0 disables)\n"
	@printf "  worker-monitor - Run aggregate ingest progress monitor\n"
	@printf "  beat        - Start the daily Celery scheduler\n"
	@printf "  services    - Start OpenSearch, Redis, RabbitMQ, worker, and beat\n"
	@printf "  status      - Show durable job states and ingest coverage\n"
	@printf "  health-check- Check SQLite, Celery, Redis, OpenSearch, backlog, and failures\n"
	@printf "  backend-api - Start FastAPI backend (reload)\n"
	@printf "  frontend-dev- Install frontend deps and run Vite dev server\n"
	@printf "  stack-up    - Start full containerized stack (infra, api, worker, beat, frontend)\n"
	@printf "  stack-down  - Stop full containerized stack\n"
	@printf "  stack-logs  - Tail logs for full containerized stack\n"
	@printf "  contracts-sync - Regenerate frontend API types from backend OpenAPI\n"
